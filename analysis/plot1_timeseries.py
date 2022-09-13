#!/usr/bin/env python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib

from sklearn.linear_model import LinearRegression

matplotlib.use('TkAgg')

series = read_csv('~/measurements.csv', header=0, index_col=4)

ext = True
gen = 2082

series = series[series["gen"] == gen]
series = series[series["ext"] == ext]
series["ts_offset"] = series["ts"] - float(series.head(1)["ts"])
plot1 = series.plot(x="ts_offset", y="angle", fontsize=20)
plot1.set_title("Angle change over time", fontsize=20)

lin = LinearRegression()

scores = []
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
        scores.append(score)


        plot1.plot(fit_x, lin.predict(fit_x_tsb), c="r")


scores.sort()
print("Max score: {}".format(scores[-1]))
print("Min score: {}".format(scores[0]))

#plot1 = series[series["gen"] == gen][series["ext"] == ext].plot(y="angle", fontsize=20)
#plot1.set_title("Step size: 1 second", fontsize=50)

#plot2 = series[series["gen"] == 10][series["ext"] == ext].plot(y="angle", fontsize=20)
#plot2.set_title("Step size: 500 milliseconds", fontsize=50)
#
#plot2 = series[series["gen"] == 20][series["ext"] == ext].plot(y="angle", fontsize=20)
#plot2.set_title("Step size: 100 milliseconds", fontsize=50)
#
#plot2 = series[series["gen"] == 30][series["ext"] == ext].plot(y="angle", fontsize=20)
#plot2.set_title("Step size: 50 milliseconds", fontsize=50)

#plot2 = series[series["gen"] == 98][series["ext"] == ext].plot(y="angle", fontsize=20)
#plot2.set_title("Step size: 20 milliseconds", fontsize=50)

pyplot.show()

# df2 = series.head(1000)["angle"]
