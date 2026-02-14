# SCL3300-D01 Accuracy Improvements for Structural Health Monitoring

Reference: Murata SCL3300-D01 Datasheet, Doc.No. 4921 Rev. 2 (47 pages)
Use case: Monitoring structure integrity of a home during remodeling (wall removal, foundation excavation)

## Datasheet navigation

- **Table 2 (p5-6)**: Performance specs — offset error, noise density, sensitivity per mode. The footnotes (A-I) are critical, especially G (SPI clock affects noise) and E (angle sensitivity valid only 0-1°).
- **Table 12 (p22)**: Mode comparison table — sensitivity, bandwidth, full-scale per mode.
- **Section 2.5 (p7)**: Angle output equations — atan2 formulas the sensor uses internally, and `Angle [°] = d'ANG_% / 2^14 * 90` conversion.
- **Section 2.9 (p10-12)**: Offset temperature curves and noise spectra — the Z-axis offset drifts more with temperature than X/Y.
- **Section 2.11.1 (p16)**: Mode 3/4 ±10° range limits, Y-axis parallel to gravity not recommended in mode 3/4.
- **Section 4.1 (p20)**: "if all data is not read the full noise performance of sensor is not met" — must read ACCX/Y/Z every ODR cycle (0.5ms).
- **Section 4.2 (p21)**: Start-up sequence Table 11 — SW Reset, set mode, enable ANG_CTRL, wait, clear STATUS.
- **Section 6.6 (p41)**: ANG_CTRL — must write 0x1F to enable angle outputs (default is disabled/zeroes).
- **Table 8 (p14)**: SPI AC characteristics — min 10µs between SPI cycles (TLH), recommended 2-4 MHz clock.
- **Section 2.4 (p7)**: Temperature conversion: `Temp [°C] = -273 + (TEMP / 18.9)`.
- **Section 3.1 (p19)**: Factory calibration — offset calibration after assembly recommended, "accuracy can be improved with longer stabilization time".
- **Section 6.2 (p33)**: STO self-test — threshold monitoring for component health, Table 23 for thresholds per mode.

## Findings vs collect.c

### 1. Switch to Mode 4 (highest impact)

Current: Mode 1 (±1.2g, 40 Hz LPF, 6000 LSB/g)
Recommended: Mode 4 (inclination mode, 10 Hz LPF, 12000 LSB/g, low noise)

Per Table 2:
- Integrated noise Mode 4 X,Z: 0.08 mg RMS vs Mode 1 which is higher
- Integrated noise Mode 4 Y: 0.06 mg RMS (best channel)
- Noise density Mode 4 Y: 0.0009 °/√Hz (lowest available)
- 10 Hz LPF cuts construction vibration and foot traffic
- 2x sensitivity (12000 vs 6000 LSB/g)

Constraint: Mode 4 limited to ±10° tilt (section 2.11.1). Fine for structural monitoring.
Constraint: Y-axis parallel to gravity not recommended in Mode 3/4 — mount sensor so Z-axis is vertical.

collect.c change: `setMode1()` → use `Change_to_mode_4`, update sensitivity constant, wait 100ms (Table 11 step 6).

### 2. Use built-in angle outputs (ANG_X/Y/Z)

Current: Reads raw ACC_X/Y/Z, computes angle via dot-product with initial reading (collect.c:343-352).
Problem: Dot product gives single scalar "deviation from initial" — loses per-axis information.

The sensor computes angles internally (section 2.5) using:
```
ANG_X = atan2(accx / sqrt(accy^2 + accz^2))
ANG_Y = atan2(accy / sqrt(accx^2 + accz^2))
ANG_Z = atan2(accz / sqrt(accx^2 + accy^2))
```

This runs at full 2000 Hz ODR before the LPF, averaging better than software computation.

collect.c changes:
- Send `Enable ANGLE outputs` (0xB0001F6F) during startup after mode set (Table 11 step 5)
- Add Read_ANG_X (0x240000C7), Read_ANG_Y (0x280000CD), Read_ANG_Z (0x2C0000CB)
- Convert: `angle_deg = raw_value / 16384.0 * 90.0`

Per-axis tilt answers "is the wall leaning east?" instead of just "something changed".

### 3. SPI clock is ~40x too slow

Current: `speedSPI = 50000` (50 kHz) at collect.c:123.
Datasheet Table 8 footnote: "SPI communication may affect the noise level. Recommended SPI clock is 2 MHz - 4 MHz to achieve the best performance."

Below 2 MHz, noise specs in Table 2 are not guaranteed.

Fix: `const int speedSPI = 2000000;`

### 4. Not reading at ODR — degraded noise performance

Datasheet section 4.1: "Registers are updated in every 0.5 ms and if all data is not read the full noise performance of sensor is not met."

Current: Reads only on TCP request (once per 60s from record.py). Between requests, registers are not drained, degrading the internal filter.

Fix: Run continuous read loop at ~2000 Hz, keep running average. Return averaged result on TCP request.

### 5. Average multiple samples

Even without continuous ODR, reading N samples per request and averaging reduces noise by √N.
With Mode 4's 10 Hz bandwidth, ~20 samples over 2 seconds is a reasonable window.
For 60s intervals, 100 samples over 50ms → 10x noise reduction.

### 6. Read and log temperature

Offset temperature dependency (Table 2):
- X, Y channels: up to ±0.57° across -40 to +125°C
- Z channel: up to ±0.86° across full range

For a house going through seasons or heated/unheated during remodel, this matters.
`Read_Temperature` (0x140000EF) is already defined but never used.
Conversion: `temp_C = -273.0 + (raw_temp / 18.9)` (section 2.4)

Log alongside angle data for post-processing temperature-offset curve fitting.

### 7. Signed char bug

collect.c:254: `retval = (data1 << 8) | data2` where data1, data2 are `char` (signed on ARM).
When high bit is set, data2 sign-extends on OR, corrupting upper bits.

Fix: Use `uint8_t` for data1/data2, then: `retval = (int16_t)((uint8_t)data1 << 8 | (uint8_t)data2);`

### 8. Excessive inter-frame delays

collect.c:137: `time_sleep(1.0 / MODE1_HZ)` = 25ms between SPI frames.
Datasheet Table 8: TLH minimum = 10µs.

Each full read cycle (8 SPI frames) takes ~200ms currently. Could take <1ms.

### 9. Post-processing: baseline drift removal

For structural monitoring, track a rolling baseline and alert on deviations:
- Monotonic drift → foundation settling
- Step changes → structural member failure/removal
- Increased variance → instability

Approach: 24h rolling median as baseline, alert when current reading deviates > threshold (e.g. 0.05°).
Diurnal thermal expansion cycles are normal and should be filtered out (correlate with temperature data from #6).
