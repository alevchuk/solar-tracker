# Inclinometer changelog

## 2026-02-17: Persistent reference position

Added persistent storage of the inclinometer reference position in
`~/reference_position.json` on the Pi, so the dot-product angle baseline
no longer resets on every reboot.

### Commits

- `aa3470f` collect.c, live.py: persistent reference position from ~/reference_position.json
  - Initial implementation used g-values multiplied by MODE4_SENSITIVITY
    to reconstruct raw LSBs — introduced precision loss, angle_deg jumped
    from ~0.0382° to ~0.039°
  - x_0/y_0/z_0 were changed from `short` to `double`, altering dot-product behavior

- `5db5531` collect.c, live.py: fix reference position to use raw LSB values
  - Reverted x_0/y_0/z_0 back to `short`
  - JSON now stores `raw_x`/`raw_y`/`raw_z` as integer LSBs directly
  - angle_deg increased to ~0.0495° after first deploy (06:50), then ~0.0544°
    after second deploy (07:44)

### Observations

The angle_deg baseline shifted with each reboot/redeploy:
- Before changes: ~0.0382° (first-read reference from last reboot, ~0.005° at reference time on 2026-02-15)
- After first deploy (06:50, g-value roundtrip): ~0.039°
- After second deploy (07:04, still g-values): ~0.0495°
- After third deploy (07:44, raw LSBs from log): ~0.0544°

The increasing offset is expected: the original raw shorts from the 2026-02-15
first-read were never logged (record.py stores g-values already divided by
12000), so the reference values are approximations. Each reboot also means the
sensor re-initializes with slightly different internal state.

### Reference position format

See `reference_position.example.json` for the file format. Fields:
- `raw_x`, `raw_y`, `raw_z`: raw accelerometer LSBs (used by collect.c dot-product)
- `x`, `y`, `z`: g-values (human-readable, = raw / 12000)
- `ang_x`, `ang_y`: on-chip angle degrees (used by live.py --delta)
- `timestamp`: when the reference was captured
