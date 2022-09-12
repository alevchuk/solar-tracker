= Before running any commands here =

== (frequent) Every time you open a new shell ==
run:
```
. ./bin/activate
```

== (rare) Every time you clone github repo ==
```
cd solar-tracker
virtualenv -p python3 analysis/
cd analysis/
. ./bin/activate
pip install pandas matplotlib
```
