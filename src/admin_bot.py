#!/usr/bin/env python3
from typing import Optional
from telegram import ReplyKeyboardMarkup
from telegram.ext import MessageHandler
from home.config import config
from home.bot import Wrapper, Context, text_filter


def get_latest_logs(ctx: Context):
    u = ctx.user
    ctx.reply(ctx.lang('blbla'))


class AdminBot(Wrapper):
    def __init__(self):
        super().__init__()

        self.lang.ru(get_latest_logs="Смотреть последние логи")
        self.lang.en(get_latest_logs="Get latest logs")

        self.add_handler(MessageHandler(text_filter(self.lang('get_latest_logs')), self.wrap(get_latest_logs)))

    def markup(self, ctx: Optional[Context]) -> Optional[ReplyKeyboardMarkup]:
        buttons = [
            [self.lang('get_latest_logs')]
        ]
        return ReplyKeyboardMarkup(buttons, one_time_keyboard=False)


if __name__ == '__main__':
    config.load('admin_bot')

    bot = AdminBot()
    # bot.enable_logging(BotType.ADMIN)
    bot.run()
