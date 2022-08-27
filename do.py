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
import os

HOME = os.path.expanduser("~")


SENSOR_PORT = 2017

MODE_HILL_CLIMB = "hill-climb"
MODE_HILL_CLIMB_RET = "hill-climb-ret"
MODE_HILL_CLIMB_EXT = "hill-climb-ext"
MODE_SCAN_RESET = "scan-reset"
MODE_SCAN_EXT = "scan-ext"
MODE_SCAN_RET = "scan-ret"

RET_CHANNEL = 20
EXT_CHANNEL = 21



MEASURE_SLEEP = 0.6

OPTIMA_SAMPLES = 8

REWIND_SLEEP = 6
SCAN_DEG_START = 1
SCAN_DEG_END = 60



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
        self.wobble_data = None

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

    def setWobbleData(self, value):
        self.wobble_data = value

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
            'pos': self.pos,
            'wobble_data': self.wobble_data
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


def pretty_print_pow(measured_power):
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

def further(state):
    if state.attemted_direction == "ret":
        METRICS.setMode(MODE_HILL_CLIMB_RET)
        state.armRet()
        print("Try Ret")
    else:
        METRICS.setMode(MODE_HILL_CLIMB_EXT)
        state.armExt()
        print("Try Ext")

def undo(state):
    if state.attemted_direction == "ret":
        METRICS.setMode(MODE_HILL_CLIMB_EXT)
        state.armExt()
        print("Undo Ret")
    else:
        METRICS.setMode(MODE_HILL_CLIMB_RET)
        state.armRet()
        print("Undo Ext")

def hill_climb(state):
    print(state.descision_history)

    power_before = None
    while (power_before is None):
        time.sleep(MEASURE_SLEEP)
        power_before = LAST_SENSOR_READ.read(state)

    # Try
    further(state)

    power_after = None
    while (power_after is None):
        time.sleep(MEASURE_SLEEP)
        power_after = LAST_SENSOR_READ.read(state)

    # print("Power before: {}   <=> Power after {}".format(power_before, power_after))
    state.updateEfficiency(power_after)
    METRICS.setMode(MODE_HILL_CLIMB)

    descision = state.attemted_direction
    if power_after - power_before > 0:
        print("We have improvement of +%.3f mW !" % (power_after - power_before))
        # we still need to test for ani-imporvment to avoid getting tricked by clouds

        undo(state)
        undo(state)

        power_on_the_filp_side = None
        while (power_on_the_filp_side is None):
            time.sleep(MEASURE_SLEEP)
            power_on_the_filp_side = LAST_SENSOR_READ.read(state)

        if power_before - power_on_the_filp_side < (power_after - power_before) * 0.9:
            print("Anti-improvement of %.3f mW is not sufficient! Maybe a cloud?" % (power_before - power_on_the_filp_side))
            further(state)
            descision = "stay"
        else:
            # Advance in favorable direction
            further(state)
            further(state)
    else:
        # before reversing we still need to test for ani-imporvment to avoid getting tricked by clouds
        undo(state)

        power_before = None
        while (power_before is None):
            time.sleep(MEASURE_SLEEP)
            power_before = LAST_SENSOR_READ.read(state)

        undo(state)
        power_after = None
        while (power_after is None):
            time.sleep(MEASURE_SLEEP)
            power_after = LAST_SENSOR_READ.read(state)

        if power_after - power_before < 0:
            print("Reversing also does not make sense. Maybe a cloud?")
            further(state)
            descision = "stay"
        else:
            print("We have improvement of +%.3f mW when revrsing !" % (power_after - power_before))
            # we still need to test for ani-imporvment to avoid getting tricked by clouds

            power_on_the_filp_side = None
            while (power_on_the_filp_side is None):
                time.sleep(MEASURE_SLEEP)
                power_on_the_filp_side = LAST_SENSOR_READ.read(state)

            if power_on_the_filp_side - power_before > abs(power_after - power_before) * 0.9:
                # Reverse directions
                if state.attemted_direction == "ret":
                    state.attemted_direction = "ext"
                else:
                    state.attemted_direction = "ret"
            else:
                print("Anti-improvement of +%.3f mW is not sufficient! Maybe a cloud?" % (power_on_the_filp_side - power_before))
                further(state)
                descision = "stay"

    METRICS.setMode(MODE_HILL_CLIMB)

    state.descision_history.append(descision)
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
    state.toLowerExtreme(state)
    # scan
    METRICS.setMode("scan-ext")
    max_measured_power = 0
    hill_pos = 0
    scan_measurements = []
    print("Starting scan")
    while state.pos < SCAN_DEG_END:
        state.armExt()
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

    print("Max found: %.3f W at %.3f degrees" % (max_measured_power / 1000, hill_pos))

    # localize to be on top of the hill
    found_hill = False
    actual_hill_pos = None
    measurements = None
    METRICS.setMode(MODE_SCAN_RET)
    max_power_seen_during_localization = 0

    while True:
        hill_on_the_left = (hill_pos < SCAN_DEG_START and state.pos < SCAN_DEG_START)
        # take first step bellow the hill degrees + 0.5 degree
        # we can make this more accurate by
        # moving the reflector back up by a smaller degree
        # then back down, etc... until we get desired precision
        if state.pos <= (hill_pos + 0.5) or hill_on_the_left:
            time.sleep(MEASURE_SLEEP)
            found_hill = True
            actual_hill_pos = state.pos
            break

        state.armRet()

        # so we don't mark data as stale
        METRICS.setValue(max_measured_power / 1000)
        METRICS.setPos(hill_pos * 15)

    if found_hill:
        print("Hill found: {}W".format(int(max_measured_power / 1000)))
        print("Optima search position was {} while the localization postion was {}".format(hill_pos, actual_hill_pos))
        pretty_print_pow(max_measured_power)
        print()

    else:
        print("Hill NOT found! Was looking for {}W at position: {}".format(int(max_measured_power / 1000), hill_pos))
        print("Instead the largest we got was: {}W".format(int(max_power_seen_during_localization / 1000)))

    return found_hill

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


def wait_for_wobble_to_stop():
    angles_while_wobble = []
    while True:
        angle = get_line_and_parse()
        angles_while_wobble.append(angle)
        if not has_wobble(angles_while_wobble):
            break

def pretty_print_deg(angle_degrees):
    label = "Angle (degrees): %.3f" % angle_degrees
    print(label, end = " ")
    term_width = get_terminal_size()[0] - len(label) - 1
    ratio = (angle_degrees) / 180
    print("*" * int(term_width * ratio))


class TrackerState(object):
    def __init__(self):
        self.step_delay = 0.5
        self.descision_history = []
        self.attemted_direction = "ext"
        self.pos = 0
        self.start_of_scan = None
        self.scan_measurements = None
        self.angles_while_wobble = []

        self.moves_count = 0
        self.useful_total = 0
        self.wobble_total = 0

    def updateWobbleData(self, latest_dur, useful_time):
        self.moves_count += 1
        self.wobble_total += latest_dur
        avg_dur = self.wobble_total / self.moves_count

        self.useful_total += useful_time
        time_loss_pct = (self.wobble_total / self.useful_total) * 100

        METRICS.setWobbleData([latest_dur, avg_dur, time_loss_pct])

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

    def _arm(self, delay, direction):
        if delay is not None:
            _delay = delay
        else:
            _delay = self.step_delay

        angle_before = get_line_and_parse()

        try:
            move_arm(direction, _delay)
            GPIO.cleanup()
        except KeyboardInterrupt:
            GPIO.cleanup()
        else:
            # 1. wait for wobble to stop
            start_wobble_wait = time.time()
            wait_for_wobble_to_stop()
            dur = time.time() - start_wobble_wait

            self.updateWobbleData(dur, useful_time=_delay)

            # 2. set pos to inclinometer angle
            angle = get_line_and_parse()
            pretty_print_deg(angle)
            self.pos = angle

            with open(HOME + "/drag.tab", "a") as fout:
                dist = angle - angle_before
                fout.write("{}\t{}\t{}\t{}\n".format(_delay, angle_before, angle, dist))

    def armRet(self, delay=None):
        self._arm(delay, RET_CHANNEL)

    def armExt(self, delay=None):
        self._arm(delay, EXT_CHANNEL)

    def toLowerExtreme(self, state):
        state.armRet(REWIND_SLEEP)

        while state.pos > SCAN_DEG_START:
            state.armRet(REWIND_SLEEP)

        state.start_of_scan = None
        METRICS.setEfficiency(None)


def get_line():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("127.0.0.1", SENSOR_PORT))
        return s.recv(1024)


def get_line_and_parse():
    try:
        line = get_line()
        ts, x, y, z, angle, crc_ok_rate, sto = line.split(b'\t')
        angle = float(angle)
    except Exception as e:
        print("ERROR: cold not get incli data: {}".format(e))
        print(e)
        raise e
    else:
        return angle


if __name__ == "__main__":
    state = TrackerState()
    scan_every_n_moves = 100
    n = 0
    time.sleep(MEASURE_SLEEP)  # let reader thread get it's first measurement



    while(True):
        n_remainder = n % scan_every_n_moves
        print("{} of {} moves; {} left until next scan".format(
                n_remainder, scan_every_n_moves, scan_every_n_moves - n_remainder))

        if n % scan_every_n_moves == 0:
            found = doScan(state)
            while(not found):
                found = doScan(state)

        hill_climb(state)
        n += 1
