import logging
import threading

from typing import Optional
from time import sleep
from ..util import stringify, send_datagram, Addr

from pyA20.gpio import gpio
from pyA20.gpio import port as gpioport

logger = logging.getLogger(__name__)


class SoundSensorNode:
    def __init__(self,
                 name: str,
                 pinname: str,
                 server_addr: Optional[Addr],
                 delay=0.005):

        if not hasattr(gpioport, pinname):
            raise ValueError(f'invalid pin {pinname}')

        self.pin = getattr(gpioport, pinname)
        self.name = name
        self.delay = delay

        self.server_addr = server_addr

        self.hits = 0
        self.hitlock = threading.Lock()

        self.interrupted = False

    def run(self):
        try:
            t = threading.Thread(target=self.sensor_reader)
            t.daemon = True
            t.start()

            while True:
                with self.hitlock:
                    hits = self.hits
                    self.hits = 0

                if hits > 0:
                    try:
                        if self.server_addr is not None:
                            send_datagram(stringify([self.name, hits]), self.server_addr)
                        else:
                            logger.debug(f'server reporting disabled, skipping reporting {hits} hits')
                    except OSError as exc:
                        logger.exception(exc)

                sleep(1)

        except (KeyboardInterrupt, SystemExit) as e:
            self.interrupted = True
            logger.info(str(e))

    def sensor_reader(self):
        gpio.init()
        gpio.setcfg(self.pin, gpio.INPUT)
        gpio.pullup(self.pin, gpio.PULLUP)

        while not self.interrupted:
            state = gpio.input(self.pin)
            sleep(self.delay)

            if not state:
                with self.hitlock:
                    logger.debug('got a hit')
                    self.hits += 1
