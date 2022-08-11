#!/usr/bin/python3

import os

def path(path):
    return os.path.expanduser(path)

all_rows = []
with open(path("~/measurements-2022-07-15.txt")) as f:
    for line in f:
        #ts, delay, gen, ext, count, angle = line.split()
        #ts = float(ts)
        #delay = float(delay)
        #gen = int(gen)
        #ext = bool(ext)
        #count = int(count)
        #angle = float(angle)

        #all_rows.append([ts, gen, ext, count, angle])
        all_rows.append(line.split())

with open(path("~/measurements-2022-07-15.csv"), "w") as f:
    f.write("ts,delay,gen,ext,count,angle\n")
    for line_no, row in enumerate(all_rows):
        if row[2].isdigit():
            f.write(",".join(row) + "\n")
        else:
            print("BAD ROW: {}".format(line_no))
