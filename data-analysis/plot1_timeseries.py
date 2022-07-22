#!/home/nky/pandas/bin/python3

from pandas import read_csv
from matplotlib import pyplot
import matplotlib

matplotlib.use('TkAgg')

ext = True
series = read_csv('/home/nky/measurements.csv', header=0, index_col=4)

plot1 = series[series["gen"] == 1][series["ext"] == ext].plot(y="angle", fontsize=20)
plot1.set_title("Step size: 1 second", fontsize=50)

plot2 = series[series["gen"] == 10][series["ext"] == ext].plot(y="angle", fontsize=20)
plot2.set_title("Step size: 500 milliseconds", fontsize=50)

plot2 = series[series["gen"] == 20][series["ext"] == ext].plot(y="angle", fontsize=20)
plot2.set_title("Step size: 100 milliseconds", fontsize=50)

plot2 = series[series["gen"] == 30][series["ext"] == ext].plot(y="angle", fontsize=20)
plot2.set_title("Step size: 50 milliseconds", fontsize=50)

#plot2 = series[series["gen"] == 98][series["ext"] == ext].plot(y="angle", fontsize=20)
#plot2.set_title("Step size: 20 milliseconds", fontsize=50)

pyplot.show()

# df2 = series.head(1000)["angle"]
