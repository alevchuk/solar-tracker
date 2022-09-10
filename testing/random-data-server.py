#!/usr/bin/env python3

import time
import json
import threading
import socket
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

import random

START_TIME = time.time()

MODE_HILL_CLIMB = "hill-climb"
MODE_HILL_CLIMB_RET = "hill-climb-ret"
MODE_HILL_CLIMB_EXT = "hill-climb-ext"
MODE_SCAN = "scan"
MODE_SCAN_RESET = "scan-reset"
MODE_SCAN_EXT = "scan-ext"
MODE_SCAN_RET = "scan-ret"

SCAN_DEG_START = 1
SCAN_DEG_END = 60

class RandomTestData(object):
    MAX_VALUE = 100

    def __init__(self):
        self.direction = "up"
        self.prev_value = 0

    def next(self):
        delta = random.random() - 0.5

        if METRICS.mode.startswith(MODE_HILL_CLIMB):
            delta /= 10

        if (self.direction == "up" and delta > 0) or (self.direction == "down" and delta < 0):
            delta *= 2

        new_value = self.prev_value + delta * 30
        if new_value < 0:
            new_value = 0
            self.direction = "up"

        if new_value > RandomTestData.MAX_VALUE:
            new_value = RandomTestData.MAX_VALUE
            self.direction = "down"

        self.prev_value = new_value

        return new_value


class Metrics(object):
    PORT = 9732
    ADDR = ('0.0.0.0', PORT)
    NUM_LISTENER_THREADS = 2

    def __init__(self):
        self.value = None
        self.last_updated = None
        self.pos = SCAN_DEG_START
        self.pos_direction = 'ext'
        self.mode = MODE_SCAN_EXT
        self.step_count = 0

        # is_probe and is_decision only applies to hill climb
        self.is_probe = False
        self.is_decision = False

    def setMode(self, value):
        self.mode = value

    def updatePos(self):
        self.step_count += 1
        step_size = 0.5

        if self.mode.startswith(MODE_HILL_CLIMB):
            step_size /= 2
            self.is_probe = True
            self.is_decision = False

            # proble left
            if self.step_count % 5 == 0:
                self.pos -= step_size
                return

            # go back to center
            if self.step_count % 5 == 1:
                self.pos += step_size
                return

            # proble right
            if self.step_count % 5 == 2:
                self.pos += step_size
                return

            # go back to center
            if self.step_count % 5 == 3:
                self.pos -= step_size
                return

            # make a decision
            if self.step_count % 5 == 4:
                if random.random() > 0.5:
                    self.pos_direction = 'ret'
                else:
                    self.pos_direction = 'ext'

            self.is_decision = True
            self.is_probe = False

        if self.mode.startswith(MODE_SCAN):
            # is_probe and is_decision only applies to hill climb
            self.is_probe = False
            self.is_decision = False

        # continue moving in the direction of pos_direction
        # the following code is reused for scans and hill climb
        if self.pos_direction == 'ext':
            if self.pos < SCAN_DEG_END:
                self.pos += step_size
            else:
                self.pos_direction = 'ret'
        else:
            if self.pos > SCAN_DEG_START:
                self.pos -= step_size
            else:
                self.pos_direction = 'ext'

    def setValue(self, value):
        self.value = value
        self.last_updated = time.time()

    def getValue(self):
        age = None
        if self.last_updated:
            age = time.time() - self.last_updated
        assert self.is_probe is False or self.is_decision is False, "is_probe and is_decision can't both be True"
        return {
            'value': self.value,
            'age': age,
            'mode': self.mode,
            'pos': self.pos,
            'efficiency_pct': 199,
            'wobble_data': [12, 34, 56],
            'is_probe': self.is_probe,
            'is_decision': self.is_decision,
        }

METRICS = Metrics()

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        response_obj = METRICS.getValue()
        self.wfile.write(json.dumps(response_obj).encode(encoding='utf_8'))

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


if __name__ == "__main__":
    SCAN_SECONDS = 15
    HILL_CLIMB_SECONDS = 300
    METRICS.setMode(MODE_SCAN_EXT)  # start with a scan

    remainder1_s = SCAN_SECONDS
    remainder2_s = HILL_CLIMB_SECONDS
    generator = RandomTestData()

    while True:
        elapsed_time = time.time() - START_TIME
        if METRICS.mode == MODE_SCAN_EXT:
            # calc new remainder
            prev_remainder1_s = remainder1_s
            remainder1_s = elapsed_time % SCAN_SECONDS
            is_monotonic1 = (remainder1_s > prev_remainder1_s)
            if not is_monotonic1:
                # remainder jumped, we're in a new era
                METRICS.setMode(MODE_HILL_CLIMB)
        else:
            # calc new remainder
            prev_remainder2_s = remainder2_s
            remainder2_s = elapsed_time % HILL_CLIMB_SECONDS
            is_monotonic2 = (remainder2_s > prev_remainder2_s)
            if not is_monotonic2:
                METRICS.setMode(MODE_SCAN_EXT)


        METRICS.updatePos()
        METRICS.setValue(generator.next())
        time.sleep(1)
