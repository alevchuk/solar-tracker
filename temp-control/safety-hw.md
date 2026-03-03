---
name: heater-safety-hw
description: Physical hardware safety layers for Raspberry Pi heater control. Human-performed actions: wiring, pull-downs, relay interlocks, thermal cutoffs, fusing.
---

# Heater Control — Hardware Safety Actions

These are physical steps a human must perform. Software cannot substitute for any of these.
Reference `heater-gpio-behavior` for GPIO defaults and MOSFET gate voltage details.

## Layer 4 — External pull-down resistor (mandatory)

**What to buy:** 10kΩ resistor, 220–470Ω resistor (330Ω ideal)

**Where to wire it:** At the MOSFET module — not at the Pi.

**Circuit:**
```
Pi GPIO 18 → 330Ω series resistor → junction point → MOSFET trigger input
                                           ↓
                                     10kΩ to GND
```

- The 10kΩ holds the gate LOW whenever the Pi resets, reboots, or GPIO floats
- The 330Ω protects the Pi from gate capacitance inrush (~3nF for two AOD4184A)
- This is the single most impactful hardware decision — do this before anything else

**Verify:** Disconnect the Pi GPIO wire. Measure voltage at the MOSFET trigger input — should read near 0V (< 0.2V).

## Layer 5 — Normally-open relay interlock (strongly recommended)

**What to buy:** Mechanical relay module with normally-open (NO) contacts rated for your heater load. A 555-timer or ATtiny85-based heartbeat watchdog circuit.

**Principle:** Wire the NO relay in series with the heater power supply, upstream of the MOSFET module. The relay must be **actively energized** to allow power flow. In any failure state — Pi crashed, relay coil open, power lost — the contacts are open and the heater is off.

**Heartbeat circuit:** Drive the relay coil from an independent watchdog (555 timer or ATtiny85) that requires a continuous pulse from the Pi. If the Pi stops sending heartbeats, the relay drops out within seconds. This catches the gap where the OOM killer kills the watchdog-petting process without triggering a kernel panic.

**Note on relay failure:** Mechanical NO relays fail open ~99.999% of the time — the fail-safe direction.

**Verify:** Kill the Pi process that sends heartbeats. The relay should drop out and the heater should lose power within the watchdog timeout.

## Layer 6 — KSD301 resettable thermal cutoff (essential)

**What to buy:** KSD301 bimetal thermostat, normally-closed (NC), **manual-reset** type, rated 10–20°C above your maximum operating temperature.

**Where to mount:** Directly on or immediately adjacent to the heater element.

**Wiring:** In series with the heater power line (not the control signal — the actual power).

- Manual-reset requires human intervention to restart → prevents unattended thermal cycling
- Opens the circuit on over-temperature regardless of software, GPIO state, or MOSFET condition

**Verify:** Apply heat to the thermostat body with a heat gun. Confirm the heater loses power at the rated trip point. Confirm it does not self-reset.

## Layer 7 — One-shot thermal fuse (last resort)

**What to buy:** SEFUSE-type thermal fuse rated 20–40°C above the KSD301 trip point.

**Where to wire:** In series with the heater power line, between the KSD301 and the heater element.

- Permanently opens and must be physically replaced — exists only for catastrophic failure
- Catches the scenario where the KSD301 fails closed or is bypassed somehow

**Verify:** Do not test by tripping it — inspect installation. Note the fuse location for future replacement access.

## Fusing and wiring

**Fuse sizing:** 125% of continuous current draw.
- 400W at 24V = 16.7A → use a 20A fast-blow fuse

**Wire gauge:** 12 AWG minimum for 20A runs under 6 feet. Oversize for longer DC runs where voltage drop matters.

**Wire all power connections before software development begins** — the hardware interlocks must be in place before the heater is ever energized.

## Hardware safety checklist

Before first power-on:
- [ ] GPIO 18 selected (default pull-down, hardware PWM capable)
- [ ] 330Ω series resistor between Pi GPIO and MOSFET trigger
- [ ] 10kΩ pull-down resistor at MOSFET module (gate to GND)
- [ ] Floating gate test: disconnect Pi, measure gate voltage < 0.2V
- [ ] NO relay in series with heater supply, driven by independent watchdog
- [ ] KSD301 manual-reset thermostat mounted on heater, in series with power
- [ ] Thermal fuse in series with power, between thermostat and heater
- [ ] Fuse sized at 125% continuous current
- [ ] Wire gauge appropriate for load and run length
