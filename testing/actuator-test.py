#!/usr/bin/env python

import RPi.GPIO as GPIO
import time

ret_channel = 20
ext_channel = 21
sleep_time = 0.5

def setup(channel):
    # GPIO setup
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(channel, GPIO.OUT)


def motor_on(pin):
    GPIO.output(pin, GPIO.HIGH)  # Turn motor on


def motor_off(pin):
    GPIO.output(pin, GPIO.LOW)  # Turn motor off


if __name__ == '__main__':
    try:

        while True:
            # both off
            print("both off")
            time.sleep(sleep_time)

            # retract
            print("ret")
            channel = ret_channel
            setup(channel)
            motor_on(channel)
            time.sleep(sleep_time)
            motor_off(channel)

            # # extend
            # print("ext")
            # channel = ext_channel
            # setup(channel)
            # motor_on(channel)
            # time.sleep(sleep_time)
            # motor_off(channel)
    
            ### both on
            #print("both on")
            #setup(ext_channel)
            #setup(ret_channel)
            #motor_on(ext_channel)
            #motor_on(ret_channel)
            #time.sleep(sleep_time)
            #motor_off(ext_channel)
            #motor_off(ret_channel)
    
            GPIO.cleanup()



    except KeyboardInterrupt:
        GPIO.cleanup()
