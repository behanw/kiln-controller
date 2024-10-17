import logging
import datetime
import math
import time
import statistics

from settings import config, NoSettingError

log = logging.getLogger("plugins." + __name__)

class TempSamples(object):
    '''TempSamples averages thermocouple readings and calculates heating rate.
    '''
    def __init__(self):
        self.samples = []

        self.temp_count = config.get('plugins.thermocouple.temperature_average_samples', 10)
        self.rate_count = config.get('plugins.thermocouple.heat_rate_samples', 60)

        self.count = max(self.temp_count, self.rate_count)

    def add(self, timestamp, temp):
        self.samples.append((timestamp, temp))
        self.samples = self.samples[-self.count:]

    def getavg(self):
        count = len(self.samples)
        temp_start = max(0, count - self.temp_count)
        rate_start = max(1, count - self.rate_count + 1)

        # The median temperature is more reliable than the mean
        temps = [self.samples[i][1] for i in range(temp_start, count)]
        avgtemp = statistics.median(temps) if temps else 0

        #log.info(self.samples)
        rates = [(self.samples[i][1] - self.samples[i-1][1]) * 3600 /
                 (self.samples[i][0] - self.samples[i-1][0]).total_seconds()
                 for i in range(rate_start, count)]
        #medianrate = statistics.median(rates) if rates else 0
        meanrate = statistics.mean(rates) if rates else 0
        #interval = 3600 * (self.samples[-1][1] - self.samples[0][1]) / (self.samples[-1][0] - self.samples[0][0]).total_seconds()
        #log.info("Heat Rate -> Count: {}  Median: {}  Mean: {}  Interval: {}".format(count, round(medianrate), round(meanrate), round(interval)))
        avgrate = meanrate

        return { 'temperature': avgtemp, 'heat_rate': avgrate }

class ThermocoupleStatus(object):
    '''Keeps sliding window to track successful/failed calls to get temp
       over the last two duty cycles.
    '''
    def __init__(self):
        self.limit = config.get('plugins.thermocouple.error_limit', 30)
        self.size = config.get('plugins.thermocouple.temperature_average_samples', 10) * 2
        self.status = [True for i in range(self.size)]

    def good(self):
        '''True is good!'''
        self.status.append(True)
        del self.status[0]

    def bad(self):
        '''False is bad!'''
        self.status.append(False)
        del self.status[0]

    def error_percent(self):
        errors = sum(i == False for i in self.status)
        return (errors / self.size) * 100

    def over_error_limit(self):
        if self.error_percent() > self.limit:
            return True
        return False

class Thermocouple(object):
    '''Used by the Board class. Each Board must have
    a Thermocouple.
    '''
    def __init__(self, name: str, offset=0):
        super().__init__()
        self.name = name
        self.offset = offset
        self.status = ThermocoupleStatus()

class ThermocoupleSimulated(Thermocouple):
    '''Simulates a temperature sensor '''
    def __init__(self, name: str, offset=0):
        super().__init__(name, offset)
        self.simulated_temperature = config.get_temp('oven.simulation.t_env')[0]

    def temperature(self):
        return self.simulated_temperature

class ThermocoupleReal(Thermocouple):
    '''real temperature sensor that takes many measurements
       during the time_step
       inputs
    '''
    def __init__(self, name: str, chipselect, offset=0):
        super().__init__(name, offset)
        self.samples = TempSamples()

        self.spi_setup()
        import digitalio
        self.chipselect = chipselect
        self.cs = digitalio.DigitalInOut(self.chipselect)

    def spi_setup(self):
        try:
            import adafruit_bitbangio as bitbangio
            sclk = config.get_pin('plugins.thermocouple.hw.spi.sclk')
            mosi = config.get_pin('plugins.thermocouple.hw.spi.mosi')
            miso = config.get_pin('plugins.thermocouple.hw.spi.miso')
            self.spi = bitbangio.SPI(sclk, mosi, miso)
            log.info("Software/Bit-bang SPI selected for reading thermocouple")
        except NoSettingError:
            try:
                import board
                self.spi = board.SPI();
                log.info("Hardware SPI selected for reading thermocouple")
            except:
                raise FileNotFoundError("No SPI found or configured")

    def sample_temperature(self, timestamp):
        '''read temp from tc and convert if needed'''
        try:
            sample = math.ceil(config.c_to_tempunit(self.raw_temp()) + self.offset)
            self.samples.add(timestamp, sample)
            self.status.good()
        except ThermocoupleError as tce:
            if tce.ignore:
                log.error("Problem reading temp (ignored) {}".format(tce.message))
                self.status.good()
            else:
                log.error("Problem reading temp {}".format(tce.message))
                self.status.bad()
        return None

    def get_temperature(self):
        return self.samples.getavg()

    def temperature(self):
        '''average temp over a duty cycle'''
        return self.averagetemp.get_temp()

error_ignore_list = config.get('plugins.thermocouple.mitigations.ignore_errors')

class ThermocoupleError(Exception):
    '''
    thermocouple exception parent class to handle mapping of error messages
    and make them consistent across adafruit libraries. Also set whether
    each exception should be ignored based on settings in config.yaml.
    '''
    def __init__(self, message):
        super().__init__(message)
        self.message = message
        self.ignore = False

        if self.message.startswith('Unsupported'):
            pass
        elif self.is_ignored('Not connected', 'ignore_tc_lost_connection') \
                or self.is_ignored('Unknown', 'ignore_tc_unknown_error'):
            self.ignore = True

    def is_ignored(self, error, flag, replacement=None):
        if self.message.startswith(error):
            if replacement:
                self.message = replacement
            return flag in error_ignore_list
        return False


class Max31855(ThermocoupleReal):
    '''Each subclass expected to handle errors and get temperature
    The Max31855 only accepts K-type thermocouples.
    '''
    def __init__(self, name: str, chipselect, typecode: str="K", offset=0):
        super().__init__(name, chipselect, offset)
        log.info("Thermocouple MAX31855")

        import adafruit_max31855
        self.thermocouple = adafruit_max31855.MAX31855(self.spi, self.cs)

    def raw_temp(self):
        try:
            return self.thermocouple.temperature_NIST
        except RuntimeError as rte:
            #print("My ERROR: {}".format(rte.args[0]))
            if rte.args and rte.args[0]:
                raise Max31855_Error(rte.args[0])
            raise Max31855_Error('unknown')

class Max31855_Error(ThermocoupleError):
    def __init__(self, message):
        super().__init__(message)

        if self.ignored \
                or self.is_ignored('Thermocouple not connected', 'ignore_tc_lost_connection') \
                or self.is_ignored('Short circuit', 'ignore_tc_short_errors') \
                or self.is_ignored('faulty reading', 'ignore_tc_faulty_reading') \
                or self.is_ignored('Total thermoelectric voltage out of range', 'ignore_tc_range_error'):
            self.ignored = True

class Max31856(ThermocoupleReal):
    '''each subclass expected to handle errors and get temperature'''
    def __init__(self, name: str, chipselect, typecode: str="K", offset=0):
        super().__init__(name, chipselect, offset)
        log.info("Thermocouple MAX31856")

        import adafruit_max31856
        self.thermocouple = adafruit_max31856.MAX31856(self.spi, self.cs,
                               thermocouple_type=self.thermo_type(typecode))

        freq = config.get('plugins.thermocouple.mitigations.ac_freq_hz', 60,
                          "ac_freq_hz not set in config. Assuming 60Hz")
        if freq in [50, 60]:
            self.thermocouple.noise_rejection = freqs[freq]
        else:
            raise Max31856_Error(
                "Unsupported ac_freq_hz (must be 50 or 60): {}".format(freq))

    def thermo_type(self, typecode: str):
        # Here are the possible max-31856 thermocouple types
        types = {
                "B": adafruit_max31856.ThermocoupleType.B,
                "E": adafruit_max31856.ThermocoupleType.E,
                "J": adafruit_max31856.ThermocoupleType.J,
                "K": adafruit_max31856.ThermocoupleType.K,
                "N": adafruit_max31856.ThermocoupleType.N,
                "R": adafruit_max31856.ThermocoupleType.R,
                "S": adafruit_max31856.ThermocoupleType.S,
                "T": adafruit_max31856.ThermocoupleType.T,
                }
        if typecode in types:
            return types[typecode]
        else:
            raise Max31856_Error("Unsupported Thermocouple")

    def raw_temp(self):
        # The underlying adafruit library does not throw exceptions
        # for thermocouple errors. Instead, they are stored in
        # dict named self.thermocouple.fault. Here we check that
        # dict for errors and raise an exception.
        # and raise Max31856_Error(message)
        temp = self.thermocouple.temperature
        for k, v in self.thermocouple.fault.items():
            if v:
                raise Max31856_Error(k)
        return temp

class Max31856_Error(ThermocoupleError):
    def __init__(self, message):
        super().__init__(message)

        if self.message == 'not_supported':
            self.message = 'Unsupported Thermocouple'
        if self.ignored \
                or self.is_ignored('cj_high', 'ignore_tc_cold_junction_temp_high', 'Cold junctuin temp too high') \
                or self.is_ignored('cj_low', 'ignore_tc_cold_junction_temp_low', 'Cold junctuin temp too low') \
                or self.is_ignored('cj_range', 'ignore_tc_cold_junction_range_error', 'Cold junctuin range fault') \
                or self.is_ignored('open_tc', 'ignore_tc_lost_connection', 'Not connected') \
                or self.is_ignored('tc_high', 'ignore_tc_temp_high', 'Thermocouple temp too high') \
                or self.is_ignored('tc_low', 'ignore_tc_temp_low', 'Thermocouple temp too low') \
                or self.is_ignored('tc_range', 'ignore_tc_range_error', 'Thermocouple range fault') \
                or self.is_ignored('voltage', 'ignore_tc_voltage_error', 'Voltage too high or low'):
            self.ignored = True


from plugins import hookimpl, KilnPlugin

class Thermocouples(KilnPlugin):
    def __init__(self):
        super().__init__(__name__)
        self.thermocouples = []

        self.verbose = config.get_log_subsystem('thermocouple')

        self.time_step = config.get('oven.duty_cycle')
        self.numsamples = config.get('plugins.thermocouple.temperature_average_samples', 10)
        self.sleeptime = self.time_step / self.numsamples
        self.emergency_shutoff_temp = config.get_temp('oven.emergency_shutoff_temp')

        interfaces = {
                "max31855": Max31855,
                "max31856": Max31856,
                }

        sensors = config.get('plugins.thermocouple.hw.device', None, 'No Sensors specified in config')
        for name, sensor in sensors.items():
            (chip, chipselect, thermo, offset) = sensor
            try:
                if config.get('general.simulate', False):
                    self.thermocouples.append(ThermocoupleSimulated(name, 0))
                else:
                    chip = interfaces[sensor['chip']]
                    chipselect = config.get_pin('plugins.thermocouple.hw.device.{}.chipselect'.format(name)) 
                    self.thermocouples.append(chip(name, chipselect, sensor['type'], sensor['offset']))
            except (AttributeError, KeyError) as error:
                raise ThermocoupleError("Thermocouple configuration error: {}".format(error))

    def is_too_hot(self):
        '''reset if the temperature is way TOO HOT, or other critical errors detected'''
        if (temp >= self.emergency_shutoff_temp):
            log.critical("Emergency!!! temperature too high")
            self.hook.failure(info={
                "reason": "Emergency!!! temperature too high",
                "pattern": "fail2"
                })
            if 'ignore_temp_too_high' not in error_ignore_list:
                self.abort_run()

        elif self.board.thermocouple.status.over_error_limit():
            log.critical("Emergency!!! too many errors in a short period")
            self.hook.failure(info={
                "reason": "Emergency!!! too many errors in a short period",
                "pattern": "fail3"
                })
            if 'ignore_tc_too_many_errors' not in error_ignore_list:
                self.abort_run()


    def run(self):
        while True:
            start = datetime.datetime.now()

            for i in range(0, self.numsamples):
                then = datetime.datetime.now()
                for sensor in self.thermocouples:
                    #timestamp = self.hook.get_time()
                    #log.info("**** time: {}".format(timestamp))
                    #timestamp = timestamp[0]['runtime']
                    #timestamp = self.hook.get_time()[0]['runtime']
                    #log.info("**** time: {}".format(timestamp))
                    sensor.sample_temperature(then)
                if i < self.numsamples - 1:
                    now = datetime.datetime.now()
                    sleepy = self.sleeptime - (now - then).total_seconds()
                    time.sleep(sleepy)

            thermos = {}
            tempsum = 0
            ratesum = 0
            for sensor in self.thermocouples:
                meta = sensor.get_temperature()
                tempsum += meta['temperature']
                ratesum += meta['heat_rate']
                thermos[sensor.name] = meta

            count = len(self.thermocouples)
            now = datetime.datetime.now()
            info = {
                    'timestamp': now,
                    'temperature': tempsum / count,
                    'heat_rate': ratesum / count,
                    'thermocouples': thermos,
                }
            self.hook.record_temperature(info=info)

            sleepy = self.time_step - (now - start).total_seconds()
            #log.info("Sleep {} of {} info = {}".format(sleepy, self.time_step, info))
            if sleepy > 0:
                time.sleep(sleepy)
            else:
                log.warning("Ran out of time reading thermocouples.")

thermocoupleObj = None

@hookimpl
def start_plugin():
    global thermocoupleObj
    thermocoupleObj = Thermocouples()
    thermocoupleObj.start()
