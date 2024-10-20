import logging
import datetime
import math
import time
import statistics

from settings import config, NoSettingError
from plugins import hookimpl, KilnPlugin, plugin_manager

log = logging.getLogger("plugins." + __name__)

time_step = config.get_time_in_unit('oven.duty_cycle', 's')
numsamples = config.get('plugins.thermocouple.temperature_average_samples', 10)
error_ignore_list = config.get('plugins.thermocouple.mitigations.ignore_errors')

class TempSamples(object):
    '''TempSamples averages thermocouple readings, calculates heating rate
    and error rate.
    '''

    status_labels = [ "Success", "Ignored", "Error" ]

    def __init__(self):
        self.rate_count = config.get('plugins.thermocouple.heat_rate_samples', 60)
        self.minconfidence = config.get_percent('plugins.thermocouple.mitigations.minimum_confidence', '30%') * 100
        self.confidence = 100 # 100%
        self.samples = []
        self.maxsamples = max(numsamples, self.rate_count)
        if time_step < 6:
            # After 2 duty cycles, readings are probably stale
            self.maxsamples *= 2

    def add(self, timestamp, temp, status):
        self.samples.append((timestamp, temp, status))
        self.samples = self.samples[-self.maxsamples:]

    def examine(self):
        count = 0
        timestamps = []
        temps = []
        status = [ 0, 0, 0]
        errors = {}

        for then, temp, error in self.samples:
            if error[0] == 0:
                status[0] += 1
                count += 1
                timestamps.append(then.timestamp())
                temps.append(temp)
            else:
                (code, message) = error
                status[code] += 1
                # Longest message before variable number is 41 chars
                errors[message[0:41]] = message

        return count, timestamps, temps, status, errors

    def high_confidence(self):
        return True if self.confidence() >= self.minconfidence else False

    def get(self):
        (count, timestamps, alltemps, status, errors) = self.examine()

        # Calculate median temperatures
        temp_start = max(0, count - numsamples)
        recent_samples = alltemps[temp_start:]
        avgtemp = statistics.median(recent_samples) if recent_samples else 0

        # Calculate heat rate
        if count < self.rate_count:
            heat_rate = 0
        else:
            rate_start = max(1, count - self.rate_count + 1)
            temps = alltemps[rate_start:]
            times = timestamps[rate_start:]
            heat_rate = round(3600 * (temps[-1] - temps[0]) / (times[-1] - times[0]))

        # Calculate recent confidence
        (good, ignored, fatal) = status
        self.confidence = round(100 * good / sum(status))

        return { 'temperature': avgtemp,
                'heat_rate': heat_rate,
                'confidence': self.confidence }


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

class Max31855_Error(ThermocoupleError):
    def __init__(self, message):
        super().__init__(message)

        if self.ignore \
                or self.is_ignored('Thermocouple not connected', 'ignore_tc_lost_connection') \
                or self.is_ignored('Short circuit', 'ignore_tc_short_errors') \
                or self.is_ignored('faulty reading', 'ignore_tc_faulty_reading') \
                or self.is_ignored('Total thermoelectric voltage out of range', 'ignore_tc_range_error'):
            self.ignore = True

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


class Thermocouple(KilnPlugin):
    '''Used by the Board class. Each Board must have
    a Thermocouple.
    '''
    def __init__(self, name: str, offset=0):
        super().__init__('Thermocouple.' + name)
        self.offset = offset

        self.emergency_shutoff_temp = config.get_temp('oven.emergency_shutoff_temp')[0]

class ThermocoupleSimulated(Thermocouple):
    '''Simulates a temperature sensor '''
    def __init__(self, name: str, offset=0):
        super().__init__(name, offset)
        self.simulated_temperature = config.get_temp('oven.simulation.t_env')[0]

    def get_temperature(self):
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

    def is_too_hot(self, temp) -> bool:
        '''reset i the temperature is way TOO HOT, or other critical errors detected'''
        if (temp >= self.emergency_shutoff_temp):
            if 'ignore_temp_too_high' not in error_ignore_list:
                log.critical("Emergency!!! temperature too high")
                self.hook.failure(info={
                    "reason": "Emergency!!! temperature too high",
                    "pattern": "fail2"
                })
                self.abort_run()
                return True
            else:
                log.warning("Temperature too high")
        return False

    def too_many_Errors(self, temp):
        if self.board.thermocouple.status.high_confidence():
            return False
        log.critical("Emergency!!! too many errors in a short period")
        self.hook.failure(info={
            "reason": "Emergency!!! too many errors in a short period",
            "pattern": "fail3"
            })
        if 'ignore_tc_too_many_errors' not in error_ignore_list:
            self.abort_run()
        return True

    def get_temperature(self):
        return self.samples.get()

    def sample_temperature(self, timestamp):
        '''read temp from tc and convert if needed'''
        try:
            sample = math.ceil(config.c_to_tempunit(self.raw_temp()) + self.offset)
            self.samples.add(timestamp, sample, (0, "Success"))
        except ThermocoupleError as tce:
            if tce.ignore:
                log.error("Problem reading temp (ignored) {}".format(tce.message))
                self.samples.add(timestamp, 0, (1, str(tce.message)))
            else:
                log.error("Problem reading temp {}".format(tce.message))
                self.samples.add(timestamp, 0, (2, str(tce.message)))

    def run(self):
        log.info(self.message("Starting Thermocouple: " + self.name))
        sleeptime = time_step / numsamples
        while True:
            for i in range(0, numsamples):
                then = datetime.datetime.now()
                self.sample_temperature(then)
                since_then = (datetime.datetime.now() - then).total_seconds()
                time.sleep(sleeptime - since_then)

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

def list_median(base, key):
        return statistics.median([base[n][key] for n in base.keys()])

def list_mean(base, key):
        return statistics.mean([base[n][key] for n in base.keys()])

def list_min(base, key):
        return min([base[n][key] for n in base.keys()])

class Thermocouples(KilnPlugin):
    def __init__(self):
        super().__init__('thermocouples')
        self.thermocouples = {}

        self.verbose = config.get_log_subsystem('thermocouple')

        interfaces = {
                "max31855": Max31855,
                "max31856": Max31856,
                }

        sensors = config.get('plugins.thermocouple.hw.device', None, 'No Sensors specified in config')
        for name, sensor in sensors.items():
            if config.get('general.simulate', False):
                thermocouple = ThermocoupleSimulated(name, 0)
            elif sensor['chip'] == 'simulated':
                thermocouple = ThermocoupleSimulated(name, sensor['offset'])
            else:
                try:
                    chip = interfaces[sensor['chip']]
                    chipselect = config.get_pin('plugins.thermocouple.hw.device.{}.chipselect'.format(name)) 
                    thermocouple = chip(name, chipselect, sensor['type'], sensor['offset'])
                except (AttributeError, KeyError) as error:
                    raise ThermocoupleError("Thermocouple configuration error: {}".format(error))
            self.thermocouples[name] = thermocouple
            plugin_manager.register(thermocouple)

    def report_readings(self, now):
        info = {
                'timestamp': now,
                'thermocouple': {}
                }
        for name, sensor in self.thermocouples.items():
            info['thermocouple'][name] = sensor.get_temperature()
        info['temperature'] = round(list_median(info['thermocouple'], 'temperature'),1)
        #info['heat_offset'] = round(list_mean(info['thermocouple'], 'heat_offset'),1)
        info['heat_rate'] = round(list_mean(info['thermocouple'], 'heat_rate'),1)
        info['confidence'] = list_min(info['thermocouple'], 'confidence')
        self.hook.temperature_reading(info=info)

    def run(self):
        log.info(self.message("Starting Thermocouple polling"))
        time.sleep(time_step)
        while True:
            then = datetime.datetime.now()
            self.report_readings(then.timestamp())

            since_then = (datetime.datetime.now() - then).total_seconds()
            if since_then < time_step:
                time.sleep(time_step - since_then)
            else:
                log.warning("Ran out of time reading thermocouples. Possible time skew")

    @hookimpl
    def start_plugin(self):
        for sensor in self.thermocouples.values():
            sensor.start()
        self.start()

plugin_manager.register(Thermocouples())
