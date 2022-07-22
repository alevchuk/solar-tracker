#!/home/nky/pandas/bin/python3

import pandas as pd
from pandas import read_csv
from matplotlib import pyplot
import matplotlib

import numpy as np
from scipy.fftpack import fft, ifft

matplotlib.use('TkAgg')

ext = True
series = read_csv('/home/nky/measurements.csv', header=0, index_col=4)
series = series[series["gen"] == 10][series["ext"] == ext]
#series = series.rolling(3).mean()
series = series.head(550)

plot1 = series.plot(y="angle", fontsize=20)
plot1.set_title("Raw data", fontsize=50)

def detect_outliers(data_1):
      outliers = []
      threashold = 50

      for idx, a in enumerate(np.abs(data_1)):
          if a > threashold or a < -threashold:
              outliers.append(idx)

      return outliers

freqs = fft(series["angle"].values)
plot_freqs = freqs.copy()
plot_freqs[0] = 0 ## drop 0Hz peak for plotting

peaks = detect_outliers(freqs)

print("Peaks:")
for idx in peaks:
    print(np.abs(freqs)[idx])
print()


for idx in peaks:
    if idx != 0:  # don't drop 0Hz
        freqs[idx] = 0
series["new_angle"] = ifft(freqs)


series["fft"] = plot_freqs

plotx = series.plot(y="fft", fontsize=20)
plotx.set_title("FFT frequencies", fontsize=50)

plotz = series.plot(y="new_angle", fontsize=20)
plotz.set_title("Filtered angles", fontsize=50)


pyplot.show()
