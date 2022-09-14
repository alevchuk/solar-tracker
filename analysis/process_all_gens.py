#!/usr/bin/env python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib

from sklearn.linear_model import LinearRegression

matplotlib.use('TkAgg')

df = read_csv('~/measurements-2022-09-14-windy-day.csv', header=0, index_col=4)

gens_list = df["gen"].unique()

lin = LinearRegression()
scores = {}
count = 0
total = len(gens_list)
for gen in gens_list:
    series = df[df["gen"] == gen].copy()

    series["ts_offset"] = series["ts"] - float(series.head(1)["ts"])
    #plot1 = series.plot(x="ts_offset", y="angle", fontsize=20)
    #plot1.set_title("Angle change over time", fontsize=20)
    
    score_sum = 0
    for start in range(100, len(series), 50):
        diff = 100
        end = start + diff
        if end > len(series) - 100:
            break
    
        fit_x = series["ts_offset"][start:end]
        fit_x_tsb = series[["ts_offset"]][start:end]  # two square brackets (TSB)
        fit_y = series["angle"][start:end]
        lin.fit(fit_x_tsb, fit_y)
        score = lin.score(fit_x_tsb, fit_y)
    
        if score > 0.1:
            score_sum += score
            #plot1.plot(fit_x, lin.predict(fit_x_tsb), c="r")

    scores[gen] = score_sum 

    count += 1
    print("{} of {}".format(count, total))

for t in sorted(scores.items(), key=lambda x:x[1], reverse=True):
    gen, score_sum = t
    print("Gen {} score sum: {}".format(gen, score_sum))


#pyplot.show()
