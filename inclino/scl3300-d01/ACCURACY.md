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

### 1. Switch to Mode 4 (highest impact) — DONE

~~Current: Mode 1 (±1.2g, 40 Hz LPF, 6000 LSB/g)~~
Implemented: Mode 4 (inclination mode, 10 Hz LPF, 12000 LSB/g, low noise)

Per Table 2:
- Integrated noise Mode 4 X,Z: 0.08 mg RMS vs Mode 1 which is higher
- Integrated noise Mode 4 Y: 0.06 mg RMS (best channel)
- Noise density Mode 4 Y: 0.0009 °/√Hz (lowest available)
- 10 Hz LPF cuts construction vibration and foot traffic
- 2x sensitivity (12000 vs 6000 LSB/g)

Constraint: Mode 4 limited to ±10° tilt (section 2.11.1). Fine for structural monitoring.
Constraint: Y-axis parallel to gravity not recommended in Mode 3/4 — mount sensor so Z-axis is vertical.

collect.c: `setMode4()` sends `Change_to_mode_4`, enables angle outputs, waits 100ms per Table 11 step 6, then polls status until normal. Uses `MODE4_SENSITIVITY = 12000`.

### 2. Use built-in angle outputs (ANG_X/Y/Z) — DONE

~~Current: Reads raw ACC_X/Y/Z, computes angle via dot-product with initial reading.~~
Implemented: Reads ANG_X/Y/Z registers alongside raw accelerometer data.

The sensor computes angles internally (section 2.5) using:
```
ANG_X = atan2(accx / sqrt(accy^2 + accz^2))
ANG_Y = atan2(accy / sqrt(accx^2 + accz^2))
ANG_Z = atan2(accz / sqrt(accx^2 + accy^2))
```

This runs at full 2000 Hz ODR before the LPF, averaging better than software computation.

collect.c: `Enable_ANG` (0xB0001F6F) sent during `setMode4()` startup. `readAngle()` reads ANG_X/Y/Z registers. Reader thread accumulates angle sums and `collectSensorData()` averages and converts: `angle_deg = avg_raw / 16384.0 * 90.0`. Per-axis tilt output appended to TCP response.

### 3. SPI clock fixed to 2 MHz — DONE

~~Current: `speedSPI = 50000` (50 kHz).~~
Implemented: `const int speedSPI = 2000000;`

Datasheet Table 8 footnote: "SPI communication may affect the noise level. Recommended SPI clock is 2 MHz - 4 MHz to achieve the best performance." Below 2 MHz, noise specs in Table 2 are not guaranteed.

### 4. Continuous ODR read loop — DONE

~~Current: Reads only on TCP request (once per 60s from record.py). Between requests, registers are not drained, degrading the internal filter.~~
Implemented: Background `reader_thread()` runs continuously at configurable `READ_SPEED_PCT` of the 2 kHz ODR (default 100%).

Datasheet section 4.1: "Registers are updated in every 0.5 ms and if all data is not read the full noise performance of sensor is not met."

collect.c: `reader_thread()` launched via `pthread_create()` at startup, detached. Reads all registers (ACC_X/Y/Z, STO, Temperature, ANG_X/Y/Z) each cycle with 10µs inter-frame gaps. Accumulates into `g_acc` struct protected by mutex. TCP handler snapshots and resets accumulator.

### 5. Average multiple samples — DONE

~~Reading N samples per request and averaging reduces noise by √N.~~
Implemented: `accumulator_t` struct uses `int64_t` sums to safely accumulate up to 120k+ samples between TCP requests. `collectSensorData()` divides sums by count for averaged output.

At 2 kHz for 60s = 120,000 samples; int64_t avoids overflow (max sum = 120k × 32767 ≈ 3.93 billion, exceeding int32_t range).

### 6. Read and log temperature — DONE

~~`Read_Temperature` (0x140000EF) is already defined but never used.~~
Implemented: `readTemperature()` reads TEMP register every ODR cycle. Accumulated and averaged like other channels. Converted via `temp_C = -273.0 + (avg_raw / 18.9)` (section 2.4). Output as `%.2f` in TCP response.

Offset temperature dependency (Table 2):
- X, Y channels: up to ±0.57° across -40 to +125°C
- Z channel: up to ±0.86° across full range

### 7. Signed char bug — DONE

~~collect.c: `retval = (data1 << 8) | data2` where data1, data2 are `char` (signed on ARM). When high bit is set, data2 sign-extends on OR, corrupting upper bits.~~
Fixed: `readSPIFrame()` outputs `uint8_t* data1, data2`. All callers (`readAcc`, `readAngle`, `readTemperature`, `readSTO`) receive `uint8_t` values, so `(data1 << 8) | data2` assembles correctly without sign extension.

### 8. Excessive inter-frame delays — DONE

~~collect.c: `time_sleep(1.0 / MODE1_HZ)` = 25ms between SPI frames.~~
Fixed: `time_sleep(10e-6)` — 10µs inter-frame gap, matching the datasheet Table 8 TLH minimum.

Each full read cycle (16 SPI frames for 8 registers) now takes <1ms instead of ~200ms.

### 9. Post-processing: baseline drift removal

For structural monitoring, track a rolling baseline and alert on deviations:
- Monotonic drift → foundation settling
- Step changes → structural member failure/removal
- Increased variance → instability

Approach: 24h rolling median as baseline, alert when current reading deviates > threshold (e.g. 0.05°).
Diurnal thermal expansion cycles are normal and should be filtered out (correlate with temperature data from #6).
