#!/usr/bin/env python3

import json
import sys
import math
import sys
import time
from shutil import get_terminal_size

import threading
import socket
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

import logging

import RPi.GPIO as GPIO
import time

SENSOR_PORT = 2017
MEASUREMENTS_FILE = "/home/pi/measurements.txt"

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


def pretty_print(angle_degrees):
    label = "Angle (degrees): %.4f" % angle_degrees
    print(label, end = " ")
    term_width = get_terminal_size()[0] - len(label) - 1
    ratio = (angle_degrees) / 180
    print("*" * int(term_width * ratio))


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

    print("SMA: {}".format(sma))

    return False  # does not have wobble


class StepSize(object):
    def __init__(self):
        self.count = 0
        self.gen = 0  # gen 0 is 1s step, 1 is 1s-0.01s, 2 is 1s-0.02s, ...
        self.ext = True  # every gen has ext + ret
        self.measurements = []
        self.angles = []

    def do(self, ts, angle):
        self.count += 1

        now_ts = time.time()
        self.measurements.append([ts, ts - now_ts, self.gen, self.ext, self.count, angle])
        self.angles.append(angle)

        if not has_wobble(self.angles):
            ext(0.1)  # TODO: remove

            with open(MEASUREMENTS_FILE, "a") as f: 
                for measurements_row in self.measurements:
                    f.write("\t".join([str(m) for m in measurements_row]) + "\n")

            self.angles = []
            self.measurements = []

            pretty_print(angle)
            # print("Delay: {}".format(time.time() - ts))

            step_size = 1 - (self.gen * 0.01)  # in seconds
            if self.ext:
                ext(step_size)
                if angle > 40:
                    self.ext = False
            else:
                ret(step_size)
                if angle < 3:
                    self.ext = True
                    self.gen += 1
                    print("")
                    print("===============================")
                    print("Generation: {}".format(self.gen))
                    print("===============================")
                    if self.gen == 101:
                        sys.exit(0)


def get_line():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("127.0.0.1", SENSOR_PORT))
        return s.recv(1024)

if __name__ == "__main__":
    ss = StepSize()
    setup()

    # drop old records
    with open(MEASUREMENTS_FILE, "w") as f: 
        pass

    # TODO: remove
    ext(0.01)

    try:
        while True:
            line = None
            try:
                line = get_line()    
                ts, x, y, z, angle, crc_ok_rate, sto = line.split(b'\t')
            except Exception as e:
                print("ERROR: could not read data from network")
                print(e)
                print(repr(line))
                sys.exit(1)

            if -70 < int(sto) < 70:
                angle = float(angle)
                ts = float(ts)

                if time.time() - ts > 0.1:
                    print("ERROR: sensor data is too stale")
                    sys.exit(1)

                if not math.isnan(angle):
                    METRICS.setValue(angle)
                    #pretty_print(angle)
                    ss.do(ts, angle)
            else:
                print("Bad STO (self test output) {} for {}".format(sto, line))

            time.sleep(0.01)


    except KeyboardInterrupt:
        GPIO.cleanup()
