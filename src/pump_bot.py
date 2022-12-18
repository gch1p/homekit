#!/usr/bin/env python3
from enum import Enum
from typing import Optional
from telegram import ReplyKeyboardMarkup, User

from home.config import config
from home.telegram import bot
from home.telegram._botutil import user_any_name
from home.relay.sunxi_h3_client import RelayClient
from home.api.types import BotType

config.load('pump_bot')

bot.initialize()
bot.lang.ru(
    start_message="Выберите команду на клавиатуре",
    unknown_command="Неизвестная команда",

    enable="Включить",
    enable_silently="Включить тихо",
    enabled="Включен ✅",

    disable="Выключить",
    disable_silently="Выключить тихо",
    disabled="Выключен ❌",

    status="Статус",
    done="Готово 👌",
    user_action_notification='Пользователь <a href="tg://user?id=%d">%s</a> <b>%s</b> насос.',
    user_action_on="включил",
    user_action_off="выключил",
)
bot.lang.en(
    start_message="Select command on the keyboard",
    unknown_command="Unknown command",

    enable="Turn ON",
    enable_silently="Turn ON silently",
    enabled="Turned ON ✅",

    disable="Turn OFF",
    disable_silently="Turn OFF silently",
    disabled="Turned OFF ❌",

    status="Status",
    done="Done 👌",
    user_action_notification='User <a href="tg://user?id=%d">%s</a> turned the pump <b>%s</b>.',
    user_action_on="ON",
    user_action_off="OFF",
)


class UserAction(Enum):
    ON = 'on'
    OFF = 'off'


def get_relay() -> RelayClient:
    relay = RelayClient(host=config['relay']['ip'], port=config['relay']['port'])
    relay.connect()
    return relay


def on(ctx: bot.Context, silent=False) -> None:
    get_relay().on()
    ctx.reply(ctx.lang('done'))
    if not silent:
        notify(ctx.user, UserAction.ON)


def off(ctx: bot.Context, silent=False) -> None:
    get_relay().off()
    ctx.reply(ctx.lang('done'))
    if not silent:
        notify(ctx.user, UserAction.OFF)


def notify(user: User, action: UserAction) -> None:
    def text_getter(lang: str):
        action_name = bot.lang.get(f'user_action_{action.value}', lang)
        user_name = user_any_name(user)
        return 'ℹ ' + bot.lang.get('user_action_notification', lang,
                                   user.id, user_name, action_name)

    bot.notify_all(text_getter, exclude=(user.id,))


@bot.handler(message='enable')
def enable_handler(ctx: bot.Context) -> None:
    on(ctx)


@bot.handler(message='enable_silently')
def enable_s_handler(ctx: bot.Context) -> None:
    on(ctx, True)


@bot.handler(message='disable')
def disable_handler(ctx: bot.Context) -> None:
    off(ctx)


@bot.handler(message='disable_silently')
def disable_s_handler(ctx: bot.Context) -> None:
    off(ctx, True)


@bot.handler(message='status')
def status(ctx: bot.Context) -> None:
    ctx.reply(
        ctx.lang('enabled') if get_relay().status() == 'on' else ctx.lang('disabled')
    )


@bot.defaultreplymarkup
def markup(ctx: Optional[bot.Context]) -> Optional[ReplyKeyboardMarkup]:
    buttons = [
        [ctx.lang('enable'), ctx.lang('disable')],
    ]

    if ctx.user_id in config['bot']['silent_users']:
        buttons.append([ctx.lang('enable_silently'), ctx.lang('disable_silently')])

    buttons.append([ctx.lang('status')])

    return ReplyKeyboardMarkup(buttons, one_time_keyboard=False)


if __name__ == '__main__':
    bot.enable_logging(BotType.PUMP)
    bot.run()
