# SuperMicro SYS-4029GP-TRT GPU Temperature-based Fan Control
===========================================================

## Introduction

This project provides a Python script for controlling the fan speeds of SuperMicro SYS-4029GP-TRT GPU machines based on the temperature of AMD GPUs. The script uses the `ipmitool` and `rocm-smi` utilities to monitor and adjust fan speeds.

## Features

* Automatically adjusts fan speeds based on GPU temperatures
* Configurable temperature thresholds and fan speed ranges
* Supports multiple AMD GPUs
* Runs as a systemd service for continuous monitoring and control

## Requirements

* SuperMicro SYS-4029GP-TRT server with AMD GPUs
* `ipmitool` utility installed
* `rocm-smi` utility installed (for AMD GPUs)
* Python 3.x

## Installation

1. Clone the repository or download the scripts.
2. Run the installation script (`install.sh`) as root:
```bash
sudo ./install.sh
```
3. The script will copy the necessary files, configure the systemd service, and start the service.

## Configuration

The fan control script can be configured by editing the `fan_controller.py` file. The following variables can be adjusted:

* `MIN_SPEED`: Minimum fan speed percentage (default: 25%)
* `MAX_SPEED`: Maximum fan speed percentage (default: 100%)
* `TEMP_LOW`: Temperature threshold for minimum fan speed (default: 70°C)
* `TEMP_HIGH`: Temperature threshold for maximum fan speed (default: 90°C)
* `CHECK_INTERVAL`: Interval between temperature checks (default: 10 seconds)

## Usage

The fan control script runs as a systemd service, which starts automatically on boot. You can manage the service using the following commands:

* Check status: `sudo systemctl status fan-controller.service`
* View logs: `sudo journalctl -u fan-controller.service -f`
* Restart service: `sudo systemctl restart fan-controller.service`
* Stop service: `sudo systemctl stop fan-controller.service`

## Uninstallation

To uninstall the fan control script and remove the systemd service, run the uninstallation script (`uninstall.sh`) as root:
```bash
sudo ./uninstall.sh
```
This will stop and disable the service, remove the service file, and delete the installation directory.