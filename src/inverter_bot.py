#!/usr/bin/env python3
import logging
import re
import datetime
import json

from enum import Enum
from inverterd import Format, InverterError
from html import escape
from typing import Optional, Tuple, Union
from home.config import config
from home.bot import (
    Wrapper,
    Context,
    text_filter,
    command_usage,
    Store,
    IgnoreMarkup
)
from home.inverter import (
    wrapper_instance as inverter,
    beautify_table,

    InverterMonitor,
    ChargingEvent,
    ACPresentEvent,
    BatteryState,
    ACMode
)
from home.api.types import BotType
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    Filters
)

monitor: Optional[InverterMonitor] = None
bot: Optional[Wrapper] = None
db = None
LT = escape('<=')
flags_map = {
    'buzzer': 'BUZZ',
    'overload_bypass': 'OLBP',
    'escape_to_default_screen_after_1min_timeout': 'LCDE',
    'overload_restart': 'OLRS',
    'over_temp_restart': 'OTRS',
    'backlight_on': 'BLON',
    'alarm_on_on_primary_source_interrupt': 'ALRM',
    'fault_code_record': 'FTCR',
}
logger = logging.getLogger(__name__)

SETACMODE_STARTED, = range(1)
SETOSP_STARTED, = range(1)


class OutputSourcePriority(Enum):
    SolarUtilityBattery = 'SUB'
    SolarBatteryUtility = 'SBU'


def monitor_charging(event: ChargingEvent, **kwargs) -> None:
    args = []
    is_util = False
    if event == ChargingEvent.AC_CHARGING_STARTED:
        key = 'started'
    elif event == ChargingEvent.AC_CHARGING_FINISHED:
        key = 'finished'
    elif event == ChargingEvent.AC_DISCONNECTED:
        key = 'disconnected'
    elif event == ChargingEvent.AC_NOT_CHARGING:
        key = 'not_charging'
    elif event == ChargingEvent.AC_CURRENT_CHANGED:
        key = 'current_changed'
        args.append(kwargs['current'])
    elif event == ChargingEvent.AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR:
        key = 'na_solar'
    elif event == ChargingEvent.AC_MOSTLY_CHARGED:
        key = 'mostly_charged'
    elif event == ChargingEvent.UTIL_CHARGING_STARTED:
        key = 'started'
        is_util = True
    elif event == ChargingEvent.UTIL_CHARGING_STOPPED:
        key = 'stopped'
        is_util = True
    elif event == ChargingEvent.UTIL_CHARGING_STOPPED_SOLAR:
        key = 'stopped_solar'
        is_util = True
    else:
        logger.error('unknown charging event:', event)
        return

    key = f'chrg_evt_{key}'
    if is_util:
        key = f'util_{key}'
    bot.notify_all(
        lambda lang: bot.lang.get(key, lang, *args)
    )


def monitor_battery(state: BatteryState, v: float, load_watts: int) -> None:
    if state == BatteryState.NORMAL:
        emoji = '✅'
    elif state == BatteryState.LOW:
        emoji = '⚠️'
    elif state == BatteryState.CRITICAL:
        emoji = '‼️'
    else:
        logger.error('unknown battery state:', state)
        return

    bot.notify_all(
        lambda lang: bot.lang.get('battery_level_changed', lang,
                                  emoji, bot.lang.get(f'bat_state_{state.name.lower()}', lang), v, load_watts)
    )


def monitor_util(event: ACPresentEvent):
    if event == ACPresentEvent.CONNECTED:
        key = 'connected'
    else:
        key = 'disconnected'
    key = f'util_{key}'
    bot.notify_all(
        lambda lang: bot.lang.get(key, lang)
    )


def monitor_error(error: str) -> None:
    bot.notify_all(
        lambda lang: bot.lang.get('error_message', lang, error)
    )


def full_status(ctx: Context) -> None:
    status = inverter.exec('get-status', format=Format.TABLE)
    ctx.reply(beautify_table(status))


def full_rated(ctx: Context) -> None:
    rated = inverter.exec('get-rated', format=Format.TABLE)
    ctx.reply(beautify_table(rated))


def full_errors(ctx: Context) -> None:
    errors = inverter.exec('get-errors', format=Format.TABLE)
    ctx.reply(beautify_table(errors))


def flags(ctx: Context) -> None:
    flags = inverter.exec('get-flags')['data']
    text, markup = build_flags_keyboard(flags, ctx)
    ctx.reply(text, markup=markup)


def build_flags_keyboard(flags: dict, ctx: Context) -> Tuple[str, InlineKeyboardMarkup]:
    keyboard = []
    for k, v in flags.items():
        label = ('✅' if v else '❌') + ' ' + ctx.lang(f'flag_{k}')
        proto_flag = flags_map[k]
        keyboard.append([InlineKeyboardButton(label, callback_data=f'flag_{proto_flag}')])

    return ctx.lang('flags_press_button'), InlineKeyboardMarkup(keyboard)


def status(ctx: Context) -> None:
    gs = inverter.exec('get-status')['data']

    # render response
    power_direction = gs['battery_power_direction'].lower()
    power_direction = re.sub(r'ge$', 'ging', power_direction)

    charging_rate = ''
    chrg_at = ctx.lang('charging_at')

    if power_direction == 'charging':
        charging_rate = f'{chrg_at}%s %s' % (
            gs['battery_charge_current']['value'], gs['battery_charge_current']['unit'])
        pd_label = ctx.lang('pd_charging')
    elif power_direction == 'discharging':
        charging_rate = f'{chrg_at}%s %s' % (
            gs['battery_discharge_current']['value'], gs['battery_discharge_current']['unit'])
        pd_label = ctx.lang('pd_discharging')
    else:
        pd_label = ctx.lang('pd_nothing')

    html = f'<b>{ctx.lang("battery")}:</b> %s %s' % (gs['battery_voltage']['value'], gs['battery_voltage']['unit'])
    html += ' (%s%s)' % (pd_label, charging_rate)

    html += f'\n<b>{ctx.lang("load")}:</b> %s %s' % (gs['ac_output_active_power']['value'], gs['ac_output_active_power']['unit'])
    html += ' (%s%%)' % (gs['output_load_percent']['value'])

    if gs['pv1_input_power']['value'] > 0:
        html += f'\n<b>{ctx.lang("gen_input_power")}:</b> %s %s' % (gs['pv1_input_power']['value'], gs['pv1_input_power']['unit'])

    if gs['grid_voltage']['value'] > 0 or gs['grid_freq']['value'] > 0:
        ac_mode = getacmode()
        html += f'\n<b>{ctx.lang(ac_mode.value)}:</b> %s %s' % (gs['grid_voltage']['unit'], gs['grid_voltage']['value'])
        html += ', %s %s' % (gs['grid_freq']['value'], gs['grid_freq']['unit'])

    # send response
    ctx.reply(html)


def generation(ctx: Context) -> None:
    today = datetime.date.today()
    yday = today - datetime.timedelta(days=1)
    yday2 = today - datetime.timedelta(days=2)

    gs = inverter.exec('get-status')['data']

    gen_today = inverter.exec('get-day-generated', (today.year, today.month, today.day))['data']
    gen_yday = None
    gen_yday2 = None

    if yday.month == today.month:
        gen_yday = inverter.exec('get-day-generated', (yday.year, yday.month, yday.day))['data']

    if yday2.month == today.month:
        gen_yday2 = inverter.exec('get-day-generated', (yday2.year, yday2.month, yday2.day))['data']

    # render response
    html = f'<b>{ctx.lang("gen_input_power")}:</b> %s %s' % (gs['pv1_input_power']['value'], gs['pv1_input_power']['unit'])
    html += ' (%s %s)' % (gs['pv1_input_voltage']['value'], gs['pv1_input_voltage']['unit'])

    html += f'\n<b>{ctx.lang("gen_today")}:</b> %s Wh' % (gen_today['wh'])

    if gen_yday is not None:
        html += f'\n<b>{ctx.lang("gen_yday1")}:</b> %s Wh' % (gen_yday['wh'])

    if gen_yday2 is not None:
        html += f'\n<b>{ctx.lang("gen_yday2")}:</b> %s Wh' % (gen_yday2['wh'])

    # send response
    ctx.reply(html)


def setgencc(ctx: Context) -> None:
    allowed_values = inverter.exec('get-allowed-ac-charge-currents')['data']

    try:
        current = int(ctx.args[0])
        if current not in allowed_values:
            raise ValueError(f'invalid value {current}')

        response = inverter.exec('set-max-ac-charge-current', (0, current))
        ctx.reply('OK' if response['result'] == 'ok' else 'ERROR')

        # TODO notify monitor

    except (IndexError, ValueError):
        ctx.reply(command_usage('setgencc', {
            'A': ctx.lang('setgencc_a', ', '.join(map(lambda x: str(x), allowed_values)))
        }, language=ctx.user_lang))


def setgenct(ctx: Context) -> None:
    try:
        cv = float(ctx.args[0])
        dv = float(ctx.args[1])

        if 44 <= cv <= 51 and 48 <= dv <= 58:
            response = inverter.exec('set-charge-thresholds', (cv, dv))
            ctx.reply('OK' if response['result'] == 'ok' else 'ERROR')
        else:
            raise ValueError('invalid values')

    except (IndexError, ValueError):
        ctx.reply(command_usage('setgenct', {
            'CV': ctx.lang('setgenct_cv'),
            'DV': ctx.lang('setgenct_dv')
        }, language=ctx.user_lang))


def getacmode() -> ACMode:
    return ACMode(db.get_param('ac_mode', default=ACMode.GENERATOR))


def setacmode(mode: ACMode):
    monitor.set_ac_mode(mode)

    cv, dv = config['ac_mode'][str(mode.value)]['thresholds']
    a = config['ac_mode'][str(mode.value)]['initial_current']

    logger.debug(f'setacmode: mode={mode}, cv={cv}, dv={dv}, a={a}')

    inverter.exec('set-charge-thresholds', (cv, dv))
    inverter.exec('set-max-ac-charge-current', (0, a))


def setosp(sp: OutputSourcePriority):
    logger.debug(f'setosp: sp={sp}')
    inverter.exec('set-output-source-priority', (sp.value,))


# /setacmode
# ----------

def setacmode_start(ctx: Context) -> None:
    if monitor.active_current is not None:
        raise RuntimeError('generator charging program is active')

    buttons = []
    for mode in ACMode:
        buttons.append(ctx.lang(str(mode.value)))
    markup = ReplyKeyboardMarkup([buttons, [ctx.lang('cancel')]], one_time_keyboard=False)

    ctx.reply(ctx.lang('select_ac_mode'), markup=markup)
    return SETACMODE_STARTED


def setacmode_input(ctx: Context):
    if monitor.active_current is not None:
        raise RuntimeError('generator charging program is active')

    if ctx.text == ctx.lang('utilities'):
        newmode = ACMode.UTILITIES
    elif ctx.text == ctx.lang('generator'):
        newmode = ACMode.GENERATOR
    else:
        raise ValueError('invalid mode')

    # apply the mode
    setacmode(newmode)

    # save
    db.set_param('ac_mode', str(newmode.value))

    # reply to user
    ctx.reply(ctx.lang('saved'), markup=IgnoreMarkup())

    # notify other users
    bot.notify_all(
        lambda lang: bot.lang.get('ac_mode_changed_notification', lang,
                                  ctx.user.id, ctx.user.name,
                                  bot.lang.get(str(newmode.value), lang)),
        exclude=(ctx.user_id,)
    )

    bot.start(ctx)
    return ConversationHandler.END


def setacmode_invalid(ctx: Context):
    ctx.reply(ctx.lang('invalid_mode'), markup=IgnoreMarkup())
    return SETACMODE_STARTED


def setacmode_cancel(ctx: Context):
    bot.start(ctx)
    return ConversationHandler.END


# /setosp
# ------

def setosp_start(ctx: Context) -> None:
    buttons = []
    for sp in OutputSourcePriority:
        buttons.append(ctx.lang(f'setosp_{sp.value.lower()}'))
    markup = ReplyKeyboardMarkup([buttons, [ctx.lang('cancel')]], one_time_keyboard=False)

    ctx.reply(ctx.lang('select_ac_mode'), markup=markup)
    return SETOSP_STARTED


def setosp_input(ctx: Context):
    selected_sp = None
    for sp in OutputSourcePriority:
        if ctx.text == ctx.lang(f'setosp_{sp.value.lower()}'):
            selected_sp = sp
            break

    if selected_sp is None:
        raise ValueError('invalid sp')

    # apply the mode
    setosp(selected_sp)

    # reply to user
    ctx.reply(ctx.lang('saved'), markup=IgnoreMarkup())

    # notify other users
    bot.notify_all(
        lambda lang: bot.lang.get('osp_changed_notification', lang,
                                  ctx.user.id, ctx.user.name,
                                  bot.lang.get(f'setosp_{selected_sp.value.lower()}', lang)),
        exclude=(ctx.user_id,)
    )

    bot.start(ctx)
    return ConversationHandler.END


def setosp_invalid(ctx: Context):
    ctx.reply(ctx.lang('invalid_input'), markup=IgnoreMarkup())
    return SETOSP_STARTED


def setosp_cancel(ctx: Context):
    bot.start(ctx)
    return ConversationHandler.END


# other
# -----

def setbatuv(ctx: Context) -> None:
    try:
        v = float(ctx.args[0])

        if 40.0 <= v <= 48.0:
            response = inverter.exec('set-battery-cutoff-voltage', (v,))
            ctx.reply('OK' if response['result'] == 'ok' else 'ERROR')
        else:
            raise ValueError('invalid voltage')

    except (IndexError, ValueError):
        ctx.reply(command_usage('setbatuv', {
            'V': ctx.lang('setbatuv_v')
        }, language=ctx.user_lang))


def monstatus(ctx: Context) -> None:
    msg = ''
    st = monitor.dump_status()
    for k, v in st.items():
        msg += k + ': ' + str(v) + '\n'
    ctx.reply(msg)


def monsetcur(ctx: Context) -> None:
    ctx.reply('not implemented yet')


def calcw(ctx: Context) -> None:
    ctx.reply('not implemented yet')


def calcwadv(ctx: Context) -> None:
    ctx.reply('not implemented yet')


def button_callback(ctx: Context) -> None:
    query = ctx.callback_query

    if query.data.startswith('flag_'):
        flag = query.data[5:]
        found = False
        json_key = None
        for k, v in flags_map.items():
            if v == flag:
                found = True
                json_key = k
                break
        if not found:
            query.answer(ctx.lang('flags_invalid'))
            return

        flags = inverter.exec('get-flags')['data']
        cur_flag_value = flags[json_key]
        target_flag_value = '0' if cur_flag_value else '1'

        # set flag
        response = inverter.exec('set-flag', (flag, target_flag_value))

        # notify user
        query.answer(ctx.lang('done') if response['result'] == 'ok' else ctx.lang('flags_fail'))

        # edit message
        flags[json_key] = not cur_flag_value
        text, markup = build_flags_keyboard(flags, ctx)
        query.edit_message_text(text, reply_markup=markup)

    else:
        query.answer(ctx.lang('unexpected_callback_data'))


class InverterBot(Wrapper):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.lang.ru(
            status='Статус',
            generation='Генерация',
            battery="АКБ",
            load="Нагрузка",
            generator="Генератор",
            utilities="Столб",
            done="Готово",
            unexpected_callback_data="Ошибка: неверные данные",
            select_ac_mode="Выберите режим:",
            select_priortiy="Установите приоритет:",
            invalid_input="Неверное значение",
            invalid_mode="Invalid mode",

            flags_press_button='Нажмите кнопку для переключения настройки',
            flags_fail='Не удалось установить настройку',
            flags_invalid='Неизвестная настройка',

            # generation
            gen_today='Сегодня',
            gen_yday1='Вчера',
            gen_yday2='Позавчера',
            gen_input_power='Зарядная мощность',

            # status
            charging_at=', ',
            pd_charging='заряжается',
            pd_discharging='разряжается',
            pd_nothing='не используется',

            # flags
            flag_buzzer='Звуковой сигнал',
            flag_overload_bypass='Разрешить перегрузку',
            flag_escape_to_default_screen_after_1min_timeout='Возврат на главный экран через 1 минуту',
            flag_overload_restart='Перезапуск при перегрузке',
            flag_over_temp_restart='Перезапуск при перегреве',
            flag_backlight_on='Подсветка экрана',
            flag_alarm_on_on_primary_source_interrupt='Сигнал при разрыве основного источника питания',
            flag_fault_code_record='Запись кодов ошибок',

            # commands
            setbatuv_v=f'напряжение, 40.0 {LT} V {LT} 48.0',
            setgenct_cv=f'напряжение включения заряда, 44 {LT} CV {LT} 51',
            setgenct_dv=f'напряжение отключения заряда, 48 {LT} DV {LT} 58',
            setgencc_a='максимальный ток заряда, допустимые значения: %s',

            setosp_sub='Solar-Utility-Battery',
            setosp_sbu='Solar-Battery-Utility',

            # monitor
            chrg_evt_started='✅ Начали заряжать от генератора.',
            chrg_evt_finished='✅ Зарядили. Генератор пора выключать.',
            chrg_evt_disconnected='ℹ️ Генератор отключен.',
            chrg_evt_current_changed='ℹ️ Ток заряда от генератора установлен в %d A.',
            chrg_evt_not_charging='ℹ️ Генератор подключен, но не заряжает.',
            chrg_evt_na_solar='⛔️ Генератор подключен, но аккумуляторы не заряжаются из-за подключенных панелей.',
            chrg_evt_mostly_charged='✅ Аккумуляторы более-менее заряжены, генератор пора выключать.',
            battery_level_changed='Уровень заряда АКБ: <b>%s %s</b> (<b>%0.1f V</b> при нагрузке <b>%d W</b>)',
            error_message='<b>Ошибка:</b> %s.',

            util_chrg_evt_started='✅ Начали заряжать от столба.',
            util_chrg_evt_stopped='ℹ️ Перестали заряжать от столба.',
            util_chrg_evt_stopped_solar='ℹ️ Перестали заряжать от столба из-за подключения панелей.',

            util_connected='✅️ Столб подключён.',
            util_disconnected='‼️ Столб отключён.',

            # other notifications
            ac_mode_changed_notification='Пользователь <a href="tg://user?id=%d">%s</a> установил режим AC: <b>%s</b>.',
            osp_changed_notification='Пользователь <a href="tg://user?id=%d">%s</a> установил приоритет источника питания нагрузки: <b>%s</b>.',

            bat_state_normal='Нормальный',
            bat_state_low='Низкий',
            bat_state_critical='Критический',
        )

        self.lang.en(
            status='Status',
            generation='Generation',
            battery="Battery",
            load="Load",
            generator="Generator",
            utilities="Utilities",
            done="Done",
            unexpected_callback_data="Unexpected callback data",
            select_ac_mode="Select AC input mode:",
            select_priortiy="Select priority:",
            invalid_input="Invalid input",
            invalid_mode="Invalid mode",

            flags_press_button='Press a button to toggle a flag.',
            flags_fail='Failed to toggle flag',
            flags_invalid='Invalid flag',

            # generation
            gen_today='Today',
            gen_yday1='Yesterday',
            gen_yday2='The day before yesterday',
            gen_input_power='Input power',

            # status
            charging_at=' @ ',
            pd_charging='charging',
            pd_discharging='discharging',
            pd_nothing='not used',

            # flags
            flag_buzzer='Buzzer',
            flag_overload_bypass='Overload bypass',
            flag_escape_to_default_screen_after_1min_timeout='Reset to default LCD page after 1min timeout',
            flag_overload_restart='Restart on overload',
            flag_over_temp_restart='Restart on overtemp',
            flag_backlight_on='LCD backlight',
            flag_alarm_on_on_primary_source_interrupt='Beep on primary source interruption',
            flag_fault_code_record='Fault code recording',

            # commands
            setbatuv_v=f'floating point number, 40.0 {LT} V {LT} 48.0',
            setgenct_cv=f'charging voltage, 44 {LT} CV {LT} 51',
            setgenct_dv=f'discharging voltage, 48 {LT} DV {LT} 58',
            setgencc_a='max charging current, allowed values: %s',

            setosp_sub='Solar-Utility-Battery',
            setosp_sbu='Solar-Battery-Utility',

            # monitor
            chrg_evt_started='✅ Started charging from AC.',
            chrg_evt_finished='✅ Finished charging, it\'s time to stop the generator.',
            chrg_evt_disconnected='ℹ️ AC disconnected.',
            chrg_evt_current_changed='ℹ️ AC charging current set to %d A.',
            chrg_evt_not_charging='ℹ️ AC connected but not charging.',
            chrg_evt_na_solar='⛔️ AC connected, but battery won\'t be charged due to active solar power line.',
            chrg_evt_mostly_charged='✅ The battery is mostly charged now. The generator can be turned off.',
            battery_level_changed='Battery level: <b>%s</b> (<b>%0.1f V</b> under <b>%d W</b> load)',
            error_message='<b>Error:</b> %s.',

            util_chrg_evt_started='✅ Started charging from utilities.',
            util_chrg_evt_stopped='ℹ️ Stopped charging from utilities.',
            util_chrg_evt_stopped_solar='ℹ️ Stopped charging from utilities because solar panels were connected.',

            util_connected='✅️ Utilities connected.',
            util_disconnected='‼️ Utilities disconnected.',

            # other notifications
            ac_mode_changed_notification='User <a href="tg://user?id=%d">%s</a> set AC mode to <b>%s</b>.',
            osp_changed_notification='Пользователь <a href="tg://user?id=%d">%s</a> set output source priority: <b>%s</b>.',

            bat_state_normal='Normal',
            bat_state_low='Low',
            bat_state_critical='Critical',
        )

        self.add_handler(MessageHandler(text_filter(self.lang.all('status')), self.wrap(status)))
        self.add_handler(MessageHandler(text_filter(self.lang.all('generation')), self.wrap(generation)))

        self.add_handler(CommandHandler('setgencc', self.wrap(setgencc)))
        self.add_handler(CommandHandler('setgenct', self.wrap(setgenct)))
        self.add_handler(CommandHandler('setbatuv', self.wrap(setbatuv)))
        self.add_handler(CommandHandler('monstatus', self.wrap(monstatus)))
        self.add_handler(CommandHandler('monsetcur', self.wrap(monsetcur)))
        self.add_handler(CommandHandler('calcw', self.wrap(calcw)))
        self.add_handler(CommandHandler('calcwadv', self.wrap(calcwadv)))

        self.add_handler(CommandHandler('flags', self.wrap(flags)))
        self.add_handler(CommandHandler('status', self.wrap(full_status)))
        self.add_handler(CommandHandler('config', self.wrap(full_rated)))
        self.add_handler(CommandHandler('errors', self.wrap(full_errors)))

        self.add_handler(CallbackQueryHandler(self.wrap(button_callback)))

    def run(self):
        cancel_filter = Filters.text(self.lang.all('cancel'))

        self.add_handler(ConversationHandler(
            entry_points=[CommandHandler('setacmode', self.wrap(setacmode_start), self.user_filter)],
            states={
                SETACMODE_STARTED: [
                    *[MessageHandler(text_filter(self.lang.all(mode.value)), self.wrap(setacmode_input)) for mode in ACMode],
                    MessageHandler(self.user_filter & ~cancel_filter, self.wrap(setacmode_invalid))
                ]
            },
            fallbacks=[MessageHandler(self.user_filter & cancel_filter, self.wrap(setacmode_cancel))]
        ))

        self.add_handler(ConversationHandler(
            entry_points=[CommandHandler('setosp', self.wrap(setosp_start), self.user_filter)],
            states={
                SETOSP_STARTED: [
                    *[MessageHandler(text_filter(self.lang.all(f'setosp_{sp.value.lower()}')), self.wrap(setosp_input)) for sp in OutputSourcePriority],
                    MessageHandler(self.user_filter & ~cancel_filter, self.wrap(setosp_invalid))
                ]
            },
            fallbacks=[MessageHandler(self.user_filter & cancel_filter, self.wrap(setosp_cancel))]
        ))

        super().run()

    def markup(self, ctx: Optional[Context]) -> Optional[ReplyKeyboardMarkup]:
        button = [
            [ctx.lang('status'), ctx.lang('generation')]
        ]
        return ReplyKeyboardMarkup(button, one_time_keyboard=False)

    def exception_handler(self, e: Exception, ctx: Context) -> Optional[bool]:
        if isinstance(e, InverterError):
            try:
                err = json.loads(str(e))['message']
            except json.decoder.JSONDecodeError:
                err = str(e)
            err = re.sub(r'((?:.*)?error:) (.*)', r'<b>\1</b> \2', err)
            ctx.reply(err)
            return True


class InverterStore(Store):
    SCHEMA = 2

    def schema_init(self, version: int) -> None:
        super().schema_init(version)

        if version < 2:
            cursor = self.cursor()
            cursor.execute("""CREATE TABLE IF NOT EXISTS params (
                id TEXT NOT NULL PRIMARY KEY,
                value TEXT NOT NULL
            )""")
            cursor.execute("CREATE INDEX param_id_idx ON params (id)")
            self.commit()

    def get_param(self, key: str, default=None):
        cursor = self.cursor()
        cursor.execute('SELECT value FROM params WHERE id=?', (key,))
        row = cursor.fetchone()

        return default if row is None else row[0]

    def set_param(self, key: str, value: Union[str, int, float]):
        cursor = self.cursor()
        cursor.execute('REPLACE INTO params (id, value) VALUES (?, ?)', (key, str(value)))
        self.commit()


if __name__ == '__main__':
    config.load('inverter_bot')

    inverter.init(host=config['inverter']['ip'], port=config['inverter']['port'])

    db = InverterStore()

    monitor = InverterMonitor()
    monitor.set_charging_event_handler(monitor_charging)
    monitor.set_battery_event_handler(monitor_battery)
    monitor.set_util_event_handler(monitor_util)
    monitor.set_error_handler(monitor_error)

    setacmode(getacmode())

    bot = InverterBot(store=db)
    bot.enable_logging(BotType.INVERTER)

    monitor.start()

    bot.run()

    monitor.stop()
