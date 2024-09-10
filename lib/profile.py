import config
import json
import os

import logging
logging.basicConfig(level=config.log_level, format=config.log_format)
log = logging.getLogger("kiln-controller")

profile_path = config.kiln_profiles_directory

def convert_to_c(profile):
    newdata=[]
    for (secs,temp) in profile["data"]:
        temp = (5/9)*(temp-32)
        newdata.append((secs,temp))
    profile["data"]=newdata
    return profile

def convert_to_f(profile):
    newdata=[]
    for (secs,temp) in profile["data"]:
        temp = ((9/5)*temp)+32
        newdata.append((secs,temp))
    profile["data"]=newdata
    return profile

def add_temp_units(profile):
    """
    always store the temperature in degrees c
    this way folks can share profiles
    """
    if "temp_units" in profile:
        return profile
    profile['temp_units']="c"
    if config.temp_scale=="c":
        return profile
    if config.temp_scale=="f":
        profile=convert_to_c(profile);
        return profile

def normalize_temp_units(profiles):
    normalized = []
    for profile in profiles:
        if "temp_units" in profile:
            if config.temp_scale == "f" and profile["temp_units"] == "c": 
                profile = convert_to_f(profile)
                profile["temp_units"] = "f"
        normalized.append(profile)
    return normalized

class Profile():
    def __init__(self, obj):
        self.name = obj["name"]
        self.data = sorted(obj["data"])

    @staticmethod
    def get_profiles():
        try:
            profile_files = os.listdir(profile_path)
        except:
            profile_files = []
        profiles = []
        for filename in profile_files:
            with open(os.path.join(profile_path, filename), 'r') as f:
                profiles.append(json.load(f))
        profiles = normalize_temp_units(profiles)
        return json.dumps(profiles)

    @staticmethod
    def find_profile(wanted):
        '''
        given a wanted profile name, find it and return the parsed
        json profile object or None.
        '''
        #load all profiles from disk
        profiles = get_profiles()
        json_profiles = json.loads(profiles)

        # find the wanted profile
        for profile in json_profiles:
            if profile['name'] == wanted:
                return profile
        return None

    @staticmethod
    def save_profile(profile, force=False):
        profile=add_temp_units(profile)
        profile_json = json.dumps(profile)
        filename = profile['name']+".json"
        filepath = os.path.join(profile_path, filename)
        if not force and os.path.exists(filepath):
            log.error("Could not write, %s already exists" % filepath)
            return False
        with open(filepath, 'w+') as f:
            f.write(profile_json)
            f.close()
        log.info("Wrote %s" % filepath)
        return True

    @staticmethod
    def delete_profile(profile):
        profile_json = json.dumps(profile)
        filename = profile['name']+".json"
        filepath = os.path.join(profile_path, filename)
        os.remove(filepath)
        log.info("Deleted %s" % filepath)
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
        if time > self.get_duration():
            return (None, None)

        prev_point = None
        next_point = None

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
