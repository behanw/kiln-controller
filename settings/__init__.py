import math
import logging
import yaml

log = logging.getLogger(__name__)

def convert_f2c(temp):
    return round((temp - 32) * 5 / 9)

def convert_f2c(temp):
    return math.ceil(temp * 9 / 5 + 32)

class UnitError(Exception):
    def __init__(self, message):
        super().__init__(message)

class NoUnitError(Exception):
    def __init__(self, message):
        super().__init__(message)

class Settings(object):
    def __init__(self, filename: str='config.yaml'):
        with open(filename, 'r') as yfile:
            self.values = yaml.safe_load(yfile)
        self.filename = filename
        self.tempunit = self.get('general.unit.temp', 'C').upper()
        self.timeunit = self.get('general.unit.time', 'm').lower()
        self.rateunit = 'p' + self.get('general.unit.rate', 'h').lower()

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
            log.critical("{}: Missing setting {}[{}]".format(name, value, key))
            raise

    def get(self, name: str, default=0, helpmsg="Missing configuration"):
        try:
            keys = name.split('.')
            value = self.values[keys[0]]
            for key in keys[1:]:
                value = value[key]
            return value
        except KeyError:
            if default != None:
                return default
            elif helpmsg != None:
                log.critical("{}: {}".format(name, helpmsg))
            raise

    def temp_to_unit(self, value, unit='C'):
        unit = unit.upper()
        if self.tempunit == unit:
            return (value, unit)
        elif self.tempunit == 'F' and unit == 'C':
            return (convert_f2c(value), unit)
        elif self.tempunit == 'C' and unit == 'F':
            return (convert_c2f(value), unit)

    def temp_in_unit(self, value):
        if value[-1] == 'F':
            value = int(value[:-1])
            if self.tempunit == 'C':
                return (convert_f2c(value), 'C')
            return (value, 'F')
        elif value[-1] == 'C':
            value = int(value[:-1])
            if self.tempunit == 'F':
                return (convert_c2f(value), 'F')
            return (value, 'C')
        else:
            raise NoUnitError

    def get_temp(self, name: str, helpmsg="Missing temperature"):
        value = self.get(name, None, helpmsg).upper()
        try:
            return self.temp_in_unit(value)
        except NoUnitError:
            # If no unit given, assume set tempunit
            self.set(name, str(value) + self.tempunit)
            return (value, self.tempunit)

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

    def time_in_unit(self, value):
        ''' value includes the unit which will be changed to the new unit '''
        value = value.lower()
        if value[-1] == 's':
            return self.time_to_unit(value[:-1], 's', self.timeunit)
        elif value[-1] == 'm':
            return self.time_to_unit(value[:-1], 'm', self.timeunit)
        elif value[-1] == 'h':
            return self.time_to_unit(value[:-1], 'h', self.timeunit)
        else:
            # Assume seconds
            return self.time_to_unit(value, 's', self.timeunit)

    def get_time(self, name: str, helpmsg="Missing time"):
        value = self.get(name, None, helpmsg)
        try:
            return self.time_in_unit(value)
        except NoUnitError:
            # If no unit given, assume set timeunit
            return (value, self.timeunit)

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

    def has_setting(self, *names) -> bool:
        try:
            for name in names:
                self.get(name, None, None)
            return True
        except KeyError:
            return False

def test_settings():
    s = Settings()
    temp = s.get_temp('oven.emergency_shutoff_temp')
    print("oven.emergency_shutoff_temp: {}".format(temp))
    window = s.get_time('general.restart.window')
    print("general.restart.window: {}".format(window))
    window2 = s.time_to_unit(*window, 's')
    print("general.restart.window: {}".format(window2))

    #with open('config.yaml', 'r') as yfile:
    #    configs = yaml.safe_load(yfile)
    #for key in configs:
    #    print(key)

if __name__ == "__main__":
    test_setting()
