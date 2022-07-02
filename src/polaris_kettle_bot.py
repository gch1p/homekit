#!/usr/bin/env python3
from __future__ import annotations

import logging
import locale
import queue
import time
import threading
import paho.mqtt.client as mqtt

from home.bot import Wrapper, Context, text_filter, handlermethod
from home.api.types import BotType
from home.mqtt import MQTTBase
from home.config import config
from home.util import chunks
from polaris import (
    Kettle,
    PowerType,
    DeviceListener,
    IncomingMessageListener,
    ConnectionStatusListener,
    ConnectionStatus
)
import polaris.protocol as kettle_proto
from typing import Optional, Tuple, List, Union
from collections import namedtuple
from functools import partial
from datetime import datetime
from abc import abstractmethod
from telegram.error import TelegramError
from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message
)
from telegram.ext import (
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler
)

logger = logging.getLogger(__name__)
kc: Optional[KettleController] = None
bot: Optional[Wrapper] = None
RenderedContent = Tuple[str, Optional[Union[InlineKeyboardMarkup, ReplyKeyboardMarkup]]]
tasks_lock = threading.Lock()


def run_tasks(tasks: queue.SimpleQueue, done: callable):
    def next_task(r: Optional[kettle_proto.MessageResponse]):
        if r is not None:
            try:
                assert r is not False, 'server error'
            except AssertionError as exc:
                logger.exception(exc)
                tasks_lock.release()
                return done(False)

        if not tasks.empty():
            task = tasks.get()
            args = task[1:]
            args.append(next_task)
            f = getattr(kc.kettle, task[0])
            f(*args)
        else:
            tasks_lock.release()
            return done(True)

    tasks_lock.acquire()
    next_task(None)


def temperature_emoji(temp: int) -> str:
    if temp > 90:
        return '🔥'
    elif temp >= 40:
        return '♨️'
    elif temp >= 35:
        return '🌡'
    else:
        return '❄️'


class KettleInfoListener:
    @abstractmethod
    def info_updated(self, field: str):
        pass


# class that holds data coming from the kettle over mqtt
class KettleInfo:
    update_time: int
    _mode: Optional[PowerType]
    _temperature: Optional[int]
    _target_temperature: Optional[int]
    _update_listener: KettleInfoListener

    def __init__(self, update_listener: KettleInfoListener):
        self.update_time = 0
        self._mode = None
        self._temperature = None
        self._target_temperature = None
        self._update_listener = update_listener

    def _update(self, field: str):
        self.update_time = int(time.time())
        if self._update_listener:
            self._update_listener.info_updated(field)

    @property
    def temperature(self) -> int:
        return self._temperature

    @temperature.setter
    def temperature(self, value: int):
        self._temperature = value
        self._update('temperature')

    @property
    def mode(self) -> PowerType:
        return self._mode

    @mode.setter
    def mode(self, value: PowerType):
        self._mode = value
        self._update('mode')

    @property
    def target_temperature(self) -> int:
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, value: int):
        self._target_temperature = value
        self._update('target_temperature')


class KettleController(threading.Thread,
                       MQTTBase,
                       DeviceListener,
                       IncomingMessageListener,
                       KettleInfoListener,
                       ConnectionStatusListener):
    kettle: Kettle
    info: KettleInfo

    _logger: logging.Logger
    _stopped: bool
    _restart_server_at: int
    _lock: threading.Lock
    _info_lock: threading.Lock
    _accumulated_updates: dict
    _info_flushed_time: float
    _mqtt_root_topic: str
    _muts: List[MessageUpdatingTarget]

    def __init__(self):
        # basic setup
        MQTTBase.__init__(self, clean_session=False)
        threading.Thread.__init__(self)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.kettle = Kettle(mac=config['kettle']['mac'],
                             device_token=config['kettle']['token'])
        self.kettle_reconnect()

        # info
        self.info = KettleInfo(update_listener=self)
        self._accumulated_updates = {}
        self._info_flushed_time = 0

        # mqtt
        self._mqtt_root_topic = '/polaris/6/'+config['kettle']['token']+'/#'
        self.connect_and_loop(loop_forever=False)

        # thread loop related
        self._stopped = False
        # self._lock = threading.Lock()
        self._info_lock = threading.Lock()
        self._restart_server_at = 0

        # bot
        self._muts = []
        self._muts_lock = threading.Lock()

        self.start()

    def kettle_reconnect(self):
        self.kettle.discover(wait=False, listener=self)

    def stop_all(self):
        self.kettle.stop_all()
        self._stopped = True

    def add_updating_message(self, mut: MessageUpdatingTarget):
        with self._muts_lock:
            for m in self._muts:
                if m.user_id == m.user_id and m.user_did_turn_on() or m.user_did_turn_on() != mut.user_did_turn_on():
                    m.delete()
            self._muts.append(mut)

    # ---------------------
    # threading.Thread impl

    def run(self):
        while not self._stopped:
            updates = []
            deletions = []
            forget = []

            with self._muts_lock and self._info_lock:
                if self._muts and self._accumulated_updates and (self._info_flushed_time == 0 or time.time() - self._info_flushed_time >= 1):
                    deletions = []

                    for mut in self._muts:
                        upd = mut.update(
                            mode=self.info.mode,
                            current_temp=self.info.temperature,
                            target_temp=self.info.target_temperature)

                        if upd.finished or upd.delete:
                            forget.append(mut)

                        if upd.delete:
                            deletions.append((mut, upd))

                        elif upd.changed:
                            updates.append((mut, upd))

                    self._info_flushed_time = time.time()
                    self._accumulated_updates = {}

            # edit messages
            for mut, upd in updates:
                self._logger.debug(f'loop: got update: {upd}')
                try:
                    do_edit = True
                    if upd.finished:
                        # try to delete the old message and send a new one, to notify user more effectively
                        try:
                            bot.delete_message(upd.user_id, upd.message_id)
                            do_edit = False
                        except TelegramError as exc:
                            self._logger.error(f'loop: failed to delete old message (in order to send a new one)')
                            self._logger.exception(exc)

                    if do_edit:
                        bot.edit_message_text(upd.user_id, upd.message_id,
                                              text=upd.html,
                                              reply_markup=upd.markup)
                    else:
                        bot.notify_user(upd.user_id, upd.html, reply_markup=upd.markup)
                except TelegramError as exc:
                    if "Message can't be edited" in exc.message:
                        self._logger.warning("message can't be edited, adding it to forget list")
                        forget.append(upd)

                    self._logger.error(f'loop: edit_message_text failed for update: {upd}')
                    self._logger.exception(exc)

            # delete messages
            for mut, upd in deletions:
                self._logger.debug(f'loop: got deletion: {upd}')
                try:
                    bot.delete_message(upd.user_id, upd.message_id)
                except TelegramError as exc:
                    self._logger.error(f'loop: delete_message failed for update: {upd}')
                    self._logger.exception(exc)

            # delete muts, if needed
            if forget:
                with self._muts_lock:
                    for mut in forget:
                        self._logger.debug(f'loop: removing mut {mut}')
                        self._muts.remove(mut)

            time.sleep(0.5)

    # -------------------
    # DeviceListener impl

    def device_updated(self):
        self._logger.info(f'device updated: {self.kettle.device.si}')
        self.kettle.start_server_if_needed(incoming_message_listener=self,
                                           connection_status_listener=self)

    # -----------------------
    # KettleInfoListener impl

    def info_updated(self, field: str):
        with self._info_lock:
            newval = getattr(self.info, field)
            self._logger.debug(f'info_updated: updated {field}, new value is {newval}')
            self._accumulated_updates[field] = newval

    # ----------------------------
    # IncomingMessageListener impl

    def incoming_message(self, message: kettle_proto.Message) -> Optional[kettle_proto.Message]:
        self._logger.info(f'incoming message: {message}')

        if isinstance(message, kettle_proto.ModeMessage):
            self.info.mode = message.pt
        elif isinstance(message, kettle_proto.CurrentTemperatureMessage):
            self.info.temperature = message.current_temperature
        elif isinstance(message, kettle_proto.TargetTemperatureMessage):
            self.info.target_temperature = message.temperature

        return kettle_proto.AckMessage()

    # -----------------------------
    # ConnectionStatusListener impl

    def connection_status_updated(self, status: ConnectionStatus):
        self._logger.info(f'connection status updated: {status}')
        if status == ConnectionStatus.DISCONNECTED:
            self.kettle.stop_all()
            self.kettle_reconnect()

    # -------------
    # MQTTBase impl

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)
        client.subscribe(self._mqtt_root_topic, qos=1)
        self._logger.info(f'subscribed to {self._mqtt_root_topic}')

    def on_message(self, client: mqtt.Client, userdata, msg):
        try:
            topic = msg.topic[len(self._mqtt_root_topic)-2:]
            pld = msg.payload.decode()

            self._logger.debug(f'mqtt: on message: topic={topic} pld={pld}')

            if topic == 'state/sensor/temperature':
                self.info.temperature = int(float(pld))
            elif topic == 'state/mode':
                self.info.mode = PowerType(int(pld))
            elif topic == 'state/temperature':
                self.info.target_temperature = int(float(pld))

        except Exception as e:
            self._logger.exception(str(e))


class Renderer:
    @classmethod
    def index(cls, ctx: Context) -> RenderedContent:
        html = f'<b>{ctx.lang("settings")}</b>\n\n'
        html += ctx.lang('select_place')
        return html, None

    @classmethod
    def status(cls, ctx: Context,
               connected: bool,
               mode: PowerType,
               current_temp: int,
               target_temp: int,
               update_time: int) -> RenderedContent:
        if not connected:
            return cls.not_connected(ctx)
        else:
            # power status
            if mode != PowerType.OFF:
                html = ctx.lang('status_on', target_temp)
            else:
                html = ctx.lang('status_off')

            # current temperature
            html += '\n'
            html += ctx.lang('status_current_temp', current_temp)

            # updated on
            html += '\n'
            html += cls.updated(ctx, update_time)

        return html, None

    @classmethod
    def temp(cls, ctx: Context, choices) -> RenderedContent:
        buttons = []
        for chunk in chunks(choices, 5):
            buttons.append([f'{temperature_emoji(n)} {n}' for n in chunk])
        buttons.append([ctx.lang('back')])
        return ctx.lang('select_temperature'), ReplyKeyboardMarkup(buttons)

    @classmethod
    def turned_on(cls, ctx: Context,
                  target_temp: int,
                  current_temp: int,
                  mode: PowerType,
                  update_time: Optional[int] = None,
                  reached=False,
                  no_keyboard=False) -> RenderedContent:
        if mode == PowerType.OFF and not reached:
            html = ctx.lang('enabling')
        else:
            if not reached:
                html = ctx.lang('enabled')

                # target temperature
                html += '\n'
                html += ctx.lang('enabled_target', temperature_emoji(target_temp), target_temp)

                # current temperature
                html += '\n'
                html += temperature_emoji(current_temp) + ' '
                html += ctx.lang('status_current_temp', current_temp)
            else:
                html = ctx.lang('enabled_reached', current_temp)

            # updated on
            if not reached and update_time is not None:
                html += '\n'
                html += cls.updated(ctx, update_time)

        return html, None if no_keyboard else cls.wait_buttons(ctx)

    @classmethod
    def turned_off(cls, ctx: Context,
                   mode: PowerType,
                   update_time: Optional[int] = None,
                   reached=False,
                   no_keyboard=False) -> RenderedContent:
        if mode != PowerType.OFF:
            html = ctx.lang('disabling')
        else:
            html = ctx.lang('disabled')

            # updated on
            if not reached and update_time is not None:
                html += '\n'
                html += cls.updated(ctx, update_time)

        return html, None if no_keyboard else cls.wait_buttons(ctx)

    @classmethod
    def not_connected(cls, ctx: Context) -> RenderedContent:
        return ctx.lang('status_not_connected'), None

    @classmethod
    def smth_went_wrong(cls, ctx: Context) -> RenderedContent:
        html = ctx.lang('smth_went_wrong')
        return html, None

    @classmethod
    def updated(cls, ctx: Context, update_time: int):
        locale_bak = locale.getlocale(locale.LC_TIME)
        locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8' if ctx.user_lang == 'ru' else 'en_US.UTF-8')
        dt = datetime.fromtimestamp(update_time)
        html = ctx.lang('status_update_time', dt.strftime(ctx.lang('status_update_time_fmt')))
        locale.setlocale(locale.LC_TIME, locale_bak)
        return html

    @classmethod
    def wait_buttons(cls, ctx: Context):
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(ctx.lang('please_wait'), callback_data='wait')
            ]
        ])


MUTUpdate = namedtuple('MUTUpdate', 'message_id, user_id, finished, changed, delete, html, markup')


class MessageUpdatingTarget:
    ctx: Context
    message: Message
    user_target_temp: Optional[int]
    user_enabled_power_mode: PowerType
    initial_power_mode: PowerType
    need_to_delete: bool
    rendered_content: Optional[RenderedContent]

    def __init__(self,
                 ctx: Context,
                 message: Message,
                 user_enabled_power_mode: PowerType,
                 initial_power_mode: PowerType,
                 user_target_temp: Optional[int] = None):
        self.ctx = ctx
        self.message = message
        self.initial_power_mode = initial_power_mode
        self.user_enabled_power_mode = user_enabled_power_mode
        self.ignore_pm = initial_power_mode is PowerType.OFF and self.user_did_turn_on()
        self.user_target_temp = user_target_temp
        self.need_to_delete = False
        self.rendered_content = None
        self.last_reported_temp = None

    def set_rendered_content(self, content: RenderedContent):
        self.rendered_content = content

    def rendered_content_changed(self, content: RenderedContent) -> bool:
        return content != self.rendered_content

    def update(self,
               mode: PowerType,
               current_temp: int,
               target_temp: int) -> MUTUpdate:

        # determine whether status updating is finished
        finished = False
        reached = False
        if self.ignore_pm:
            if mode != PowerType.OFF:
                self.ignore_pm = False
        elif mode == PowerType.OFF:
            reached = True
            if self.user_did_turn_on():
                # when target is 100 degrees, this kettle sometimes turns off at 91, sometimes at 95, sometimes at 98.
                # it's totally unpredictable, so in this case, we keep updating the message until it reaches at least 97
                # degrees, or if temperature started dropping.
                if self.user_target_temp < 100 \
                        or current_temp >= self.user_target_temp - 3 \
                        or current_temp < self.last_reported_temp:
                    finished = True
            else:
                finished = True

        self.last_reported_temp = current_temp

        # render message
        if self.user_did_turn_on():
            rc = Renderer.turned_on(self.ctx,
                                    target_temp=target_temp,
                                    current_temp=current_temp,
                                    mode=mode,
                                    reached=reached,
                                    no_keyboard=finished)
        else:
            rc = Renderer.turned_off(self.ctx,
                                     mode=mode,
                                     reached=reached,
                                     no_keyboard=finished)

        changed = self.rendered_content_changed(rc)
        update = MUTUpdate(message_id=self.message.message_id,
                           user_id=self.ctx.user_id,
                           finished=finished,
                           changed=changed,
                           delete=self.need_to_delete,
                           html=rc[0],
                           markup=rc[1])
        if changed:
            self.set_rendered_content(rc)
        return update

    def user_did_turn_on(self) -> bool:
        return self.user_enabled_power_mode in (PowerType.ON, PowerType.CUSTOM)

    def delete(self):
        self.need_to_delete = True

    @property
    def user_id(self) -> int:
        return self.ctx.user_id


class KettleBot(Wrapper):
    def __init__(self):
        super().__init__()

        self.lang.ru(
            start_message="Выберите команду на клавиатуре:",
            invalid_command="Неизвестная команда",
            unexpected_callback_data="Ошибка: неверные данные",
            disable="❌ Выключить",
            server_error="Ошибка сервера",
            back="🔙 Назад",
            smth_went_wrong="😱 Что-то пошло не так",

            # /status
            status_not_connected="😟 Связь с чайником не установлена",
            status_on="🟢 Чайник <b>включён</b> (до <b>%d °C</b>)",
            status_off="🔴 Чайник <b>выключен</b>",
            status_current_temp="Сейчас: <b>%d °C</b>",
            status_update_time="<i>Обновлено %s</i>",
            status_update_time_fmt="%d %b в %H:%M:%S",

            # /temp
            select_temperature="Выберите температуру:",

            # enable/disable
            enabling="💤 Чайник включается...",
            disabling="💤 Чайник выключается...",
            enabled="🟢 Чайник <b>включён</b>.",
            enabled_target="%s Цель: <b>%d °C</b>",
            enabled_reached="✅ <b>Готово!</b> Чайник вскипел, температура <b>%d °C</b>.",
            disabled="✅ Чайник <b>выключен</b>.",
            please_wait="⏳ Ожидайте..."
        )

        self.lang.en(
            start_message="Select command on the keyboard:",
            invalid_command="Unknown command",
            unexpected_callback_data="Unexpected callback data",
            disable="❌ Turn OFF",
            server_error="Server error",
            back="🔙 Back",
            smth_went_wrong="😱 Something went wrong",

            # /status
            status_not_connected="😟 No connection",
            status_on="🟢 Turned <b>ON</b>! Target: <b>%d °C</b>",
            status_off="🔴 Turned <b>OFF</b>",
            status_current_temp="Now: <b>%d °C</b>",
            status_update_time="<i>Updated on %s</i>",
            status_update_time_fmt="%b %d, %Y at %H:%M:%S",

            # /temp
            select_temperature="Select a temperature:",

            # enable/disable
            enabling="💤 Turning on...",
            disabling="💤 Turning off...",
            enabled="🟢 The kettle is <b>turned ON</b>.",
            enabled_target="%s Target: <b>%d °C</b>",
            enabled_reached="✅ <b>Done</b>! The kettle has boiled, the temperature is <b>%d °C</b>.",
            disabled="✅ The kettle is <b>turned OFF</b>.",
            please_wait="⏳ Please wait..."
        )

        self.primary_choices = (70, 80, 90, 100)
        self.all_choices = range(
            config['kettle']['temp_min'],
            config['kettle']['temp_max']+1,
            config['kettle']['temp_step'])

        # commands
        self.add_handler(CommandHandler('status', self.status))
        self.add_handler(CommandHandler('temp', self.temp))

        # enable messages
        for temp in self.primary_choices:
            self.add_handler(MessageHandler(text_filter(f'{temperature_emoji(temp)} {temp}'), self.wrap(partial(self.on, temp))))
        for temp in self.all_choices:
            self.add_handler(MessageHandler(text_filter(f'{temperature_emoji(temp)} {temp}'), self.wrap(partial(self.on, temp))))

        # disable message
        self.add_handler(MessageHandler(text_filter(self.lang.all('disable')), self.off))

        # back message
        self.add_handler(MessageHandler(text_filter(self.lang.all('back')), self.back))

    def markup(self, ctx: Optional[Context]) -> Optional[ReplyKeyboardMarkup]:
        buttons = [
            [f'{temperature_emoji(n)} {n}' for n in self.primary_choices],
            [ctx.lang('disable')]
        ]
        return ReplyKeyboardMarkup(buttons, one_time_keyboard=False)

    def on(self, temp: int, ctx: Context) -> None:
        if not kc.kettle.is_connected():
            text, markup = Renderer.not_connected(ctx)
            ctx.reply(text, markup=markup)
            return

        tasks = queue.SimpleQueue()
        if temp == 100:
            power_mode = PowerType.ON
        else:
            power_mode = PowerType.CUSTOM
            tasks.put(['set_target_temperature', temp])
        tasks.put(['set_power', power_mode])

        def done(ok: bool):
            if not ok:
                html, markup = Renderer.smth_went_wrong(ctx)
            else:
                html, markup = Renderer.turned_on(ctx,
                                                  target_temp=temp,
                                                  current_temp=kc.info.temperature,
                                                  mode=kc.info.mode)
            message = ctx.reply(html, markup=markup)
            logger.debug(f'ctx.reply returned message: {message}')

            if ok:
                mut = MessageUpdatingTarget(ctx, message,
                                            initial_power_mode=kc.info.mode,
                                            user_enabled_power_mode=power_mode,
                                            user_target_temp=temp)
                mut.set_rendered_content((html, markup))
                kc.add_updating_message(mut)

        run_tasks(tasks, done)

    @handlermethod
    def off(self, ctx: Context) -> None:
        if not kc.kettle.is_connected():
            text, markup = Renderer.not_connected(ctx)
            ctx.reply(text, markup=markup)
            return

        def done(ok: bool):
            mode = kc.info.mode
            if not ok:
                html, markup = Renderer.smth_went_wrong(ctx)
            else:
                kw = {}
                if mode == PowerType.OFF:
                    kw['reached'] = True
                    kw['no_keyboard'] = True
                html, markup = Renderer.turned_off(ctx, mode=mode, **kw)
            message = ctx.reply(html, markup=markup)
            logger.debug(f'ctx.reply returned message: {message}')

            if ok and mode != PowerType.OFF:
                mut = MessageUpdatingTarget(ctx, message,
                                            initial_power_mode=mode,
                                            user_enabled_power_mode=PowerType.OFF)
                mut.set_rendered_content((html, markup))
                kc.add_updating_message(mut)

        tasks = queue.SimpleQueue()
        tasks.put(['set_power', PowerType.OFF])
        run_tasks(tasks, done)

    @handlermethod
    def status(self, ctx: Context):
        text, markup = Renderer.status(ctx,
                                       connected=kc.kettle.is_connected(),
                                       mode=kc.info.mode,
                                       current_temp=kc.info.temperature,
                                       target_temp=kc.info.target_temperature,
                                       update_time=kc.info.update_time)
        return ctx.reply(text, markup=markup)

    @handlermethod
    def temp(self, ctx: Context):
        text, markup = Renderer.temp(
            ctx, choices=self.all_choices)
        return ctx.reply(text, markup=markup)

    @handlermethod
    def back(self, ctx: Context):
        self.start(ctx)


if __name__ == '__main__':
    config.load('polaris_kettle_bot')

    kc = KettleController()

    bot = KettleBot()
    if 'api' in config:
        bot.enable_logging(BotType.POLARIS_KETTLE)
    bot.run()

    # bot library handles signals, so when sigterm or something like that happens, we should stop all other threads here
    kc.stop_all()
