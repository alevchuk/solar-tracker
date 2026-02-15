#!/usr/bin/env python3
"""Live display of SCL3300 angle readings at 1-second cadence."""
import argparse
import os
import socket
import time

PORT = 2017
MIN_RANGE = 0.005  # minimum +/- range in degrees


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
    return ang_x, ang_y, total


def bar(value, scale, width, label="x"):
    mid = width // 2
    pos = int(mid + (value / scale) * mid)
    pos = max(0, min(width - 1, pos))
    line = list(" " * width)
    marker = f"|{label}|"
    start = mid - len(marker) // 2
    for i, ch in enumerate(marker):
        line[start + i] = ch
    if pos <= start:
        for i in range(pos, start):
            line[i] = "*"
    elif pos >= start + len(marker):
        for i in range(start + len(marker), pos + 1):
            line[i] = "*"
    return "".join(line)


def main():
    parser = argparse.ArgumentParser(description="Live SCL3300 angle display")
    parser.add_argument("-1", "--once", action="store_true",
                        help="print one reading and exit")
    args = parser.parse_args()

    zero_x, zero_y = None, None
    peak = MIN_RANGE
    while True:
        try:
            cols = os.get_terminal_size().columns
        except OSError:
            cols = 80
        label_w = 18
        bar_w = cols - label_w
        if bar_w < 10:
            bar_w = 10
        try:
            x, y, total = get_angles()
            if args.once:
                print(f"X={x:+.4f}° Y={y:+.4f}° total={total:.4f}°")
                return
            if zero_x is None:
                zero_x, zero_y = x, y
                print(f"  zero: X={zero_x:+.4f}° Y={zero_y:+.4f}°")
            dx = x - zero_x
            dy = y - zero_y
            peak = max(peak, abs(dx), abs(dy))
            scale = peak * 1.1
            print(f"X {dx:+8.4f} {bar(dx, scale, bar_w, 'x')}  ±{scale:.4f}°")
            print(f"Y {dy:+8.4f} {bar(dy, scale, bar_w, 'y')}")
            print(f"  total: {total:.4f}°")
        except Exception as e:
            print(f"  error: {e}")
            if args.once:
                return
        time.sleep(0.2)


if __name__ == "__main__":
    main()
