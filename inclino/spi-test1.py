#!/usr/bin/env python3

import spidev
import time

spi = spidev.SpiDev(0, 0) # create spi object connecting to /dev/spidev0.0
spi.max_speed_hz = 2000000 # set speed to 2 Mhz

try:
    while True: # endless loop, press Ctrl+C to exit
        spi.writebytes([0x3A]) # write one byte
        time.sleep(0.1) # sleep for 0.1 seconds
finally:
    spi.close() # always close the port before exit
