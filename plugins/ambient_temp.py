import threading
import time
import logging
import config

from adafruit_onewire.bus import OneWireBus
from adafruit_ds18x20 import DS18X20

log = logging.getLogger(__name__)

import plugins

class AmbientTemp(threading.Thread):
    '''This represents a GPIO output that controls a
    status LED which beats like a heart.
        config.ambient_temp_gpio
        config.ambient_temp_quiet
    '''
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True

        # Read AmbientTemp GPIO
        try:
            self.w1bus = OneWireBus(config.ambient_temp_gpio)
            self.w1devs = self.w1bus.scan()
            self.sensors = {}
            for device in self.w1devs:
                sensor = DS18X20(self.w1bus, device)
                log.info( { 'name': sensor.address,
                            'device': sensor } )
            self.simulated = False
        except:
            self.simulated = True

        # Quiet AmbientTemp during simulation for debugging
        try:
            self.quiet = config.ambient_temp_quiet
        except:
            self.quiet = False
        if self.simulated and self.quiet:
            log.warn("AmbientTemp disabled during simulation")

        self.start()

    # This method will be executed when the thread starts
    def run(self):
        log.info("Starting AmbientTemp")

        while True:
            time.sleep(1)
