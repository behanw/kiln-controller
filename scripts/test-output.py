#!/usr/bin/env python
import config
import adafruit_max31855
import digitalio
import time
import datetime

try:
    import board
except NotImplementedError:
    print("not running a recognized blinka board, exiting...")
    import sys
    sys.exit()

########################################################################
#
# To test your gpio output to control a relay...
#
# Edit config.py and set the following in that file to match your
# hardware setup: gpio_heat, gpio_heat_invert
#
# then run this script...
# 
# ./scripts/test-output.py
#
# This will switch the output on for five seconds and then off for five 
# seconds. Measure the voltage between the output and any ground pin.
# You can also run ./scripts/gpioreadall.py in another window to see the voltage
# on your configured pin change.
########################################################################

heater = digitalio.DigitalInOut(config.gpio_heat)
heater.direction = digitalio.Direction.OUTPUT
off = config.gpio_heat_invert
on = not off

print("\nboard: %s" % (board.board_id))
print("heater configured as config.gpio_heat = %s BCM pin\n" % (config.gpio_heat))
print("heater output pin configured as invert = %r\n" % (config.gpio_heat_invert))

while True:
    heater.value = on
    print("%s heater on" % datetime.datetime.now())
    time.sleep(5)
    heater.value = off
    print("%s heater off" % datetime.datetime.now())
    time.sleep(5)
