# Framework 13 Intel AX210 WiFi Fix for Omarchy Linux

## Problem
Intel AX210 has a driver bug where it enters D3cold power state and crashes when reinitializing, causing disconnections and slow speeds.

## Fix Applied

### 1. Prevent D3cold power state
```bash
echo 'ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x8086", ATTR{device}=="0x2725", ATTR{d3cold_allowed}="0"' | sudo tee /etc/udev/rules.d/99-disable-d3cold-ax210.rules
```

### 2. Disable iwd power management for iwlwifi
```bash
echo -e '[DriverQuirks]\nDefaultInterface=iwlwifi\nPowerSaveDisable=iwlwifi' | sudo tee -a /etc/iwd/main.conf
```

### 3. Reboot
```bash
sudo reboot
```

## How to Reverse

### Remove udev rule
```bash
sudo rm /etc/udev/rules.d/99-disable-d3cold-ax210.rules
```

### Remove iwd config (edit manually to remove the [DriverQuirks] section)
```bash
sudo vim /etc/iwd/main.conf
```
Delete these lines:
```
[DriverQuirks]
DefaultInterface=iwlwifi
PowerSaveDisable=iwlwifi
```

### Reboot
```bash
sudo reboot
```
