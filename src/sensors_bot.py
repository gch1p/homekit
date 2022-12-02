#!/usr/bin/env python3
import json
import socket
import logging
import re
import gc

from io import BytesIO
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

from home.config import config
from home.telegram import bot
from home.util import chunks, MySimpleSocketClient
from home.api import WebAPIClient
from home.api.types import (
    BotType,
    TemperatureSensorLocation
)

config.load('sensors_bot')
bot.initialize()

bot.lang.ru(
    start_message="Выберите датчик на клавиатуре",
    unknown_command="Неизвестная команда",
    temperature="Температура",
    humidity="Влажность",
    plot_3h="График за 3 часа",
    plot_6h="График за 6 часов",
    plot_12h="График за 12 часов",
    plot_24h="График за 24 часа",
    unexpected_callback_data="Ошибка: неверные данные",
    loading="Загрузка...",
    n_hrs="график за %d ч."
)
bot.lang.en(
    start_message="Select the sensor on the keyboard",
    unknown_command="Unknown command",
    temperature="Temperature",
    humidity="Relative humidity",
    plot_3h="Graph for 3 hours",
    plot_6h="Graph for 6 hours",
    plot_12h="Graph for 12 hours",
    plot_24h="Graph for 24 hours",
    unexpected_callback_data="Unexpected callback data",
    loading="Loading...",
    n_hrs="graph for %d hours"
)

plt.rcParams['font.size'] = 7
logger = logging.getLogger(__name__)
plot_hours = [3, 6, 12, 24]


_sensor_names = []
for k, v in config['sensors'].items():
    _sensor_names.append(k)
    bot.lang.set({k: v['label_ru']}, 'ru')
    bot.lang.set({k: v['label_en']}, 'en')


@bot.handler(messages=_sensor_names, argument='message_key')
def read_sensor(sensor: str, ctx: bot.Context) -> None:
    host = config['sensors'][sensor]['ip']
    port = config['sensors'][sensor]['port']

    try:
        client = MySimpleSocketClient(host, port)
        client.write('read')
        data = json.loads(client.read())
    except (socket.timeout, socket.error) as error:
        return ctx.reply_exc(error)

    temp = round(data['temp'], 2)
    humidity = round(data['humidity'], 2)

    text = ctx.lang('temperature') + f': <b>{temp} °C</b>\n'
    text += ctx.lang('humidity') + f': <b>{humidity}%</b>'

    buttons = list(map(
        lambda h: InlineKeyboardButton(ctx.lang(f'plot_{h}h'), callback_data=f'plot/{sensor}/{h}'),
        plot_hours
    ))
    ctx.reply(text, markup=InlineKeyboardMarkup(chunks(buttons, 2)))


@bot.callbackhandler(callback='*')
def callback_handler(ctx: bot.Context) -> None:
    query = ctx.callback_query

    sensors_variants = '|'.join(config['sensors'].keys())
    hour_variants = '|'.join(list(map(
        lambda n: str(n),
        plot_hours
    )))

    match = re.match(rf'plot/({sensors_variants})/({hour_variants})', query.data)
    if not match:
        query.answer(ctx.lang('unexpected_callback_data'))
        return

    query.answer(ctx.lang('loading'))

    # retrieve data
    sensor = TemperatureSensorLocation[match.group(1).upper()]
    hours = int(match.group(2))

    api = WebAPIClient(timeout=20)
    data = api.get_sensors_data(sensor, hours)

    title = ctx.lang(sensor.name.lower()) + ' (' + ctx.lang('n_hrs', hours) + ')'
    plot = draw_plot(data, title,
                     ctx.lang('temperature'),
                     ctx.lang('humidity'))
    bot.send_photo(ctx.user_id, photo=plot)

    gc.collect()


def draw_plot(data,
              title: str,
              label_temp: str,
              label_hum: str) -> BytesIO:
    tempval = []
    humval = []
    dates = []
    for date, temp, humidity in data:
        dates.append(date)
        tempval.append(temp)
        humval.append(humidity)

    fig, axs = plt.subplots(2, 1)
    df = mdates.DateFormatter('%H:%M')

    axs[0].set_title(label_temp)
    axs[0].plot(dates, tempval)
    axs[0].xaxis.set_major_formatter(df)
    axs[0].yaxis.set_major_formatter(mticker.FormatStrFormatter('%2.2f °C'))

    fig.suptitle(title, fontsize=10)

    axs[1].set_title(label_hum)
    axs[1].plot(dates, humval)
    axs[1].xaxis.set_major_formatter(df)
    axs[1].yaxis.set_major_formatter(mticker.FormatStrFormatter('%2.1f %%'))

    fig.autofmt_xdate()

    # should be called after all axes have been added
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=160)
    buf.seek(0)

    plt.clf()
    plt.close('all')

    return buf


@bot.defaultreplymarkup
def markup(ctx: Optional[bot.Context]) -> Optional[ReplyKeyboardMarkup]:
    buttons = []
    for k in config['sensors'].keys():
        buttons.append(ctx.lang(k))
    buttons = chunks(buttons, 2)
    return ReplyKeyboardMarkup(buttons, one_time_keyboard=False)


if __name__ == '__main__':
    if 'api' in config:
        bot.enable_logging(BotType.SENSORS)

    bot.run()
