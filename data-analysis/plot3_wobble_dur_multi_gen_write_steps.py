#!./bin/python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib
import math
import pandas as pd

matplotlib.use('TkAgg')
matplotlib.style.use('ggplot')

data_all = read_csv('~/measurements.csv', header=0, index_col=4)

for ext in [True]:
    for gen in range(0, 98):
        data = data_all.query('ext == {} and gen == {}'.format(ext, gen))

        #<><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
        #
        #     Cacluate the duration of the wabble (in 3 steps)
        #
        #<><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
        
        data['wobble'] = data['angle'].rolling(20).mean()
        data['sma'] = data['angle'].rolling(20).mean()
        
        # 1. when SMA stops changing more than X1 degree from previous sma datapoint
        T1 = 0.01
        data['sma'][data['sma'].diff() > T1] = None
        data['sma'][data['sma'].diff() < -T1] = None
        
        # 2. values are within X2 degrees of the SMA
        T2 = 0.5
        data['sma'][(data['sma'] - data['angle']) > T2] = None
        data['sma'][(data['sma'] - data['angle']) < -T2] = None
        
        # 3. 1 and 2 were true for the the last T3 datapoints
        T3 = 30
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

df.to_csv("~/steps.csv")
