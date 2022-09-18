#!/usr/bin/env python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib
import math
import sys

matplotlib.use('TkAgg')
matplotlib.style.use('ggplot')

# head -n1 ~/measurements.csv > ~/gen1.csv && awk -F, '$3 == 1 {print $0}' ~/measurements.csv >> ~/gen1.csv 
df = read_csv('~/measurements-2022-09-14-fast-moves-with-watts2.csv', header=0)

def show_gens(df):
    meta = {}
    gens_list = df["gen"].unique()
    for gen in gens_list:
        subset = df[df["gen"] == gen]
        meta[min(subset["ts"])] = gen
    
    first_ts = df["ts"][0]
    count = 0
    for t in sorted(meta.items(), key=lambda x:x[0], reverse=False):
        ts, gen = t
        count += 1
        print("{} offset: {:.2f} hours gen: {}".format(count, (ts - first_ts) / 3600, gen))

## show_gens(df); sys.exit()

gen = 5502718  # 70w
gen = 2083620
gen = 1415321

series = df[df["gen"] == gen].copy()



# todo fill-in missing timestamps for watts
series = series[series["watts"] != "None"]
series["watts"] = series["watts"] / 1000 
print(series)
series["watts_ts_offset"] = series["watts_ts"] - float(series.head(1)["watts_ts"])
plot1 = series.plot(x="watts_ts_offset", y="watts", fontsize=20)
plot1.set_title("Watts change over time", fontsize=20)

series["ts_offset"] = series["ts"] - float(series.head(1)["ts"])
plot2 = series.plot(x="ts_offset", y="angle", fontsize=20, ax=plot1)

plot2.set_title("Angle change over time", fontsize=20)
pyplot.show()

sys.exit()

#<><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
#
#     Cacluate the duration of the wabble (in 3 steps)
#
#<><><><><><><><><><><><><><><><><><><><><><><><><><><><><>

data['wobble'] = data['angle'].rolling(20).mean()
data['sma'] = data['angle'].rolling(20).mean()

# 1. when SMA stops changing more than X1 degree from previous sma datapoint
T1 = 0.01
data.loc[data['sma'].diff() > T1, "sma"] = None
data.loc[data['sma'].diff() < -T1, "sma"] = None

# 2. values are within X2 degrees of the SMA
T2 = 0.5
data.loc[(data['sma'] - data['angle']) > T2, "sma"] = None
data.loc[(data['sma'] - data['angle']) < -T2, "sma"] = None

# 3. 1 and 2 were true for the the last T3 datapoints
T3 = 50
run_start = 0
run_length = 0

for idx in range(len(data)):
    row = data.iloc[idx]

    # check if run has ended
    if math.isnan(row['sma']):
        if run_length < T3:
            data["sma"][run_start:idx] = None  # data.loc[] approach does not work

        run_length = 0
        run_start = idx
    else:
        run_length += 1
        #print("@{} run length: {}".format(idx, run_length))

 
#plot1 = data[data["gen"] == 0][data["ext"] == ext].plot(y="angle", fontsize=20)
#pyplot.plot(data.index, data["wobble"], linewidth=3)
pyplot.plot(data.index, data["sma"], linewidth=8)
pyplot.plot(data.index, data["angle"], linewidth=2)
pyplot.title("Step size: 1 second", fontsize=50)

#pyplot.legend(["wobble", "stable", "angle"], loc=2, prop={'size': 40})
pyplot.legend(["stable", "angle"], loc=2, prop={'size': 40})


#plot1 = data.plot(y="sma", fontsize=20)
#plot2 = data.plot(y="angle", fontsize=20)


# df2 = data.head(1000)["angle"]
