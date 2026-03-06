#!/usr/bin/env python3
import time, os, signal, socket

def _shutdown(signum, frame):
    raise SystemExit(0)

signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGHUP, _shutdown)

# --- Temperature sensor ---
INCLO_PORT = 2017

def get_temp():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(("127.0.0.1", INCLO_PORT))
        data = s.recv(1024).decode().strip()
    return float(data.split("\t")[7])

# --- PWM setup ---
PWM_CHIP = "/sys/class/pwm/pwmchip0"
PWM_PATH = f"{PWM_CHIP}/pwm0"
PERIOD_NS = 1_000_000  # 1 kHz

def w(path, val):
    with open(path, "w") as f:
        f.write(str(val))

def set_duty(pct):
    ns = int(PERIOD_NS * pct / 100)
    w(f"{PWM_PATH}/duty_cycle", ns)

if os.path.exists(PWM_PATH):
    w(f"{PWM_PATH}/enable", 0)
    w(f"{PWM_PATH}/duty_cycle", 0)

if not os.path.exists(PWM_PATH):
    w(f"{PWM_CHIP}/export", 0)
    time.sleep(0.1)

w(f"{PWM_PATH}/period", PERIOD_NS)
w(f"{PWM_PATH}/duty_cycle", 0)
w(f"{PWM_PATH}/enable", 1)

# --- PID parameters ---
SETPOINT = 24.0   # °C
DT       = 5      # loop interval (seconds)
MIN_OUT  = 0.0    # % duty
MAX_OUT  = 20.0   # % duty

Kp = 5.0
Ki = 0.05
Kd = 2.0

integral   = 0.0
prev_error = None

print(f"PID controller: setpoint={SETPOINT} °C, Kp={Kp}, Ki={Ki}, Kd={Kd}, range={MIN_OUT}-{MAX_OUT}%")

try:
    while True:
        temp = get_temp()
        error = SETPOINT - temp

        # Proportional
        p = Kp * error

        # Reset integral on zero crossing
        if prev_error is not None and error * prev_error < 0:
            integral = 0.0

        # Integral with anti-windup
        candidate = integral + Ki * error * DT
        raw_output = p + candidate + (Kd * (error - prev_error) / DT if prev_error is not None else 0)

        if MIN_OUT <= raw_output <= MAX_OUT:
            integral = candidate
        # else: don't accumulate — output is saturated

        # Derivative
        d = Kd * (error - prev_error) / DT if prev_error is not None else 0.0
        prev_error = error

        output = max(MIN_OUT, min(MAX_OUT, p + integral + d))
        set_duty(output)

        print(f"temp={temp:6.2f} °C  err={error:+6.2f}  P={p:5.2f} I={integral:5.2f} D={d:+6.2f}  duty={output:5.2f}%")
        time.sleep(DT)

except (KeyboardInterrupt, SystemExit):
    pass
finally:
    w(f"{PWM_PATH}/duty_cycle", 0)
    w(f"{PWM_PATH}/enable", 0)
    print("Stopped.")
