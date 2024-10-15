import logging
import math
import os
import yaml

log = logging.getLogger(__name__)

def convert_f2c(temp):
    return round((temp - 32) * 5 / 9)

def convert_c2f(temp):
    return math.ceil(temp * 9 / 5 + 32)

class SettingsError(Exception):
    def __init__(self, message):
        super().__init__(message)

class NoSettingError(SettingsError):
    def __init__(self, message):
        super().__init__(message)

class UnitError(SettingsError):
    def __init__(self, message):
        super().__init__(message)

class NoUnitError(SettingsError):
    def __init__(self, message):
        super().__init__(message)

class SettingToHighError(SettingsError):
    def __init__(self, message):
        super().__init__(message)

log_levels = {
        'NOTSET': logging.NOTSET,
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

class Settings(object):
    def __init__(self, filename: str='config.yaml'):
        with open(filename, 'r') as yfile:
            self.values = yaml.safe_load(yfile)
        self.filename = filename
        self.topdir = self.get('general.location.topdir',
                               os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
        self.tempunit = self.get('general.unit.temp', 'C').upper()
        self.timeunit = self.get('general.unit.time', 'm').lower()
        self.rateunit = 'p' + self.get('general.unit.rate', 'h').lower()

        self.log_verbose = self.get('general.logging.verbose')

    def set(self, name: str, value):
        try:
            keys = name.split('.')
            if len(keys[0]) == 0:
                self.values[name] = value
            else:
                value = self.values[0]
                for key in keys[1:-1]:
                    value = value[key]
                value[keys[-1]] = value
        except KeyError:
            raise NoSettingError("{}: Missing setting {}[{}]".format(name, value, key))

    def get(self, name: str, default=0, helpmsg="Missing configuration"):
        try:
            keys = name.split('.')
            value = self.values[keys[0]]
            for key in keys[1:]:
                value = value[key]
            if value == None:
                return default
            return value
        except KeyError:
            if default != None:
                return default
            raise NoSettingError("{}: {}".format(name, helpmsg))

    def get_location(self, name: str, default: str=None, helpmsg="Location is not found in settings"):
        value = self.get(name, default, helpmsg)
        if value == 'TOPDIR':
            value = self.topdir
        elif value[0] != '/':
            value = os.path.join(self.topdir, value)
        value = os.path.abspath(value)
        if os.path.exists(value):
            return value
        else:
            raise FileNotFoundError("{}: Directory doesn't exist: {}".format(name, value))

    def get_file_at_location(self, name: str, filename: str, default: str=None, helpmsg="Location is not found in settings"):
        path = self.get_location(name, default, helpmsg)
        filepath = os.path.abspath(os.path.join(path, filename))
        return filepath

    def get_log_level(self) -> str:
        return log_levels[self.get('general.logging.level', None, "Must be one of: " + " ".join(log_levels))]

    def get_log_subsystem(self, name:str) -> bool:
        return name in self.log_verbose

    def get_percent(self, name: str, default='100%', helpmsg: str="Missing percent in settings") -> float:
        value = self.get(name, None, helpmsg)
        if type(value) == str:
            if value[-1] == '%':
                return float(value[:-1]) / 100
            value = float(value)
        if value < 1:
            return value
        elif value <= 100:
            return value / 100
        else:
            raise SettingTooHigh("{}: Percentage is higher that 100%: {}".format(name, value))

    def c_to_tempunit(self, value):
        if self.tempunit == 'F':
            return convert_c2f(value)
        return value

    def temp_to_unit(self, value, fromunit=None, tounit='C'):
        fromunit = self.tempunit if fromunit == None else fromunit.upper()
        tounit = tounit.upper()
        if fromunit == tounit:
            return (value, tounit)
        elif fromunit == 'F' and tounit == 'C':
            return (convert_f2c(value), tounit)
        elif fromunit == 'C' and tounit == 'F':
            return (convert_c2f(value), tounit)

    def temp_in_unit(self, value):
        if value[-1] == 'F':
            value = int(value[:-1])
            if self.tempunit == 'C':
                return (convert_f2c(value), 'C')
            return (value, 'F')
        elif value[-1] == 'C':
            value = float(value[:-1])
            if self.tempunit == 'F':
                return (convert_c2f(value), 'F')
            return (value, 'C')
        else:
            raise UnitError("Invalid unit: {}".format(value))

    def get_temp(self, name: str, helpmsg="Missing temperature"):
        value = self.get(name, None, helpmsg).upper()
        try:
            return self.temp_in_unit(value)
        except NoUnitError:
            # If no unit given, assume set tempunit
            self.set(name, str(value) + self.tempunit)
            return (value, self.tempunit)

    def get_tempunit(self):
        return self.tempunit

    def is_temp_unit(self, unit: str) -> bool:
        return self.tempunit == unit.upper()

    def time_to_unit(self, value, fromunit, tounit):
        ''' value is only a number which will be changed to unit '''
        value = int(value)
        fromunit = fromunit.lower()
        tounit = tounit.lower()
        #print("Value: {}{} -> {}".format(value, fromunit, tounit))
        if fromunit[-1] == 's':
            if tounit[-1] == 's':
                return (value, tounit)
            elif tounit[-1] == 'm':
                return (value / 60, tounit)
            elif tounit[-1] == 'h':
                return (value / 3600, tounit)
            else:
                raise UnitError("Invalid unit: {}".format(unit))
        elif fromunit[-1] == 'm':
            if tounit[-1] == 's':
                return (value * 60, tounit)
            elif tounit[-1] == 'm':
                return (value, tounit)
            elif tounit[-1] == 'h':
                return (value / 60, tounit)
            else:
                raise UnitError("Invalid unit: {}".format(unit))
        elif fromunit[-1] == 'h':
            if tounit[-1] == 's':
                return (value * 3600, tounit)
            elif tounit[-1] == 'm':
                return (value * 60, tounit)
            elif tounit[-1] == 'h':
                return (value, tounit)
            else:
                raise UnitError("Invalid unit: {}".format(unit))
        else:
            raise NoUnitError("No unit: {}".format(value))

    def time_in_unit(self, value, unit):
        ''' value includes the unit which will be changed to the new unit '''
        value = value.lower()
        if value[-1] == 's':
            return self.time_to_unit(value[:-1], 's', unit)
        elif value[-1] == 'm':
            return self.time_to_unit(value[:-1], 'm', unit)
        elif value[-1] == 'h':
            return self.time_to_unit(value[:-1], 'h', unit)
        else:
            # Assume seconds
            return self.time_to_unit(value, 's', self.timeunit)

    def get_time_in_unit(self, name: str, unit: str, helpmsg="Missing time"):
        value = self.get(name, None, helpmsg)
        try:
            result = self.time_in_unit(value, unit)
            if result[1] == unit:
                return result[0]
            raise UnitError("Incorrect unit returned: {} -> {}".format(unit, result[1]))
        except NoUnitError:
            # If no unit given, assume set timeunit
            return value

    def get_time(self, name: str, helpmsg="Missing time"):
        return self.get_time_in_unit(name, self.timeunit, helpmsg)

    def get_timeunit(self):
        return self.timeunit

    def rate_in_unit(self, value):
        ''' value includes the unit which will be changed to the new unit '''
        value = value.lower()
        if value.endswith('ps'):
            return self.time_to_unit(value[:-2], 'ps', self.rateunit)
        elif value.endswith('pm'):
            return self.time_to_unit(value[:-2], 'pm', self.rateunit)
        elif value.endswith('ph'):
            return self.time_to_unit(value[:-2], 'ph', self.rateunit)
        else:
            # Assume seconds
            return self.time_to_unit(value, 'ps', self.rateunit)

    def get_rate(self, name: str, helpmsg="Missing rate"):
        value = self.get(name, None, helpmsg)
        try:
            return self.rate_in_unit(value)
        except NoUnitError:
            # If no unit given, assume set timeunit
            return (value, self.rateunit)

    def get_rateunit(self):
        return self.rateunit

    def get_pin(self, name: str, helpmsg="Missing pin assignment"):
        import board
        value = self.get(name, None, helpmsg).split('.')
        try:
            if value[0] == 'board':
                return board.__dict__[value[1]]
            else:
                raise NoSettingError("{}: Invalid board pin assignment".format(name))
        except IndexError:
            raise NoSettingError("{}: Invalid board pin assignment".format(name))

    def has_setting(self, *names) -> bool:
        try:
            for name in names:
                self.get(name, None, None)
            return True
        except KeyError:
            return False

config = Settings()
log_format = config.get('general.logging.format', None, "No log format specified")
logging.basicConfig(level=config.get_log_level(), format=log_format)

def test_settings():
    temp = config.get_temp('oven.emergency_shutoff_temp')
    print("oven.emergency_shutoff_temp: {}".format(temp))
    window = config.get_time('general.restart.window')
    print("general.restart.window: {}".format(window))
    window2 = config.time_to_unit(*window, 's')
    print("general.restart.window: {}".format(window2))
    print("Log Level: {}".format(config.get_log_level()))

if __name__ == "__main__":
    test_setting()
