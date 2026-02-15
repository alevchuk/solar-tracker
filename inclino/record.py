#!/usr/bin/env python3
import socket
import json
import time
import os
from datetime import date

PORT = 2017
INTERVAL = 60


def output_file():
    return os.path.expanduser(f"~/inclino-{date.today()}.jsonl")


def get_reading():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(("127.0.0.1", PORT))
        data = s.recv(1024).decode().strip()
    parts = data.split("\t")
    reading = {
        "ts": round(float(parts[0]), 1),
        "x": float(parts[1]),
        "y": float(parts[2]),
        "z": float(parts[3]),
        "deg": round(float(parts[4]), 4),
        "crc": round(float(parts[5]), 2),
        "sto": int(parts[6]),
    }
    if len(parts) > 7:
        reading["temp"] = round(float(parts[7]), 2)
    if len(parts) > 10:
        reading["ang_x"] = round(float(parts[8]), 4)
        reading["ang_y"] = round(float(parts[9]), 4)
        reading["ang_z"] = round(float(parts[10]), 4)
    return reading


def main():
    print(f"Recording to {output_file()} every {INTERVAL}s")
    while True:
        try:
            reading = get_reading()
            with open(output_file(), "a") as f:
                f.write(json.dumps(reading) + "\n")
            print(f"{reading['ts']:.0f}  deg={reading['deg']}")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
