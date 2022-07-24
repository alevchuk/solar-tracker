#!/home/nky/solar-tracker/data-analysis/bin/python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib
import math
import sys

matplotlib.use('TkAgg')
matplotlib.style.use('ggplot')

ext = False
# head -n1 ~/measurements.csv > ~/gen1.csv && awk -F, '$3 == 1 {print $0}' ~/measurements.csv >> ~/gen1.csv 
data = read_csv('~/gen1.csv', header=0, index_col=4)


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
T3 = 30
run_start = 0
run_length = 0

for idx in range(len(data)):
    row = data.iloc[idx]

    # check if run has ended
    if math.isnan(row['sma']):
        if run_length < T3:
            data.loc[run_start:idx, "sma"] = None

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

pyplot.show()

# df2 = data.head(1000)["angle"]
