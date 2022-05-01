#!/usr/bin/env python3

import time
import json
import threading
import socket
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

import random

MODE_SCAN_RESET = "scan-reset"
MODE_SCAN_EXT = "scan-ext"
MODE_SCAN_RET = "scan-ret"
MODE_HILL_CLIMB = "hill-climb"
MODE_HILL_CLIMB_RET = "hill-climb-ret"
MODE_HILL_CLIMB_EXT = "hill-climb-ext"

SCAN_SLEEP = 8
SCAN_NUM_MOVES = 25 # Metrics getData()["pos"] will range is (0, SCAN_NUM_MOVES)
HILL_CLIMB_MULT = 10  # resolution multiplier for hill climbing
# Also:
# - hill climbing takes one measurement per move
# - scan has finer granularity than hill climbing
TOTAL_POSITIONS = SCAN_NUM_MOVES * HILL_CLIMB_MULT
DELAY_BETWEEN_SCAN_MOVES = SCAN_SLEEP / SCAN_NUM_MOVES  # during scan
DELAY_BETWEEN_CLIMB_MOVES = SCAN_SLEEP / TOTAL_POSITIONS  # during hill climbing


class RandomTestData(object):
    MAX_VALUE = 100

    def __init__(self):
        self.watts_direction = "up"
        self.prev_value = 0
        self.mode = MODE_SCAN_RESET
        self.mode_start = time.time()
        self.next_mode_delay = SCAN_SLEEP
        self.pos = 0
        self.num_measurments = 0
        self.start_of_scan = None


    def update_mode(self):
        if self.mode_start + self.next_mode_delay < time.time():
            if self.mode == MODE_SCAN_EXT:
                self.next_mode_delay = SCAN_SLEEP / 2
            else:
                self.next_mode_delay = SCAN_SLEEP

            if self.mode == MODE_SCAN_RESET:
                self.mode = MODE_SCAN_EXT
            elif self.mode == MODE_SCAN_EXT:
                self.mode = MODE_SCAN_RET
            elif self.mode == MODE_SCAN_RET:
                self.mode = MODE_HILL_CLIMB
            elif self.mode.startswith(MODE_HILL_CLIMB):
                self.mode = MODE_SCAN_RESET

            self.mode_start = time.time()


    def next(self):
        self.num_measurments += 1
        self.update_mode()

        delta = random.random() - 0.5

        # smaller value fluctuations during hill climbing
        if self.mode.startswith(MODE_HILL_CLIMB):
           delta /= HILL_CLIMB_MULT

        new_value = self.prev_value + delta * 5

        if new_value < 0:
            new_value = 0
            self.watts_direction = "up"

        if new_value > RandomTestData.MAX_VALUE:
            new_value = RandomTestData.MAX_VALUE
            self.watts_direction = "down"

        self.prev_value = new_value

        efficiency_pct = None
        if self.mode.startswith(MODE_HILL_CLIMB):
            if random.random() > 0.5:
                self.mode = MODE_HILL_CLIMB_EXT
            else:
                self.mode = MODE_HILL_CLIMB_RET

            if self.start_of_scan is not None and self.start_of_scan != 0:
                efficiency_pct = (new_value / self.start_of_scan) * 100

            if self.mode == MODE_HILL_CLIMB_EXT:
                self.pos += 1
            elif self.mode == MODE_HILL_CLIMB_RET:
                self.pos -= 1
        elif self.mode == MODE_SCAN_RESET:
            self.pos = 0
        else:
            if self.mode == MODE_SCAN_EXT:
                if self.pos == 0:
                    self.start_of_scan = new_value
                self.pos += HILL_CLIMB_MULT
            elif self.mode == MODE_SCAN_RET:
                self.pos -= HILL_CLIMB_MULT


        retval = {
            'value': new_value,
            'mode': self.mode,
            'pos': self.pos,
        }

        if efficiency_pct is not None:
            retval["efficiency_pct"] = efficiency_pct

        return retval


class Metrics(object):
    PORT = 9732
    ADDR = ('0.0.0.0', PORT)
    NUM_LISTENER_THREADS = 2

    def __init__(self):
        self.data = None
        self.last_updated = None

    def setData(self, data):
        self.data = data
        self.last_updated = time.time()

    def getData(self):
        age = None
        if self.last_updated:
            age = time.time() - self.last_updated

        if self.data is not None:
            self.data['age'] = age
            return self.data
        else:
            return {'starting': True}

METRICS = Metrics()

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        response_obj = METRICS.getData()
        self.wfile.write(json.dumps(response_obj).encode(encoding='utf_8'))

        # debug print in a way thats easy to read
        value = response_obj.get("value")
        new_obj = {}
        for k, v in response_obj.items():
            if k != "value":
                new_obj[k] = v
        print("{}\t{}".format(new_obj, value))

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
    generator = RandomTestData()
    while True:
        if generator.mode.startswith(MODE_HILL_CLIMB):
            time.sleep(DELAY_BETWEEN_CLIMB_MOVES)
        else:
            time.sleep(DELAY_BETWEEN_SCAN_MOVES)

        METRICS.setData(generator.next())
