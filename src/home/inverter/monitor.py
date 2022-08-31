import logging
import time

from enum import Enum, auto
from threading import Thread
from typing import Callable, Optional
from .inverter_wrapper import wrapper_instance as inverter
from inverterd import InverterError
from ..util import Stopwatch, StopwatchError
from ..config import config

logger = logging.getLogger(__name__)


class BatteryPowerDirection(Enum):
    DISCHARGING = auto()
    CHARGING = auto()
    DO_NOTHING = auto()


class ChargingEvent(Enum):
    AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR = auto()
    AC_NOT_CHARGING = auto()
    AC_CHARGING_STARTED = auto()
    AC_DISCONNECTED = auto()
    AC_CURRENT_CHANGED = auto()
    AC_MOSTLY_CHARGED = auto()
    AC_CHARGING_FINISHED = auto()


class ChargingState(Enum):
    NOT_CHARGING = auto()
    AC_BUT_SOLAR = auto()
    AC_WAITING = auto()
    AC_OK = auto()
    AC_DONE = auto()


class CurrentChangeDirection(Enum):
    UP = auto()
    DOWN = auto()


class BatteryState(Enum):
    NORMAL = auto()
    LOW = auto()
    CRITICAL = auto()


class ACMode(Enum):
    GENERATOR = 'generator'
    UTILITIES = 'utilities'


def _pd_from_string(pd: str) -> BatteryPowerDirection:
    if pd == 'Discharge':
        return BatteryPowerDirection.DISCHARGING
    elif pd == 'Charge':
        return BatteryPowerDirection.CHARGING
    elif pd == 'Do nothing':
        return BatteryPowerDirection.DO_NOTHING
    else:
        raise ValueError(f'invalid power direction: {pd}')


class MonitorConfig:
    def __getattr__(self, item):
        return config['monitor'][item]


cfg = MonitorConfig()


"""
TODO:
- поддержать возможность ручного (через бота) переключения тока заряда вверх и вниз
- поддержать возможность бесшовного перезапуска бота, когда монитор понимает, что зарядка уже идет, и он
  не запускает программу с начала, а продолжает с уже существующей позиции. Уведомления при этом можно не
  присылать совсем, либо прислать какое-то одно приложение, в духе "программа была перезапущена"
"""


class InverterMonitor(Thread):
    charging_event_handler: Optional[Callable]
    battery_event_handler: Optional[Callable]
    error_handler: Optional[Callable]

    def __init__(self):
        super().__init__()
        self.setName('InverterMonitor')

        self.interrupted = False
        self.min_allowed_current = 0
        self.ac_mode = None

        # Event handlers for the bot.
        self.charging_event_handler = None
        self.battery_event_handler = None
        self.error_handler = None

        # Currents list, defined in the bot config.
        self.currents = cfg.gen_currents
        self.currents.sort()

        # We start charging at lowest possible current, then increase it once per minute (or so) to the maximum level.
        # This is done so that the load on the generator increases smoothly, not abruptly. Generator will thank us.
        self.current_change_direction = CurrentChangeDirection.UP
        self.next_current_enter_time = 0
        self.active_current_idx = -1

        self.battery_state = BatteryState.NORMAL
        self.charging_state = ChargingState.NOT_CHARGING

        # 'Mostly-charged' means that we've already lowered the charging current to the level
        # at which batteries are charging pretty slow. So instead of burning gasoline and shaking the air,
        # we can just turn the generator off at this point.
        self.mostly_charged = False

        # The stopwatch is used to measure how long does the battery voltage exceeds the float voltage level.
        # We don't want to damage our batteries, right?
        self.floating_stopwatch = Stopwatch()

    @property
    def active_current(self) -> Optional[int]:
        try:
            if self.active_current_idx < 0:
                return None
            return self.currents[self.active_current_idx]
        except IndexError:
            return None

    def run(self):
        # Check allowed currents and validate the config.
        allowed_currents = list(inverter.exec('get-allowed-ac-charging-currents')['data'])
        allowed_currents.sort()

        for a in self.currents:
            if a not in allowed_currents:
                raise ValueError(f'invalid value {a} in gen_currents list')

        self.min_allowed_current = min(allowed_currents)

        # Read data and run implemented programs every 2 seconds.
        while not self.interrupted:
            try:
                response = inverter.exec('get-status')
                if response['result'] != 'ok':
                    logger.error('get-status failed:', response)
                else:
                    gs = response['data']

                    ac = gs['grid_voltage']['value'] > 0 or gs['grid_freq']['value'] > 0
                    solar = gs['pv1_input_power']['value'] > 0
                    v = float(gs['battery_voltage']['value'])
                    load_watts = int(gs['ac_output_active_power']['value'])
                    pd = _pd_from_string(gs['battery_power_direction'])

                    logger.debug(f'got status: ac={ac}, solar={solar}, v={v}, pd={pd}')

                    if self.ac_mode == ACMode.GENERATOR:
                        self.gen_charging_program(ac, solar, v, pd)

                    if not ac or pd != BatteryPowerDirection.CHARGING:
                        # if AC is disconnected or not charging, run the low voltage checking program
                        self.low_voltage_program(v, load_watts)

                    elif self.battery_state != BatteryState.NORMAL:
                        # AC is connected and the battery is charging, assume battery level is normal
                        self.battery_state = BatteryState.NORMAL

            except InverterError as e:
                logger.exception(e)

            time.sleep(2)

    def gen_charging_program(self,
                             ac: bool,                  # whether AC is connected
                             solar: bool,               # whether MPPT is active
                             v: float,                  # current battery voltage
                             pd: BatteryPowerDirection  # current power direction
                             ):
        if self.charging_state == ChargingState.NOT_CHARGING:
            if ac and solar:
                # Not charging because MPPT is active (solar line is connected).
                # Notify users about it and change the current state.
                self.charging_state = ChargingState.AC_BUT_SOLAR
                self.charging_event_handler(ChargingEvent.AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR)
                logger.info('entering AC_BUT_SOLAR state')
            elif ac:
                # Not charging, but AC is connected and ready to use.
                # Start the charging program.
                self.gen_start(pd)

        elif self.charging_state == ChargingState.AC_BUT_SOLAR:
            if not ac:
                # AC charger has been disconnected. Since the state is AC_BUT_SOLAR,
                # charging probably never even started. Stop the charging program.
                self.gen_stop(ChargingState.NOT_CHARGING)
            elif not solar:
                # MPPT has been disconnected, and, since AC is still connected, we can
                # try to start the charging program.
                self.gen_start(pd)

        elif self.charging_state in (ChargingState.AC_OK, ChargingState.AC_WAITING):
            if not ac:
                # Charging was in progress, but AC has been suddenly disconnected.
                # Sad, but what can we do? Stop the charging program and return.
                self.gen_stop(ChargingState.NOT_CHARGING)
                return

            if solar:
                # Charging was in progress, but MPPT has been detected. Inverter doesn't charge
                # batteries from AC when MPPT is active, so we have to pause our program.
                self.charging_state = ChargingState.AC_BUT_SOLAR
                self.charging_event_handler(ChargingEvent.AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR)
                try:
                    self.floating_stopwatch.pause()
                except StopwatchError:
                    msg = 'gen_charging_program: floating_stopwatch.pause() failed at (1)'
                    logger.warning(msg)
                    # self.error_handler(msg)
                logger.info('solar power connected during charging, entering AC_BUT_SOLAR state')
                return

            # No surprises at this point, just check the values and make decisions based on them.
            # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

            # We've reached the 'mostly-charged' point, the voltage level is not float,
            # but inverter decided to stop charging (or somebody used a kettle, lol).
            # Anyway, assume that charging is complete, stop the program, notify users and return.
            if self.mostly_charged and v > (cfg.gen_floating_v - 1) and pd != BatteryPowerDirection.CHARGING:
                self.gen_stop(ChargingState.AC_DONE)
                return

            # Monitor inverter power direction and notify users when it changes.
            state = ChargingState.AC_OK if pd == BatteryPowerDirection.CHARGING else ChargingState.AC_WAITING
            if state != self.charging_state:
                self.charging_state = state

                evt = ChargingEvent.AC_CHARGING_STARTED if state == ChargingState.AC_OK else ChargingEvent.AC_NOT_CHARGING
                self.charging_event_handler(evt)

            if self.floating_stopwatch.get_elapsed_time() >= cfg.gen_floating_time_max:
                # We've been at a bulk voltage level too long, so we have to stop charging.
                # Set the minimum current possible.

                if self.current_change_direction == CurrentChangeDirection.UP:
                    # This shouldn't happen, obviously an error.
                    msg = 'gen_charging_program:'
                    msg += ' been at bulk voltage level too long, but current change direction is still \'up\'!'
                    msg += ' This is obviously an error, please fix it'
                    logger.warning(msg)
                    self.error_handler(msg)

                self.gen_next_current(current=self.min_allowed_current)

            elif self.active_current is not None:
                # If voltage is greater than float voltage, keep the stopwatch ticking
                if v > cfg.gen_floating_v and self.floating_stopwatch.is_paused():
                    try:
                        self.floating_stopwatch.go()
                    except StopwatchError:
                        msg = 'gen_charging_program: floating_stopwatch.go() failed at (2)'
                        logger.warning(msg)
                        self.error_handler(msg)
                # Otherwise, pause it
                elif v <= cfg.gen_floating_v and not self.floating_stopwatch.is_paused():
                    try:
                        self.floating_stopwatch.pause()
                    except StopwatchError:
                        msg = 'gen_charging_program: floating_stopwatch.pause() failed at (3)'
                        logger.warning(msg)
                        self.error_handler(msg)

                # Charging current monitoring
                if self.current_change_direction == CurrentChangeDirection.UP:
                    # Generator is warming up in this code path

                    if self.next_current_enter_time != 0 and pd != BatteryPowerDirection.CHARGING:
                        # Generator was warming up and charging, but stopped (pd has changed).
                        # Resetting to the minimum possible current
                        logger.info(f'gen_charging_program (warming path): was charging but power direction suddeny changed. resetting to minimum current')
                        self.next_current_enter_time = 0
                        self.gen_next_current(current=self.min_allowed_current)

                    elif self.next_current_enter_time == 0 and pd == BatteryPowerDirection.CHARGING:
                        self.next_current_enter_time = time.time() + cfg.gen_raise_intervals[self.active_current_idx]
                        logger.info(f'gen_charging_program (warming path): set next_current_enter_time to {self.next_current_enter_time}')

                    elif self.next_current_enter_time != 0 and time.time() >= self.next_current_enter_time:
                        logger.info('gen_charging_program (warming path): hit next_current_enter_time, calling gen_next_current()')
                        self.gen_next_current()
                else:
                    # Gradually lower the current level, based on how close
                    # battery voltage has come to the bulk level.
                    if self.active_current >= 30:
                        upper_bound = cfg.gen_cur30_v_limit
                    elif self.active_current == 20:
                        upper_bound = cfg.gen_cur20_v_limit
                    else:
                        upper_bound = cfg.gen_cur10_v_limit

                    # Voltage is high enough already and it's close to bulk level; we hit the upper bound,
                    # so let's lower the current
                    if v >= upper_bound:
                        self.gen_next_current()

        elif self.charging_state == ChargingState.AC_DONE:
            # We've already finished charging, but AC was connected. Not that it's disconnected,
            # set the appropriate state and notify users.
            if not ac:
                self.gen_stop(ChargingState.NOT_CHARGING)

    def gen_start(self, pd: BatteryPowerDirection):
        if pd == BatteryPowerDirection.CHARGING:
            self.charging_state = ChargingState.AC_OK
            self.charging_event_handler(ChargingEvent.AC_CHARGING_STARTED)
            logger.info('AC line connected and charging, entering AC_OK state')

            # Continue the stopwatch, if needed
            try:
                self.floating_stopwatch.go()
            except StopwatchError:
                msg = 'floating_stopwatch.go() failed at ac_charging_start(), AC_OK path'
                logger.warning(msg)
                self.error_handler(msg)
        else:
            self.charging_state = ChargingState.AC_WAITING
            self.charging_event_handler(ChargingEvent.AC_NOT_CHARGING)
            logger.info('AC line connected but not charging yet, entering AC_WAITING state')

            # Pause the stopwatch, if needed
            try:
                if not self.floating_stopwatch.is_paused():
                    self.floating_stopwatch.pause()
            except StopwatchError:
                msg = 'floating_stopwatch.pause() failed at ac_charging_start(), AC_WAITING path'
                logger.warning(msg)
                self.error_handler(msg)

        # idx == -1 means haven't started our program yet.
        if self.active_current_idx == -1:
            self.gen_next_current()
            # self.set_hw_charging_current(self.min_allowed_current)

    def gen_stop(self, reason: ChargingState):
        self.charging_state = reason

        if reason == ChargingState.AC_DONE:
            event = ChargingEvent.AC_CHARGING_FINISHED
        elif reason == ChargingState.NOT_CHARGING:
            event = ChargingEvent.AC_DISCONNECTED
        else:
            raise ValueError(f'ac_charging_stop: unexpected reason {reason}')

        logger.info(f'charging is finished, entering {reason} state')
        self.charging_event_handler(event)

        self.next_current_enter_time = 0
        self.mostly_charged = False
        self.active_current_idx = -1
        self.floating_stopwatch.reset()
        self.current_change_direction = CurrentChangeDirection.UP

        self.set_hw_charging_current(self.min_allowed_current)

    def gen_next_current(self, current=None):
        if current is None:
            try:
                current = self._next_current()
                logger.debug(f'gen_next_current: ready to change charging current to {current} A')
            except IndexError:
                logger.debug('gen_next_current: was going to change charging current, but no currents left; finishing charging program')
                self.gen_stop(ChargingState.AC_DONE)
                return

        else:
            try:
                idx = self.currents.index(current)
            except ValueError:
                msg = f'gen_next_current: got current={current} but it\'s not in the currents list'
                logger.error(msg)
                self.error_handler(msg)
                return
            self.active_current_idx = idx

        if self.current_change_direction == CurrentChangeDirection.DOWN:
            if current == self.currents[0]:
                self.mostly_charged = True
                self.gen_stop(ChargingState.AC_DONE)

            elif current == self.currents[1] and not self.mostly_charged:
                self.mostly_charged = True
                self.charging_event_handler(ChargingEvent.AC_MOSTLY_CHARGED)

        self.set_hw_charging_current(current)

    def set_hw_charging_current(self, current: int):
        try:
            response = inverter.exec('set-max-ac-charging-current', (0, current))
            if response['result'] != 'ok':
                logger.error(f'failed to change AC charging current to {current} A')
                raise InverterError('set-max-ac-charging-current: inverterd reported error')
            else:
                self.charging_event_handler(ChargingEvent.AC_CURRENT_CHANGED, current=current)
                logger.info(f'changed AC charging current to {current} A')
        except InverterError as e:
            self.error_handler(f'failed to set charging current to {current} A (caught InverterError)')
            logger.exception(e)

    def _next_current(self):
        if self.current_change_direction == CurrentChangeDirection.UP:
            self.active_current_idx += 1
            if self.active_current_idx == len(self.currents)-1:
                logger.info('_next_current: charging current power direction to DOWN')
                self.current_change_direction = CurrentChangeDirection.DOWN
            self.next_current_enter_time = 0
        else:
            if self.active_current_idx == 0:
                raise IndexError('can\'t go lower')
            self.active_current_idx -= 1

        logger.info(f'_next_current: active_current_idx set to {self.active_current_idx}, returning current of {self.currents[self.active_current_idx]} A')
        return self.currents[self.active_current_idx]

    def low_voltage_program(self, v: float, load_watts: int):
        crit_level = cfg.vcrit
        low_level = cfg.vlow

        if v <= crit_level:
            state = BatteryState.CRITICAL
        elif v <= low_level:
            state = BatteryState.LOW
        else:
            state = BatteryState.NORMAL

        if state != self.battery_state:
            self.battery_state = state
            self.battery_event_handler(state, v, load_watts)

    def set_charging_event_handler(self, handler: Callable):
        self.charging_event_handler = handler

    def set_battery_event_handler(self, handler: Callable):
        self.battery_event_handler = handler

    def set_error_handler(self, handler: Callable):
        self.error_handler = handler

    def set_ac_mode(self, mode: ACMode):
        self.ac_mode = mode

    def stop(self):
        self.interrupted = True

    def dump_status(self) -> dict:
        return {
            'interrupted': self.interrupted,
            'currents': self.currents,
            'active_current': self.active_current,
            'current_change_direction': self.current_change_direction.name,
            'battery_state': self.battery_state.name,
            'charging_state': self.charging_state.name,
            'mostly_charged': self.mostly_charged,
            'floating_stopwatch_paused': self.floating_stopwatch.is_paused(),
            'floating_stopwatch_elapsed': self.floating_stopwatch.get_elapsed_time(),
            'time_now': time.time(),
            'next_current_enter_time': self.next_current_enter_time,
            'ac_mode': self.ac_mode
        }
