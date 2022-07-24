#!./bin/python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib
import math
import pandas as pd

matplotlib.use('TkAgg')
matplotlib.style.use('ggplot')

data_all = read_csv('~/measurements.csv', header=0, index_col=4)

steps_angles = []
steps_wobble_duration = []
steps_ext = []
steps_gen = []

for ext in [True, False]:
    for gen in data_all["gen"].unique():

        data = data_all.query('ext == {} and gen == {}'.format(ext, gen))

        #<><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
        #
        #     Cacluate the duration of the wabble (in 3 steps)
        #
        #<><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
        
        data.insert(4, 'wobble', data['angle'].rolling(20).mean())
        data.insert(5, 'sma', data['angle'].rolling(20).mean())

        # 1. when SMA stops changing more than X1 degree from previous sma datapoint
        T1 = 0.01
        data.loc[data['sma'].diff() > T1,"sma"] = None
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
        
            # check if stable run has ended
            if math.isnan(row['sma']):
                if run_length < T3:
                    data[run_start:idx]["sma"] = None  # data.loc[] approach does not work
        
                run_length = 0
                run_start = idx
            else:
                run_length += 1
       
        
        print("Gen: {}".format(gen))
        print(data)

        run_start = None
        prev_run_end = None
        run_start_angle = None
        for idx in range(len(data)):
            row = data.iloc[idx]
            if math.isnan(row['sma']):
                # stable run has ended
                if run_start_angle is not None and run_start is not None and prev_run_end is not None:
                    # fill in steps data
                    steps_angles.append(run_start_angle)
                    steps_wobble_duration.append(run_start - prev_run_end)
                    steps_ext.append(row['ext'])
                    steps_gen.append(row['gen'])
                prev_run_end = run_start
                run_start = None
                
            else:
                # run is still going
                if run_start is None:
                    # start of the run
                    run_start = idx
                    run_start_angle = row['angle']




#for idx in range(len(data)):
#    row = data.iloc[idx]
#    print(row)
#
#    # check if run has ended
#    if math.isnan(row['sma']):
#        print((run_start, idx))
#        if run_length < X3:
#            data['sma'][run_start:idx] = None
#
#
#        prev_run_end = run_start + run_length
#
#        run_length = 0
#        run_start = idx
#
#    else:
#        run_length += 1
#        step_start_angle = row['angle']

 
df = pd.DataFrame.from_dict(
    {
        'angles': steps_angles,
        'wobble_dur': steps_wobble_duration,
        'ext': steps_ext,
        'gen': steps_gen
    }
)

df.to_csv("~/steps.csv")
