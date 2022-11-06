#!/usr/bin/env python3
import logging
import re
import datetime
import json
import itertools

from inverterd import Format, InverterError
from html import escape
from typing import Optional, Tuple, Union

from home.util import chunks
from home.config import config
from home.telegram import bot
from home.inverter import (
    wrapper_instance as inverter,
    beautify_table,
    InverterMonitor,
)
from home.inverter.types import (
    ChargingEvent,
    ACPresentEvent,
    BatteryState,
    ACMode,
    OutputSourcePriority
)
from home.database.inverter_time_formats import *
from home.api.types import BotType
from home.api import WebAPIClient
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

monitor: Optional[InverterMonitor] = None
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
config.load('inverter_bot')

bot.initialize()
bot.lang.ru(
    status='Статус',
    generation='Генерация',
    priority='Приоритет',
    battery="АКБ",
    load="Нагрузка",
    generator="Генератор",
    utilities="Столб",
    consumption="Статистика потребления",
    settings="Настройки",
    done="Готово",
    unexpected_callback_data="Ошибка: неверные данные",
    invalid_input="Неверное значение",
    invalid_mode="Invalid mode",

    flags_press_button='Нажмите кнопку для переключения настройки',
    flags_fail='Не удалось установить настройку',
    flags_invalid='Неизвестная настройка',

    # generation
    gen_input_power='Зарядная мощность',

    # settings
    settings_msg="Что вы хотите настроить?",
    settings_osp='Приоритет питания нагрузки',
    settings_ac_preset="Применить шаблон режима AC",
    settings_bat_thresholds="Пороги заряда АКБ от AC",
    settings_bat_cut_off_voltage="Порог отключения АКБ",
    settings_ac_max_charging_current="Максимальный ток заряда от AC",

    settings_osp_msg="Установите приоритет:",
    settings_osp_sub='Solar-Utility-Battery',
    settings_osp_sbu='Solar-Battery-Utility',

    settings_select_bottom_threshold="Выберите нижний порог:",
    settings_select_upper_threshold="Выберите верхний порог:",
    settings_select_max_current='Выберите максимальный ток:',
    settings_enter_cutoff_voltage=f'Введите напряжение V, где 40.0 {LT} V {LT} 48.0',

    # time and date
    today='Сегодня',
    yday1='Вчера',
    yday2='Позавчера',
    for_7days='За 7 дней',
    for_30days='За 30 дней',
    # to_select_interval='Выбрать интервал',

    # consumption
    consumption_msg="Выберите тип:",
    consumption_total="Домашние приборы",
    consumption_grid="Со столба",
    consumption_select_interval='Выберите период:',
    consumption_request_sent="⏳ Запрос отправлен...",

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
    osp_auto_changed_notification='ℹ️ Бот установил приоритет источника питания нагрузки: <b>%s</b>. Причины: напряжение АКБ %.1f V, мощность заряда с панелей %d W.',

    bat_state_normal='Нормальный',
    bat_state_low='Низкий',
    bat_state_critical='Критический',
)

bot.lang.en(
    status='Status',
    generation='Generation',
    priority='Priority',
    battery="Battery",
    load="Load",
    generator="Generator",
    utilities="Utilities",
    consumption="Consumption statistics",
    settings="Settings",
    done="Done",
    unexpected_callback_data="Unexpected callback data",
    select_priortiy="Select priority:",
    invalid_input="Invalid input",
    invalid_mode="Invalid mode",

    flags_press_button='Press a button to toggle a flag.',
    flags_fail='Failed to toggle flag',
    flags_invalid='Invalid flag',

    # settings
    settings_msg='What do you want to configure?',
    settings_osp='Output source priority',
    settings_ac_preset="AC preset",
    settings_bat_thresholds="Battery charging thresholds",
    settings_bat_cut_off_voltage="Battery cut-off voltage",
    settings_ac_max_charging_current="Max AC charging current",

    settings_osp_msg="Select priority:",
    settings_osp_sub='Solar-Utility-Battery',
    settings_osp_sbu='Solar-Battery-Utility',

    settings_select_bottom_threshold="Select bottom (lower) threshold:",
    settings_select_upper_threshold="Select top (upper) threshold:",
    settings_select_max_current='Select max current:',
    settings_enter_cutoff_voltage=f'Enter voltage V (40.0 {LT} V {LT} 48.0):',

    # generation
    gen_input_power='Input power',

    # time and date
    today='Today',
    yday1='Yesterday',
    yday2='The day before yesterday',
    for_7days='7 days',
    for_30days='30 days',
    # to_select_interval='Select interval',

    # consumption
    consumption_msg="Select type:",
    consumption_total="Home appliances",
    consumption_grid="Consumed from grid",
    consumption_select_interval='Select period:',
    consumption_request_sent="⏳ Request sent...",

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
    osp_changed_notification='User <a href="tg://user?id=%d">%s</a> set output source priority: <b>%s</b>.',
    osp_auto_changed_notification='Bot changed output source priority to <b>%s</b>. Reasons: battery voltage is %.1f V, solar input is %d W.',

    bat_state_normal='Normal',
    bat_state_low='Low',
    bat_state_critical='Critical',
)


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


def osp_change_cb(new_osp: OutputSourcePriority,
                  solar_input: int,
                  v: float):

    setosp(new_osp)

    bot.notify_all(
        lambda lang: bot.lang.get('osp_auto_changed_notification', lang,
                                  bot.lang.get(f'settings_osp_{new_osp.value.lower()}', lang), v, solar_input),
    )


@bot.handler(command='status')
def full_status(ctx: bot.Context) -> None:
    status = inverter.exec('get-status', format=Format.TABLE)
    ctx.reply(beautify_table(status))


@bot.handler(command='config')
def full_rated(ctx: bot.Context) -> None:
    rated = inverter.exec('get-rated', format=Format.TABLE)
    ctx.reply(beautify_table(rated))


@bot.handler(command='errors')
def full_errors(ctx: bot.Context) -> None:
    errors = inverter.exec('get-errors', format=Format.TABLE)
    ctx.reply(beautify_table(errors))


@bot.handler(command='flags')
def flags_handler(ctx: bot.Context) -> None:
    flags = inverter.exec('get-flags')['data']
    text, markup = build_flags_keyboard(flags, ctx)
    ctx.reply(text, markup=markup)


def build_flags_keyboard(flags: dict, ctx: bot.Context) -> Tuple[str, InlineKeyboardMarkup]:
    keyboard = []
    for k, v in flags.items():
        label = ('✅' if v else '❌') + ' ' + ctx.lang(f'flag_{k}')
        proto_flag = flags_map[k]
        keyboard.append([InlineKeyboardButton(label, callback_data=f'flag_{proto_flag}')])

    return ctx.lang('flags_press_button'), InlineKeyboardMarkup(keyboard)


def getacmode() -> ACMode:
    return ACMode(bot.db.get_param('ac_mode', default=ACMode.GENERATOR))


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
    monitor.notify_osp(sp)


class SettingsConversation(bot.conversation):
    START, OSP, AC_PRESET, BAT_THRESHOLDS_1, BAT_THRESHOLDS_2, BAT_CUT_OFF_VOLTAGE, AC_MAX_CHARGING_CURRENT = range(7)
    STATE_SEQS = [
        [START, OSP],
        [START, AC_PRESET],
        [START, BAT_THRESHOLDS_1, BAT_THRESHOLDS_2],
        [START, BAT_CUT_OFF_VOLTAGE],
        [START, AC_MAX_CHARGING_CURRENT]
    ]

    START_BUTTONS = bot.lang.pfx('settings_', ['ac_preset',
                                               'ac_max_charging_current',
                                               'bat_thresholds',
                                               'bat_cut_off_voltage',
                                               'osp'])
    OSP_BUTTONS = bot.lang.pfx('settings_osp_', [sp.value.lower() for sp in OutputSourcePriority])
    AC_PRESET_BUTTONS = [mode.value for mode in ACMode]

    RECHARGE_VOLTAGES = [44, 45, 46, 47, 48, 49, 50, 51]
    REDISCHARGE_VOLTAGES = [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58]

    @bot.conventer(START, message='settings')
    def start_enter(self, ctx: bot.Context):
        buttons = list(chunks(list(self.START_BUTTONS), 2))
        buttons.reverse()
        return self.reply(ctx, self.START, ctx.lang('settings_msg'), buttons,
                          with_cancel=True)

    @bot.convinput(START, messages={
        'settings_osp': OSP,
        'settings_ac_preset': AC_PRESET,
        'settings_bat_thresholds': BAT_THRESHOLDS_1,
        'settings_bat_cut_off_voltage': BAT_CUT_OFF_VOLTAGE,
        'settings_ac_max_charging_current': AC_MAX_CHARGING_CURRENT
    })
    def start_input(self, ctx: bot.Context):
        pass

    @bot.conventer(OSP)
    def osp_enter(self, ctx: bot.Context):
        return self.reply(ctx, self.OSP, ctx.lang('settings_osp_msg'), self.OSP_BUTTONS,
                          with_back=True)

    @bot.convinput(OSP, messages=OSP_BUTTONS)
    def osp_input(self, ctx: bot.Context):
        selected_sp = None
        for sp in OutputSourcePriority:
            if ctx.text == ctx.lang(f'settings_osp_{sp.value.lower()}'):
                selected_sp = sp
                break

        if selected_sp is None:
            raise ValueError('invalid sp')

        # apply the mode
        setosp(selected_sp)

        # reply to user
        ctx.reply(ctx.lang('saved'), markup=bot.IgnoreMarkup())

        # notify other users
        bot.notify_all(
            lambda lang: bot.lang.get('osp_changed_notification', lang,
                                      ctx.user.id, ctx.user.name,
                                      bot.lang.get(f'settings_osp_{selected_sp.value.lower()}', lang)),
            exclude=(ctx.user_id,)
        )
        return self.END

    @bot.conventer(AC_PRESET)
    def acpreset_enter(self, ctx: bot.Context):
        return self.reply(ctx, self.AC_PRESET, ctx.lang('settings_ac_preset_msg'), self.AC_PRESET_BUTTONS,
                          with_back=True)

    @bot.convinput(AC_PRESET, messages=AC_PRESET_BUTTONS)
    def acpreset_input(self, ctx: bot.Context):
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
        bot.db.set_param('ac_mode', str(newmode.value))

        # reply to user
        ctx.reply(ctx.lang('saved'), markup=bot.IgnoreMarkup())

        # notify other users
        bot.notify_all(
            lambda lang: bot.lang.get('ac_mode_changed_notification', lang,
                                      ctx.user.id, ctx.user.name,
                                      bot.lang.get(str(newmode.value), lang)),
            exclude=(ctx.user_id,)
        )
        return self.END

    @bot.conventer(BAT_THRESHOLDS_1)
    def thresholds1_enter(self, ctx: bot.Context):
        buttons = list(map(lambda v: f'{v} V', self.RECHARGE_VOLTAGES))
        buttons = chunks(buttons, 4)
        return self.reply(ctx, self.BAT_THRESHOLDS_1, ctx.lang('settings_select_bottom_threshold'), buttons,
                          with_back=True, buttons_lang_completed=True)

    @bot.convinput(BAT_THRESHOLDS_1,
                   messages=list(map(lambda n: f'{n} V', RECHARGE_VOLTAGES)),
                   messages_lang_completed=True)
    def thresholds1_input(self, ctx: bot.Context):
        v = self._parse_voltage(ctx.text)
        ctx.user_data['bat_thrsh_v1'] = v
        return self.invoke(self.BAT_THRESHOLDS_2, ctx)

    @bot.conventer(BAT_THRESHOLDS_2)
    def thresholds2_enter(self, ctx: bot.Context):
        buttons = list(map(lambda v: f'{v} V', self.REDISCHARGE_VOLTAGES))
        buttons = chunks(buttons, 4)
        return self.reply(ctx, self.BAT_THRESHOLDS_2, ctx.lang('settings_select_upper_threshold'), buttons,
                          with_back=True, buttons_lang_completed=True)

    @bot.convinput(BAT_THRESHOLDS_2,
                   messages=list(map(lambda n: f'{n} V', REDISCHARGE_VOLTAGES)),
                   messages_lang_completed=True)
    def thresholds2_input(self, ctx: bot.Context):
        v2 = v = self._parse_voltage(ctx.text)
        v1 = ctx.user_data['bat_thrsh_v1']
        del ctx.user_data['bat_thrsh_v1']

        response = inverter.exec('set-charge-thresholds', (v1, v2))
        ctx.reply(ctx.lang('saved') if response['result'] == 'ok' else 'ERROR',
                  markup=bot.IgnoreMarkup())
        return self.END

    @bot.conventer(AC_MAX_CHARGING_CURRENT)
    def ac_max_enter(self, ctx: bot.Context):
        buttons = self._get_allowed_ac_charge_amps()
        buttons = map(lambda n: f'{n} A', buttons)
        buttons = [list(buttons)]
        return self.reply(ctx, self.AC_MAX_CHARGING_CURRENT, ctx.lang('settings_select_max_current'), buttons,
                          with_back=True, buttons_lang_completed=True)

    @bot.convinput(AC_MAX_CHARGING_CURRENT, regex=r'^\d+ A$')
    def ac_max_input(self, ctx: bot.Context):
        a = self._parse_amps(ctx.text)
        allowed = self._get_allowed_ac_charge_amps()
        if a not in allowed:
            raise ValueError('input is not allowed')

        response = inverter.exec('set-max-ac-charge-current', (0, a))
        ctx.reply(ctx.lang('saved') if response['result'] == 'ok' else 'ERROR',
                  markup=bot.IgnoreMarkup())
        return self.END

    @bot.conventer(BAT_CUT_OFF_VOLTAGE)
    def cutoff_enter(self, ctx: bot.Context):
        return self.reply(ctx, self.BAT_CUT_OFF_VOLTAGE, ctx.lang('settings_enter_cutoff_voltage'), None,
                          with_back=True)

    @bot.convinput(BAT_CUT_OFF_VOLTAGE, regex=r'^(\d{2}(\.\d{1})?)$')
    def cutoff_input(self, ctx: bot.Context):
        v = float(ctx.text)
        if 40.0 <= v <= 48.0:
            response = inverter.exec('set-battery-cutoff-voltage', (v,))
            ctx.reply(ctx.lang('saved') if response['result'] == 'ok' else 'ERROR',
                      markup=bot.IgnoreMarkup())
        else:
            raise ValueError('invalid voltage')

        return self.END

    def _get_allowed_ac_charge_amps(self) -> list[int]:
        l = inverter.exec('get-allowed-ac-charge-currents')['data']
        l = filter(lambda n: n <= 40, l)
        return list(l)

    def _parse_voltage(self, s: str) -> int:
        return int(re.match(r'^(\d{2}) V$', s).group(1))

    def _parse_amps(self, s: str) -> int:
        return int(re.match(r'^(\d{1,2}) A$', s).group(1))


class ConsumptionConversation(bot.conversation):
    START, TOTAL, GRID = range(3)
    STATE_SEQS = [
        [START, TOTAL],
        [START, GRID]
    ]

    START_BUTTONS = bot.lang.pfx('consumption_', ['total', 'grid'])
    INTERVAL_BUTTONS = [
        ['today'],
        ['yday1'],
        ['for_7days', 'for_30days'],
        # ['to_select_interval']
    ]
    INTERVAL_BUTTONS_FLAT = list(itertools.chain.from_iterable(INTERVAL_BUTTONS))

    @bot.conventer(START, message='consumption')
    def start_enter(self, ctx: bot.Context):
        return self.reply(ctx, self.START, ctx.lang('consumption_msg'), [self.START_BUTTONS],
                          with_cancel=True)

    @bot.convinput(START, messages={
        'consumption_total': TOTAL,
        'consumption_grid': GRID
    })
    def start_input(self, ctx: bot.Context):
        pass

    @bot.conventer(TOTAL)
    def total_enter(self, ctx: bot.Context):
        return self._render_interval_btns(ctx, self.TOTAL)

    @bot.conventer(GRID)
    def grid_enter(self, ctx: bot.Context):
        return self._render_interval_btns(ctx, self.GRID)

    def _render_interval_btns(self, ctx: bot.Context, state):
        return self.reply(ctx, state, ctx.lang('consumption_select_interval'), self.INTERVAL_BUTTONS,
                          with_back=True)

    @bot.convinput(TOTAL, messages=INTERVAL_BUTTONS_FLAT)
    def total_input(self, ctx: bot.Context):
        return self._render_interval_results(ctx, self.TOTAL)

    @bot.convinput(GRID, messages=INTERVAL_BUTTONS_FLAT)
    def grid_input(self, ctx: bot.Context):
        return self._render_interval_results(ctx, self.GRID)

    def _render_interval_results(self, ctx: bot.Context, state):
        # if ctx.text == ctx.lang('to_select_interval'):
        #     TODO
        # pass
        #
        # else:

        now = datetime.datetime.now()
        s_to = now.strftime(FormatDate)

        if ctx.text == ctx.lang('today'):
            s_from = now.strftime(FormatDate)
            s_to = 'now'
        elif ctx.text == ctx.lang('yday1'):
            s_from = (now - datetime.timedelta(days=1)).strftime(FormatDate)
        elif ctx.text == ctx.lang('for_7days'):
            s_from = (now - datetime.timedelta(days=7)).strftime(FormatDate)
        elif ctx.text == ctx.lang('for_30days'):
            s_from = (now - datetime.timedelta(days=30)).strftime(FormatDate)

        # markup = InlineKeyboardMarkup([
        #     [InlineKeyboardButton(ctx.lang('please_wait'), callback_data='wait')]
        # ])

        message = ctx.reply(ctx.lang('consumption_request_sent'),
                  markup=bot.IgnoreMarkup())

        api = WebAPIClient(timeout=60)
        method = 'inverter_get_consumed_energy' if state == self.TOTAL else 'inverter_get_grid_consumed_energy'

        try:
            wh = getattr(api, method)(s_from, s_to)
            bot.delete_message(message.chat_id, message.message_id)
            ctx.reply('%.2f Wh' % (wh,),
                      markup=bot.IgnoreMarkup())
            return self.END
        except Exception as e:
            bot.delete_message(message.chat_id, message.message_id)
            ctx.reply_exc(e)

# other
# -----

@bot.handler(command='monstatus')
def monstatus_handler(ctx: bot.Context) -> None:
    msg = ''
    st = monitor.dump_status()
    for k, v in st.items():
        msg += k + ': ' + str(v) + '\n'
    ctx.reply(msg)


@bot.handler(command='monsetcur')
def monsetcur_handler(ctx: bot.Context) -> None:
    ctx.reply('not implemented yet')


@bot.handler(command='calcw')
def calcw_handler(ctx: bot.Context) -> None:
    ctx.reply('not implemented yet')


@bot.handler(command='calcwadv')
def calcwadv_handler(ctx: bot.Context) -> None:
    ctx.reply('not implemented yet')


@bot.callbackhandler
def button_callback(ctx: bot.Context) -> None:
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


@bot.exceptionhandler
def exception_handler(e: Exception, ctx: bot.Context) -> Optional[bool]:
    if isinstance(e, InverterError):
        try:
            err = json.loads(str(e))['message']
        except json.decoder.JSONDecodeError:
            err = str(e)
        err = re.sub(r'((?:.*)?error:) (.*)', r'<b>\1</b> \2', err)
        ctx.reply(err,
                  markup=bot.IgnoreMarkup())
        return True


@bot.handler(message='status')
def status_handler(ctx: bot.Context) -> None:
    gs = inverter.exec('get-status')['data']
    rated = inverter.exec('get-rated')['data']

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

    html += f'\n<b>{ctx.lang("priority")}</b>: {rated["output_source_priority"]}'

    # send response
    ctx.reply(html)


@bot.handler(message='generation')
def generation_handler(ctx: bot.Context) -> None:
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

    html += f'\n<b>{ctx.lang("today")}:</b> %s Wh' % (gen_today['wh'])

    if gen_yday is not None:
        html += f'\n<b>{ctx.lang("yday1")}:</b> %s Wh' % (gen_yday['wh'])

    if gen_yday2 is not None:
        html += f'\n<b>{ctx.lang("yday2")}:</b> %s Wh' % (gen_yday2['wh'])

    # send response
    ctx.reply(html)


@bot.defaultreplymarkup
def markup(ctx: Optional[bot.Context]) -> Optional[ReplyKeyboardMarkup]:
    button = [
        [ctx.lang('status'), ctx.lang('generation')],
        [ctx.lang('consumption')],
        [ctx.lang('settings')]
    ]
    return ReplyKeyboardMarkup(button, one_time_keyboard=False)


class InverterStore(bot.BotDatabase):
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
    inverter.init(host=config['inverter']['ip'], port=config['inverter']['port'])

    bot.set_database(InverterStore())
    bot.enable_logging(BotType.INVERTER)

    bot.add_conversation(SettingsConversation(enable_back=True))
    bot.add_conversation(ConsumptionConversation(enable_back=True))

    monitor = InverterMonitor()
    monitor.set_charging_event_handler(monitor_charging)
    monitor.set_battery_event_handler(monitor_battery)
    monitor.set_util_event_handler(monitor_util)
    monitor.set_error_handler(monitor_error)
    monitor.set_osp_need_change_callback(osp_change_cb)

    setacmode(getacmode())

    if not config.get('monitor.disabled'):
        logging.info('starting monitor')
        monitor.start()

    bot.run()

    monitor.stop()
