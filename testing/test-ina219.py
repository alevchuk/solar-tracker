#!/usr/bin/env python

from shutil import get_terminal_size

# Advanced - Manual Gain, High Resolution Example

from ina219 import INA219
from ina219 import DeviceRangeError
import time

# Set the constants that were calculated
SHUNT_MV = 75
MAX_EXPECTED_AMPS = 100
SHUNT_OHMS = (SHUNT_MV / 1000) / MAX_EXPECTED_AMPS  # R = V / i

#SHUNT_OHMS = 0.00075
print(SHUNT_OHMS)

def read():
	# Instantiate the ina object with the above constants
    ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, address=0x40)
	# Configure the object with the expected bus voltage
	# (either up to 16V or up to 32V with .RANGE_32V)
	# Also, configure the gain to be GAIN_2_80MW for the above example
    ina.configure(
            voltage_range=ina.RANGE_32V,
    )

	# Prints the values to the console
    #print("Voltage: %.3f V" % ina.voltage())
    try:
        #print("Power: %.3f W" % (ina.power() / 1000), end = " ")
        print("Power: {} mW".format(ina.power()), end = " ")
        term_width = get_terminal_size()[0]
        ratio = (ina.power() / 1000) / 100
        if ratio > 1:
            ratio = 1

        print("*" * int(term_width * ratio))


        #print("Current: %.3f A" % (ina.current() / 1000))
        #print("Power: %.3f W" % (ina.power() / 1000))
        #print("Shunt voltage: %.3f mV" % (ina.shunt_voltage()))
    except DeviceRangeError as e:
        print("Current overflow")


if __name__ == "__main__":
    while True:
        read()
        time.sleep(0.1)
