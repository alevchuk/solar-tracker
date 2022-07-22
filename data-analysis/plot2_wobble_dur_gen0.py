#!/home/nky/pandas/bin/python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib
import math
import sys

matplotlib.use('TkAgg')
matplotlib.style.use('ggplot')

ext = False
# head -n1 /home/nky/measurements.csv > gen1.csv && awk -F, '$3 == 1 {print $0}' /home/nky/measurements.csv >> gen1.csv 
data = read_csv('gen1.csv', header=0, index_col=4)


# calculating simple moving average
data['wobble'] = data['angle'].rolling(100).mean()
data['sma'] = data['angle'].rolling(100).mean()
 
# to cacluate the duration of the wabble, we'll find 1 and 2:

# 1. when SMA stops changing more than X1 degree from previous sma datapoint
T1 = 0.01
data['sma'][data['sma'].diff() > T1] = None
data['sma'][data['sma'].diff() < -T1] = None

# 2. values are within X2 degrees of the SMA
T2 = 0.5
data['sma'][(data['sma'] - data['angle']) > T2] = None
data['sma'][(data['sma'] - data['angle']) < -T2] = None

# 3. 1 and 2 were true for the the last T3 datapoints
T3 = 10
run_start = 0
run_length = 0

for idx in range(len(data)):
    row = data.iloc[idx]

    # check if run has ended
    if math.isnan(row['sma']):
        if run_length < T3:
            data['sma'][run_start:idx] = None

        run_length = 0
        run_start = idx
    else:
        run_length += 1
        print("@{} run length: {}".format(idx, run_length))

 
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
