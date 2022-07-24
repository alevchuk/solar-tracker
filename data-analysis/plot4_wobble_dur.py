#!/home/nky/solar-tracker/data-analysis/bin/python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib
import math
import pandas as pd

matplotlib.use('TkAgg')
matplotlib.style.use('ggplot')

df = read_csv('~/steps.csv', header=0, index_col=4)

for ext in [True, False]:
    if ext:
        direction = "Direcion: extend"
    else:
        direction = "Direcion: retract"
        
    #plot2 = df[series["gen"] == 98][series["ext"] == ext].plot(y="angle", fontsize=20)
    #plot2.set_title("Step size: 20 milliseconds", fontsize=50)

    for gen in [0, 1, 2, 5, 10, 15, 20, 30]:
        df.query('ext == {} and gen == {}'.format(ext, gen)).plot(x="angles", y="wobble_dur", fontsize=20).set_title(
            "Step size: {} milliseconds, {}".format(1000 - (gen * 10), direction), fontsize=30)


pyplot.show()


