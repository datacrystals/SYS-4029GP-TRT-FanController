#!/usr/bin/env python3
"""
SuperMicro SYS-4029GP-TRT GPU Temperature-based Fan Control
Systemd service version
"""

import os
import time
import subprocess
import sys
import json
import signal

# Configuration
MIN_SPEED = 25   # Minimum fan speed percentage (25% = 0x40)
MAX_SPEED = 100  # Maximum fan speed percentage (100% = 0x64)
TEMP_LOW = 70    # Temperature (°C) where we start increasing fan speed
TEMP_HIGH = 90   # Temperature (°C) where we run at maximum speed
CHECK_INTERVAL = 10  # Seconds between checks

class GracefulExiter:
    def __init__(self):
        self.should_exit = False
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)
    
    def handle_signal(self, signum, frame):
        print(f"Received signal {signum}, shutting down gracefully...")
        self.should_exit = True
    
    def exit_requested(self):
        return self.should_exit

def run_command(cmd):
    """Execute a command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1

def set_fan_speed(percent):
    """Set fan speed to specific percentage using the confirmed working command"""
    # Ensure we stay within safe bounds
    percent = max(MIN_SPEED, min(percent, MAX_SPEED))
    
    # Convert percentage to hex value (0-100% maps to 0x00-0x64)
    hex_value = int(percent * 100 / 100)
    hex_speed = format(hex_value, "02x")
    
    # Use the exact command that works
    cmd = f"ipmitool raw 0x30 0x70 0x66 0x01 0x02 0x{hex_speed}"
    stdout, stderr, returncode = run_command(cmd)
    
    if returncode != 0:
        print(f"Failed to set fan speed to {percent}%: {stderr}")
        return False
    
    print(f"Fan speed set to {percent}% (0x{hex_speed})")
    return True

def get_gpu_temperatures():
    """Get GPU temperatures using rocm-smi with proper JSON parsing"""
    temperatures = []
    
    try:
        # Get GPU stats using JSON format
        result = subprocess.run([
            'rocm-smi', 
            '--showtemp', 
            '--json'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            json_data = json.loads(result.stdout)
            
            # Parse temperatures from JSON
            for card_key, card_data in json_data.items():
                if card_key.startswith('card'):
                    try:
                        if 'Temperature (Sensor edge) (C)' in card_data:
                            temp_str = card_data['Temperature (Sensor edge) (C)']
                            temperature = float(temp_str)
                            temperatures.append(temperature)
                    except (ValueError, KeyError):
                        continue
        
        if temperatures:
            return temperatures
            
        # Fallback method
        cmd = "rocm-smi --showtemp | grep -E 'Sensor edge|Temperature' | grep -Eo '[0-9]+\\.[0-9]+' | head -6"
        stdout, stderr, returncode = run_command(cmd)
        if returncode == 0 and stdout:
            for temp_str in stdout.split():
                try:
                    temperature = float(temp_str)
                    temperatures.append(temperature)
                except ValueError:
                    continue
    
    except Exception as e:
        print(f"Error getting GPU temperatures: {e}")
    
    return temperatures if temperatures else None

def calculate_fan_speed(max_temp):
    """Calculate fan speed based on temperature"""
    if max_temp <= TEMP_LOW:
        return MIN_SPEED
    elif max_temp >= TEMP_HIGH:
        return MAX_SPEED
    else:
        slope = (MAX_SPEED - MIN_SPEED) / (TEMP_HIGH - TEMP_LOW)
        return int(MIN_SPEED + slope * (max_temp - TEMP_LOW))

def main():
    print("SuperMicro Fan Controller Service starting...")
    print(f"Config: {TEMP_LOW}°C-{TEMP_HIGH}°C → {MIN_SPEED}%-{MAX_SPEED}%")
    
    # Set initial fan speed
    set_fan_speed(MIN_SPEED)
    
    exiter = GracefulExiter()
    
    try:
        while not exiter.exit_requested():
            # Get GPU temperatures
            temperatures = get_gpu_temperatures()
            
            if temperatures is None:
                print("Could not read GPU temperatures. Waiting...")
                time.sleep(CHECK_INTERVAL)
                continue
            
            max_temp = max(temperatures)
            avg_temp = sum(temperatures) / len(temperatures)
            
            print(f"GPU Temperatures: Max={max_temp:.1f}°C, Avg={avg_temp:.1f}°C, Count={len(temperatures)}")
            
            # Calculate and set fan speed
            fan_speed = calculate_fan_speed(max_temp)
            set_fan_speed(fan_speed)
            
            # Wait for next check
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\nReceived interrupt signal, shutting down...")
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Fan Controller Service stopped")

if __name__ == "__main__":
    # Check if we have required tools
    for tool in ["ipmitool", "rocm-smi"]:
        stdout, stderr, returncode = run_command(f"which {tool}")
        if returncode != 0:
            print(f"Error: {tool} not found. Please install it.")
            sys.exit(1)
    
    # Check if we're running as root
    if os.geteuid() != 0:
        print("This script requires root privileges. Please run with sudo.")
        sys.exit(1)
    
    main()