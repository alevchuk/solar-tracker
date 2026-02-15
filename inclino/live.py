#!/usr/bin/env python3
"""Live display of SCL3300 angle readings at 1-second cadence."""
import socket
import time

PORT = 2017


def get_angles():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(("127.0.0.1", PORT))
        data = s.recv(1024).decode().strip()
    parts = data.split("\t")
    if len(parts) < 11:
        raise ValueError(f"expected 11+ fields, got {len(parts)}")
    total = float(parts[4])
    ang_x = float(parts[8])
    ang_y = float(parts[9])
    ang_z = float(parts[10])
    return ang_x, ang_y, ang_z, total


def main():
    print(f"{'X °':>10s}  {'Y °':>10s}  {'Z °':>10s}  {'Total °':>10s}")
    print("-" * 50)
    while True:
        try:
            x, y, z, total = get_angles()
            print(f"{x:10.4f}  {y:10.4f}  {z:10.4f}  {total:10.4f}")
        except Exception as e:
            print(f"  error: {e}")
        time.sleep(1)


if __name__ == "__main__":
    main()
