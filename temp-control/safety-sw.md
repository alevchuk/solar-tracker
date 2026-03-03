---
name: heater-safety-sw
description: Software watchdog configuration for Raspberry Pi heater control. Commands Claude Code can run: BCM2711 hardware watchdog, systemd service watchdog, ExecStopPost cleanup.
---

# Heater Control — Software Watchdog Setup

These are software-level safety actions Claude Code can help configure on the Pi.
Reference `heater-safety-pid` for PID control code and sensor validation.
Reference `heater-gpio-behavior` for what happens to GPIO on software failure.

## Layer 3 — BCM2711 hardware watchdog (reboots on kernel hang)

The BCM2711 hardware watchdog forces a full system reset if the kernel hangs. GPIO returns to defaults on reset — GPIO 18 goes low (heater off).

**Maximum timeout: 15 seconds.** Setting higher causes boot loops.

### Step 1: Enable the watchdog device in boot config

Edit `/boot/firmware/config.txt` (or `/boot/config.txt` on older images):
```
dtparam=watchdog=on
```

### Step 2: Configure systemd to pet the watchdog

Edit `/etc/systemd/system.conf`:
```ini
[Manager]
RuntimeWatchdogSec=10
ShutdownWatchdogSec=10min
```

Reload: `sudo systemctl daemon-reload && sudo systemctl restart systemd-logind`

### Step 3: Verify the watchdog device exists

```bash
ls -la /dev/watchdog /dev/watchdog0
# Should show character devices
```

**Known gap:** If the OOM killer kills the process holding `/dev/watchdog`, the watchdog timer stops — no reboot. This is why the hardware NO relay interlock (Layer 5 in `heater-safety-hw`) is also required.

## Layer 2 — systemd service watchdog (auto-restarts crashed processes)

Configure your heater control service to notify systemd it is alive. If it stops notifying, systemd kills and restarts it.

### Service unit template: `/etc/systemd/system/heater-control.service`

```ini
[Unit]
Description=Heater PID Control
After=network.target

[Service]
Type=notify
ExecStart=/usr/bin/python3 /home/pi/heater_control.py
ExecStopPost=/home/pi/heater_gpio_cleanup.sh
Restart=on-failure
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=120
StartLimitAction=reboot-force
WatchdogSec=10

[Install]
WantedBy=multi-user.target
```

Key settings:
- `WatchdogSec=10` — process must call `sd_notify("WATCHDOG=1")` every 10s or systemd kills it
- `Restart=on-failure` — auto-restart on crash
- `StartLimitAction=reboot-force` — full reboot if it fails 5× in 2 minutes
- `ExecStopPost` — GPIO cleanup script runs even on abnormal exit

### GPIO cleanup script: `/home/pi/heater_gpio_cleanup.sh`

```bash
#!/bin/bash
# Explicitly drive heater pin low on any service exit
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(18, GPIO.OUT)
GPIO.output(18, GPIO.LOW)
import time; time.sleep(0.1)
GPIO.cleanup()
"
```

Make executable: `sudo chmod +x /home/pi/heater_gpio_cleanup.sh`

### Sending watchdog heartbeats from Python

```python
import os
import time

def notify_watchdog():
    """Call this every ~5s (half of WatchdogSec=10)."""
    os.system("systemd-notify WATCHDOG=1")
    # Or use the sdnotify library:
    # import sdnotify; sdnotify.SystemdNotifier().notify("WATCHDOG=1")
```

### Deploy and enable

```bash
sudo systemctl daemon-reload
sudo systemctl enable heater-control.service
sudo systemctl start heater-control.service
sudo systemctl status heater-control.service
```

### Verify watchdog is wired up

```bash
# Check systemd sees the watchdog
sudo systemctl show heater-control.service | grep -i watchdog
# Should show WatchdogTimestamp and WatchdogUSec

# Check journal for watchdog events
sudo journalctl -u heater-control.service -f
```

## sysctl for kernel panic auto-reboot

Without this, a kernel panic leaves the system hung (GPIO stays in last state, hardware PWM keeps running):

```bash
# Add to /etc/sysctl.conf:
echo "kernel.panic=10" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

Reboots 10 seconds after a kernel panic. The hardware watchdog should catch this too, but defense in depth.

## Software safety layer summary

| Layer | What it does | Configured by |
|-------|-------------|---------------|
| `kernel.panic=10` | Reboots on kernel panic | sysctl.conf |
| BCM2711 hardware watchdog | Reboots on kernel hang | /boot/config.txt + systemd.conf |
| systemd service watchdog | Restarts crashed process | heater-control.service |
| ExecStopPost cleanup | Drives pin low on any exit | heater_gpio_cleanup.sh |

Software cannot catch: shorted MOSFET, crashed kernel with running hardware PWM before watchdog triggers. Those require hardware layers — see `heater-safety-hw`.
