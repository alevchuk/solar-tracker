---
name: heater-gpio-behavior
description: Reference for BCM2711 GPIO default states and MOSFET gate behavior in heater control. Load when debugging GPIO or MOSFET issues.
---

# GPIO and MOSFET Behavior Reference

Use this as a lookup when reasoning about failure modes or debugging heater control circuits.

## BCM2711 GPIO defaults at power-on

The Pi 4's BCM2711 initializes all GPIO as inputs with per-pin pull resistors (~50kΩ):

| GPIO range | Default pull | Boot voltage | Safety for heater |
|------------|-------------|--------------|-------------------|
| GPIO 0–8   | Pull-UP (3.3V) | HIGH | **Dangerous — avoid** |
| GPIO 9–27  | Pull-DOWN (GND) | LOW | Safe |

**Use GPIO 18** (default pull-down, hardware PWM capable) for heater control.

## What happens to GPIO when software fails

| Failure scenario | GPIO pin state | Hardware PWM | Software PWM | Heater risk |
|-----------------|---------------|--------------|--------------|-------------|
| Process crash (SIGKILL) | Stays at last value | Keeps running | Stops (random freeze) | HIGH |
| Kernel panic | Stays at last value | Keeps running | Stops | HIGH |
| OOM / CPU starvation | Unpredictable | Keeps running | Jittery or frozen | HIGH |
| Clean shutdown | Input + default pull | Stops (firmware) | Stops | Low (GPIO 9–27) |
| Power loss | Full reset to defaults | Stops | Stops | Low |
| Watchdog reset | Full reset to defaults | Stops | Stops | Low |

**Key insight:** Hardware PWM is the most dangerous — the BCM2711 PWM peripheral is an autonomous hardware state machine that continues after process crash, pigpio daemon crash, and even kernel panic. It stops only on explicit register writes, firmware shutdown, or power loss.

## D4184-based dual MOSFET module

The common "DC 400W Dual MOSFET" module uses two AOD4184A N-channel MOSFETs in parallel.

- Gate threshold V_GS(th): **1.7V–2.6V** (begins conducting at 1.7V minimum)
- Built-in pull-down: 10kΩ–100kΩ (varies by clone manufacturer)
- No per-gate resistors, no flyback diode

### Why GPIO 0–8 are unsafe with this module

A GPIO 0–8 pin in default pull-up state (3.3V through ~50kΩ internal) with a 100kΩ clone pull-down on the module:

```
V_gate = 3.3V × 100k / (100k + 50k) ≈ 2.2V  → ABOVE 1.7V threshold → MOSFET ON
```

Even with a 10kΩ pull-down, cheap clones create uncertainty. Always use GPIO 9–27.

### MOSFET common failure modes

- **Fail short (most common):** Drain-to-source shorted → heater permanently connected. No software can detect or prevent this. Only a thermal cutoff can stop it.
- **Floating gate:** Acts as antenna, picks up noise exceeding 1.7V. Gate capacitance (~3nF total) holds charge without active discharge.
- **3.3V drive limitation:** Current should be derated to under 10A due to higher on-resistance at 3.3V.

## Software PWM vs Hardware PWM vs DMA PWM

| Method | Dies with process? | Safe on crash? |
|--------|-------------------|----------------|
| RPi.GPIO software PWM | Yes (thread dies) | Freezes at random level |
| pigpio hardware PWM | No | Keeps running through crash/panic |
| pigpio DMA PWM | No (DMA is independent) | Keeps running through crash/panic |

For heater control: prefer software PWM so it fails off, OR use hardware PWM with external pull-down ensuring fail-safe is the pull-down, not software.
