import logging
import config
import os
import glob
import time

log = logging.getLogger("plugins." + __name__)

from kilnapp.plugins import hookimpl, KilnPlugin

class OneWire(object):
    bus = "/sys/bus/w1/devices/"

    def __init__(self):
        # Load the kernel drivers:
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')

    def scan(self):
        return glob.glob(self.bus + '28*')


class DS18X20(object):
    def __init__(self, bus, device):
        self.bus = bus
        self.device = device
        self.address = device.replace(bus.bus, '')
        self.label = config.w1_ds18x20_label[self.address]
        self.adjustment = config.w1_ds18x20_adjustment[self.address]

    def temperature(self):
        f = open(self.device+"/temperature", 'r')
        temp = int(f.readlines()[0])
        f.close
        return temp / 1000 + self.adjustment


class AmbientTemp(KilnPlugin):
    '''This reads ambient temperature from one or more
    DS18B20 sensors.
        config.w1_ds18x20_label
        config.w1_ds18x20_adjustment
        config.ambient_temp_verbose
    '''

    sensors = {}

    def __init__(self):
        super().__init__()

        # Read AmbientTemp GPIO
        try:
            self.w1bus = OneWire()
            self.w1devs = self.w1bus.scan()
            for device in self.w1devs:
                sensor = DS18X20(self.w1bus, device)
                name = sensor.address
                self.sensors[name] = sensor
            self.simulated = False
        except:
            self.simulated = True

        # Quiet AmbientTemp during simulation for debugging
        try:
            self.verbose = config.ambient_temp_verbose
        except:
            self.verbose = False
        if self.simulated and self.verbose:
            log.warn("AmbientTemp disabled during simulation")

    # This method will be executed when the thread starts
    def run(self):
        log.info(self.message("Starting AmbientTemp"))

        while True:
            for name, sensor in self.sensors.items():
                if self.verbose:
                    log.info("{:12} {:8.1f}C  {}".format(sensor.label, \
                        sensor.temperature(), name))
            time.sleep(self.period)

ambientObj = None

@hookimpl
def start_plugin():
    global ambientObj
    ambientObj = AmbientTemp()
    ambientObj.start()