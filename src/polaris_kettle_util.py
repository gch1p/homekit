#!/usr/bin/env python3
import logging
# import os
import sys
import paho.mqtt.client as mqtt

# from datetime import datetime
# from html import escape
from argparse import ArgumentParser
# from home.bot import Wrapper, Context
# from home.api.types import BotType
# from home.util import parse_addr
from home.mqtt import MQTTBase
from home.config import config
from polaris import Kettle

# from telegram.error import TelegramError
# from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
# from telegram.ext import (
#     CallbackQueryHandler,
#     MessageHandler,
#     CommandHandler
# )


logger = logging.getLogger(__name__)

# bot: Optional[Wrapper] = None
# RenderedContent = tuple[str, Optional[InlineKeyboardMarkup]]


class MQTTServer(MQTTBase):
    def __init__(self):
        super().__init__(clean_session=False)

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)
        logger.info("subscribing to #")
        client.subscribe('#', qos=1)

    def on_message(self, client: mqtt.Client, userdata, msg):
        try:
            print(msg.topic, msg.payload)

        except Exception as e:
            logger.exception(str(e))


# class Renderer:
#     @classmethod
#     def index(cls, ctx: Context) -> RenderedContent:
#         html = f'<b>{ctx.lang("settings")}</b>\n\n'
#         html += ctx.lang('select_place')
#         return html, None


# status handler
# --------------

# def status(ctx: Context):
#     text, markup = Renderer.index(ctx)
#     return ctx.reply(text, markup=markup)


# class SoundBot(Wrapper):
#     def __init__(self):
#         super().__init__()
#
#         self.lang.ru(
#             start_message="Выберите команду на клавиатуре",
#             unknown_command="Неизвестная команда",
#             unexpected_callback_data="Ошибка: неверные данные",
#             status="Статус",
#         )
#
#         self.lang.en(
#             start_message="Select command on the keyboard",
#             unknown_command="Unknown command",
#             unexpected_callback_data="Unexpected callback data",
#             status="Status",
#         )
#
#         self.add_handler(CommandHandler('status', self.wrap(status)))
#
#     def markup(self, ctx: Optional[Context]) -> Optional[ReplyKeyboardMarkup]:
#         buttons = [
#             [ctx.lang('status')]
#         ]
#         return ReplyKeyboardMarkup(buttons, one_time_keyboard=False)


def main():
    tempmin = 30
    tempmax = 100
    tempstep = 5

    parser = ArgumentParser()
    parser.add_argument('-m', dest='mode', required=True, type=str, choices=('mqtt', 'control'))
    parser.add_argument('--on', action='store_true')
    parser.add_argument('--off', action='store_true')
    parser.add_argument('-t', '--temperature', dest='temp', type=int, choices=range(tempmin, tempmax+tempstep, tempstep))

    arg = config.load('polaris_kettle_bot', use_cli=True, parser=parser)

    if arg.mode == 'mqtt':
        server = MQTTServer()
        try:
            server.connect_and_loop(loop_forever=True)
        except KeyboardInterrupt:
            pass

    elif arg.mode == 'control':
        if arg.on and arg.off:
            raise RuntimeError('--on and --off are mutually exclusive')

        k = Kettle(mac='40f52018dec1', token='3a5865f015950cae82cd120e76a80d28')
        k.find()
        print('device found')

        k.genkeys()
        k.genshared()
        k.handshake()

        if arg.on:
            k.setpower(True)
        elif arg.off:
            k.setpower(False)
        elif arg.temp:
            k.settemperature(arg.temp)

        # k.sendfirst()

        # print('shared key:', key_to_hex(k.sharedkey))
        # print('shared hash:', key_to_hex(k.sharedsha256))

        # print(len(k.sharedsha256))

    return 0


if __name__ == '__main__':
    sys.exit(main())

    # bot = SoundBot()
    # if 'api' in config:
    #     bot.enable_logging(BotType.POLARIS_KETTLE)
    # bot.run()
