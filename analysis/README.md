= Before running any commands here =

== (frequent) Every time you open a new shell ==
run:
```
. ./bin/activate
```

== (sometimes) Every time you get a new measurements.txt file ==
```
echo ts,delay,gen,ext,count,angle > ~/measurements.csv
cat ~/measurements.txt | tr '\t' ',' >> ~/measurements.csv
```

== (rare) Every time you get a fresh linux install ==
```
sudo apt-get install python3-tk
sudo apt install python3.10-venv
```

== (rare) Every time you clone github repo ==
```
cd solar-tracker
python3 -m venv analysis
cd analysis/
. ./bin/activate
pip install pandas matplotlib sklearn
```
