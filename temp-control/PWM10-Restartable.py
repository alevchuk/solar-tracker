#!/usr/bin/env python3
import time, os, signal

def _shutdown(signum, frame):
    raise SystemExit(0)

signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGHUP, _shutdown)

PWM_CHIP = "/sys/class/pwm/pwmchip0"
PWM_PATH = f"{PWM_CHIP}/pwm0"

PERIOD_NS = 1_000_000  # 1 kHz

MIN_DUTY = 0.1
MAX_DUTY = 20.0

# 0.1->20%: 40 steps of 0.5%, ~79ms each = 3s
STEP  = 0.5
DELAY = 3.0 / ((MAX_DUTY - MIN_DUTY) / STEP)

def w(path, val):
    with open(path, "w") as f:
        f.write(str(val))

def set_duty(pct):
    ns = int(PERIOD_NS * pct / 100)
    w(f"{PWM_PATH}/duty_cycle", ns)

# Setup — always disable first to handle dirty state from prior crash
if os.path.exists(PWM_PATH):
    w(f"{PWM_PATH}/enable", 0)
    w(f"{PWM_PATH}/duty_cycle", 0)

if not os.path.exists(PWM_PATH):
    w(f"{PWM_CHIP}/export", 0)
    time.sleep(0.1)

w(f"{PWM_PATH}/period", PERIOD_NS)
w(f"{PWM_PATH}/duty_cycle", 0)
w(f"{PWM_PATH}/enable", 1)
set_duty(MIN_DUTY)

print(f"Breathing: {MIN_DUTY}% --(3s)--> {MAX_DUTY}% and back")

duty      = MIN_DUTY
direction = 1

try:
    while True:
        set_duty(round(duty, 3))
        duty += direction * STEP
        duty = round(duty, 3)
        if duty >= MAX_DUTY:
            duty = MAX_DUTY
            direction = -1
        elif duty <= MIN_DUTY:
            duty = MIN_DUTY
            direction = 1
        time.sleep(DELAY)
except (KeyboardInterrupt, SystemExit):
    pass
finally:
    w(f"{PWM_PATH}/duty_cycle", 0)
    w(f"{PWM_PATH}/enable", 0)
    print("Stopped.")
