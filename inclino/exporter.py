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
g_temp = Gauge("inclinometer_temp_celsius", "SCL3300 sensor temperature (celsius)")
g_ang_x = Gauge("inclinometer_ang_x_deg", "SCL3300 angle X (degrees)")
g_ang_y = Gauge("inclinometer_ang_y_deg", "SCL3300 angle Y (degrees)")
g_ang_z = Gauge("inclinometer_ang_z_deg", "SCL3300 angle Z (degrees)")


def get_reading():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect((INCLO_HOST, INCLO_PORT))
        data = s.recv(1024).decode().strip()
    parts = data.split("\t")
    reading = {
        "ts": float(parts[0]),
        "x": float(parts[1]),
        "y": float(parts[2]),
        "z": float(parts[3]),
        "deg": float(parts[4]),
        "crc": float(parts[5]),
        "sto": int(parts[6]),
    }
    if len(parts) > 7:
        reading["temp"] = float(parts[7])
    if len(parts) > 10:
        reading["ang_x"] = float(parts[8])
        reading["ang_y"] = float(parts[9])
        reading["ang_z"] = float(parts[10])
    return reading


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
        if "temp" in r:
            g_temp.set(r["temp"])
        if "ang_x" in r:
            g_ang_x.set(r["ang_x"])
            g_ang_y.set(r["ang_y"])
            g_ang_z.set(r["ang_z"])
    except Exception as e:
        print(f"Error reading inclinometer: {e}")


if __name__ == "__main__":
    print(f"Starting inclinometer exporter on :{EXPORTER_PORT}")
    start_http_server(EXPORTER_PORT)
    while True:
        update_metrics()
        time.sleep(POLL_INTERVAL)
