#!/usr/bin/env python3
"""Prometheus exporter for SCL3300-D01 sensor temperature.

Reads from the local inclinometer TCP server (port 2017) and exposes
the sensor temperature as a Prometheus gauge on port 9103.
"""
import socket
import time
from prometheus_client import start_http_server, Gauge

INCLO_PORT = 2017
EXPORTER_PORT = 9103
POLL_INTERVAL = 15

g_temp = Gauge("scl3300_temperature_celsius", "SCL3300-D01 sensor temperature")


def get_sensor_temp():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(("127.0.0.1", INCLO_PORT))
        data = s.recv(1024).decode().strip()
    parts = data.split("\t")
    return float(parts[7])


def update_metrics():
    try:
        g_temp.set(get_sensor_temp())
    except Exception as e:
        print(f"Error reading sensor temperature: {e}")


if __name__ == "__main__":
    print(f"Starting SCL3300 sensor temperature exporter on :{EXPORTER_PORT}")
    start_http_server(EXPORTER_PORT)
    while True:
        update_metrics()
        time.sleep(POLL_INTERVAL)
