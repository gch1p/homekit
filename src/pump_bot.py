#!/usr/bin/env python3
from typing import Optional
from home.config import config
from home.bot import Wrapper, Context, text_filter, user_any_name
from home.relay import RelayClient
from home.api.types import BotType
from telegram import ReplyKeyboardMarkup, User
from telegram.ext import MessageHandler
from enum import Enum
from functools import partial

bot: Optional[Wrapper] = None


class UserAction(Enum):
    ON = 'on'
    OFF = 'off'


def get_relay() -> RelayClient:
    relay = RelayClient(host=config['relay']['ip'], port=config['relay']['port'])
    relay.connect()
    return relay


def on(silent: bool, ctx: Context) -> None:
    get_relay().on()
    ctx.reply(ctx.lang('done'))
    if not silent:
        notify(ctx.user, UserAction.ON)


def off(silent: bool, ctx: Context) -> None:
    get_relay().off()
    ctx.reply(ctx.lang('done'))
    if not silent:
        notify(ctx.user, UserAction.OFF)


def status(ctx: Context) -> None:
    ctx.reply(
        ctx.lang('enabled') if get_relay().status() == 'on' else ctx.lang('disabled')
    )


def notify(user: User, action: UserAction) -> None:
    def text_getter(lang: str):
        action_name = bot.lang.get(f'user_action_{action.value}', lang)
        user_name = user_any_name(user)
        return 'ℹ ' + bot.lang.get('user_action_notification', lang,
                                   user.id, user_name, action_name)

    bot.notify_all(text_getter, exclude=(user.id,))


class PumpBot(Wrapper):
    def __init__(self):
        super().__init__()

        self.lang.ru(
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

        self.lang.en(
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

        self.add_handler(MessageHandler(text_filter(self.lang.all('enable')), self.wrap(partial(on, False))))
        self.add_handler(MessageHandler(text_filter(self.lang.all('disable')), self.wrap(partial(off, False))))

        self.add_handler(MessageHandler(text_filter(self.lang.all('enable_silently')), self.wrap(partial(on, True))))
        self.add_handler(MessageHandler(text_filter(self.lang.all('disable_silently')), self.wrap(partial(off, True))))

        self.add_handler(MessageHandler(text_filter(self.lang.all('status')), self.wrap(status)))

    def markup(self, ctx: Optional[Context]) -> Optional[ReplyKeyboardMarkup]:
        buttons = [
            [ctx.lang('enable'), ctx.lang('disable')],
        ]

        if ctx.user_id in config['bot']['silent_users']:
            buttons.append([ctx.lang('enable_silently'), ctx.lang('disable_silently')])

        buttons.append([ctx.lang('status')])

        return ReplyKeyboardMarkup(buttons, one_time_keyboard=False)


if __name__ == '__main__':
    config.load('pump_bot')

    bot = PumpBot()
    bot.enable_logging(BotType.PUMP)
    bot.run()
