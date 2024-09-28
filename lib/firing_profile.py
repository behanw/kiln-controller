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

def convert_profile(profile, converto):
    if profile["temp_units"] == converto:
        return profile
    profile["data"] = [ [duration, convert_temp(temp, converto)] for (duration, temp) in profile["data"] ]
    profile["temp_units"] = converto
    return profile

def convert_to_temp_scale(profile):
    if "temp_units" not in profile:
        profile["temp_units"] = 'f'
    if config.temp_scale == profile["temp_units"]:
        return profile
    elif config.temp_scale == 'f' and profile["temp_units"] == 'c':
        return convert_profile(profile, 'f')
    else:
        return convert_profile(profile, 'c')

def add_temp_units(profile):
    """
    always store the temperature in degrees c
    this way folks can share profiles
    """
    profile['temp_units'] = config.temp_scale
    return convert_profile(profile, 'c')

def get_filename(name):
    if not name.endswith(".json"):
        name += ".json"
    return os.path.join(config.kiln_profiles_directory, name)

def read_profile(name):
    with open(get_filename(name), 'r') as f:
        return(convert_to_temp_scale(json.load(f)))

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

    @staticmethod
    def get_all_json():
        return json.dumps(read_all())

    @staticmethod
    def load(name):
        return Firing_Profile(read_profile(name))

    @staticmethod
    def save(profile, force=True):
        filepath = get_filename(profile["name"])
        if not force and os.path.exists(filepath):
            log.error("Could not write, {} already exists".format(filepath))
            return False
        with open(filepath, 'w+') as f:
            f.write(json.dumps(add_temp_units(profile)))
        log.info("Wrote {}".format(filepath))
        return True

    @staticmethod
    def delete(profile):
        filepath = get_filename(profile["name"])
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
