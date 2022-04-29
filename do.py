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

RET_CHANNEL = 20
EXT_CHANNEL = 21
measure_sleep = 0.6


num_samples = 3

optima_pause = 5 * 60
optima_samples = 8

SCAN_SLEEP = 20
SCAN_NUM_MOVES = 100 # Metrics getData()["pos"] will range is (0, SCAN_NUM_MOVES)
MEASURE_MOVE_RATIO = 10  # scan has this many meanusments per move
# Also:
# - hill climbing takes one measurement per move
# - scan has finer granularity than hill climbing
SCAN_NUM_MEASUREMENTS = SCAN_NUM_MOVES * MEASURE_MOVE_RATIO
DELAY_BETWEEN_MOVES = SCAN_SLEEP / SCAN_NUM_MOVES  # during scan and hill climbing
DELAY_BETWEEN_MEASUREMENTS = SCAN_SLEEP / SCAN_NUM_MEASUREMENTS  # during scan

SCAN_RET_BUFFER = int(SCAN_NUM_MOVES * 0.15)  #  NOTE: drive asccuracy when localizing after a scan. the lower the more accriate. currently this is set high for demo of hill climbing, so accuracy will be low

class Metrics(object):
    PORT = 9732
    ADDR = ('', PORT)
    NUM_LISTENER_THREADS = 2

    def __init__(self):
        self.value = None
        self.last_updated = None
        self.mode = None
        self.pos = None
        self.efficiency_pct = None

    def setMode(self, mode):
        self.mode = mode

    def setValue(self, value):
        assert value is not None
        self.value = value
        self.last_updated = time.time()

    def setPos(self, value):
        self.pos = value

    def setEfficiency(self, value):
        self.efficiency_pct = value

    def getValue(self):
        age = None
        if self.last_updated:
            age = time.time() - self.last_updated

        if self.value is None:
            return {'starting': True}

        retval = {
            'value': self.value,
            'age': age,
            'mode': self.mode,
            'pos': self.pos
        }

        if self.efficiency_pct is not None:
            retval["efficiency_pct"] = self.efficiency_pct

        return retval


METRICS = Metrics()

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        response_obj = METRICS.getValue()
        self.wfile.write(json.dumps(response_obj).encode(encoding='utf_8'))

        # # debug print in a way thats easy to read
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

def setup(channel):
    # GPIO setup
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(channel, GPIO.OUT)


def motor_on(pin):
    GPIO.output(pin, GPIO.HIGH)  # Turn motor on


def motor_off(pin):
    GPIO.output(pin, GPIO.LOW)  # Turn motor off


def move_arm(channel, movement_sleep):
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


def read(state):
    # Instantiate the ina object with the above constants
    ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, address=0x40)
    # Configure the object with the expected bus voltage
    # (either up to 16V or up to 32V with .RANGE_32V)
    # Also, configure the gain to be GAIN_2_80MW for the above example
    ina.configure(
            voltage_range=ina.RANGE_32V,
    )

    while True:
        if not ina.is_conversion_ready():
            print("INA Conversion not ready, sleeping for 100ms")
            time.sleep(0.1)
            continue

        try:
            measured_power = ina.power()  # Power in milliwatts
            #pretty_print(measured_power)

            METRICS.setValue(measured_power / 1000)
            METRICS.setPos(state.pos)

            return measured_power
        except DeviceRangeError as e:
            print("Current overflow, sleeping for 100ms")
            time.sleep(0.1)



def hill_climb(state):
    print(state.descision_history)

    improving_list = []
    for attempt in range(num_samples):
        improving = 0
        power_before = read(state)
        state.updateEfficiency(power_before)

        # Try
        if state.attemted_direction == "ret":
            METRICS.setMode(MODE_HILL_CLIMB_RET)
            state.hillClimbRet()
        else:
            METRICS.setMode(MODE_HILL_CLIMB_EXT)
            state.hillClimbExt()

        time.sleep(0.2)
        power_after = read(state)
        state.updateEfficiency(power_after)

        METRICS.setMode(MODE_HILL_CLIMB)

        improving = power_after - power_before
        improving_list.append(improving)

        # Undo
        if state.attemted_direction == "ret":
            METRICS.setMode(MODE_HILL_CLIMB_EXT)
            state.hillClimbExt()
        else:
            METRICS.setMode(MODE_HILL_CLIMB_RET)
            state.hillClimbRet()

        time.sleep(0.2)
        METRICS.setMode(MODE_HILL_CLIMB)

    state.improvement_history.append(sum(improving_list) / len(improving_list))
    if sum(improving_list) >= 0:
        # Advance in favorable direction
        if state.attemted_direction == "ret":
            state.hillClimbRet()
        else:
            state.hillClimbExt()
        time.sleep(0.2)
    else:
        if state.attemted_direction == "ret":
            state.attemted_direction = "ext"
        else:
            state.attemted_direction = "ret"


    state.descision_history.append(state.attemted_direction)
    if len(state.descision_history) > optima_samples:
        state.descision_history = state.descision_history[-optima_samples:]


def remove_outliers(measurements):
    cutoff = 1.2
    no_outliers = []
    if len(measurements) > 0:
        avg_measured_power = sum(measurements) / len(measurements)
        delta = avg_measured_power * cutoff - avg_measured_power
        for i in measurements:
            if i < avg_measured_power - delta or i > avg_measured_power + delta:
                human_measurements = ["%.3f" % (i / 1000) for i in measurements]
                print("OUTLIER: dropping {} from {}".format("%.3f" % (i / 1000), human_measurements))
                continue  # ignore this measurment
            no_outliers.append(i)

    return no_outliers


def scan(state):
    """
    Returns True if the hill is found
    """
    hill_buffer_ratio = 0.06

    METRICS.setMode(MODE_SCAN_RESET)
    state.goToLowerExtreme()

    # scan
    METRICS.setMode("scan-ext")

    max_measured_power = 0
    hill_pos = 0
    for _ in range(SCAN_NUM_MOVES):
        measurements = state.moveMeasure(ret=False)
        for m in measurements:
            if m > max_measured_power:
                max_measured_power = m
                hill_pos = state.pos

    print("Max found: %.3f W at position %d" % (max_measured_power / 1000, hill_pos))

    # localize to be on top of the hill
    found_hill = False
    measurements = None
    METRICS.setMode(MODE_SCAN_RET)
    for _ in range(SCAN_NUM_MOVES):
        measurements = state.moveMeasure(ret=True)

        if hill_pos - SCAN_RET_BUFFER < state.pos < hill_pos + SCAN_RET_BUFFER:
            found_hill = True
            max_measured_power2 = max(measurements)
            break

    if found_hill:
        print("Hill found: {}".format(max_measured_power2 / 1000))
        pretty_print(max_measured_power2)
        print()
    else:
        print("Hill NOT found! Was looking for:")
        pretty_print(max_measured_power2)
        print()

    return found_hill


class TrackerState(object):
    def __init__(self):
        self.descision_history = []
        self.improvement_history = []
        self.attemted_direction = "ext"
        self.pos = 0
        self.start_of_scan = None

    def updateEfficiency(self, new_value):
        if self.start_of_scan is not None and self.start_of_scan != 0:
            efficiency_pct = (new_value / self.start_of_scan) * 100
            METRICS.setEfficiency(efficiency_pct)

    def hillClimbRet(self):
        if self.pos <= 0:
            return

        try:
            move_arm(RET_CHANNEL, DELAY_BETWEEN_MOVES)
            GPIO.cleanup()
        except KeyboardInterrupt:
            GPIO.cleanup()
        else:
            self.pos -= 1
    
    def hillClimbExt(self):
        if self.pos >= SCAN_NUM_MOVES:
            return

        try:
            move_arm(EXT_CHANNEL, DELAY_BETWEEN_MOVES)
            GPIO.cleanup()
        except KeyboardInterrupt:
            GPIO.cleanup()
        else:
            self.pos += 1

    def _moveMeasure(self, ret):
        measurements = []
        first_move = False

        if ret:
            channel = RET_CHANNEL
            self.pos -= 1
        else:
            channel = EXT_CHANNEL
            self.pos += 1
            if self.pos == 1:
                first_move = True

        setup(channel)
        motor_on(channel)

        for _ in range(int(MEASURE_MOVE_RATIO / 2)):
            measured_power = read(state)
            measurements.append(measured_power)
            delay = SCAN_SLEEP / SCAN_NUM_MEASUREMENTS
            time.sleep(delay)

        motor_off(channel)

        for _ in range(int(MEASURE_MOVE_RATIO / 2)):
            measured_power = read(state)
            measurements.append(measured_power)
            delay = SCAN_SLEEP / SCAN_NUM_MEASUREMENTS
            time.sleep(delay)

        measurements = remove_outliers(measurements)

        if first_move and len(measurements) > 0:
            self.start_of_scan = sum(measurements) / len(measurements)

        return measurements

    def moveMeasure(self, ret=True):
        try:
            return self._moveMeasure(ret)
            GPIO.cleanup()
        except KeyboardInterrupt:
            GPIO.cleanup()

    def goToLowerExtreme(self):
        channel = RET_CHANNEL

        setup(channel)
        motor_on(channel)
        num_moves = 5
        for _ in range(num_moves):
            time.sleep(SCAN_SLEEP / num_moves)
            read(state)

        motor_off(channel)

        state.pos = 0
        state.start_of_scan = None
        METRICS.setEfficiency(None)


if __name__ == "__main__":
    state = TrackerState()
    scan_every_n_moves = 20
    n = 0
    while(True):
        if n % scan_every_n_moves == 0:
            found = scan(state)
            while(not found):
                found = scan(state)

        hill_climb(state)
        n += 1
