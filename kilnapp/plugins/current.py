import time
import logging
import config
import array
import math
import threading
import array

import board
import digitalio
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.ads1x15 import Mode
from adafruit_ads1x15.ads1x15 import Comp_Mode
from adafruit_ads1x15.analog_in import AnalogIn

log = logging.getLogger("plugins." + __name__)

from kilnapp.plugins import hookimpl, KilnPlugin

pgafsr = [ 6.2114, 4.096, 2.048, 1.024, 0.512, 0.256 ]

# Polynomial regression coefs to estimate amps
# Based on experiments from 0 to 13 amps
#A = 0.1051
#B = 0.00324
#C = 0.0000011614

class SCT013(threading.Thread):
    amps = 0

    def __init__(self, chan, name="clamp"):
        threading.Thread.__init__(self)
        self.daemon = True

        self.chan = chan
        self.name = name

        self.vstep = 2 * pgafsr[config.current_pga] / pow(2, config.current_adc_bits - 1)
        self.burdenres = config.current_burden_res
        self.ratio = config.current_sensoramps[0] / config.current_sensoramps[1]
        self.multiplier = self.ratio / self.burdenres
        self.period = config.current_period

        self.check_burdenres()
        #log.info("{} Multiplier: {}".format(self.name, self.multiplier))

    def check_burdenres(self):
        inputamps = config.current_inputamps
        sensoramps = config.current_sensoramps
        outputamps = sensoramps[1] * inputamps / sensoramps[0]
        suggested_burdenres = round(config.current_vcc / 2 / outputamps)
        if(not math.isclose(a=suggested_burdenres, b=self.burdenres, rel_tol=20)):
            log.warn("Burden resistor should be about {}, but it is set to {}".format(suggested_burdenres, self.burdenres))

        #vburden = outputamps * burdenres
        #fsrange = pgafsr[count.current_pga]
        #vstep = fsrange / pow(2, config.current_adc_bits - 1)
        #vstep = pgatable[count.current_pga]["vpc"]
        #counts = vburden / vstep
        ##counts = outputamps * burdenres / pgatable[count.current_pga]["vpc"]
        ##return round(inputamps / counts, 8)

    def sample(self):
        count = config.current_samples
        maxVolts = 0
        for i in range(count):
            try:
                value = self.chan.value * self.vstep
                maxVolts = max(maxVolts, abs(value))
            except OSError:
                log.warn("{}: I2C Input/output error, skipping sample".format(self.name))
                continue
        self.amps = maxVolts * self.multiplier

        #log.info("Name: {}  Max: {}  Amps: {}".format(self.name, maxVolts, round(self.amps,3)))

    def sample_rms(self):
        data = array.array('f')
        count = config.current_samples
        summation = 0.0
        sumsquare = 0.0
        maxValue = 0
        for i in range(count):
            value = self.chan.value * self.vstep
            data.append(value)
            maxValue = max(maxValue, abs(value))
            summation += value
            sumsquare += value * value

        bias = summation / count
        variance = sumsquare / count - bias * bias
        stddev = math.sqrt(variance)
        threshold = bias + 3 * stddev

        n = 0
        accum = 0
        #csv = "\"{}\"".format(self.name)
        for value in data:
            #csv = "{}, \"{}\"".format(csv, round(value,3))
            value = abs(value)
            if value < threshold:
                n += 1
                value -= bias
                accum += value * value
            else:
                log.warn("Throwing away {}".format(value))

        vrms = 0
        if n > 0:
            vrms = math.sqrt(accum / n)

        self.amps= vrms * self.ratio / self.burdenres

        #log.info(csv)
        log.info("Name: {}  Max: {}  VRMS: {}  Amps: {}".format(self.name, maxValue, round(vrms,6), round(self.amps,3)))

    def run(self):
        while True:
            self.sample()
            time.sleep(self.period)

    def get_amps(self):
        return (self.name, self.amps)

    def __str__(self):
        return "{}: {} Amps".format(self.name, round(self.amps, 3))


class Current(KilnPlugin):
    '''This thread reads 2 SCT013 Current clamps from
    a ADS1115 ADC.
        config.current_verbose
        config.current_gpio       = board.D25 # ALRT pin
        config.current_period     = 2 # Seconds
        config.current_pga        = 4
        config.current_adc_rate   = 860 # Samples per second
        config.current_samples    = 256 # Samples
        config.current_sensoramps = (100, 0.050) # Amps
        config.current_inputamps  = 30 # Amps
        config.current_vcc        = 5 # Volts
        config.current_burden_res = 150 # Ohms
        config.current_adc_bits   = 16 # bits
    '''

    sensor = []

    def __init__(self):
        super().__init__()

        #try:
        self.period = config.current_period

        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c)
        ads.gain = config.current_pga
        ads.data_rate = config.current_adc_rate
        ads.mode = Mode.CONTINUOUS
        ads.comparator_mode = Comp_Mode.TRADITIONAL

        # ALRT pin
        self.ready = digitalio.DigitalInOut(config.current_gpio)
        self.ready.direction = digitalio.Direction.INPUT

        self.sensor.append(SCT013(AnalogIn(ads, ADS.P0, ADS.P1), "Upper coil"))
        self.sensor.append(SCT013(AnalogIn(ads, ADS.P2, ADS.P3), "Lower coil"))

        self.sensor[0].start()
        self.sensor[1].start()

        self.simulated = False
        #except:
        #    self.simulated = True

        # Quiet Current during simulation for debugging
        try:
            self.verbose = config.current_verbose
        except:
            self.verbose = False
        if self.simulated and self.verbose:
            log.warn("Current disabled during simulation")

    # This method will be executed when the thread starts
    def run(self):
        log.info(self.message("Starting Current"))

        while True:
            for sensor in self.sensor:
                if self.verbose:
                    log.info(sensor)
            time.sleep(self.period)

currentObj = None

@hookimpl
def start_plugin():
    global currentObj
    currentObj = Current()
    currentObj.start()
