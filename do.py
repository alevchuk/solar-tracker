#!/usr/bin/env python3

# actuator imports
import RPi.GPIO as GPIO
import time
from shutil import get_terminal_size

# shunt imports
from ina219 import INA219
from ina219 import DeviceRangeError
import time

import json
import threading
import socket
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

import logging
logging.getLogger("imported_module").setLevel(logging.WARNING)

MODE_HILL_CLIMB = "hill-climb"
MODE_HILL_CLIMB_RET = "hill-climb-ret"
MODE_HILL_CLIMB_EXT = "hill-climb-ext"
MODE_SCAN_RESET = "scan-reset"
MODE_SCAN_EXT = "scan-ext"
MODE_SCAN_RET = "scan-ret"

ret_channel = 20
ext_channel = 21
movement_sleep = 0.3
measure_sleep = 0.6

SCAN_SLEEP = 20

num_samples = 3

optima_pause = 5 * 60
optima_samples = 8

SCAN_NUM_MEASUREMENTS = 500
MEASURE_MOVE_RATIO = 10
SCAN_NUM_MOVES = int(SCAN_NUM_MEASUREMENTS / MEASURE_MOVE_RATIO)

class Metrics(object):
    PORT = 9732
    ADDR = ('', PORT)
    NUM_LISTENER_THREADS = 2

    def __init__(self):
        self.value = None
        self.last_updated = None
        self.mode = None

    def setMode(self, mode):
        self.mode = mode

    def setValue(self, value):
        self.value = value
        self.last_updated = time.time()

    def getValue(self):
        age = None
        if self.last_updated:
            age = time.time() - self.last_updated
        return {
            'value': self.value,
            'age': age,
            'mode': self.mode,
        }

METRICS = Metrics()

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        response_obj = METRICS.getValue()
        #print(response_obj)
        self.wfile.write(json.dumps(response_obj).encode(encoding='utf_8'))

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
    time.sleep(movement_sleep)
    motor_off(channel)
    time.sleep(measure_sleep)




# Set the constants that were calculated
SHUNT_MV = 75
MAX_EXPECTED_AMPS = 100
SHUNT_OHMS = (SHUNT_MV / 1000) / MAX_EXPECTED_AMPS  # R = V / i

#SHUNT_OHMS = 0.00075
print("Shunt resistance: {} ohms".format(SHUNT_OHMS))


def pretty_print(measured_power):
    label = "Power: %.3f W" % (measured_power / 1000)
    print(label, end = " ")
    term_width = get_terminal_size()[0] - len(label) - 1
    ratio = (measured_power / 1000) / 100
    if ratio > 1:
        ratio = 1

    print("*" * int(term_width * ratio))


def read():
    # Instantiate the ina object with the above constants
    ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, address=0x40)
    # Configure the object with the expected bus voltage
    # (either up to 16V or up to 32V with .RANGE_32V)
    # Also, configure the gain to be GAIN_2_80MW for the above example
    ina.configure(
            voltage_range=ina.RANGE_32V,
    )

    try:
        measured_power = ina.power()  # Power in milliwatts
        pretty_print(measured_power)

        METRICS.setValue(measured_power / 1000)

        return measured_power
    except DeviceRangeError as e:
        print("Current overflow")


def r():
     try:
         test(ret_channel)
         GPIO.cleanup()
     except KeyboardInterrupt:
         GPIO.cleanup()

def e():
     try:
         test(ext_channel)
         GPIO.cleanup()
     except KeyboardInterrupt:
         GPIO.cleanup()


def hill_climb(state):
    print(state.descision_history)

    improving_list = []
    for attempt in range(num_samples):
        improving = 0
        power_before = read()

        # Try
        if state.attemted_direction == "ret":
            METRICS.setMode(MODE_HILL_CLIMB_RET)
            r()
        else:
            METRICS.setMode(MODE_HILL_CLIMB_EXT)
            e()

        time.sleep(0.2)
        power_after = read()

        METRICS.setMode(MODE_HILL_CLIMB)

        improving = power_after - power_before
        improving_list.append(improving)

        # Undo
        if state.attemted_direction == "ret":
            METRICS.setMode(MODE_HILL_CLIMB_EXT)
            e()
        else:
            METRICS.setMode(MODE_HILL_CLIMB_RET)
            r()

        time.sleep(0.2)
        METRICS.setMode(MODE_HILL_CLIMB)

    state.improvement_history.append(sum(improving_list) / len(improving_list))
    if sum(improving_list) >= 0:
        # Advance in favorable direction
        if state.attemted_direction == "ret":
            r()
        else:
            e()
        time.sleep(0.2)
    else:
        if state.attemted_direction == "ret":
            state.attemted_direction = "ext"
        else:
            state.attemted_direction = "ret"


    state.descision_history.append(state.attemted_direction)
    if len(state.descision_history) > optima_samples:
        state.descision_history = state.descision_history[-optima_samples:]


def go_to_lower_extreme():
    channel = ret_channel
    setup(channel)
    motor_on(channel)

    for step in range(SCAN_NUM_MOVES):
        time.sleep(SCAN_SLEEP / SCAN_NUM_MOVES)
        read()

    motor_off(channel)


def scan():
    """
    Returns True if the hill is found
    """
    hill_buffer_ratio = 0.06
    measurements = []

    METRICS.setMode(MODE_SCAN_RESET)
    go_to_lower_extreme()

    # scan
    METRICS.setMode("scan-ext")
    channel = ext_channel
    setup(channel)
    for step in range(SCAN_NUM_MOVES):
        motor_on(channel)

        for _ in range(int(MEASURE_MOVE_RATIO / 2)):
            measured_power = read()
            measurements.append(measured_power)
            time.sleep(SCAN_SLEEP / SCAN_NUM_MEASUREMENTS)

        motor_off(channel)

        for _ in range(int(MEASURE_MOVE_RATIO / 2)):
            measured_power = read()
            measurements.append(measured_power)
            time.sleep(SCAN_SLEEP / SCAN_NUM_MEASUREMENTS)

    # Remove outliers
    avg_measured_power = sum(measurements) / len(measurements)
    new_measured_power = []
    for i in measurements:
        if i < avg_measured_power * 1.5:
            new_measured_power.append(i)

    hill_milliwatts = max(new_measured_power)
    hill_lower_bound = hill_milliwatts - hill_milliwatts * hill_buffer_ratio / 2
    print("Max found: %.3f W" % (hill_milliwatts / 1000))

    # localize to be on top of the hill
    found_hill = False
    measurements = []
    METRICS.setMode(MODE_SCAN_RET)
    channel = ret_channel
    setup(channel)
    for step in range(SCAN_NUM_MOVES):
        motor_on(channel)

        for _ in range(int(MEASURE_MOVE_RATIO / 2)):
            measured_power = read()
            measurements.append(measured_power)
            time.sleep(SCAN_SLEEP / SCAN_NUM_MEASUREMENTS)

        motor_off(channel)

        for _ in range(int(MEASURE_MOVE_RATIO / 2)):
            measured_power = read()
            measurements.append(measured_power)
            time.sleep(SCAN_SLEEP / SCAN_NUM_MEASUREMENTS)

        # Remove outliers
        avg_measured_power = sum(measurements) / len(measurements)
        new_measured_power = []
        for i in measurements:
            if i < avg_measured_power * 1.5:
                new_measured_power.append(i)

        if max(new_measured_power) > hill_lower_bound:
            found_hill = True
            hill_milliwatts = max(new_measured_power)
            break

    if found_hill:
        print("Hill found: {}".format(hill_milliwatts / 1000))
        pretty_print(hill_milliwatts)
        print()
    else:
        print("Hill NOT found! Was looking for:")
        pretty_print(hill_milliwatts)
        print()

    return found_hill


class TrackerState(object):
    def __init__(self):
        self.descision_history = []
        self.improvement_history = []
        self.attemted_direction = "ext"


if __name__ == "__main__":

    state = TrackerState()

    scan_every_n_moves = 100
    n = 0
    while(True):
        if n % scan_every_n_moves == 0:
            found = scan()
            while(not found):
                found = scan()

        hill_climb(state)
        n += 1
