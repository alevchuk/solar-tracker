#!/usr/bin/env python3
import time, os

PWM_CHIP = "/sys/class/pwm/pwmchip0"
PWM_PATH = f"{PWM_CHIP}/pwm0"

PERIOD_NS = 1_000_000  # 1 kHz

MIN_DUTY = 0.1
MID_DUTY = 1.0
MAX_DUTY = 20.0

# slow zone 0.1->1%: 18 steps of 0.05%, ~167ms each = 3s
SLOW_STEP  = 0.05
SLOW_DELAY = 3.0 / ((MID_DUTY - MIN_DUTY) / SLOW_STEP)

# fast zone 1->20%: 38 steps of 0.5%, ~79ms each = 3s
FAST_STEP  = 0.5
FAST_DELAY = 3.0 / ((MAX_DUTY - MID_DUTY) / FAST_STEP)

def w(path, val):
    with open(path, "w") as f:
        f.write(str(val))

def set_duty(pct):
    ns = int(PERIOD_NS * pct / 100)
    w(f"{PWM_PATH}/duty_cycle", ns)

# Setup
if not os.path.exists(PWM_PATH):
    w(f"{PWM_CHIP}/export", 0)
    time.sleep(0.1)

w(f"{PWM_PATH}/period", PERIOD_NS)
w(f"{PWM_PATH}/duty_cycle", 0)
w(f"{PWM_PATH}/enable", 1)
set_duty(MIN_DUTY)

print(f"Breathing: {MIN_DUTY}% --(3s slow)--> {MID_DUTY}% --(3s fast)--> {MAX_DUTY}% and back")

duty      = MIN_DUTY
direction = 1

try:
    while True:
        set_duty(round(duty, 3))
        in_slow = (duty <= MID_DUTY) if direction == -1 else (duty < MID_DUTY)
        if in_slow:
            duty += direction * SLOW_STEP
            delay = SLOW_DELAY
        else:
            duty += direction * FAST_STEP
            delay = FAST_DELAY
        duty = round(duty, 3)
        if duty >= MAX_DUTY:
            duty = MAX_DUTY
            direction = -1
        elif duty <= MIN_DUTY:
            duty = MIN_DUTY
            direction = 1
        time.sleep(delay)
except KeyboardInterrupt:
    pass
finally:
    w(f"{PWM_PATH}/duty_cycle", 0)
    w(f"{PWM_PATH}/enable", 0)
    print("Stopped.")
