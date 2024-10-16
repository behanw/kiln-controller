import array
import logging
import math
import threading
import time

from settings import config

log = logging.getLogger("plugins." + __name__)

from kilnapp.plugins import hookimpl, KilnPlugin

pgafsr = [ 6.2114, 4.096, 2.048, 1.024, 0.512, 0.256 ]

class SCT013(object):
    amps = 0

    def __init__(self, adc, chan, sensor, name="clamp"):
        threading.Thread.__init__(self)
        self.daemon = True
        self.chan = chan
        self.name = name
        self.sample_count = config.get('plugins.current.samples')

        self.vstep = pgafsr[adc['pga_gain']] / pow(2, adc['bits'] - 1)
        self.ratio = sensor['inputamps'] / sensor['outputamps']
        self.burdenres = sensor['burden_res']
        self.multiplier = self.ratio / self.burdenres

        self.check_burdenres(sensor['inputamps'], sensor['outputamps'], adc['vcc'])
        #log.info("{} Multiplier: {}".format(self.name, self.multiplier))

    def check_burdenres(self, sensor_in_amps, sensor_out_amps, vcc):
        maxamps = config.get('plugins.current.maxamps')
        outputamps = sensor_out_amps * maxamps / sensor_in_amps
        suggested_burdenres = round(vcc / 2 / sensor_out_amps)
        if(not math.isclose(a=suggested_burdenres, b=self.burdenres, rel_tol=20)):
            log.warning("Burden resistor should be about {}, but it is set to {}"
                        .format(suggested_burdenres, self.burdenres))

        #vburden = outputamps * burdenres
        #fsrange = pgafsr[count.current_pga]
        #vstep = fsrange / pow(2, config.current_adc_bits - 1)
        #vstep = pgatable[count.current_pga]["vpc"]
        #counts = vburden / vstep
        ##counts = outputamps * burdenres / pgatable[count.current_pga]["vpc"]
        ##return round(inputamps / counts, 8)

    def sample(self):
        maxVolts = 0
        for i in range(self.sample_count):
            try:
                value = self.chan.value * self.vstep
                maxVolts = max(maxVolts, abs(value))
            except OSError:
                log.warning("{}: I2C Input/output error, skipping sample".format(self.name))
                continue
        amps = maxVolts * self.multiplier
        if amps < 0.02: amps = 0
        #log.info("Name: {}  Max: {}  Amps: {}".format(self.name, maxVolts, round(self.amps,3)))
        return amps

    def sample_rms(self):
        data = array.array('f')
        summation = 0.0
        sumsquare = 0.0
        maxValue = 0
        for i in range(self.sample_count):
            value = self.chan.value * self.vstep
            data.append(value)
            maxValue = max(maxValue, abs(value))
            summation += value
            sumsquare += value * value

        bias = summation / self.sample_count
        variance = sumsquare / self.sample_count - bias * bias
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
                log.warning("Throwing away {}".format(value))

        vrms = math.sqrt(accum / n) if n > 0 else 0
        amps = vrms * self.ratio / self.burdenres
        log.info("Name: {}  Max: {}  VRMS: {}  Amps: {}".format(self.name, maxValue, round(vrms,6), round(amps,3)))
        return amps

    def __str__(self):
        return "{}: {} Amps".format(self.name, round(self.amps, 3))


class Current(KilnPlugin):
    '''This thread reads 2 SCT013 Current clamps from
    a ADS1115 ADC.
    '''

    def __init__(self):
        super().__init__(__name__)

        self.sensor = {}
        self.period = config.get_time_in_unit('plugins.current.period', 's')

        try:
            import board
            import busio
            i2c = busio.I2C(board.SCL, board.SDA)

            adc_config = config.get('plugins.current.hw.adc')

            import adafruit_ads1x15.ads1115 as ADS
            ads = ADS.ADS1115(i2c)
            ads.gain = adc_config['pga_gain']
            ads.data_rate = adc_config['rate']

            from adafruit_ads1x15.ads1x15 import Comp_Mode, Mode
            ads.mode = Mode.CONTINUOUS
            ads.comparator_mode = Comp_Mode.TRADITIONAL

            # ALRT pin
            import digitalio
            alrt = config.get_pin('plugins.current.hw.adc.alert-gpio')
            self.ready = digitalio.DigitalInOut(alrt)
            self.ready.direction = digitalio.Direction.INPUT

            from adafruit_ads1x15.analog_in import AnalogIn
            mapping = [ ADS.P0, ADS.P1, ADS.P2, ADS.P3 ]
            sensors = config.get('plugins.current.hw.sensors')
            for name, sensor in sensors.items():
                channels = [ mapping[pin] for pin in sensor["channel"] ]
                self.sensor[name] = SCT013(adc_config, AnalogIn(ads, *channels), sensor, name)

            self.simulated = False
        except:
            self.simulated = True

        # Quiet Current during simulation for debugging
        self.verbose = config.get_log_subsystem('current')

    # This method will be executed when the thread starts
    def run(self):
        log.info(self.message("Starting Current"))

        while True:
            info = {}
            for name, sensor in self.sensor.items():
                info[name] = round(sensor.sample(), 2)
                if self.verbose:
                    log.info(sensor)
            self.hook.record_meta(info=info)
            time.sleep(self.period)

currentObj = None

@hookimpl
def start_plugin():
    global currentObj
    currentObj = Current()
    currentObj.start()
