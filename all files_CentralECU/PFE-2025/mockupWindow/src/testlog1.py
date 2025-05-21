#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import os
import sys
from datetime import datetime

class VehicleWindowSystem:
    # Constants for modes
    PARKEN = "P"       # Parking mode
    STANDBY = "S"      # Standby mode
    WOHNEN = "W"       # Wohnen mode
    FAHREN = "F"       # Fahren mode
    
    # Window statuses
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    OPENING = "OPENING"
    CLOSING = "CLOSING"
    FULLY_OPEN = "FULLY_OPEN"
    CLOSED_SAFETY = "CLOSED_SAFETY"
    OPEN_SAFETY = "OPEN_SAFETY"
    OPENING_SAFETY = "OPENING_SAFETY"
    CLOSING_SAFETY = "CLOSING_SAFETY"
    FULLY_OPEN_SAFETY = "FULLY_OPEN_SAFETY"
    
    # Level types
    MANUAL = "MANUAL"
    AUTO = "AUTO"

    def __init__(self):
        self.current_mode = self.PARKEN
        self.windows = {
            'Driver Window': None,
            'Passenger Window': None,
            'Rear Driver Window': None,
            'Rear Passenger Window': None
        }

    def set_initial_parken_state(self):
        self.current_mode = self.PARKEN
        for window in self.windows:
            self.windows[window] = None

    def validate_window_status(self, status, mode, level_type, safety, window_level):
        """Validate if window status is acceptable for given parameters"""
        # Normalize mode (handle typos like 'Whonen' and spaces)
        normalized_mode = mode.upper().replace(" ", "")
        if "WHONEN" in normalized_mode:
            normalized_mode = "WOHNEN"
        
        system_mode = {
            "PARKING": self.PARKEN,
            "STANDBY": self.STANDBY,
            "WOHNEN": self.WOHNEN,
            "FAHREN": self.FAHREN,
        }.get(normalized_mode, self.PARKEN)
        
        # Check if mode is valid
        if system_mode not in [self.WOHNEN, self.FAHREN]:
            return False
            
        # Check if level_type is valid
        if level_type not in [self.MANUAL, self.AUTO]:
            return False
            
        # Check if window_level is valid (0-100)
        try:
            level = int(window_level)
            if level < 0 or level > 100:
                return False
        except (ValueError, TypeError):
            return False
            
        # Check safety status
        safety_on = safety.upper() == "ON"
        
        # Define valid statuses based on safety
        if safety_on:
            valid_statuses = [
                self.CLOSED_SAFETY, self.OPEN_SAFETY, 
                self.OPENING_SAFETY, self.CLOSING_SAFETY, 
                self.FULLY_OPEN_SAFETY
            ]
        else:
            valid_statuses = [
                self.CLOSED, self.OPEN, 
                self.OPENING, self.CLOSING, 
                self.FULLY_OPEN
            ]
        
        # Check if status is valid
        return status in valid_statuses

def parse_windows_log(filename, last_position=0):
    """Extracts all window status entries since last read"""
    pattern = (
        r"(Driver Window|Passenger Window|Rear Driver Window|Rear Passenger Window) \| "
        r"Status:\s*(\w+),\s*mode:\s*([\w\s]*),\s*level_type:\s*(\w+),\s*safety:\s*(\w+),\s*window_level:\s*(\d+)"
    )
    log_entries = {
        'Driver Window': [],
        'Passenger Window': [],
        'Rear Driver Window': [],
        'Rear Passenger Window': []
    }
    
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            file.seek(last_position)
            for line in file:
                line = line.strip()
                if (line.startswith("CLIENT:") or "=" in line or 
                    "Window | Status" not in line):
                    continue
                
                match = re.search(pattern, line)
                if match:
                    window_name = match.group(1)
                    status = match.group(2).strip()
                    mode = match.group(3).strip()
                    level_type = match.group(4).strip()
                    safety = match.group(5).strip()
                    window_level = match.group(6).strip()
                    
                    if window_name in log_entries:
                        log_entries[window_name].append((status, mode, level_type, safety, window_level))
                    
            last_position = file.tell()
    except Exception as e:
        print(f"Error reading log file: {e}", file=sys.stderr)
    return log_entries, last_position

def analyze_windows(log_entries, output_file=sys.stdout):
    system = VehicleWindowSystem()
    system.set_initial_parken_state()
    
    window_abbreviations = {
        'Driver Window': 'DR',
        'Passenger Window': 'PS',
        'Rear Driver Window': 'DRS',
        'Rear Passenger Window': 'PRS'
    }
    
    status_abbreviations = {
        'OPEN': 'OP',
        'CLOSED': 'CL',
        'OPENING': 'OPG',
        'CLOSING': 'CLG',
        'FULLY_OPEN': 'FOP',
        'OPEN_SAFETY': 'OP_S',
        'CLOSED_SAFETY': 'CL_S',
        'OPENING_SAFETY': 'OPG_S',
        'CLOSING_SAFETY': 'CLG_S',
        'FULLY_OPEN_SAFETY': 'FOP_S'
    }
    
    output_lines = []
    
    # Console output headers
    print("\n" + "="*60)
    print("VEHICLE WINDOW SYSTEM ANALYSIS".center(60))
    print("="*60)
    print("\nWindow Status Analysis:")
    print("-" * 60)
    
    for window_name in log_entries:
        short_name = window_abbreviations.get(window_name, window_name)
        
        for status, mode, level_type, safety, window_level in log_entries[window_name]:
            is_valid = system.validate_window_status(status, mode, level_type, safety, window_level)
            short_status = status_abbreviations.get(status, status)
            
            line = (f"Window: {short_name:<12} | Result:  {short_status:<6} | Level: {window_level}% | "
                   f"Level_type: {level_type} | mode: {mode}")
            
            print(line)  # Console output
            output_lines.append(line)  # File output
    
    if output_file != sys.stdout and output_lines:
        # Write to file without any additional headers
        print("\n".join(output_lines), file=output_file)
    
    return output_lines

def monitor_window_log_file(filename):
    print(f"\nStarting real-time monitoring of: {filename}")
    print("\nPress Ctrl+C to stop monitoring...\n")
    
    with open("windows_analysis.txt", "a", encoding='utf-8') as output_file:
        last_position = 0 if not os.path.exists(filename) else os.path.getsize(filename)
        try:
            while True:
                new_entries, last_position = parse_windows_log(filename, last_position)
                if any(new_entries.values()):
                    print("\n" + "="*60)
                    print("NEW WINDOW STATUS UPDATE".center(60))
                    print("="*60)
                    
                    analyze_windows(new_entries, output_file)
                    output_file.flush()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")

if __name__ == "__main__":
    log_file = "windows_log.txt"
    
    # Initialize output file
    with open("windows_analysis.txt", "w", encoding='utf-8'):
        pass
    
    print(f"Initial analysis of {log_file}...")
    entries, _ = parse_windows_log(log_file)
    
    if any(entries.values()):
        with open("windows_analysis.txt", "a", encoding='utf-8') as output_file:
            analyze_windows(entries, output_file)
    else:
        print("No initial window entries found.")
    
    monitor_window_log_file(log_file)