#!/usr/bin/env python

import RPi.GPIO as GPIO
import time

ret_channel = 20
ext_channel = 21
sleep_time = 20

def setup(channel):
    # GPIO setup
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(channel, GPIO.OUT)


def motor_on(pin):
    GPIO.output(pin, GPIO.HIGH)  # Turn motor on


def motor_off(pin):
    GPIO.output(pin, GPIO.LOW)  # Turn motor off


def test(channel):
    setup(channel)
    motor_on(channel)
    time.sleep(sleep_time)
    motor_off(channel)
    time.sleep(sleep_time)

if __name__ == '__main__':
    try:
        channel = ret_channel
        setup(channel)
        motor_on(channel)
        time.sleep(sleep_time)
        motor_off(channel)

        #test(ret_channel)
        #test(ext_channel)

        GPIO.cleanup()
    except KeyboardInterrupt:
        GPIO.cleanup()
