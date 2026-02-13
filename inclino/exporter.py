#!/usr/bin/env python3
import socket
import time
from prometheus_client import start_http_server, Gauge

INCLO_HOST = "192.168.50.80"
INCLO_PORT = 2017
EXPORTER_PORT = 9101
POLL_INTERVAL = 15

g_x = Gauge("inclinometer_x", "X-axis acceleration (g)")
g_y = Gauge("inclinometer_y", "Y-axis acceleration (g)")
g_z = Gauge("inclinometer_z", "Z-axis acceleration (g)")
g_deg = Gauge("inclinometer_deg", "Tilt angle (degrees)")
g_crc = Gauge("inclinometer_crc", "CRC ok rate")
g_sto = Gauge("inclinometer_sto", "Self-test output")
g_ts = Gauge("inclinometer_timestamp", "Sensor reading timestamp (unix)")


def get_reading():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect((INCLO_HOST, INCLO_PORT))
        data = s.recv(1024).decode().strip()
    parts = data.split("\t")
    return {
        "ts": float(parts[0]),
        "x": float(parts[1]),
        "y": float(parts[2]),
        "z": float(parts[3]),
        "deg": float(parts[4]),
        "crc": float(parts[5]),
        "sto": int(parts[6]),
    }


def update_metrics():
    try:
        r = get_reading()
        g_x.set(r["x"])
        g_y.set(r["y"])
        g_z.set(r["z"])
        g_deg.set(r["deg"])
        g_crc.set(r["crc"])
        g_sto.set(r["sto"])
        g_ts.set(r["ts"])
    except Exception as e:
        print(f"Error reading inclinometer: {e}")


if __name__ == "__main__":
    print(f"Starting inclinometer exporter on :{EXPORTER_PORT}")
    start_http_server(EXPORTER_PORT)
    while True:
        update_metrics()
        time.sleep(POLL_INTERVAL)
