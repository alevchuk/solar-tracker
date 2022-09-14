#!/usr/bin/env python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib

from sklearn.linear_model import LinearRegression

matplotlib.use('TkAgg')

series = read_csv('~/measurements-2022-09-14-windy-day.csv', header=0, index_col=4)


# outliers
"""
Gen 3080 score sum: 223.08071150417643
Gen 5450 score sum: 157.66045556845572
Gen 9741 score sum: 156.0167686924164
Gen 8541 score sum: 155.89389623075536
Gen 2591 score sum: 155.63327220253197
Gen 1060 score sum: 150.06972861777223
Gen 1457 score sum: 148.9748549401625
Gen 6993 score sum: 148.56955283484152
Gen 816 score sum: 148.41948427752877
Gen 6062 score sum: 148.1667897348097
Gen 5818 score sum: 147.55967905882744
Gen 9114 score sum: 147.31451268492148
Gen 7851 score sum: 147.11521539618238
Gen 5292 score sum: 147.01903575210758
Gen 6045 score sum: 145.3307448827425
Gen 6864 score sum: 145.20663056356935
Gen 8799 score sum: 145.11412761744012
Gen 8797 score sum: 143.29001624617237
Gen 9050 score sum: 139.35420647927535
Gen 1798 score sum: 138.96844158806834
Gen 8308 score sum: 138.86322217213174
Gen 4224 score sum: 138.31187882884223
Gen 3350 score sum: 137.63845790070613
Gen 5010 score sum: 137.52281885139033
Gen 8483 score sum: 137.29185397392732
Gen 4718 score sum: 135.326198971045
Gen 6107 score sum: 132.89054073087425
Gen 5905 score sum: 131.67926767026128
Gen 3950 score sum: 130.0770547903217
Gen 8011 score sum: 129.7867521048588
Gen 7455 score sum: 127.6329298258799
Gen 4441 score sum: 81.20560384430813
"""
gen = 7455

series = series[series["gen"] == gen]
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
