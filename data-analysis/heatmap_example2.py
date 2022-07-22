from pandas import read_csv
from pandas import DataFrame
from pandas import Grouper
from matplotlib import pyplot
import matplotlib

matplotlib.use('TkAgg')
matplotlib.style.use('ggplot')

series = read_csv('daily-minimum-temperatures.csv', header=0, index_col=0, parse_dates=True, squeeze=True)
print(series)
groups = series.groupby(Grouper(freq='A'))
years = DataFrame()
for name, group in groups:
	years[name.year] = group.values

print(years)

years = years.T
pyplot.matshow(years, interpolation=None, aspect='auto')
pyplot.show()
