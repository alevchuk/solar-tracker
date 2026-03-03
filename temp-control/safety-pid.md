---
name: heater-safety-pid
description: PID control code patterns and sensor validation for Raspberry Pi heater control. Software actions: output clamping, dead man's switch, temperature sensor validation, thermal runaway detection.
---

# Heater Control — PID Code Patterns and Sensor Validation

These are software patterns for the heater control loop itself. Claude Code can help implement these.
Reference `heater-safety-sw` for watchdog setup. Reference `heater-safety-hw` for hardware prerequisites.

## Layer 1 — PID output clamping (prevent runaway in software)

Always clamp PID output. With `simple-pid`:

```python
from simple_pid import PID

pid = PID(Kp=1.0, Ki=0.1, Kd=0.05, setpoint=target_temp)
pid.output_limits = (0, 80)  # Max 80% duty cycle — never 100%
```

The `output_limits` clamp also automatically prevents integral windup.

### Rate-of-change limiting (manual wrapper)

Cap output changes to prevent thermal shock and give safety systems time to react:

```python
MAX_CHANGE_PER_SECOND = 5.0  # percent per second
last_output = 0.0
last_time = time.monotonic()

def rate_limited_output(raw_output):
    global last_output, last_time
    now = time.monotonic()
    dt = now - last_time
    max_delta = MAX_CHANGE_PER_SECOND * dt
    clamped = max(last_output - max_delta, min(last_output + max_delta, raw_output))
    last_output = clamped
    last_time = now
    return clamped
```

## Dead man's switch pattern (most important control pattern)

**The heater must be off by default and require active, continuous commanding to stay on.**

If any part of the loop fails — sensor read, PID calculation, safety check — output drops to zero immediately.

```python
import RPi.GPIO as GPIO
import time

HEATER_PIN = 18
LOOP_TIMEOUT = 2.0  # seconds — if loop hangs, heater goes off

GPIO.setmode(GPIO.BCM)
GPIO.setup(HEATER_PIN, GPIO.OUT, initial=GPIO.LOW)

def control_loop():
    while True:
        start = time.monotonic()
        try:
            temp = read_temperature()          # raises on failure
            validate_temperature(temp)         # raises on invalid reading
            output = compute_pid(temp)         # raises on error
            set_heater(output)
        except Exception as e:
            set_heater(0)                      # fail OFF immediately
            log.error(f"Control loop error: {e}")

        elapsed = time.monotonic() - start
        if elapsed > LOOP_TIMEOUT:
            set_heater(0)
            log.error(f"Loop overrun: {elapsed:.1f}s")

        time.sleep(max(0, 1.0 - elapsed))     # 1Hz control loop
```

## Temperature sensor validation (DS18B20 specific)

DS18B20 known bad values:
- `85.0°C` — power-on reset, not a real reading
- `-127.0°C` — communication failure

```python
VALID_RANGE = (5.0, 150.0)       # °C — reject outside this range
MAX_RATE = 10.0                   # °C/second — reject sudden jumps
MAX_CONSECUTIVE_FAILURES = 3

last_temp = None
last_temp_time = None
failure_count = 0

def validate_temperature(temp):
    global last_temp, last_temp_time, failure_count

    # DS18B20 sentinel values
    if temp == 85.0 or temp == -127.0:
        raise ValueError(f"DS18B20 sentinel value: {temp}")

    # Range check
    if not (VALID_RANGE[0] <= temp <= VALID_RANGE[1]):
        raise ValueError(f"Temperature out of range: {temp}")

    # Rate-of-change check
    now = time.monotonic()
    if last_temp is not None and last_temp_time is not None:
        dt = now - last_temp_time
        if dt > 0:
            rate = abs(temp - last_temp) / dt
            if rate > MAX_RATE:
                raise ValueError(f"Temperature changed too fast: {rate:.1f}°C/s")

    last_temp = temp
    last_temp_time = now
    failure_count = 0  # reset on good reading

def read_and_validate():
    global failure_count
    try:
        temp = read_raw_temperature()
        validate_temperature(temp)
        return temp
    except Exception as e:
        failure_count += 1
        if failure_count >= MAX_CONSECUTIVE_FAILURES:
            set_heater(0)
            raise RuntimeError(f"Sensor failed {failure_count} times: {e}")
        raise
```

## Dual sensor cross-check

If a second independent sensor is available:

```python
def cross_check_sensors(temp1, temp2, max_divergence=5.0):
    if abs(temp1 - temp2) > max_divergence:
        set_heater(0)
        raise RuntimeError(
            f"Sensor divergence {abs(temp1-temp2):.1f}°C > {max_divergence}°C — assuming failure"
        )
    return (temp1 + temp2) / 2  # use average if both agree
```

## Thermal runaway detection (from Marlin firmware, field-tested)

These thresholds come from thousands of 3D printer deployments:

```python
RUNAWAY_HEATING_TIMEOUT = 20    # seconds to rise 2°C while heating
RUNAWAY_HEATING_DELTA = 2.0     # °C expected rise during active heating
RUNAWAY_STABLE_TIMEOUT = 40     # seconds at setpoint before checking drift
RUNAWAY_STABLE_DELTA = 4.0      # °C max drift from setpoint

class ThermalRunawayDetector:
    def __init__(self):
        self.heating_since = None
        self.temp_at_start = None
        self.at_setpoint_since = None

    def check(self, current_temp, setpoint, heater_output):
        now = time.monotonic()

        if heater_output > 0 and current_temp < setpoint - 2:
            # Should be heating — check for progress
            if self.heating_since is None:
                self.heating_since = now
                self.temp_at_start = current_temp
            elif (now - self.heating_since) > RUNAWAY_HEATING_TIMEOUT:
                delta = current_temp - self.temp_at_start
                if delta < RUNAWAY_HEATING_DELTA:
                    raise RuntimeError(
                        f"Thermal runaway: heating {now - self.heating_since:.0f}s, "
                        f"only rose {delta:.1f}°C (sensor fault or heater disconnected?)"
                    )
        else:
            self.heating_since = None
            self.temp_at_start = None

        if abs(current_temp - setpoint) <= 2:
            # At setpoint — check for drift
            if self.at_setpoint_since is None:
                self.at_setpoint_since = now
            elif (now - self.at_setpoint_since) > RUNAWAY_STABLE_TIMEOUT:
                if abs(current_temp - setpoint) > RUNAWAY_STABLE_DELTA:
                    raise RuntimeError(
                        f"Thermal runaway: drifted {abs(current_temp - setpoint):.1f}°C from setpoint"
                    )
        else:
            self.at_setpoint_since = None
```

## Systemd watchdog heartbeat integration

In your control loop, call this every ~5 seconds (half the `WatchdogSec=10` interval):

```python
import sdnotify  # pip install sdnotify

notifier = sdnotify.SystemdNotifier()
notifier.notify("READY=1")  # signal startup complete

# In loop:
notifier.notify("WATCHDOG=1")
```

Or without the library:
```python
import subprocess
subprocess.run(["systemd-notify", "WATCHDOG=1"], check=False)
```

## Summary: control loop safety requirements

- [ ] PID output clamped to (0, 80) — never full power
- [ ] Rate-of-change limit on output changes (5%/s)
- [ ] Dead man's switch: heater off on any exception
- [ ] DS18B20 sentinel values rejected (85.0, -127.0)
- [ ] Range check: reject readings outside 5–150°C
- [ ] Rate-of-change check: reject jumps > 10°C/s
- [ ] Consecutive failure counter: shut down after 3 bad reads
- [ ] Dual sensor cross-check if second sensor available
- [ ] Thermal runaway detection (Marlin thresholds)
- [ ] systemd watchdog heartbeat every ~5s
