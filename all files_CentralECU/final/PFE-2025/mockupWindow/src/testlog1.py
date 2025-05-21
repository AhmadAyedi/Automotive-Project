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
        """Validate all requirements and return (is_valid, error_message)"""
        error_messages = []
        
        # Check for NULL or empty values
        if status == "NULL" or not status.strip():
            error_messages.append("Status is NULL or empty")
        
        if not mode.strip():
            error_messages.append("Mode is empty")
        
        if not level_type.strip():
            error_messages.append("Level type is empty")
        
        # Try to convert window_level to int
        try:
            level = int(window_level)
        except (ValueError, TypeError):
            error_messages.append(f"Invalid window level: {window_level}")
            return (False, ", ".join(error_messages))
        
        # Check window level range
        if not (0 <= level <= 100):
            error_messages.append(f"Window level must be between 0 and 100")
        
        # Skip further validation if essential fields are invalid
        if error_messages:
            return (False, ", ".join(error_messages))
        
        # New requirements for window level vs status
        if level == 0:
            if status not in [self.FULLY_OPEN, self.FULLY_OPEN_SAFETY]:
                error_messages.append("Status must be FULLY_OPEN or FULLY_OPEN_SAFETY when level is 0")
        elif level == 100:
            if status not in [self.CLOSED, self.CLOSED_SAFETY]:
                error_messages.append("Status must be CLOSED or CLOSED_SAFETY when level is 100")
        else:  # 0 < level < 100
            valid_mid_statuses = [
                self.OPEN, self.OPEN_SAFETY,
                self.OPENING, self.CLOSING,
                self.OPENING_SAFETY, self.CLOSING_SAFETY
            ]
            if status not in valid_mid_statuses:
                error_messages.append("Status must be OPEN/OPENING/CLOSING (with or without SAFETY) when level is between 0 and 100")
        
        # Normalize mode
        normalized_mode = mode.upper().replace(" ", "")
        if "WHONEN" in normalized_mode:
            normalized_mode = "WOHNEN"
        
        system_mode = {
            "PARKING": self.PARKEN,
            "STANDBY": self.STANDBY,
            "WOHNEN": self.WOHNEN,
            "FAHREN": self.FAHREN,
        }.get(normalized_mode, self.PARKEN)
        
        # Check mode
        if system_mode not in [self.WOHNEN, self.FAHREN]:
            error_messages.append(f"Invalid mode: {mode}")
        
        # Check level type
        if level_type not in [self.MANUAL, self.AUTO]:
            error_messages.append(f"Invalid level type: {level_type}")
        
        # Check safety and status
        safety_on = safety.upper() == "ON"
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
        
        if status not in valid_statuses:
            error_messages.append(f"Invalid status '{status}' for safety {safety}")
        
        return (len(error_messages) == 0, ", ".join(error_messages))

def parse_windows_log(filename, last_position=0):
    """Extracts all window status entries since last read"""
    pattern = (
        r"(Driver Window|Passenger Window|Rear Driver Window|Rear Passenger Window) \| "
        r"Status:\s*([^,]+),\s*mode:\s*([^,]*),\s*level_type:\s*([^,]*),\s*safety:\s*([^,]*),?\s*window_level:\s*([^\s]*)"
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
                if not line or line.startswith("CLIENT:") or "=" in line:
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
            is_valid, _ = system.validate_window_status(status, mode, level_type, safety, window_level)
            short_status = status_abbreviations.get(status, status)
            
            if is_valid:
                line = f"Window: {short_name:<12} | Result:  {short_status:<6} | Level: {window_level}% | Level_type: {level_type} | mode: {mode}"
            else:
                line = f"Window: {short_name:<12} | Result:  FAILED  | Level: {window_level}% | Level_type: {level_type} | mode: {mode}"
            
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