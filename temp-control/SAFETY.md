# Heater Control Safety

Seven-layer defense-in-depth for a Raspberry Pi controlling a heater through a D4184-based MOSFET module. A shorted MOSFET, crashed kernel, or fried Pi can all leave the heater running uncontrolled — the layers below ensure no single point of failure causes that.

## The seven layers

| Layer | Type | File | What it does |
|-------|------|------|-------------|
| 1 | Software | [safety-pid.md](safety-pid.md) | PID output clamping, dead man's switch, sensor validation, thermal runaway |
| 2 | Software | [safety-sw.md](safety-sw.md) | systemd service watchdog — auto-restarts crashed process |
| 3 | Software | [safety-sw.md](safety-sw.md) | BCM2711 hardware watchdog — reboots on kernel hang |
| 4 | Hardware | [safety-hw.md](safety-hw.md) | External 10kΩ pull-down — holds gate low when Pi isn't driving |
| 5 | Hardware | [safety-hw.md](safety-hw.md) | Normally-open relay interlock driven by independent heartbeat circuit |
| 6 | Hardware | [safety-hw.md](safety-hw.md) | KSD301 manual-reset thermal cutoff mounted on heater |
| 7 | Hardware | [safety-hw.md](safety-hw.md) | One-shot thermal fuse — permanent last resort |

## Quick decisions

**Which GPIO pin?** GPIO 18. It defaults to pull-down at boot and supports hardware PWM.

**Most impactful hardware action:** 330Ω series resistor + 10kΩ pull-down to GND at the MOSFET module (Layer 4).

**Most impactful architectural decision:** Normally-open relay controlled by an independent watchdog (Layer 5).

**Critical insight:** MOSFETs fail short — the MOSFET module can become a permanent wire. The only thing that catches this is a mechanical thermal cutoff (Layers 6–7) that doesn't care about software, GPIO states, or electronics.

## Files in this directory

- **SAFETY.md** — this index
- **safety-hw.md** — physical wiring actions a human must perform (pull-downs, relay, thermal cutoffs, fusing)
- **safety-sw.md** — software watchdog setup Claude Code can configure (boot config, systemd service files, GPIO cleanup)
- **safety-pid.md** — PID code patterns, sensor validation, dead man's switch, thermal runaway detection
- **gpio-behavior.md** — reference: GPIO default states, failure scenario table, MOSFET gate voltage math
