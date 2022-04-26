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

SCAN_SLEEP = 20


class RandomTestData(object):
    MAX_VALUE = 100

    def __init__(self):
        self.direction = "up"
        self.prev_value = 0
        self.mode = MODE_SCAN_RESET
        self.mode_start = time.time()
        self.next_mode_delay = SCAN_SLEEP

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
        self.update_mode()

        delta = random.random() - 0.5
        if self.direction == "up":
            if delta > 0:
                if not self.mode.startswith(MODE_HILL_CLIMB):
                    delta *= 2
        else:
            if delta < 0:
                if not self.mode.startswith(MODE_HILL_CLIMB):
                    delta *= 2

        new_value = self.prev_value + delta * 5
        if new_value < 0:
            new_value = 0
            self.direction = "up"

        if new_value > RandomTestData.MAX_VALUE:
            new_value = RandomTestData.MAX_VALUE
            self.direction = "down"

        self.prev_value = new_value

        if self.mode.startswith(MODE_HILL_CLIMB):
            if random.random() > 0.5:
                self.mode = MODE_HILL_CLIMB_EXT
            else:
                self.mode = MODE_HILL_CLIMB_RET

        return {
            'value': new_value,
            'mode': self.mode
        }


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
        self.data['age'] = age
        return self.data

METRICS = Metrics()

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        response_obj = METRICS.getData()
        print(response_obj)
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
    generator = RandomTestData()
    while True:
        METRICS.setData(generator.next())
        time.sleep(0.1)
