#!/usr/bin/env python3
from enum import Enum
from typing import Optional
from telegram import ReplyKeyboardMarkup
from functools import partial

from home.config import config
from home.telegram import bot
from home.api.types import BotType
from home.mqtt import MQTTRelay, MQTTRelayState, MQTTRelayDevice
from home.mqtt.payload import MQTTPayload
from home.mqtt.payload.relay import InitialStatPayload, StatPayload


config.load('relay_mqtt_bot')

bot.initialize()
bot.lang.ru(
    start_message="Выберите команду на клавиатуре",
    unknown_command="Неизвестная команда",
    done="Готово 👌",
)
bot.lang.en(
    start_message="Select command on the keyboard",
    unknown_command="Unknown command",
    done="Done 👌",
)


type_emojis = {
    'lamp': '💡'
}
status_emoji = {
    'on': '✅',
    'off': '❌'
}
mqtt_relay: Optional[MQTTRelay] = None
relay_states: dict[str, MQTTRelayState] = {}


class UserAction(Enum):
    ON = 'on'
    OFF = 'off'


def on_mqtt_message(home_id, message: MQTTPayload):
    if isinstance(message, InitialStatPayload) or isinstance(message, StatPayload):
        kwargs = dict(rssi=message.rssi, enabled=message.flags.state)
        if isinstance(message, InitialStatPayload):
            kwargs['fw_version'] = message.fw_version
        if home_id not in relay_states[home_id]:
            relay_states[home_id] = MQTTRelayState()
        relay_states[home_id].update(**kwargs)


def enable_handler(home_id: str, ctx: bot.Context) -> None:
    mqtt_relay.set_power(home_id, True)
    ctx.reply(ctx.lang('done'))


def disable_handler(home_id: str, ctx: bot.Context) -> None:
    mqtt_relay.set_power(home_id, False)
    ctx.reply(ctx.lang('done'))


def start(ctx: bot.Context) -> None:
    ctx.reply(ctx.lang('start_message'))


@bot.exceptionhandler
def exception_handler(e: Exception, ctx: bot.Context) -> bool:
    return False


@bot.defaultreplymarkup
def markup(ctx: Optional[bot.Context]) -> Optional[ReplyKeyboardMarkup]:
    buttons = []
    for device_id, data in config['relays'].items():
        labels = data['labels']
        type_emoji = type_emojis[data['type']]
        row = [f'{type_emoji}{status_emoji[i.value]} {labels[ctx.user_lang]}'
               for i in UserAction]
        buttons.append(row)
    return ReplyKeyboardMarkup(buttons, one_time_keyboard=False)


if __name__ == '__main__':
    devices = []
    for device_id, data in config['relays'].items():
        devices.append(MQTTRelayDevice(id=device_id,
                                       secret=data['secret']))
        labels = data['labels']
        bot.lang.ru(**{device_id: labels['ru']})
        bot.lang.en(**{device_id: labels['en']})

        type_emoji = type_emojis[data['type']]

        for action in UserAction:
            messages = []
            for _lang, _label in labels.items():
                messages.append(f'{type_emoji}{status_emoji[action.value]} {labels[_lang]}')
            bot.handler(texts=messages)(partial(enable_handler if action == UserAction.ON else disable_handler, device_id))

    mqtt_relay = MQTTRelay(devices=devices)
    mqtt_relay.set_message_callback(on_mqtt_message)
    mqtt_relay.configure_tls()
    mqtt_relay.connect_and_loop(loop_forever=False)

    # bot.enable_logging(BotType.RELAY_MQTT)
    bot.run(start_handler=start)

    mqtt_relay.disconnect()
