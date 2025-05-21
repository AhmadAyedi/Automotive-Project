#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import os
import sys
from datetime import datetime
from collections import defaultdict

class CarLockSystem:
    # Car status constants
    LOCKED = 0
    UNLOCKED = 1
    
    # Door positions
    FRONT_RIGHT = "Front Right Door"
    REAR_RIGHT = "Rear Right Door"
    FRONT_LEFT = "Front Left Door"
    REAR_LEFT = "Rear Left Door"
    
    # Door states
    DOOR_LOCKED = "Locked"
    DOOR_UNLOCKED = "Unlocked"
    DOOR_OPEN = "open"
    DOOR_CLOSED = "close"
    
    def __init__(self):
        self.current_state = {
            'key_status': 0,  # 0=not in zone, 1=in zone
            'car_status': self.LOCKED,
            'doors': {
                self.FRONT_RIGHT: {'state': self.DOOR_LOCKED, 'open_close': ''},
                self.REAR_RIGHT: {'state': self.DOOR_LOCKED, 'open_close': ''},
                self.FRONT_LEFT: {'state': self.DOOR_LOCKED, 'open_close': ''},
                self.REAR_LEFT: {'state': self.DOOR_LOCKED, 'open_close': ''}
            },
            'auto_unlock_status': 1,  # Assume enabled by default
            'auto_lock_status': 1,    # Assume enabled by default
            'ST_FlashLight': 0,
            'ST_HornBeeping': 0
        }
        self.previous_state = self.current_state.copy()
        self.requirements = self._initialize_requirements()

    def _initialize_requirements(self):
        return {
            'req1': {
                'description': "The car should automatically unlock when the key comes within a predefined radius (e.g., 2 meters) of the vehicle.",
                'input': {'key_zone_status': 1, 'auto_unlock_status': 1, 'previous_car_status': self.LOCKED},
                'output': {'car_status': self.UNLOCKED, 'ST_FlashLight': 1, 'ST_HornBeeping': 1}
            },
            'req2': {
                'description': "The car should automatically lock when all doors are closed and the key is at least 3 meters away.",
                'input': {
                    'door_status_left_front': 0, 'door_status_left_rear': 0,
                    'door_status_right_front': 0, 'door_status_right_rear': 0,
                    'key_zone_status': 0, 'auto_lock_status': 1, 'previous_car_status': self.UNLOCKED
                },
                'output': {'car_status': self.LOCKED, 'ST_FlashLight': 1, 'ST_HornBeeping': 1}
            },
            'req9a': {
                'description': "If any door is opened from the inside, the car should remain unlocked while the door is open.",
                'input': {'any_door_open': True, 'key_zone_status': 'any'},
                'output': {'car_status': self.UNLOCKED}
            },
            'req9b': {
                'description': "Doors should open when interior/exterior handle is pulled while car is unlocked.",
                'input': {'car_status': self.UNLOCKED, 'door_handle_pulled': 1},
                'output': {'door_status': 1}
            },
            'req10': {
                'description': "External unlock button can unlock doors when key is nearby.",
                'input': {'key_zone_status': 1, 'exterior_unlock_pressed': True},
                'output': {'car_status': self.UNLOCKED}
            }
        }

    def update_state(self, change_type, value):
        """Update the system state based on the change"""
        self.previous_state = self._deep_copy_state(self.current_state)
        
        if change_type == 'key_status':
            self.current_state['key_status'] = value
        elif change_type == 'door_status':
            position, door_state, open_close = value
            self.current_state['doors'][position]['state'] = door_state
            self.current_state['doors'][position]['open_close'] = open_close
            
            # Update car status based on door state
            if door_state == self.DOOR_UNLOCKED:
                self.current_state['car_status'] = self.UNLOCKED

    def _deep_copy_state(self, state):
        """Create a deep copy of the state dictionary"""
        return {
            'key_status': state['key_status'],
            'car_status': state['car_status'],
            'doors': {
                pos: {'state': val['state'], 'open_close': val['open_close']}
                for pos, val in state['doors'].items()
            },
            'auto_unlock_status': state['auto_unlock_status'],
            'auto_lock_status': state['auto_lock_status'],
            'ST_FlashLight': state['ST_FlashLight'],
            'ST_HornBeeping': state['ST_HornBeeping']
        }

    def check_requirements(self, change_type):
        """Check if any requirements are triggered by the state change"""
        triggered = []
        current = self.current_state
        previous = self.previous_state
        
        # Check req1: Auto unlock when key comes near
        if (change_type == 'key_status' and current['key_status'] == 1 and 
            previous['key_status'] == 0 and
            current['auto_unlock_status'] == 1 and
            previous['car_status'] == self.LOCKED):
            triggered.append('req1')
        
        # Check req2: Auto lock when key leaves and all doors closed
        all_doors_closed = all(
            door['open_close'] != self.DOOR_OPEN 
            for door in current['doors'].values()
        )
        if (change_type == 'key_status' and current['key_status'] == 0 and 
            previous['key_status'] == 1 and
            all_doors_closed and
            current['auto_lock_status'] == 1 and
            previous['car_status'] == self.UNLOCKED):
            triggered.append('req2')
        
        # Check req9a: Doors open keeps car unlocked
        any_door_open = any(
            door['open_close'] == self.DOOR_OPEN 
            for door in current['doors'].values()
        )
        if (change_type == 'door_status' and any_door_open and 
            current['car_status'] != self.UNLOCKED):
            triggered.append('req9a')
        
        return triggered

def parse_log_line(line):
    """Parse a single line from the log file"""
    # Key status
    if "Key | Key:" in line:
        key_status = int(line.split(":")[-1].strip())
        return ('key_status', key_status)
    
    # Door status
    door_match = re.match(
        r".*(Front|Rear) (Right|Left) Door \| State: (Locked|Unlocked), Open_Close: (.*)", 
        line
    )
    if door_match:
        position = f"{door_match.group(1)} {door_match.group(2)} Door"
        state = door_match.group(3)
        open_close = door_match.group(4).strip().lower()
        return ('door_status', (position, state, open_close))
    
    return None

def analyze_log_file(filename, output_file=sys.stdout):
    """Analyze the log file and check requirements"""
    system = CarLockSystem()
    results = defaultdict(list)
    
    # Print header
    print("\n" + "="*80, file=output_file)
    print("CAR LOCK SYSTEM ANALYSIS".center(80), file=output_file)
    print("="*80, file=output_file)
    
    # System requirements summary
    print("\nSystem Requirements Summary:", file=output_file)
    print("-" * 80, file=output_file)
    for req_id, req_data in system.requirements.items():
        print(f"{req_id}: {req_data['description']}", file=output_file)
    print("-" * 80, file=output_file)
    
    # Process log file
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            
            parsed = parse_log_line(line)
            if parsed:
                change_type, value = parsed
                system.update_state(change_type, value)
                triggered = system.check_requirements(change_type)
                
                for req_id in triggered:
                    results[req_id].append({
                        'line': line,
                        'state': system.current_state.copy(),
                        'previous_state': system.previous_state.copy()
                    })
    
    # Print results
    print("\nRequirement Verification Results:", file=output_file)
    print("="*80, file=output_file)
    for req_id, req_data in system.requirements.items():
        occurrences = len(results.get(req_id, []))
        status = "PASS" if occurrences > 0 else "FAIL"
        print(f"{req_id}: {status} ({occurrences} occurrences)", file=output_file)
        print(f"Description: {req_data['description']}", file=output_file)
        
        if occurrences > 0:
            example = results[req_id][0]
            print(f"\nExample occurrence:", file=output_file)
            print(f"Log line: {example['line']}", file=output_file)
            print(f"Previous state: {example['previous_state']}", file=output_file)
            print(f"New state: {example['state']}", file=output_file)
        
        print("-" * 80, file=output_file)
    
    return results

def monitor_log_file(filename):
    """Continuously monitor the log file for changes"""
    print(f"\nStarting real-time monitoring of: {filename}")
    print("\nSystem Requirements Summary:")
    print("-" * 80)
    for req_id, req_data in CarLockSystem().requirements.items():
        print(f"{req_id}: {req_data['description']}")
    print("\nPress Ctrl+C to stop monitoring...\n")
    
    with open("car_lock_analysis.txt", "a", encoding='utf-8') as output_file:
        output_file.write(f"\n\n=== Monitoring Session {datetime.now()} ===\n")
        
        last_position = 0 if not os.path.exists(filename) else os.path.getsize(filename)
        try:
            while True:
                with open(filename, 'r', encoding='utf-8') as file:
                    file.seek(last_position)
                    new_lines = file.readlines()
                    last_position = file.tell()
                
                if new_lines:
                    print("\n" + "="*80)
                    print("NEW LOG ENTRIES".center(80))
                    print("="*80)
                    
                    temp_filename = "temp_log.txt"
                    with open(temp_filename, 'w', encoding='utf-8') as temp_file:
                        temp_file.writelines(new_lines)
                    
                    analyze_log_file(temp_filename, output_file)
                    output_file.flush()
                    os.remove(temp_filename)
                
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")

if __name__ == "__main__":
    log_file = "doors_log.txt"
    
    # Initialize output file
    with open("car_lock_analysis.txt", "w", encoding='utf-8'):
        pass
    
    print(f"Initial analysis of {log_file}...")
    print("\n" + "="*80)
    print("=== Initial Analysis ===".center(80))
    print("="*80)
    
    # Initial analysis
    with open("car_lock_analysis.txt", "a", encoding='utf-8') as output_file:
        analyze_log_file(log_file, output_file)
    
    # Start monitoring
    monitor_log_file(log_file)
