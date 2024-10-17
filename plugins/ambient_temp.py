import logging
import os
import glob
import time

log = logging.getLogger("plugins." + __name__)

from settings import config
from plugins import hookimpl, KilnPlugin

class OneWire(object):
    path = "/sys/bus/w1/devices/"

    def __init__(self):
        # Load the kernel drivers:
        os.system('modprobe w1-gpio')
        os.system('modprobe w1-therm')

    def scan(self):
        return glob.glob(self.path + '28*')

    def device_address(self, device):
        return device.replace(self.path, '')


class DS18X20(object):
    def __init__(self, bus, device):
        self.device = device
        self.address = bus.device_address(device)
        sensor = config.get('plugins.ambient_temp.sensors.w1.' + self.address)
        self.label = sensor['name']
        self.adjustment = config.get_temp('plugins.ambient_temp.sensors.w1.{}.offset'.format(self.address))[0]

    def get_address(self):
        return self.address

    def get_label(self):
        return self.label

    def temperature(self):
        try:
            with open(self.device + "/temperature", 'r') as device:
                reading = int(device.readlines()[0])
            temp = round(reading / 1000 + self.adjustment, 1)
            return temp
        except IndexError:
            return 0


class AmbientTemp(KilnPlugin):
    '''This reads ambient temperature from one or more
    DS18B20 sensors.
    '''

    def __init__(self):
        super().__init__(__name__)
        self.verbose = config.get_log_subsystem('ambient_temp')
        self.sensors = {}

        # Read AmbientTemp GPIO
        try:
            self.w1bus = OneWire()
            w1devs = self.w1bus.scan()
            for device in w1devs:
                sensor = DS18X20(self.w1bus, device)
                addr = sensor.get_address()
                log.info("Add DS18B20 ambient temperature sensor: {}".format(addr))
                self.sensors[addr] = sensor
            self.simulated = False
        except:
            self.simulated = True

    # This method will be executed when the thread starts
    def run(self):
        log.info(self.message("Starting AmbientTemp"))

        while True:
            info = {}
            for name, sensor in self.sensors.items():
                temp = sensor.temperature()
                info[sensor.label] = temp
            if self.verbose:
                log.info(info)
            self.hook.record_meta(info=info)
            time.sleep(self.period)

ambientObj = None

@hookimpl
def start_plugin():
    global ambientObj
    ambientObj = AmbientTemp()
    ambientObj.start()
