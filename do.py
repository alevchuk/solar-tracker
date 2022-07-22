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

import statistics
MODE_HILL_CLIMB = "hill-climb"
MODE_HILL_CLIMB_RET = "hill-climb-ret"
MODE_HILL_CLIMB_EXT = "hill-climb-ext"
MODE_SCAN_RESET = "scan-reset"
MODE_SCAN_EXT = "scan-ext"
MODE_SCAN_RET = "scan-ret"

RET_CHANNEL = 20
EXT_CHANNEL = 21


HACK_MULT = 5


MEASURE_SLEEP = 0.6

HILL_CLIMB_NUM_SAMPLES = 3

OPTIMA_SAMPLES = 8

SCAN_SLEEP = 12
HILL_CLIMB_MULT = 10
SCAN_NUM_MOVES = 100 # Metrics getData()["pos"] will range is (0, SCAN_NUM_MOVES)

#SCAN_SLEEP = 60   # scan ext takes 35s (why?) when SCAN_SLEEP = 7
#HILL_CLIMB_MULT = 4  # resolution multiplier for hill climbing
#SCAN_NUM_MOVES = 60 # Metrics getData()["pos"] will range is (0, SCAN_NUM_MOVES * HILL_CLIMB_MULT). Tip: make SCAN_SLEEP == SCAN_NUM_MOVES so each scan step is 1 second, this seems to work well
# Also:
# - hill climbing takes one measurement per move
TOTAL_POSITIONS = SCAN_NUM_MOVES * HILL_CLIMB_MULT
SCAN_MOVES_DELAY = SCAN_SLEEP / SCAN_NUM_MOVES  # during scan
HILL_CLIMB_MOVES_DELAY = SCAN_SLEEP / TOTAL_POSITIONS  # during hill climbing


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


LAST_SENSOR_READ = None

class SensorFetcherThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.start()

        self.last_sensor_read = None

    def read(self, state, hide_metrics=False):
        if self.last_sensor_read is None:
            return None
        else:
            last = self.last_sensor_read.copy()
            age = time.time() - last['read_at']
            measured_power = last['value']

            if not hide_metrics:
                METRICS.setValue(measured_power / 1000)
                METRICS.setPos(state.pos)

            if age > MEASURE_SLEEP:
                return None

            return measured_power

    def _read(self):
        while True:
            try:
                # Instantiate the ina object with the above constants
                ina = INA219(SHUNT_OHMS, MAX_EXPECTED_AMPS, address=0x40)
                # Configure the object with the expected bus voltage
                # (either up to 16V or up to 32V with .RANGE_32V)
                # Also, configure the gain to be GAIN_2_80MW for the above example
                ina.configure(voltage_range=ina.RANGE_32V)

                if not ina.is_conversion_ready():
                    print("INA Conversion not ready, sleeping for 100ms")
                    time.sleep(0.1)
                    continue

                measured_power = ina.power()  # Power in milliwatts

                # print(ina.voltage()) ?

                return measured_power

            except Exception as e:
                print("Exception when reading from INA, {}".format(e))

            time.sleep(0.2)


    def run(self):
        while (True):
            value = self._read()

            self.last_sensor_read = {'value': value, 'read_at': time.time()}
            time.sleep(MEASURE_SLEEP)

# Run in the background
LAST_SENSOR_READ = SensorFetcherThread()

def hill_climb(state):
    print(state.descision_history)

    improving_list = []
    for _ in range(HILL_CLIMB_NUM_SAMPLES):
        improving = 0
        power_before = None

        while (power_before is None):
            time.sleep(MEASURE_SLEEP)
            power_before = LAST_SENSOR_READ.read(state)

        # Try
        if state.attemted_direction == "ret":
            METRICS.setMode(MODE_HILL_CLIMB_RET)
            state.armRet()
            #print("Try Ret")
        else:
            METRICS.setMode(MODE_HILL_CLIMB_EXT)
            state.armExt()
            #print("Try Ext")

        power_after = None
        while (power_after is None):
            time.sleep(MEASURE_SLEEP)
            power_after = LAST_SENSOR_READ.read(state)

        # print("Power before: {}   <=> Power after {}".format(power_before, power_after))
        state.updateEfficiency(power_after)
        METRICS.setMode(MODE_HILL_CLIMB)
        improving = power_after - power_before
        improving_list.append(improving)

        # Undo
        if state.attemted_direction == "ret":
            METRICS.setMode(MODE_HILL_CLIMB_EXT)
            state.armExt()
            #print("Undo Ret")
        else:
            METRICS.setMode(MODE_HILL_CLIMB_RET)
            state.armRet()
            #print("Undo Ext")

        time.sleep(0.2)
        METRICS.setMode(MODE_HILL_CLIMB)

    improving_avg = sum(improving_list) / len(improving_list)
    state.improvement_history.append(improving_avg)
    #print("Improvement list: {}".format([round(i, 2) for i in improving_list]))
    #print("Improvement avg: {}".format(round(improving_avg, 3)))

    if sum(improving_list) >= 0:
        # Advance in favorable direction
        if state.attemted_direction == "ret":
            state.armRet()
            # print("Advance Ret  <------------")
        else:
            state.armExt()
            #print("Advance Ext <------------")
            time.sleep(MEASURE_SLEEP)
    else:
        # Reverse
        if state.attemted_direction == "ret":
            state.attemted_direction = "ext"
        else:
            state.attemted_direction = "ret"
        
        #print("Reverse to: {} <----------- X ----------".format(state.attempted_direction))


    state.descision_history.append(state.attemted_direction)
    if len(state.descision_history) > OPTIMA_SAMPLES:
        state.descision_history = state.descision_history[-OPTIMA_SAMPLES:]


def remove_outliers(measurements):
    cutoff = 1.2
    no_outliers = []
    if len(measurements) > 0:
        median_measurement = statistics.median(measurements)
        delta = median_measurement * cutoff - median_measurement
        for i in measurements:
            if i < median_measurement - delta or i > median_measurement + delta:
                human_measurements = ["%.3f" % (i / 1000) for i in measurements]
                print("OUTLIER: dropping {} from {}".format("%.3f" % (i / 1000), human_measurements))
                continue  # ignore this measurement
            no_outliers.append(i)

    return no_outliers


def doScan(state):
    """
    Returns True if the hill is found
    """
    METRICS.setMode(MODE_SCAN_RESET)
    print("Moving to lower extreme")
    state.goToLowerExtreme()
    # scan
    METRICS.setMode("scan-ext")
    max_measured_power = 0
    hill_pos = 0
    scan_measurements = []
    print("Starting scan extent")
    for _ in range(SCAN_NUM_MOVES):
        state.armExt(HILL_CLIMB_MOVES_DELAY * HILL_CLIMB_MULT)
        time.sleep(MEASURE_SLEEP)
        m = LAST_SENSOR_READ.read(state)
        if m is not None:
            scan_measurements.append(m)
            if m > max_measured_power:
                max_measured_power = m
                hill_pos = state.pos

    state.scan_measurements = scan_measurements

    if len(state.scan_measurements) > 0:
        state.start_of_scan = state.scan_measurements[0]
        state.updateEfficiency(max(state.scan_measurements))

    print("Max found: %.3f W at position %d" % (max_measured_power / 1000, hill_pos))

    # localize to be on top of the hill
    found_hill = False
    actual_hill_pos = None
    measurements = None
    METRICS.setMode(MODE_SCAN_RET)
    max_power_seen_during_localization = 0
    for _ in range(SCAN_NUM_MOVES):
        max_measured_power2 = LAST_SENSOR_READ.read(state, hide_metrics=True)
        if max_measured_power2 is not None:
            if max_measured_power2 > max_power_seen_during_localization:
                max_power_seen_during_localization = max_measured_power2

            if max_measured_power * 0.80 < max_measured_power2 < max_measured_power * 1.20:
                time.sleep(MEASURE_SLEEP)
                found_hill = True
                actual_hill_pos = state.pos
                break

        state.armRet(HILL_CLIMB_MOVES_DELAY * HILL_CLIMB_MULT)

        # so we don't mark data as stale
        METRICS.setValue(max_measured_power / 1000)
        METRICS.setPos(hill_pos)

    if max_measured_power2 is not None and found_hill:
        print("Hill found: {}W".format(int(max_measured_power2 / 1000)))
        print("Optima search position was {} while the localization postion was {}".format(hill_pos, actual_hill_pos))
        pretty_print(max_measured_power)
        print()

    else:
        print("Hill NOT found! Was looking for {}W at position: {}".format(int(max_measured_power / 1000), hill_pos))
        print("Instead the largest we got was: {}W".format(int(max_power_seen_during_localization / 1000)))

    return found_hill


class TrackerState(object):
    def __init__(self):
        self.descision_history = []
        self.improvement_history = []
        self.attemted_direction = "ext"
        self.pos = 0
        self.start_of_scan = None
        self.scan_measurements = None

    def updateEfficiency(self, new_value):
        # check if efficiency cannot be calculated:
        # 1. if all scan measurements are similar that means panel is not getting sun or reflector is not adding light
        # 2. if first measurement is max, this means we are early in the morning where reflector cannot add more light,
        #    only block light. Moreover, at this morning time, sun energy is increasing quickly and this would make the 
        #    our approximation exaggerated because it would incorrectly claim natural sunlight increase as
        #    gain from the reflector
        if state.scan_measurements is None or len(state.scan_measurements) == 0:
            return

        avg_m = sum(state.scan_measurements) / len(state.scan_measurements)
        max_m = max(state.scan_measurements)
        if max_m < avg_m * 1.01:
            print("CANNOT updateEfficiency: scan too flat")
            return

        left_most = state.scan_measurements[0]
        if left_most > max_m * 0.95:
            print("CANNOT updateEfficiency: max is too close to the left extreme: left is {}; max is {}".format(int(left_most / 1000), int(max_m / 1000)))
            return

        if self.start_of_scan is not None and self.start_of_scan != 0:
            efficiency_pct = (new_value / self.start_of_scan) * 100
            METRICS.setEfficiency(efficiency_pct)

    def armRet(self, delay=HILL_CLIMB_MOVES_DELAY):
        # apply hack only for hill climbing, not scan
        hack_mult = 1
        if delay == HILL_CLIMB_MOVES_DELAY:
            hack_mult = HACK_MULT

        if self.pos <= 0:
            return

        try:
            move_arm(RET_CHANNEL, delay * hack_mult)
            GPIO.cleanup()
        except KeyboardInterrupt:
            GPIO.cleanup()
        else:
            self.pos -= int(delay / HILL_CLIMB_MOVES_DELAY) * hack_mult

    def armExt(self, delay=HILL_CLIMB_MOVES_DELAY):

        # apply hack only for hill climbing, not scan
        hack_mult = 1
        if delay == HILL_CLIMB_MOVES_DELAY:
            hack_mult = HACK_MULT

        if self.pos >= SCAN_NUM_MOVES * HILL_CLIMB_MULT:
            return

        try:
            move_arm(EXT_CHANNEL, delay * hack_mult)
            GPIO.cleanup()
        except KeyboardInterrupt:
            GPIO.cleanup()
        else:
            self.pos += int(delay / HILL_CLIMB_MOVES_DELAY) * hack_mult

    def _moveMeasure_DEPRICATED(self, ret):
        measurements = []
        first_move = False

        if ret:
            channel = RET_CHANNEL
        else:
            channel = EXT_CHANNEL
            if self.pos == 0:
                first_move = True

        setup(channel)
        motor_on(channel)

        num_moves = HILL_CLIMB_MULT

        time.sleep(SCAN_MOVES_DELAY)

        for _ in range(int(num_moves / 2)):
            measured_power = LAST_SENSOR_READ.read(state)
            if measured_power is not None:
                measurements.append(measured_power)

            time.sleep(measure_move_delay / 2)
            if ret:
                self.pos -= 1
            else:
                self.pos += 1

        motor_off(channel)

        for _ in range(int(num_moves / 2)):
            measured_power = LAST_SENSOR_READ.read(state)
            if measured_power is not None:
                measurements.append(measured_power)
            time.sleep(measure_move_delay / 2)

        measurements = remove_outliers(measurements)

        if first_move and len(measurements) > 0:
            self.start_of_scan = measurements[0]

        return measurements

    def moveMeasure_DEPRICATED(self, ret=True):
        try:
            return self._moveMeasure_DEPRICATED(ret)
            GPIO.cleanup()
        except KeyboardInterrupt:
            GPIO.cleanup()

    def goToLowerExtreme(self):
        channel = RET_CHANNEL

        setup(channel)
        motor_on(channel)
        time.sleep(SCAN_SLEEP * 1.5)  # gotta make sure we always start at the extreme
        motor_off(channel)

        state.pos = 0
        state.start_of_scan = None
        METRICS.setEfficiency(None)


if __name__ == "__main__":
    state = TrackerState()
    scan_every_n_moves = 1000
    n = 0
    time.sleep(MEASURE_SLEEP)  # let reader thread get it's first measurement
    while(True):
        n_remainder = n % (scan_every_n_moves / 100)
        if n_remainder == 0:
            print("{} of {} moves; {} left until next scan".format(
                    n_remainder, scan_every_n_moves, scan_every_n_moves - n_remainder))
        if n % scan_every_n_moves == 0:
            found = doScan(state)
            while(not found):
                found = doScan(state)

        hill_climb(state)
        n += 1
