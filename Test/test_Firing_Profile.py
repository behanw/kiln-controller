import os
import sys
import json
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.firing_profile import Firing_Profile
import config
config.kiln_profiles_directory = os.path.abspath(os.path.dirname(__file__))

def get_profile(file = "test-fast", unit = "c"):
    config.temp_scale = unit
    return Firing_Profile.load(file)


def test_load_save_profile():
    try:
        all_profiles = Firing_Profile.get_all_json()
    except FileNotFoundError:
        assert False
    else:
        assert True

    profile_name = "temporary_test_file"
    obj = json.loads(all_profiles)
    test_profile = obj[0]
    test_profile["name"] = profile_name

    # Make sure test_profile isn't empty
    test_json = json.dumps(test_profile)
    assert len(test_json) > 10

    # Make sure test_profile is valid JSON
    assert json.loads(test_json)

    assert Firing_Profile.save(test_profile)

    profile = get_profile(profile_name)
    assert profile.data == test_profile["data"]

    assert Firing_Profile.delete(test_profile)
    try:
        profile = get_profile(profile_name)
    except FileNotFoundError:
        assert True
    else:
        assert False


def test_temp_units():
    profile = get_profile()

    assert profile.unit == "c"

    profile = get_profile(unit = "f")

    assert profile.unit == "f"


def test_get_target_temperature():
    profile = get_profile()

    temperature = profile.get_target_temperature(3000)
    assert int(temperature) == 93

    temperature = profile.get_target_temperature(6004)
    assert math.ceil(temperature) == 427

    profile = get_profile(unit = "f")

    temperature = profile.get_target_temperature(3000)
    assert int(temperature) == 200

    temperature = profile.get_target_temperature(6004)
    assert temperature == 801.0


def test_find_time_from_temperature():
    profile = get_profile()

    time = profile.find_next_time_from_temperature(260)
    assert round(time) == 4802

    time = profile.find_next_time_from_temperature(1096)
    assert round(time) == 10878

    time = profile.find_next_time_from_temperature(1038)
    assert round(time) == 10404

    profile = get_profile(unit = "f")

    time = profile.find_next_time_from_temperature(500)
    assert time == 4800

    time = profile.find_next_time_from_temperature(2004)
    assert time == 10857.6

    time = profile.find_next_time_from_temperature(1900)
    assert time == 10400.0


def test_find_time_odd_profile():
    profile = get_profile("test-cases")

    time = profile.find_next_time_from_temperature(260)
    assert time == 4200

    time = profile.find_next_time_from_temperature(1106)
    assert round(time) == 16681

    profile = get_profile("test-cases", "f")

    time = profile.find_next_time_from_temperature(500)
    assert time == 4200

    time = profile.find_next_time_from_temperature(2023)
    assert time == 16676.0


def test_find_x_given_y_on_line_from_two_points():
    profile = get_profile(unit = "f")

    y = 500
    p1 = [3600, 200]
    p2 = [10800, 2000]
    time = profile.find_x_given_y_on_line_from_two_points(y, p1, p2)

    assert time == 4800

    y = 500
    p1 = [3600, 200]
    p2 = [10800, 200]
    time = profile.find_x_given_y_on_line_from_two_points(y, p1, p2)

    assert time == 0

    y = 500
    p1 = [3600, 600]
    p2 = [10800, 600]
    time = profile.find_x_given_y_on_line_from_two_points(y, p1, p2)

    assert time == 0

    y = 500
    p1 = [3600, 500]
    p2 = [10800, 500]
    time = profile.find_x_given_y_on_line_from_two_points(y, p1, p2)

    assert time == 0


