import os
import sys
import json
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kilnapp.thermocouple import Thermocouple
import config

config.simulate = True

def get_thermocouple():
    return Thermocouple.get()

def test_thermocouple():
    thermocouple = get_thermocouple()
    temp = thermocouple.temperature()
    assert temp == config.sim_t_env
