#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import re
import logging

from home.mqtt import MQTTBase
from home.mqtt.payload.inverter import Status, Generation
from home.database import InverterDatabase
from home.config import config


class MQTTReceiver(MQTTBase):
    def __init__(self):
        super().__init__(clean_session=False)
        self.database = InverterDatabase()

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)
        self._logger.info("subscribing to hk/#")
        client.subscribe('hk/#', qos=1)

    def on_message(self, client: mqtt.Client, userdata, msg):
        try:
            match = re.match(r'(?:home|hk)/(\d+)/(status|gen)', msg.topic)
            if not match:
                return

            # FIXME string home_id must be supported
            home_id, what = int(match.group(1)), match.group(2)
            if what == 'gen':
                gen = Generation.unpack(msg.payload)
                self.database.add_generation(home_id, gen.time, gen.wh)

            elif what == 'status':
                s = Status.unpack(msg.payload)
                self.database.add_status(home_id,
                                         client_time=s.time,
                                         grid_voltage=int(s.grid_voltage*10),
                                         grid_freq=int(s.grid_freq * 10),
                                         ac_output_voltage=int(s.ac_output_voltage * 10),
                                         ac_output_freq=int(s.ac_output_freq * 10),
                                         ac_output_apparent_power=s.ac_output_apparent_power,
                                         ac_output_active_power=s.ac_output_active_power,
                                         output_load_percent=s.output_load_percent,
                                         battery_voltage=int(s.battery_voltage * 10),
                                         battery_voltage_scc=int(s.battery_voltage_scc * 10),
                                         battery_voltage_scc2=int(s.battery_voltage_scc2 * 10),
                                         battery_discharge_current=s.battery_discharge_current,
                                         battery_charge_current=s.battery_charge_current,
                                         battery_capacity=s.battery_capacity,
                                         inverter_heat_sink_temp=s.inverter_heat_sink_temp,
                                         mppt1_charger_temp=s.mppt1_charger_temp,
                                         mppt2_charger_temp=s.mppt2_charger_temp,
                                         pv1_input_power=s.pv1_input_power,
                                         pv2_input_power=s.pv2_input_power,
                                         pv1_input_voltage=int(s.pv1_input_voltage * 10),
                                         pv2_input_voltage=int(s.pv2_input_voltage * 10),
                                         mppt1_charger_status=s.mppt1_charger_status,
                                         mppt2_charger_status=s.mppt2_charger_status,
                                         battery_power_direction=s.battery_power_direction,
                                         dc_ac_power_direction=s.dc_ac_power_direction,
                                         line_power_direction=s.line_power_direction,
                                         load_connected=s.load_connected)

        except Exception as e:
            self._logger.exception(str(e))


if __name__ == '__main__':
    config.load('inverter_mqtt_receiver')

    server = MQTTReceiver()
    server.connect_and_loop()

