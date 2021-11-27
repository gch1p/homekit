#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import re
import logging

from home.mqtt import MQTTBase
from home.mqtt.message import Status, Generation
from home.database import InverterDatabase
from home.config import config

logger = logging.getLogger(__name__)


class MQTTReceiver(MQTTBase):
    def __init__(self):
        super().__init__(clean_session=False)
        self.database = InverterDatabase()

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)
        logger.info("subscribing to home/#")
        client.subscribe('home/#', qos=1)

    def on_message(self, client: mqtt.Client, userdata, msg):
        try:
            match = re.match(r'home/(\d+)/(status|gen)', msg.topic)
            if not match:
                return

            home_id, what = int(match.group(1)), match.group(2)
            if what == 'gen':
                packer = Generation()
                client_time, watts = packer.unpack(msg.payload)
                self.database.add_generation(home_id, client_time, watts)

            elif what == 'status':
                packer = Status()
                client_time, data = packer.unpack(msg.payload)
                self.database.add_status(home_id,
                                         client_time,
                                         grid_voltage=int(data['grid_voltage']*10),
                                         grid_freq=int(data['grid_freq'] * 10),
                                         ac_output_voltage=int(data['ac_output_voltage'] * 10),
                                         ac_output_freq=int(data['ac_output_freq'] * 10),
                                         ac_output_apparent_power=data['ac_output_apparent_power'],
                                         ac_output_active_power=data['ac_output_active_power'],
                                         output_load_percent=data['output_load_percent'],
                                         battery_voltage=int(data['battery_voltage'] * 10),
                                         battery_voltage_scc=int(data['battery_voltage_scc'] * 10),
                                         battery_voltage_scc2=int(data['battery_voltage_scc2'] * 10),
                                         battery_discharging_current=data['battery_discharging_current'],
                                         battery_charging_current=data['battery_charging_current'],
                                         battery_capacity=data['battery_capacity'],
                                         inverter_heat_sink_temp=data['inverter_heat_sink_temp'],
                                         mppt1_charger_temp=data['mppt1_charger_temp'],
                                         mppt2_charger_temp=data['mppt2_charger_temp'],
                                         pv1_input_power=data['pv1_input_power'],
                                         pv2_input_power=data['pv2_input_power'],
                                         pv1_input_voltage=int(data['pv1_input_voltage'] * 10),
                                         pv2_input_voltage=int(data['pv2_input_voltage'] * 10),
                                         mppt1_charger_status=data['mppt1_charger_status'],
                                         mppt2_charger_status=data['mppt2_charger_status'],
                                         battery_power_direction=data['battery_power_direction'],
                                         dc_ac_power_direction=data['dc_ac_power_direction'],
                                         line_power_direction=data['line_power_direction'],
                                         load_connected=data['load_connected'])

        except Exception as e:
            logger.exception(str(e))


if __name__ == '__main__':
    config.load('inverter_mqtt_receiver')

    server = MQTTReceiver()
    server.connect_and_loop()

