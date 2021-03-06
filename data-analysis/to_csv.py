#!/usr/bin/python3

PATH = "/home/nky"
all_rows = []
with open(PATH + "/measurements-2022-07-15.txt") as f:
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

with open(PATH + "/measurements-2022-07-15.csv", "w") as f:
    f.write("ts,delay,gen,ext,count,angle\n")
    for row in all_rows:
        f.write(",".join(row) + "\n")
