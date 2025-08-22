#!/usr/bin/env python3
"""
SuperMicro SYS-4029GP-TRT GPU Temperature-based Fan Control
Enhanced version with smoother ramping, exponential curve, and temperature averaging
"""

import os
import time
import subprocess
import sys
import json
import signal
from collections import deque
import math

# Configuration
MIN_SPEED = 18    # Minimum fan speed percentage
MAX_SPEED = 100   # Maximum fan speed percentage
TEMP_LOW = 70     # Temperature (°C) where we start increasing fan speed
TEMP_HIGH = 90    # Temperature (°C) where we run at maximum speed
CHECK_INTERVAL = 2  # Seconds between checks (more frequent)
SMOOTHING_SAMPLES = 10  # Number of temperature samples to average
EXPONENTIAL_FACTOR = 2.5  # Higher values = more aggressive curve at high temps

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

class TemperatureAverager:
    def __init__(self, window_size=SMOOTHING_SAMPLES):
        self.temperature_history = deque(maxlen=window_size)
        self.window_size = window_size
    
    def add_temperature(self, temp):
        self.temperature_history.append(temp)
    
    def get_smoothed_temperature(self):
        if not self.temperature_history:
            return None
        return sum(self.temperature_history) / len(self.temperature_history)
    
    def get_max_temperature(self):
        if not self.temperature_history:
            return None
        return max(self.temperature_history)
    
    def is_ready(self):
        return len(self.temperature_history) >= self.window_size // 2

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

def exponential_fan_curve(temp, min_temp=TEMP_LOW, max_temp=TEMP_HIGH, min_speed=MIN_SPEED, max_speed=MAX_SPEED, factor=EXPONENTIAL_FACTOR):
    """
    Exponential fan curve for smoother ramping
    More gradual changes at lower temps, more aggressive at higher temps
    """
    if temp <= min_temp:
        return min_speed
    elif temp >= max_temp:
        return max_speed
    else:
        # Normalize temperature between 0 and 1
        normalized_temp = (temp - min_temp) / (max_temp - min_temp)
        
        # Apply exponential function
        exponential_value = math.pow(normalized_temp, factor)
        
        # Scale to fan speed range
        return min_speed + exponential_value * (max_speed - min_speed)

def calculate_fan_speed(max_temp, previous_speed=None):
    """Calculate fan speed with exponential curve and optional hysteresis"""
    fan_speed = exponential_fan_curve(max_temp)
    
    # Add hysteresis to prevent rapid oscillations
    if previous_speed is not None:
        # Only change if the difference is significant (>2%)
        if abs(fan_speed - previous_speed) < 2:
            return previous_speed
    
    return int(fan_speed)

def main():
    print("SuperMicro Fan Controller Service starting...")
    print(f"Config: {TEMP_LOW}°C-{TEMP_HIGH}°C → {MIN_SPEED}%-{MAX_SPEED}%")
    print(f"Smoothing: {SMOOTHING_SAMPLES} samples, Update: {CHECK_INTERVAL}s")
    print(f"Exponential factor: {EXPONENTIAL_FACTOR}")
    
    # Initialize temperature averager
    temp_averager = TemperatureAverager(SMOOTHING_SAMPLES)
    current_fan_speed = MIN_SPEED
    
    # Set initial fan speed
    set_fan_speed(current_fan_speed)
    
    exiter = GracefulExiter()
    
    try:
        while not exiter.exit_requested():
            # Get GPU temperatures
            temperatures = get_gpu_temperatures()
            
            if temperatures is None:
                print("Could not read GPU temperatures. Waiting...")
                time.sleep(CHECK_INTERVAL)
                continue
            
            current_max_temp = max(temperatures)
            current_avg_temp = sum(temperatures) / len(temperatures)
            
            # Add to averaging window
            temp_averager.add_temperature(current_max_temp)
            
            # Use smoothed temperature if we have enough samples
            if temp_averager.is_ready():
                smoothed_max_temp = temp_averager.get_smoothed_temperature()
                raw_max_temp = temp_averager.get_max_temperature()
                
                print(f"GPU Temps: Current={current_max_temp:.1f}°C, Smoothed={smoothed_max_temp:.1f}°C, RawMax={raw_max_temp:.1f}°C, Count={len(temperatures)}")
                
                # Calculate and set fan speed using exponential curve
                new_fan_speed = calculate_fan_speed(smoothed_max_temp, current_fan_speed)
                
                if new_fan_speed != current_fan_speed:
                    if set_fan_speed(new_fan_speed):
                        current_fan_speed = new_fan_speed
            else:
                # Still building up samples, just display
                print(f"GPU Temps: Current={current_max_temp:.1f}°C, Avg={current_avg_temp:.1f}°C (warming up sensor...)")
            
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