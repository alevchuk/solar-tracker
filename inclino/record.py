#!/usr/bin/env python3
import socket
import json
import time
import os

PORT = 2017
OUTPUT_FILE = os.path.expanduser("~/inclino.jsonl")
INTERVAL = 60


def get_reading():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(("127.0.0.1", PORT))
        data = s.recv(1024).decode().strip()
    parts = data.split("\t")
    return {
        "ts": round(float(parts[0]), 1),
        "x": float(parts[1]),
        "y": float(parts[2]),
        "z": float(parts[3]),
        "deg": round(float(parts[4]), 4),
        "crc": round(float(parts[5]), 2),
        "sto": int(parts[6]),
    }


def main():
    print(f"Recording to {OUTPUT_FILE} every {INTERVAL}s")
    while True:
        try:
            reading = get_reading()
            with open(OUTPUT_FILE, "a") as f:
                f.write(json.dumps(reading) + "\n")
            print(f"{reading['ts']:.0f}  deg={reading['deg']}")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
