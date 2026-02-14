#!/usr/bin/env python3
import subprocess
import time
from prometheus_client import start_http_server, Gauge

EXPORTER_PORT = 9102
POLL_INTERVAL = 15

g_temp = Gauge("pi_cpu_temperature_celsius", "Raspberry Pi CPU temperature")


def get_cpu_temp():
    out = subprocess.check_output(["vcgencmd", "measure_temp"]).decode().strip()
    # output looks like: temp=36.9'C
    return float(out.split("=")[1].rstrip("'C"))


def update_metrics():
    try:
        g_temp.set(get_cpu_temp())
    except Exception as e:
        print(f"Error reading temperature: {e}")


if __name__ == "__main__":
    print(f"Starting Pi temperature exporter on :{EXPORTER_PORT}")
    start_http_server(EXPORTER_PORT)
    while True:
        update_metrics()
        time.sleep(POLL_INTERVAL)
