#!/usr/bin/env python3

import json
import sys
import math
import sys
import time
import os
from shutil import get_terminal_size

import threading
import socket
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

import logging

import RPi.GPIO as GPIO
import time
import random

SENSOR_PORT = 2017
MEASUREMENTS_FILE = "/home/pi/measurements.txt"

HOME = os.path.expanduser("~")

START_TIME = time.time()
def log(text):
    seconds_since_start = time.time() - START_TIME
    minutes = int(seconds_since_start / 60) % 60
    hours = int(minutes / 60)
    seconds = seconds_since_start % 60

    print("[{: >2}h {: >2}m {:0>6}s] {}".format(hours, minutes, "{:0.3f}".format(seconds), text))


ret_channel = 20
ext_channel = 21
sleep_time = 0.5

def setup():
    # GPIO setup
    GPIO.setmode(GPIO.BCM)


def motor_on(pin):
    GPIO.output(pin, GPIO.HIGH)  # Turn motor on

def motor_off(pin):
    GPIO.output(pin, GPIO.LOW)  # Turn motor off

def ext(duration_s):
    GPIO.setup(ext_channel, GPIO.OUT)
    motor_on(ext_channel)
    time.sleep(duration_s)
    motor_off(ext_channel)

def ret(duration_s):
    GPIO.setup(ret_channel, GPIO.OUT)
    motor_on(ret_channel)
    time.sleep(duration_s)
    motor_off(ret_channel)

logging.getLogger("imported_module").setLevel(logging.WARNING)


class Metrics(object):
    PORT = 9732
    ADDR = ('', PORT)
    NUM_LISTENER_THREADS = 2

    def __init__(self):
        self.value = None
        self.last_updated = None

    def setValue(self, value):
        assert value is not None
        self.value = value
        self.last_updated = time.time()

    def getValue(self):
        age = None
        if self.last_updated:
            age = time.time() - self.last_updated

        if self.value is None:
            return {'starting': True}

        retval = {
            'value': self.value,
        }

        return retval


METRICS = Metrics()

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        response_obj = METRICS.getValue()
        self.wfile.write(json.dumps(response_obj).encode(encoding='utf_8'))

        # # debug print in a way that is easy to read
        # value = response_obj.get("value")
        # new_obj = {}
        # for k, v in response_obj.items():
        #     if k != "value":
        #         new_obj[k] = v
        # print("{}\t{}".format(new_obj, value))

    def log_message(self, *args):
        pass

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(Metrics.ADDR)
sock.listen(5)

class MetricsListenerThread(threading.Thread):
    def __init__(self, i):
        threading.Thread.__init__(self)
        self.i = i
        self.daemon = True
        self.start()

    def run(self):
        httpd = HTTPServer(Metrics.ADDR, MetricsHandler, False)
        httpd.socket = sock
        httpd.server_bind = self.server_close = lambda self: None
        httpd.serve_forever()

# Launch listener threads for Metrics
[MetricsListenerThread(i) for i in range(Metrics.NUM_LISTENER_THREADS)]

def pretty_print_pow(measured_power):
    label = "Power: %.3f W " % (measured_power / 1000)
    term_width = get_terminal_size()[0] - len(label) - 1
    ratio = (measured_power / 1000) / 100
    if ratio > 1:
        ratio = 1

    log(label + ("*" * int(term_width * ratio)))

def pretty_print_deg(angle_degrees):
    label = "Angle (degrees): %.3f " % angle_degrees
    term_width = get_terminal_size()[0] - len(label) - 1
    ratio = (angle_degrees) / 180
    log(label + ("*" * int(term_width * ratio)))


# calculating simple moving average over window_size points
def rolling_mean(data, window_size):
    moving_averages = []

    for i in range(len(data)):
        new_window_size = window_size
        if (i + 1) >= window_size:
            window_start = i - (window_size - 1)
        else:
            window_start = 0
            new_window_size = i + 1

        window = data[window_start:(i + 1)]
        window_average = sum(window) / new_window_size
        moving_averages.append(window_average)

    return moving_averages


def has_wobble(angles):
    # 1. when SMA stops changing more than 0.01 degree from previous sma datapoint
    sma = rolling_mean(angles, 300)
    prev_sma = sma[0] - 1  # first data point always fails condition 1
    for i in range(len(sma)):
        currnet_sma = sma[i]
        if abs(prev_sma - currnet_sma) > 0.001:
            sma[i] = None  # fail condition 1

        prev_sma = currnet_sma

    # 2. values are within 0.05 degree of the SMA
    for i in range(len(sma)):
        if sma[i] is not None and abs(angles[i] - sma[i]) > 0.05:
            sma[i] = None

    # 3. all of the aboive is true for the the last 50 datapoints
    for s in sma[-50:]:
        if s is None:
            return True

    return False  # does not have wobble


class MeasurementsRecorder(object):
    def __init__(self, is_ext):
        self.count = 0
        self.gen = int(random.random() * 10000)
        self.ext = is_ext
        self.measurements = []
        self.angles = []

    def do(self, ts, angle, f):
        self.count += 1

        now_ts = time.time()
        self.measurements.append([ts, ts - now_ts, self.gen, self.ext, self.count, angle])
        self.angles.append(angle)

        #if not has_wobble(self.angles):
        for measurements_row in self.measurements:
            f.write("\t".join([str(m) for m in measurements_row]) + "\n")

        self.angles = []
        self.measurements = []

        if self.count % 100 == 0:
            pretty_print_deg(angle)


def get_line():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("127.0.0.1", SENSOR_PORT))
        return s.recv(1024)

if __name__ == "__main__":
    duration = 80
    if len(sys.argv) > 1 and sys.argv[1] == "1":
        is_ext = True
    else:
        is_ext = False

    if is_ext:
        arm_channel = ext_channel
    else:
        arm_channel = ret_channel

    recorder = MeasurementsRecorder(is_ext)
    setup()

    GPIO.setup(arm_channel, GPIO.OUT)
    motor_on(arm_channel)
    with open(MEASUREMENTS_FILE, "a") as f:
        try:
            while True:
                if time.time() - START_TIME > duration:
                    break

                line = None
                try:
                    line = get_line()
                    ts, x, y, z, angle, crc_ok_rate, sto = line.split(b'\t')
                except Exception as e:
                    log("ERROR: could not read data from network")
                    log(repr(e))
                    log(repr(line))
                    sys.exit(1)

                if -70 < int(sto) < 70:
                    angle = float(angle)
                    ts = float(ts)

                    if time.time() - ts > 0.1:
                        log("ERROR: sensor data is too stale")
                        sys.exit(1)

                    if not math.isnan(angle):
                        METRICS.setValue(angle)
                        recorder.do(ts, angle, f)
                    else:
                        log("did not get angle")

                        
                else:
                    log("Bad STO (self test output) {} for {}".format(sto, line))

                time.sleep(0.01)

            motor_off(arm_channel)

        except KeyboardInterrupt:
            motor_off(arm_channel)
            GPIO.cleanup()
