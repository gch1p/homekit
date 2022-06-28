#!/usr/bin/env python3
import logging
import os
import tempfile

from enum import Enum
from datetime import datetime, timedelta
from html import escape
from typing import Optional, List, Dict, Tuple

from home.config import config
from home.bot import Wrapper, Context, text_filter, user_any_name
from home.api import WebAPIClient
from home.api.types import SoundSensorLocation, BotType
from home.api.errors import ApiResponseError
from home.media import SoundNodeClient, SoundRecordClient, SoundRecordFile, CameraNodeClient
from home.soundsensor import SoundSensorServerGuardClient
from home.util import parse_addr, chunks, filesize_fmt

from telegram.error import TelegramError
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, User
from telegram.ext import (
    CallbackQueryHandler,
    MessageHandler
)

from PIL import Image

logger = logging.getLogger(__name__)
RenderedContent = Tuple[str, Optional[InlineKeyboardMarkup]]
record_client: Optional[SoundRecordClient] = None
bot: Optional[Wrapper] = None
node_client_links: Dict[str, SoundNodeClient] = {}
cam_client_links: Dict[str, CameraNodeClient] = {}


def node_client(node: str) -> SoundNodeClient:
    if node not in node_client_links:
        node_client_links[node] = SoundNodeClient(parse_addr(config['nodes'][node]['addr']))
    return node_client_links[node]


def camera_client(cam: str) -> CameraNodeClient:
    if cam not in node_client_links:
        cam_client_links[cam] = CameraNodeClient(parse_addr(config['cameras'][cam]['addr']))
    return cam_client_links[cam]


def node_exists(node: str) -> bool:
    return node in config['nodes']


def camera_exists(name: str) -> bool:
    return name in config['cameras']


def camera_settings(name: str) -> Optional[dict]:
    try:
        return config['cameras'][name]['settings']
    except KeyError:
        return None


def have_cameras() -> bool:
    return 'cameras' in config and config['cameras']


def sound_sensor_exists(node: str) -> bool:
    return node in config['sound_sensors']


def interval_defined(interval: int) -> bool:
    return interval in config['bot']['record_intervals']


def callback_unpack(ctx: Context) -> List[str]:
    return ctx.callback_query.data[3:].split('/')


def manual_recording_allowed(user_id: int) -> bool:
    return 'manual_record_allowlist' not in config['bot'] or user_id in config['bot']['manual_record_allowlist']


def guard_client() -> SoundSensorServerGuardClient:
    return SoundSensorServerGuardClient(parse_addr(config['bot']['guard_server']))


# message renderers
# -----------------

class Renderer:
    @classmethod
    def places_markup(cls, ctx: Context, callback_prefix: str) -> InlineKeyboardMarkup:
        buttons = []
        for node, nodeconfig in config['nodes'].items():
            buttons.append([InlineKeyboardButton(nodeconfig['label'][ctx.user_lang], callback_data=f'{callback_prefix}/{node}')])
        return InlineKeyboardMarkup(buttons)

    @classmethod
    def back_button(cls,
                    ctx: Context,
                    buttons: list,
                    callback_data: str):
        buttons.append([
            InlineKeyboardButton(ctx.lang('back'), callback_data=callback_data)
        ])


class SettingsRenderer(Renderer):
    @classmethod
    def index(cls, ctx: Context) -> RenderedContent:
        html = f'<b>{ctx.lang("settings")}</b>\n\n'
        html += ctx.lang('select_place')
        return html, cls.places_markup(ctx, callback_prefix='s0')

    @classmethod
    def node(cls, ctx: Context,
             controls: List[dict]) -> RenderedContent:
        node, = callback_unpack(ctx)

        html = []
        buttons = []
        for control in controls:
            html.append(f'<b>{control["name"]}</b>\n{escape(control["info"])}')
            buttons.append([
                InlineKeyboardButton(control['name'], callback_data=f's1/{node}/{control["name"]}')
            ])

        html = "\n\n".join(html)
        cls.back_button(ctx, buttons, callback_data='s0')

        return html, InlineKeyboardMarkup(buttons)

    @classmethod
    def control(cls, ctx: Context, data) -> RenderedContent:
        node, control, *rest = callback_unpack(ctx)

        html = '<b>' + ctx.lang('control_state', control) + '</b>\n\n'
        html += escape(data['info'])
        buttons = []
        callback_prefix = f's2/{node}/{control}'
        for cap in data['caps']:
            if cap == 'mute':
                muted = 'dB] [off]' in data['info']
                act = 'unmute' if muted else 'mute'
                buttons.append([InlineKeyboardButton(act, callback_data=f'{callback_prefix}/{act}')])

            elif cap == 'cap':
                cap_dis = 'Capture [off]' in data['info']
                act = 'cap' if cap_dis else 'nocap'
                buttons.append([InlineKeyboardButton(act, callback_data=f'{callback_prefix}/{act}')])

            elif cap == 'volume':
                buttons.append(
                    list(map(lambda s: InlineKeyboardButton(ctx.lang(s), callback_data=f'{callback_prefix}/{s}'),
                             ['decr', 'incr']))
                )

        cls.back_button(ctx, buttons, callback_data=f's0/{node}')

        return html, InlineKeyboardMarkup(buttons)


class RecordRenderer(Renderer):
    @classmethod
    def index(cls, ctx: Context) -> RenderedContent:
        html = f'<b>{ctx.lang("record")}</b>\n\n'
        html += ctx.lang('select_place')
        return html, cls.places_markup(ctx, callback_prefix='r0')

    @classmethod
    def node(cls, ctx: Context, durations: List[int]) -> RenderedContent:
        node, = callback_unpack(ctx)

        html = ctx.lang('select_interval')

        buttons = []
        for s in durations:
            if s >= 60:
                m = int(s / 60)
                label = ctx.lang('n_min', m)
            else:
                label = ctx.lang('n_sec', s)
            buttons.append(InlineKeyboardButton(label, callback_data=f'r1/{node}/{s}'))
        buttons = list(chunks(buttons, 3))
        cls.back_button(ctx, buttons, callback_data=f'r0')

        return html, InlineKeyboardMarkup(buttons)

    @classmethod
    def record_started(cls, ctx: Context, rid: int) -> RenderedContent:
        node, *rest = callback_unpack(ctx)

        place = config['nodes'][node]['label'][ctx.user_lang]

        html = f'<b>{ctx.lang("record_started")}</b> (<i>{place}</i>, id={rid})'
        return html, None

    @classmethod
    def record_done(cls, info: dict, node: str, uid: int) -> str:
        ulang = bot.store.get_user_lang(uid)

        def lang(key, *args):
            return bot.lang.get(key, ulang, *args)

        rid = info['id']
        fmt = '%d.%m.%y %H:%M:%S'
        start_time = datetime.fromtimestamp(int(info['start_time'])).strftime(fmt)
        stop_time = datetime.fromtimestamp(int(info['stop_time'])).strftime(fmt)

        place = config['nodes'][node]['label'][ulang]

        html = f'<b>{lang("record_result")}</b> (<i>{place}</i>, id={rid})\n\n'
        html += f'<b>{lang("beginning")}</b>: {start_time}\n'
        html += f'<b>{lang("end")}</b>: {stop_time}'

        return html

    @classmethod
    def record_error(cls, info: dict, node: str, uid: int) -> str:
        ulang = bot.store.get_user_lang(uid)

        def lang(key, *args):
            return bot.lang.get(key, ulang, *args)

        place = config['nodes'][node]['label'][ulang]
        rid = info['id']

        html = f'<b>{lang("record_error")}</b> (<i>{place}</i>, id={rid})'
        if 'error' in info:
            html += '\n'+str(info['error'])

        return html


class FilesRenderer(Renderer):
    @classmethod
    def index(cls, ctx: Context) -> RenderedContent:
        html = f'<b>{ctx.lang("files")}</b>\n\n'
        html += ctx.lang('select_place')
        return html, cls.places_markup(ctx, callback_prefix='f0')

    @classmethod
    def filelist(cls, ctx: Context, files: List[SoundRecordFile]) -> RenderedContent:
        node, = callback_unpack(ctx)

        html_files = map(lambda file: cls.file(ctx, file, node), files)
        html = '\n\n'.join(html_files)

        buttons = []
        cls.back_button(ctx, buttons, callback_data='f0')

        return html, InlineKeyboardMarkup(buttons)

    @classmethod
    def file(cls, ctx: Context, file: SoundRecordFile, node: str) -> str:
        html = ctx.lang('file_line', file.start_humantime, file.stop_humantime, filesize_fmt(file.filesize))
        if file.file_id is not None:
            html += f'/audio_{node}_{file.file_id}'
        return html


class RemoteFilesRenderer(FilesRenderer):
    @classmethod
    def index(cls, ctx: Context) -> RenderedContent:
        html = f'<b>{ctx.lang("remote_files")}</b>\n\n'
        html += ctx.lang('select_place')
        return html, cls.places_markup(ctx, callback_prefix='g0')


class SoundSensorRenderer(Renderer):
    @classmethod
    def places_markup(cls, ctx: Context, callback_prefix: str) -> InlineKeyboardMarkup:
        buttons = []
        for sensor, sensor_label in config['sound_sensors'].items():
            buttons.append(
                [InlineKeyboardButton(sensor_label[ctx.user_lang], callback_data=f'{callback_prefix}/{sensor}')])
        return InlineKeyboardMarkup(buttons)

    @classmethod
    def index(cls, ctx: Context) -> RenderedContent:
        html = f'{ctx.lang("sound_sensors_info")}\n\n'
        html += ctx.lang('select_place')
        return html, cls.places_markup(ctx, callback_prefix='S0')

    @classmethod
    def hits(cls, ctx: Context, data, is_last=False) -> RenderedContent:
        node, = callback_unpack(ctx)
        buttons = []

        if not data:
            html = ctx.lang('sound_sensors_no_24h_data')
            if not is_last:
                buttons.append([InlineKeyboardButton(ctx.lang('sound_sensors_show_anything'), callback_data=f'S1/{node}')])
        else:
            html = ''
            prev_date = None
            for item in data:
                item_date = item['time'].strftime('%d.%m.%y')
                if prev_date is None or prev_date != item_date:
                    if html != '':
                        html += '\n\n'
                    html += f'<b>{item_date}</b>'
                    prev_date = item_date
                html += '\n' + item['time'].strftime('%H:%M:%S') + f' (+{item["hits"]})'
        cls.back_button(ctx, buttons, callback_data='S0')
        return html, InlineKeyboardMarkup(buttons)

    @classmethod
    def hits_plain(cls, ctx: Context, data, is_last=False) -> bytes:
        node, = callback_unpack(ctx)

        text = ''
        prev_date = None
        for item in data:
            item_date = item['time'].strftime('%d.%m.%y')
            if prev_date is None or prev_date != item_date:
                if text != '':
                    text += '\n\n'
                text += item_date
                prev_date = item_date
            text += '\n' + item['time'].strftime('%H:%M:%S') + f' (+{item["hits"]})'

        return text.encode()


class CamerasRenderer(Renderer):
    @classmethod
    def index(cls, ctx: Context) -> RenderedContent:
        html = f'<b>{ctx.lang("cameras")}</b>\n\n'
        html += ctx.lang('select_place')
        return html, cls.places_markup(ctx, callback_prefix='c0')

    @classmethod
    def places_markup(cls, ctx: Context, callback_prefix: str) -> InlineKeyboardMarkup:
        buttons = []
        for camera_name, camera_data in config['cameras'].items():
            buttons.append(
                [InlineKeyboardButton(camera_data['label'][ctx.user_lang], callback_data=f'{callback_prefix}/{camera_name}')])
        return InlineKeyboardMarkup(buttons)

    @classmethod
    def camera(cls, ctx: Context, flash_available: bool) -> RenderedContent:
        node, = callback_unpack(ctx)

        html = ctx.lang('select_option')

        buttons = []
        if flash_available:
            buttons.append(InlineKeyboardButton(ctx.lang('w_flash'), callback_data=f'c1/{node}/1'))
        buttons.append(InlineKeyboardButton(ctx.lang('wo_flash'), callback_data=f'c1/{node}/0'))

        cls.back_button(ctx, [buttons], callback_data=f'c0')

        return html, InlineKeyboardMarkup([buttons])
    #
    # @classmethod
    # def record_started(cls, ctx: Context, rid: int) -> RenderedContent:
    #     node, *rest = callback_unpack(ctx)
    #
    #     place = config['nodes'][node]['label'][ctx.user_lang]
    #
    #     html = f'<b>{ctx.lang("record_started")}</b> (<i>{place}</i>, id={rid})'
    #     return html, None
    #
    # @classmethod
    # def record_done(cls, info: dict, node: str, uid: int) -> str:
    #     ulang = bot.store.get_user_lang(uid)
    #
    #     def lang(key, *args):
    #         return bot.lang.get(key, ulang, *args)
    #
    #     rid = info['id']
    #     fmt = '%d.%m.%y %H:%M:%S'
    #     start_time = datetime.fromtimestamp(int(info['start_time'])).strftime(fmt)
    #     stop_time = datetime.fromtimestamp(int(info['stop_time'])).strftime(fmt)
    #
    #     place = config['nodes'][node]['label'][ulang]
    #
    #     html = f'<b>{lang("record_result")}</b> (<i>{place}</i>, id={rid})\n\n'
    #     html += f'<b>{lang("beginning")}</b>: {start_time}\n'
    #     html += f'<b>{lang("end")}</b>: {stop_time}'
    #
    #     return html
    #
    # @classmethod
    # def record_error(cls, info: dict, node: str, uid: int) -> str:
    #     ulang = bot.store.get_user_lang(uid)
    #
    #     def lang(key, *args):
    #         return bot.lang.get(key, ulang, *args)
    #
    #     place = config['nodes'][node]['label'][ulang]
    #     rid = info['id']
    #
    #     html = f'<b>{lang("record_error")}</b> (<i>{place}</i>, id={rid})'
    #     if 'error' in info:
    #         html += '\n'+str(info['error'])
    #
    #     return html


# cameras handlers
# ----------------

def cameras(ctx: Context):
    text, markup = CamerasRenderer.index(ctx)
    if not ctx.is_callback_context():
        return ctx.reply(text, markup=markup)
    else:
        ctx.answer()
        return ctx.edit(text, markup=markup)


def camera_options(ctx: Context) -> None:
    cam, = callback_unpack(ctx)
    if not camera_exists(cam):
        ctx.answer(ctx.lang('invalid_location'))
        return

    ctx.answer()
    flash_available = 'flash_available' in config['cameras'][cam] and config['cameras'][cam]['flash_available'] is True

    text, markup = CamerasRenderer.camera(ctx, flash_available)
    ctx.edit(text, markup)


def camera_capture(ctx: Context) -> None:
    cam, flash = callback_unpack(ctx)
    flash = int(flash)
    if not camera_exists(cam):
        ctx.answer(ctx.lang('invalid_location'))
        return

    ctx.answer()

    client = camera_client(cam)
    fd = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    fd.close()

    client.capture(fd.name, with_flash=bool(flash))
    logger.debug(f'captured photo ({cam}), saved to {fd.name}')

    camera_config = config['cameras'][cam]
    if 'rotate' in camera_config:
        im = Image.open(fd.name)
        im.rotate(camera_config['rotate'], expand=True)
        # im.show()
        im.save(fd.name)
        logger.debug(f"rotated image {camera_config['rotate']} degrees")

    try:
        with open(fd.name, 'rb') as f:
            bot.send_photo(ctx.user_id, photo=f)
    except TelegramError as exc:
        logger.exception(exc)

    try:
        os.unlink(fd.name)
    except OSError as exc:
        logger.exception(exc)


# settings handlers
# -----------------

def settings(ctx: Context):
    text, markup = SettingsRenderer.index(ctx)
    if not ctx.is_callback_context():
        return ctx.reply(text, markup=markup)
    else:
        ctx.answer()
        return ctx.edit(text, markup=markup)


def settings_place(ctx: Context) -> None:
    node, = callback_unpack(ctx)
    if not node_exists(node):
        ctx.answer(ctx.lang('invalid_location'))
        return

    cl = node_client(node)
    controls = cl.amixer_get_all()

    ctx.answer()

    text, markup = SettingsRenderer.node(ctx, controls)
    ctx.edit(text, markup)


def settings_place_control(ctx: Context) -> None:
    node, control = callback_unpack(ctx)
    if not node_exists(node):
        ctx.answer(ctx.lang('invalid_location'))
        return

    cl = node_client(node)
    control_data = cl.amixer_get(control)

    ctx.answer()

    text, markup = SettingsRenderer.control(ctx, control_data)
    ctx.edit(text, markup)


def settings_place_control_action(ctx: Context) -> None:
    node, control, action = callback_unpack(ctx)
    if not node_exists(node):
        return

    cl = node_client(node)
    if not hasattr(cl, f'amixer_{action}'):
        ctx.answer(ctx.lang('invalid_action'))
        return

    func = getattr(cl, f'amixer_{action}')
    control_data = func(control)

    ctx.answer()

    text, markup = SettingsRenderer.control(ctx, control_data)
    ctx.edit(text, markup)


# recording handlers
# ------------------

def record(ctx: Context):
    if not manual_recording_allowed(ctx.user_id):
        return ctx.reply(ctx.lang('access_denied'))

    text, markup = RecordRenderer.index(ctx)
    if not ctx.is_callback_context():
        return ctx.reply(text, markup=markup)
    else:
        ctx.answer()
        return ctx.edit(text, markup=markup)


def record_place(ctx: Context) -> None:
    node, = callback_unpack(ctx)
    if not node_exists(node):
        ctx.answer(ctx.lang('invalid_location'))
        return

    ctx.answer()

    text, markup = RecordRenderer.node(ctx, config['bot']['record_intervals'])
    ctx.edit(text, markup)


def record_place_interval(ctx: Context) -> None:
    node, interval = callback_unpack(ctx)
    interval = int(interval)
    if not node_exists(node):
        ctx.answer(ctx.lang('invalid_location'))
        return
    if not interval_defined(interval):
        ctx.answer(ctx.lang('invalid_interval'))
        return

    try:
        record_id = record_client.record(node, interval, {'user_id': ctx.user_id, 'node': node})
    except ApiResponseError as e:
        ctx.answer(e.error_message)
        logger.error(e)
        return

    ctx.answer()

    html, markup = RecordRenderer.record_started(ctx, record_id)
    ctx.edit(html, markup)


# files handlers
# --------------

# def files(ctx: Context, remote=False):
#     renderer = RemoteFilesRenderer if remote else FilesRenderer
#     text, markup = renderer.index(ctx)
#     if not ctx.is_callback_context():
#         return ctx.reply(text, markup=markup)
#     else:
#         ctx.answer()
#         return ctx.edit(text, markup=markup)
#
#
# def files_list(ctx: Context):
#     node, = callback_unpack(ctx)
#     if not node_exists(node):
#         ctx.answer(ctx.lang('invalid_location'))
#         return
#
#     ctx.answer()
#
#     cl = node_client(node)
#     files = cl.storage_list(extended=True, as_objects=True)
#
#     text, markup = FilesRenderer.filelist(ctx, files)
#     ctx.edit(text, markup)


# sound sensor handlers
# ---------------------

def sound_sensors(ctx: Context):
    text, markup = SoundSensorRenderer.index(ctx)
    if not ctx.is_callback_context():
        return ctx.reply(text, markup=markup)
    else:
        ctx.answer()
        return ctx.edit(text, markup=markup)


def sound_sensors_last_24h(ctx: Context):
    node, = callback_unpack(ctx)
    if not sound_sensor_exists(node):
        ctx.answer(ctx.lang('invalid location'))
        return

    ctx.answer()

    cl = WebAPIClient()
    data = cl.get_sound_sensor_hits(location=SoundSensorLocation[node.upper()],
                                    after=datetime.now() - timedelta(hours=24))

    text, markup = SoundSensorRenderer.hits(ctx, data)
    if len(text) > 4096:
        plain = SoundSensorRenderer.hits_plain(ctx, data)
        bot.send_file(ctx.user_id, document=plain, filename='data.txt')
    else:
        ctx.edit(text, markup=markup)


def sound_sensors_last_anything(ctx: Context):
    node, = callback_unpack(ctx)
    if not sound_sensor_exists(node):
        ctx.answer(ctx.lang('invalid location'))
        return

    ctx.answer()

    cl = WebAPIClient()
    data = cl.get_last_sound_sensor_hits(location=SoundSensorLocation[node.upper()],
                                         last=20)

    text, markup = SoundSensorRenderer.hits(ctx, data, is_last=True)
    if len(text) > 4096:
        plain = SoundSensorRenderer.hits_plain(ctx, data)
        bot.send_file(ctx.user_id, document=plain, filename='data.txt')
    else:
        ctx.edit(text, markup=markup)


# guard enable/disable handlers
# -----------------------------

class GuardUserAction(Enum):
    ENABLE = 'enable'
    DISABLE = 'disable'


def guard_status(ctx: Context):
    guard = guard_client()
    resp = guard.guard_status()

    key = 'enabled' if resp['enabled'] is True else 'disabled'
    ctx.reply(ctx.lang(f'guard_status_{key}'))


def guard_enable(ctx: Context):
    guard = guard_client()
    guard.guard_enable()
    ctx.reply(ctx.lang('done'))

    _guard_notify(ctx.user, GuardUserAction.ENABLE)


def guard_disable(ctx: Context):
    guard = guard_client()
    guard.guard_disable()
    ctx.reply(ctx.lang('done'))

    _guard_notify(ctx.user, GuardUserAction.DISABLE)


def _guard_notify(user: User, action: GuardUserAction):
    def text_getter(lang: str):
        action_name = bot.lang.get(f'guard_user_action_{action.value}', lang)
        user_name = user_any_name(user)
        return 'ℹ ' + bot.lang.get('guard_user_action_notification', lang,
                                   user.id, user_name, action_name)

    bot.notify_all(text_getter, exclude=(user.id,))


# record client callbacks
# -----------------------

def record_onerror(info: dict, userdata: dict):
    uid = userdata['user_id']
    node = userdata['node']

    html = RecordRenderer.record_error(info, node, uid)
    try:
        bot.notify_user(userdata['user_id'], html)
    except TelegramError as exc:
        logger.exception(exc)
    finally:
        record_client.forget(node, info['id'])


def record_onfinished(info: dict, fn: str, userdata: dict):
    logger.info('record finished: ' + str(info))

    uid = userdata['user_id']
    node = userdata['node']

    html = RecordRenderer.record_done(info, node, uid)
    bot.notify_user(uid, html)

    try:
        # sending audiofile to telegram
        with open(fn, 'rb') as f:
            bot.send_audio(uid, audio=f, filename='audio.mp3')

        # deleting temp file
        try:
            os.unlink(fn)
        except OSError as exc:
            logger.exception(exc)
            bot.notify_user(uid, exc)

        # remove the recording from sound_node's history
        record_client.forget(node, info['id'])

        # remove file from storage
        # node_client(node).storage_delete(info['file']['fileid'])
    except Exception as e:
        logger.exception(e)


class SoundBot(Wrapper):
    def __init__(self):
        super().__init__()

        self.lang.ru(
            start_message="Выберите команду на клавиатуре",
            unknown_command="Неизвестная команда",
            unexpected_callback_data="Ошибка: неверные данные",
            settings="Настройки микшера",
            record="Запись",
            loading="Загрузка...",
            select_place="Выберите место:",
            invalid_location="Неверное место",
            invalid_interval="Неверная длительность",
            unsupported_action="Неподдерживаемое действие",
            # select_control="Выберите контрол для изменения настроек:",
            control_state="Состояние контрола %s",
            incr="громкость +",
            decr="громкость -",
            back="◀️ Назад",
            n_min="%d мин.",
            n_sec="%d сек.",
            select_interval="Выберите длительность:",
            place="Место",
            beginning="Начало",
            end="Конец",
            record_result="Результат записи",
            record_started='Запись запущена!',
            record_error="Ошибка записи",
            files="Локальные файлы",
            remote_files="Файлы на сервере",
            file_line="— Запись с <b>%s</b> до <b>%s</b> <i>(%s)</i>",
            access_denied="Доступ запрещён",

            guard_disable="Снять с охраны",
            guard_enable="Поставить на охрану",
            guard_status="Статус охраны",
            guard_user_action_notification='Пользователь <a href="tg://user?id=%d">%s</a> %s.',
            guard_user_action_enable="включил охрану ✅",
            guard_user_action_disable="выключил охрану ❌",
            guard_status_enabled="Включена ✅",
            guard_status_disabled="Выключена ❌",

            done="Готово 👌",

            sound_sensors="Датчики звука",
            sound_sensors_info="Здесь можно получить информацию о последних срабатываниях датчиков звука.",
            sound_sensors_no_24h_data="За последние 24 часа данных нет.",
            sound_sensors_show_anything="Показать, что есть",

            cameras="Камеры",
            select_option="Выберите опцию",
            w_flash="Со вспышкой",
            wo_flash="Без вспышки",
        )

        self.lang.en(
            start_message="Select command on the keyboard",
            unknown_command="Unknown command",
            settings="Mixer settings",
            record="Record",
            unexpected_callback_data="Unexpected callback data",
            loading="Loading...",
            select_place="Select place:",
            invalid_location="Invalid place",
            invalid_interval="Invalid duration",
            unsupported_action="Unsupported action",
            # select_control="Select control to adjust its parameters:",
            control_state="%s control state",
            incr="vol +",
            decr="vol -",
            back="◀️ Back",
            n_min="%d min.",
            n_sec="%d s.",
            select_interval="Select duration:",
            place="Place",
            beginning="Started",
            end="Ended",
            record_result="Result",
            record_started='Recording started!',
            record_error="Recording error",
            files="Local files",
            remote_files="Remote files",
            file_line="— From <b>%s</b> to <b>%s</b> <i>(%s)</i>",
            access_denied="Access denied",

            guard_disable="Disable guard",
            guard_enable="Enable guard",
            guard_status="Guard status",
            guard_user_action_notification='User <a href="tg://user?id=%d">%s</a> %s.',
            guard_user_action_enable="turned the guard ON ✅",
            guard_user_action_disable="turn the guard OFF ❌",
            guard_status_enabled="Active ✅",
            guard_status_disabled="Disabled ❌",
            done="Done 👌",

            sound_sensors="Sound sensors",
            sound_sensors_info="Here you can get information about last sound sensors hits.",
            sound_sensors_no_24h_data="No data for the last 24 hours.",
            sound_sensors_show_anything="Show me at least something",

            cameras="Cameras",
            select_option="Select option",
            w_flash="With flash",
            wo_flash="Without flash",
        )

        # ------
        #   settings
        # -------------

        # list of nodes
        self.add_handler(MessageHandler(text_filter(self.lang.all('settings')), self.wrap(settings)))
        self.add_handler(CallbackQueryHandler(self.wrap(settings), pattern=r'^s0$'))

        # list of controls
        self.add_handler(CallbackQueryHandler(self.wrap(settings_place), pattern=r'^s0/.*'))

        # list of available tunes for control
        self.add_handler(CallbackQueryHandler(self.wrap(settings_place_control), pattern=r'^s1/.*'))

        # tuning
        self.add_handler(CallbackQueryHandler(self.wrap(settings_place_control_action), pattern=r'^s2/.*'))

        # ------
        #   recording
        # --------------

        # list of nodes
        self.add_handler(MessageHandler(text_filter(self.lang.all('record')), self.wrap(record)))
        self.add_handler(CallbackQueryHandler(self.wrap(record), pattern=r'^r0$'))

        # list of available intervals
        self.add_handler(CallbackQueryHandler(self.wrap(record_place), pattern=r'^r0/.*'))

        # do record!
        self.add_handler(CallbackQueryHandler(self.wrap(record_place_interval), pattern=r'^r1/.*'))

        # ---------
        #   sound sensors
        # ------------------

        # list of places
        self.add_handler(MessageHandler(text_filter(self.lang.all('sound_sensors')), self.wrap(sound_sensors)))
        self.add_handler(CallbackQueryHandler(self.wrap(sound_sensors), pattern=r'^S0$'))

        # last 24h log
        self.add_handler(CallbackQueryHandler(self.wrap(sound_sensors_last_24h), pattern=r'^S0/.*'))

        # last _something_
        self.add_handler(CallbackQueryHandler(self.wrap(sound_sensors_last_anything), pattern=r'^S1/.*'))

        # -------------
        #   guard enable/disable
        # -------------------------
        if 'guard_server' in config['bot']:
            self.add_handler(MessageHandler(text_filter(self.lang.all('guard_enable')), self.wrap(guard_enable)))
            self.add_handler(MessageHandler(text_filter(self.lang.all('guard_disable')), self.wrap(guard_disable)))
            self.add_handler(MessageHandler(text_filter(self.lang.all('guard_status')), self.wrap(guard_status)))

        # --------
        #   local files
        # ----------------

        # list of nodes
        # self.add_handler(MessageHandler(text_filter(self.lang.all('files')), self.wrap(partial(files, remote=False))))
        # self.add_handler(CallbackQueryHandler(self.wrap(partial(files, remote=False)), pattern=r'^f0$'))

        # list of specific node's files
        # self.add_handler(CallbackQueryHandler(self.wrap(files_list), pattern=r'^f0/.*'))

        # --------
        #   remote files
        # -----------------

        # list of nodes
        # self.add_handler(MessageHandler(text_filter(self.lang.all('remote_files')), self.wrap(partial(files, remote=True))))
        # self.add_handler(CallbackQueryHandler(self.wrap(partial(files, remote=True)), pattern=r'^g0$'))

        # list of specific node's files
        # self.add_handler(CallbackQueryHandler(self.wrap(files_list), pattern=r'^g0/.*'))

        # ------
        #   cameras
        # ------------

        # list of cameras
        self.add_handler(MessageHandler(text_filter(self.lang.all('cameras')), self.wrap(cameras)))
        self.add_handler(CallbackQueryHandler(self.wrap(cameras), pattern=r'^c0$'))

        # list of options (with/without flash etc)
        self.add_handler(CallbackQueryHandler(self.wrap(camera_options), pattern=r'^c0/.*'))

        # cheese
        self.add_handler(CallbackQueryHandler(self.wrap(camera_capture), pattern=r'^c1/.*'))

    def markup(self, ctx: Optional[Context]) -> Optional[ReplyKeyboardMarkup]:
        buttons = [
            [ctx.lang('record'), ctx.lang('settings')],
            # [ctx.lang('files'), ctx.lang('remote_files')],
        ]
        if 'guard_server' in config['bot']:
            buttons.append([
                ctx.lang('guard_enable'), ctx.lang('guard_disable'), ctx.lang('guard_status')
            ])
        buttons.append([ctx.lang('sound_sensors')])
        if have_cameras():
            buttons.append([ctx.lang('cameras')])
        return ReplyKeyboardMarkup(buttons, one_time_keyboard=False)


if __name__ == '__main__':
    config.load('sound_bot')

    nodes = {}
    for nodename, nodecfg in config['nodes'].items():
        nodes[nodename] = parse_addr(nodecfg['addr'])

    record_client = SoundRecordClient(nodes,
                                      error_handler=record_onerror,
                                      finished_handler=record_onfinished,
                                      download_on_finish=True)

    bot = SoundBot()
    if 'api' in config:
        bot.enable_logging(BotType.SOUND)
    bot.run()

    record_client.stop()
