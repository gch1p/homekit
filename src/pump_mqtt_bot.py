#!/usr/bin/env python3
import datetime

from enum import Enum
from typing import Optional
from telegram import ReplyKeyboardMarkup, User

from home.config import config
from home.telegram import bot
from home.telegram._botutil import user_any_name
from home.api.types import BotType
from home.mqtt import MQTTRelay, MQTTRelayState, MQTTRelayDevice
from home.mqtt.payload import MQTTPayload
from home.mqtt.payload.relay import InitialStatPayload, StatPayload


config.load('pump_mqtt_bot')

bot.initialize()
bot.lang.ru(
    start_message="Выберите команду на клавиатуре",
    start_message_no_access="Доступ запрещён. Вы можете отправить заявку на получение доступа.",
    unknown_command="Неизвестная команда",
    send_access_request="Отправить заявку",
    management="Админка",

    enable="Включить",
    enabled="Включен ✅",

    disable="Выключить",
    disabled="Выключен ❌",

    status="Статус",
    status_updated=' (обновлено %s)',

    done="Готово 👌",
    user_action_notification='Пользователь <a href="tg://user?id=%d">%s</a> <b>%s</b> насос.',
    user_action_on="включил",
    user_action_off="выключил",
    date_yday="вчера",
    date_yyday="позавчера",
    date_at="в"
)
bot.lang.en(
    start_message="Select command on the keyboard",
    start_message_no_access="You have no access.",
    unknown_command="Unknown command",
    send_access_request="Send request",
    management="Admin options",

    enable="Turn ON",
    enable_silently="Turn ON silently",
    enabled="Turned ON ✅",

    disable="Turn OFF",
    disable_silently="Turn OFF silently",
    disabled="Turned OFF ❌",

    status="Status",
    status_updated=' (updated %s)',

    done="Done 👌",
    user_action_notification='User <a href="tg://user?id=%d">%s</a> turned the pump <b>%s</b>.',
    user_action_on="ON",
    user_action_off="OFF",

    date_yday="yesterday",
    date_yyday="the day before yesterday",
    date_at="at"
)


mqtt_relay: Optional[MQTTRelay] = None
relay_state = MQTTRelayState()


class UserAction(Enum):
    ON = 'on'
    OFF = 'off'


def on_mqtt_message(home_id, message: MQTTPayload):
    if isinstance(message, InitialStatPayload) or isinstance(message, StatPayload):
        kwargs = dict(rssi=message.rssi, enabled=message.flags.state)
        if isinstance(message, InitialStatPayload):
            kwargs['fw_version'] = message.fw_version
        relay_state.update(**kwargs)


def notify(user: User, action: UserAction) -> None:
    def text_getter(lang: str):
        action_name = bot.lang.get(f'user_action_{action.value}', lang)
        user_name = user_any_name(user)
        return 'ℹ ' + bot.lang.get('user_action_notification', lang,
                                   user.id, user_name, action_name)

    bot.notify_all(text_getter, exclude=(user.id,))


@bot.handler(message='enable')
def enable_handler(ctx: bot.Context) -> None:
    mqtt_relay.set_power(config['mqtt']['home_id'], True)
    ctx.reply(ctx.lang('done'))
    notify(ctx.user, UserAction.ON)


@bot.handler(message='disable')
def disable_handler(ctx: bot.Context) -> None:
    mqtt_relay.set_power(config['mqtt']['home_id'], False)
    ctx.reply(ctx.lang('done'))
    notify(ctx.user, UserAction.OFF)


@bot.handler(message='status')
def status(ctx: bot.Context) -> None:
    label = ctx.lang('enabled') if relay_state.enabled else ctx.lang('disabled')
    if relay_state.ever_updated:
        date_label = ''
        today = datetime.date.today()
        if today != relay_state.update_time.date():
            yday = today - datetime.timedelta(days=1)
            yyday = today - datetime.timedelta(days=2)
            if yday == relay_state.update_time.date():
                date_label = ctx.lang('date_yday')
            elif yyday == relay_state.update_time.date():
                date_label = ctx.lang('date_yyday')
            else:
                date_label = relay_state.update_time.strftime('%d.%m.%Y')
            date_label += ' '
        date_label += ctx.lang('date_at') + ' '
        date_label += relay_state.update_time.strftime('%H:%M')
        label += ctx.lang('status_updated', date_label)
    ctx.reply(label)


def start(ctx: bot.Context) -> None:
    if ctx.user_id in config['bot']['users'] or ctx.user_id in config['bot']['admin_users']:
        ctx.reply(ctx.lang('start_message'))
    else:
        buttons = [
            [ctx.lang('send_access_request')]
        ]
        ctx.reply(ctx.lang('start_message_no_access'), markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=False))


@bot.exceptionhandler
def exception_handler(e: Exception, ctx: bot.Context) -> bool:
    return False


@bot.defaultreplymarkup
def markup(ctx: Optional[bot.Context]) -> Optional[ReplyKeyboardMarkup]:
    buttons = [[ctx.lang('enable'), ctx.lang('disable')], [ctx.lang('status')]]
    if ctx.user_id in config['bot']['admin_users']:
        buttons.append([ctx.lang('management')])
    return ReplyKeyboardMarkup(buttons, one_time_keyboard=False)


if __name__ == '__main__':
    mqtt_relay = MQTTRelay(devices=MQTTRelayDevice(id=config['mqtt']['home_id'],
                                                   secret=config['mqtt']['home_secret']))
    mqtt_relay.set_message_callback(on_mqtt_message)
    mqtt_relay.configure_tls()
    mqtt_relay.connect_and_loop(loop_forever=False)

    # bot.enable_logging(BotType.PUMP_MQTT)
    bot.run(start_handler=start)

    mqtt_relay.disconnect()
