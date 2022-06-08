#!/usr/bin/env python3
import cmd
import time
import logging
import socket
import sys
import threading
import os.path
sys.path.extend([
    os.path.realpath(
        os.path.join(os.path.dirname(os.path.join(__file__)), '..', '..')
    )
])

from enum import Enum, auto
from typing import Optional
from src.home.util import stringify
from src.home.config import config
from src.home.inverter import (
    wrapper_instance as inverter,

    InverterMonitor,
    ChargingEvent,
    BatteryState,
    BatteryPowerDirection,
)


def monitor_charging(event: ChargingEvent, **kwargs) -> None:
    msg = 'event: ' + event.name
    if event == ChargingEvent.AC_CURRENT_CHANGED:
        msg += f' (current={kwargs["current"]})'
    evt_logger.info(msg)


def monitor_battery(state: BatteryState, v: float, load_watts: int) -> None:
    evt_logger.info(f'bat: {state.name}, v: {v}, load_watts: {load_watts}')


def monitor_error(error: str) -> None:
    evt_logger.warning('error: ' + error)


class InverterTestShell(cmd.Cmd):
    intro = 'Welcome to the test shell. Type help or ? to list commands.\n'
    prompt = '(test) '
    file = None

    def do_connect_ac(self, arg):
        server.connect_ac()

    def do_disconnect_ac(self, arg):
        server.disconnect_ac()

    def do_pd_charge(self, arg):
        server.set_pd(BatteryPowerDirection.CHARGING)

    def do_pd_nothing(self, arg):
        server.set_pd(BatteryPowerDirection.DO_NOTHING)

    def do_pd_discharge(self, arg):
        server.set_pd(BatteryPowerDirection.DISCHARGING)


class ChargerMode(Enum):
    NONE = auto()
    CHARGING = auto()


class ChargerEmulator(threading.Thread):
    def __init__(self):
        super().__init__()
        self.setName('ChargerEmulator')

        self.logger = logging.getLogger('charger')
        self.interrupted = False
        self.mode = ChargerMode.NONE

        self.pd = None
        self.ac_connected = False
        self.mppt_connected = False

    def run(self):
        while not self.interrupted:
            if self.pd == BatteryPowerDirection.CHARGING\
                    and self.ac_connected\
                    and not self.mppt_connected:

                v = server._get_voltage() + 0.02
                self.logger.info('incrementing voltage')
                server.set_voltage(v)

            time.sleep(2)

    def stop(self):
        self.interrupted = True

    def setmode(self, mode: ChargerMode):
        self.mode = mode

    def ac_changed(self, connected: bool):
        self.ac_connected = connected

    def mppt_changed(self, connected: bool):
        self.mppt_connected = connected

    def current_changed(self, amps):
        # FIXME
        # this method is not being called and voltage is not changing]
        # when current changes
        v = None
        if amps == 2:
            v = 49
        elif amps == 10:
            v = 51
        elif amps == 20:
            v = 52.5
        elif amps == 30:
            v = 53.5
        elif amps == 40:
            v = 54.5
        if v is not None:
            self.logger.info(f'setting voltage {v}')
            server.set_voltage(v)

    def pd_changed(self, pd: BatteryPowerDirection):
        self.pd = pd


class InverterEmulator(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__()
        self.setName('InverterEmulatorServer')
        self.lock = threading.Lock()

        self.status = {"grid_voltage": {"unit": "V", "value": 0.0},
                       "grid_freq": {"unit": "Hz", "value": 0.0},
                       "ac_output_voltage": {"unit": "V", "value": 230.0},
                       "ac_output_freq": {"unit": "Hz", "value": 50.0},
                       "ac_output_apparent_power": {"unit": "VA", "value": 92},
                       "ac_output_active_power": {"unit": "Wh", "value": 30},
                       "output_load_percent": {"unit": "%", "value": 1},
                       "battery_voltage": {"unit": "V", "value": 48.4},
                       "battery_voltage_scc": {"unit": "V", "value": 0.0},
                       "battery_voltage_scc2": {"unit": "V", "value": 0.0},
                       "battery_discharging_current": {"unit": "A", "value": 0},
                       "battery_charging_current": {"unit": "A", "value": 0},
                       "battery_capacity": {"unit": "%", "value": 62},
                       "inverter_heat_sink_temp": {"unit": "°C", "value": 8},
                       "mppt1_charger_temp": {"unit": "°C", "value": 0},
                       "mppt2_charger_temp": {"unit": "°C", "value": 0},
                       "pv1_input_power": {"unit": "Wh", "value": 0},
                       "pv2_input_power": {"unit": "Wh", "value": 0},
                       "pv1_input_voltage": {"unit": "V", "value": 0.0},
                       "pv2_input_voltage": {"unit": "V", "value": 0.0},
                       "configuration_status": "Default",
                       "mppt1_charger_status": "Abnormal",
                       "mppt2_charger_status": "Abnormal",
                       "load_connected": "Connected",
                       "battery_power_direction": "Discharge",
                       "dc_ac_power_direction": "DC/AC",
                       "line_power_direction": "Do nothing",
                       "local_parallel_id": 0}
        self.rated = {"ac_input_rating_voltage": {"unit": "V", "value": 230.0},
                      "ac_input_rating_current": {"unit": "A", "value": 21.7},
                      "ac_output_rating_voltage": {"unit": "V", "value": 230.0},
                      "ac_output_rating_freq": {"unit": "Hz", "value": 50.0},
                      "ac_output_rating_current": {"unit": "A", "value": 21.7},
                      "ac_output_rating_apparent_power": {"unit": "VA", "value": 5000},
                      "ac_output_rating_active_power": {"unit": "Wh", "value": 5000},
                      "battery_rating_voltage": {"unit": "V", "value": 48.0},
                      "battery_recharge_voltage": {"unit": "V", "value": 51.0},
                      "battery_redischarge_voltage": {"unit": "V", "value": 58.0},
                      "battery_under_voltage": {"unit": "V", "value": 42.0},
                      "battery_bulk_voltage": {"unit": "V", "value": 57.6},
                      "battery_float_voltage": {"unit": "V", "value": 54.0},
                      "battery_type": "User",
                      "max_charging_current": {"unit": "A", "value": 60},
                      "max_ac_charging_current": {"unit": "A", "value": 10},
                      "input_voltage_range": "Appliance",
                      "output_source_priority": "Parallel output",
                      "charge_source_priority": "Solar-and-Utility",
                      "parallel_max_num": 6,
                      "machine_type": "Off-Grid-Tie",
                      "topology": "Transformer-less",
                      "output_model_setting": "Single module",
                      "solar_power_priority": "Load-Battery-Utility",
                      "mppt": "2"}

        self.host = host
        self.port = port
        self.interrupted = False
        self.logger = logging.getLogger('srv')

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))

    def run(self):
        self.sock.listen(5)

        while not self.interrupted:
            conn, address = self.sock.accept()

            alive = True
            while alive:
                try:
                    buf = conn.recv(2048)
                    message = buf.decode().strip()
                except OSError as exc:
                    self.logger.error('failed to recv()')
                    self.logger.exception(exc)

                    alive = False

                    try:
                        conn.close()
                    except:
                        pass

                    continue  # exit the loop

                self.logger.log(0, f'< {message}')

                if message.strip() == '':
                    continue

                if message == 'format json':
                    # self.logger.info(f'got {message}')
                    self.reply_ok(conn)

                elif message.startswith('exec '):
                    command = message[5:].split()
                    args = command[1:]
                    command = command[0]

                    if command == 'get-allowed-ac-charging-currents':
                        self.reply_ok(conn, [2, 10, 20, 30, 40, 50, 60])
                    elif command == 'get-status':
                        self.reply_ok(conn, self._get_status())
                    elif command == 'get-rated':
                        self.reply_ok(conn, self._get_rated())
                    elif command == 'set-max-ac-charging-current':
                        self.set_ac_current(args[1])
                        self.reply_ok(conn, 1)
                    else:
                        raise ValueError('unsupported command: ' + command)
                else:
                    raise ValueError('unexpected request: ' + message)

    def reply_ok(self, connection, data=None):
        buf = 'ok' + '\r\n'
        if data:
            if not isinstance(data, str):
                data = stringify({'result': 'ok', 'data': data})
            buf += data + '\r\n'
        buf += '\r\n'
        self.logger.log(0, f'> {buf.strip()}')
        connection.sendall(buf.encode())

    def _get_status(self) -> dict:
        with self.lock:
            return self.status

    def _get_rated(self) -> dict:
        with self.lock:
            return self.rated

    def _get_voltage(self) -> float:
        with self.lock:
            return self.status['battery_voltage']['value']

    def stop(self):
        self.interrupted = True
        self.sock.close()

    def connect_ac(self):
        with self.lock:
            self.status['grid_voltage']['value'] = 230
            self.status['grid_freq']['value'] = 50
        charger.ac_changed(True)

    def disconnect_ac(self):
        with self.lock:
            self.status['grid_voltage']['value'] = 0
            self.status['grid_freq']['value'] = 0
            #self.status['battery_voltage']['value'] = 48.4  # revert to initial value
        charger.ac_changed(False)

    def connect_mppt(self):
        with self.lock:
            self.status['pv1_input_power']['value'] = 1
            self.status['pv1_input_voltage']['value'] = 50
            self.status['mppt1_charger_status'] = 'Charging'
        charger.mppt_changed(True)

    def disconnect_mppt(self):
        with self.lock:
            self.status['pv1_input_power']['value'] = 0
            self.status['pv1_input_voltage']['value'] = 0
            self.status['mppt1_charger_status'] = 'Abnormal'
        charger.mppt_changed(False)

    def set_voltage(self, v: float):
        with self.lock:
            self.status['battery_voltage']['value'] = v

    def set_ac_current(self, amps):
        with self.lock:
            self.rated['max_ac_charging_current']['value'] = amps
        charger.current_changed(amps)

    def set_pd(self, pd: BatteryPowerDirection):
        if pd == BatteryPowerDirection.CHARGING:
            val = 'Charge'
        elif pd == BatteryPowerDirection.DISCHARGING:
            val = 'Discharge'
        else:
            val = 'Do nothing'
        with self.lock:
            self.status['battery_power_direction'] = val
        charger.pd_changed(pd)


logger = logging.getLogger(__name__)
evt_logger = logging.getLogger('evt')
server: Optional[InverterEmulator] = None
charger: Optional[ChargerEmulator] = None


def main():
    global server, charger

    # start fake inverterd server
    try:
        server = InverterEmulator(host=config['inverter']['host'],
                                  port=config['inverter']['port'])
        server.start()
    except OSError as e:
        logger.error('failed to start server')
        logger.exception(e)
        return
    logger.info('server started')

    # start charger thread
    charger = ChargerEmulator()
    charger.start()

    # init inverterd wrapper
    inverter.schema_init(host=config['inverter']['host'],
                         port=config['inverter']['port'])

    # start monitor
    mon = InverterMonitor()
    mon.set_charging_event_handler(monitor_charging)
    mon.set_battery_event_handler(monitor_battery)
    mon.set_error_handler(monitor_error)
    mon.start()
    logger.info('monitor started')

    try:
        InverterTestShell().cmdloop()

        server.join()
        mon.join()
        charger.join()

    except KeyboardInterrupt:
        server.stop()
        mon.stop()
        charger.stop()


if __name__ == '__main__':
    config.load('test_inverter_monitor')
    main()
