#!/home/nky/pandas/bin/python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib
import math
import pandas as pd

matplotlib.use('TkAgg')
matplotlib.style.use('ggplot')

data = read_csv('/home/nky/measurements.csv', header=0, index_col=4)


# calculating simple moving average
data['wobble'] = data['angle'].rolling(100).mean()
data['sma'] = data['angle'].rolling(100).mean()
 
# to cacluate the duration of the wabble, we'll find 1 and 2:

# 1. when SMA stops changing more than X1 degree from previous sma datapoint
X1 = 0.01
data['sma'][data['sma'].diff() > X1] = None
data['sma'][data['sma'].diff() < -X1] = None

# 2. values are within X2 degrees of the SMA
X2 = 0.5
data['sma'][(data['sma'] - data['angle']) > X2] = None
data['sma'][(data['sma'] - data['angle']) < -X2] = None

# 3. 1 and 2 were true for the the last X3 datapoints
X3 = 10
run_start = 0
run_length = 0

step_start_angle = None
prev_run_end = 0

steps_angles = []
steps_wobble_duration = []
steps_ext = []
steps_gen = []

for idx in range(len(data)):
    row = data.iloc[idx]
    print(row)

    # check if run has ended
    if math.isnan(row['sma']):
        print((run_start, idx))
        if run_length < X3:
            data['sma'][run_start:idx] = None

        # fill in steps data
        steps_angles.append(step_start_angle)
        steps_wobble_duration.append(run_start - prev_run_end)
        steps_ext.append(row['ext'])
        steps_gen.append(row['gen'])

        prev_run_end = run_start + run_length

        run_length = 0
        run_start = idx

    else:
        run_length += 1
        step_start_angle = row['angle']

 


#for idx, row in data.iterrows():
#    # step
#    if idx % 1000 == 0:
#        # drop values for the prev step
#        if idx > 1000:
#           data['sma'][step_start:first_long_run_start] = None
#           print(run_lenght)
#           print("Dropping from {} to {}".format(step_start, first_long_run_start))
#
#        steps_angles.append(step_start_angle)
#        steps_wobble_duration.append(first_long_run_start - step_start)
#        steps_ext.append(row['ext'])
#        steps_gen.append(row['gen'])
#        
#        run_lenght = 0
#        first_long_run_start = idx
#        step_start = idx
#        step_start_angle = row['angle']
#
#    if math.isnan(row['sma']):
#        if run_lenght < 50:
#            # reset the long run if it's not long enough
#            run_lenght = 0
#            first_long_run_start = idx
#    else:
#        run_lenght += 1

df = pd.DataFrame.from_dict(
    {
        'angles': steps_angles,
        'wobble_dur': steps_wobble_duration,
        'ext': steps_ext,
        'gen': steps_gen
    }
)

df.to_csv("steps.csv")

for ext in [True, False]:
    if ext:
        direction = "Direcion: extend"
    else:
        direction = "Direcion: retract"
        
    #plot2 = df[series["gen"] == 98][series["ext"] == ext].plot(y="angle", fontsize=20)
    #plot2.set_title("Step size: 20 milliseconds", fontsize=50)

    for gen in [0, 50, 90, 98]:
        df.query('ext == {} and gen == {}'.format(ext, gen)).plot(x="angles", y="wobble_dur", fontsize=20).set_title(
            "Step size: {} milliseconds, {}".format(1000 - (gen * 10), direction), fontsize=30)


pyplot.show()







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
X1 = 0.01
data['sma'][data['sma'].diff() > X1] = None
data['sma'][data['sma'].diff() < -X1] = None

# 2. values are within X2 degrees of the SMA
X2 = 0.5
data['sma'][(data['sma'] - data['angle']) > X2] = None
data['sma'][(data['sma'] - data['angle']) < -X2] = None

# 3. 1 and 2 were true for the the last 50 datapoints
run_start = 0
run_length = 0

for idx in range(len(data)):
    row = data.iloc[idx]

    # check if run has ended
    if math.isnan(row['sma']):
        if run_length < 10:
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
