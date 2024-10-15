import config
import json
import math
import os

import logging
logging.basicConfig(level=config.log_level, format=config.log_format)
log = logging.getLogger("kiln-controller")

def convert_temp(temp, converto):
    if converto == 'c':
        temp = round((temp - 32) * 5 / 9)
    else:
        temp = math.ceil(temp * 9 / 5 + 32)
    return temp

def convert_profile(fprofile, converto):
    if fprofile["temp_units"] == converto:
        return fprofile
    fprofile["data"] = [ [duration, convert_temp(temp, converto)] for (duration, temp) in fprofile["data"] ]
    fprofile["temp_units"] = converto
    return fprofile

def convert_to_temp_scale(fprofile):
    if "temp_units" not in fprofile:
        fprofile["temp_units"] = 'f'
    if config.temp_scale == fprofile["temp_units"]:
        return fprofile
    elif config.temp_scale == 'f' and fprofile["temp_units"] == 'c':
        return convert_profile(fprofile, 'f')
    else:
        return convert_profile(fprofile, 'c')

def add_temp_units(fprofile):
    """
    always store the temperature in degrees c
    this way folks can share profiles
    """
    fprofile['temp_units'] = config.temp_scale
    return convert_profile(fprofile, 'c')

def add_rate(fprofile):
    data = fprofile["data"]
    last = len(data)
    hold = 0
    rates = []
    for i in range(1, last):
        if hold > 0:
            hold = 0
            continue
        temp = data[i][1]
        secs = data[i][0]
        since = secs - data[i-1][0]
        rate = round(3600 * (temp - data[i-1][1]) / since)
        if rate == 0:
            rates.append((0, temp, since))
        else:
            if i+1 < last and hold == 0 and temp == data[i+1][1]:
                hold = data[i+1][0] - secs
                rates.append((rate, temp, hold))
            else:
                rates.append((rate, temp, 0))
    fprofile["rates"] = rates
    return fprofile

def get_filename(name):
    if not name.endswith(".json"):
        name += ".json"
    return os.path.join(config.kiln_profiles_directory, name)

def read_profile(name):
    with open(get_filename(name), 'r') as f:
        return(add_rate(convert_to_temp_scale(json.load(f))))

def read_all():
    return [ read_profile(name) for name in os.listdir(config.kiln_profiles_directory) if name.endswith(".json") ]

class Firing_Profile():
    """The Firing_Profile Class"""
    def __init__(self, obj):
        self.name = obj["name"]
        self.data = sorted(obj["data"])
        try:
            self.unit = obj["temp_units"]
        except:
            self.unit = "f"

    def __repr__(self):
        return self.name

    @staticmethod
    def get_all_json():
        return json.dumps(read_all())

    @staticmethod
    def load(name):
        return Firing_Profile(read_profile(name))

    @staticmethod
    def save(fprofile, force=True):
        filepath = get_filename(fprofile["name"])
        if not force and os.path.exists(filepath):
            log.error("Could not write, {} already exists".format(filepath))
            return False
        with open(filepath, 'w+') as f:
            f.write(json.dumps(add_temp_units(fprofile)))
        log.info("Wrote {}".format(filepath))
        return True

    @staticmethod
    def delete(fprofile):
        filepath = get_filename(fprofile["name"])
        os.remove(filepath)
        log.info("Deleted {}".format(filepath))
        return True

    def get_duration(self):
        return max([t for (t, x) in self.data])

    #  x = (y-y1)(x2-x1)/(y2-y1) + x1
    @staticmethod
    def find_x_given_y_on_line_from_two_points(y, point1, point2):
        if point1[0] > point2[0]: return 0  # time2 before time1 makes no sense in kiln segment
        if point1[1] >= point2[1]: return 0 # Zero will crach. Negative temeporature slope, we don't want to seek a time.
        x = (y - point1[1]) * (point2[0] -point1[0] ) / (point2[1] - point1[1]) + point1[0]
        return x

    def find_next_time_from_temperature(self, temperature):
        time = 0 # The seek function will not do anything if this returns zero, no useful intersection was found
        for index, point2 in enumerate(self.data):
            if point2[1] >= temperature:
                if index > 0: #  Zero here would be before the first segment
                    if self.data[index - 1][1] <= temperature: # We have an intersection
                        time = self.find_x_given_y_on_line_from_two_points(temperature, self.data[index - 1], point2)
                        if time == 0:
                            if self.data[index - 1][1] == point2[1]: # It's a flat segment that matches the temperature
                                time = self.data[index - 1][0]
                                break

        return time

    def get_surrounding_points(self, time):
        prev_point = None
        next_point = None

        if time <= self.get_duration():
            for i in range(len(self.data)):
                if time < self.data[i][0]:
                    prev_point = self.data[i-1]
                    next_point = self.data[i]
                    break

        return (prev_point, next_point)

    def get_target_temperature(self, time):
        if time > self.get_duration():
            return 0

        (prev_point, next_point) = self.get_surrounding_points(time)

        incl = float(next_point[1] - prev_point[1]) / float(next_point[0] - prev_point[0])
        temp = prev_point[1] + (time - prev_point[0]) * incl
        return temp

    def get_start_from_temperature(self, temp):
        target_temp = self.get_target_temperature(0)
        if temp > target_temp + 5:
            startat = self.find_next_time_from_temperature(temp)
            log.info("seek_start is in effect, starting at: {} s, {} deg".format(round(startat), round(temp)))
            return startat
        return 0
