#!/home/nky/solar-tracker/data-analysis/bin/python3

import matplotlib.pyplot as plt
from matplotlib import pyplot
import seaborn as sns

from pandas import read_csv
import matplotlib
import math
import pandas as pd
import numpy as np
import sys

matplotlib.use('TkAgg')
matplotlib.style.use('ggplot')




# example_heatmap()

df = read_csv('~/steps.csv', header=0) #, index_col=4)

angles_range = range(0, 40)

df["angle_bin"] = None

for r in angles_range:
    df.loc[(r <= df["angles"]) & (df["angles"]< r + 1), "angle_bin"] = r


print(df)

# columns are gen
# index is angle
# value is wabble time


matrix = []
for gen in range(0, 98):
    row = []
    angles = df.loc[(df["gen"] == gen) & (df["ext"] == False)].sort_values(by=["angle_bin"])
    angles = angles.groupby("angle_bin").mean()

    print("gen: {}".format(gen))

    for a in angles_range:
        sub_df = angles.query("angle_bin == {}".format(a))
        if len(sub_df) > 0:
            row.append(sub_df[["wobble_dur"]].iloc[0,0])
        else:
            row.append(None)

    matrix.append(row)



df = pd.DataFrame(matrix, columns=list(angles_range), index=[1000 - (gen * 10) for gen in list(range(0, 98))])
df.replace([None], np.nan, inplace=True)
print(df)

# plot heatmap
ax = sns.heatmap(df)

# turn the axis label
for item in ax.get_yticklabels():
    item.set_rotation(0)

for item in ax.get_xticklabels():
    item.set_rotation(0)

# adjust the ticks for the primary axes
ax.tick_params(axis='both', labelsize=24)

# set the primary (left) y label
ax.set_ylabel('Step Size (milliseconds)', fontsize=38)

# set the primary (left) y label
ax.set_xlabel('Angle (degrees)', fontsize=38)

# save figure
plt.savefig('seabornPandas.png', dpi=100)
plt.show()





#heat_dict = {}
#for ext in [True]:
#    if ext:
#        direction = "Direcion: extend"
#    else:
#        direction = "Direcion: retract"
#        
#    for gen in range(0, 98):
#        ms = 1000 - (gen * 10)
#        heat_dict[ms] = []
#
#        for idx, row in df.query('ext == {} and gen == {}'.format(ext, gen)).iterrows():
#            heat_dict["row_angle"] = row["wobble_dur"]



