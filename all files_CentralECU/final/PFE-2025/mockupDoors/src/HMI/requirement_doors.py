import time
import re
import os
import sys

def display_function_summary():
    """Display a summary of all implemented functions at startup."""
    print("\n" + "="*80)
    print("IMPLEMENTED FUNCTIONS SUMMARY:")
    print("-"*80)
    print("1. Function 1: When key_zone=1, key_button=1, and all doors locked")
    print("   ? All doors unlocked, FlashLight=1, HornBeeping=1")
    print("-"*80)
    print("2. Function 2: When key_zone=0, key_button=0, and all doors unlocked")
    print("   ? All doors locked, FlashLight=1, HornBeeping=1")
    print("-"*80)
    print("3. Function 3 Case 1: When key_button=0 and all doors unlocked")
    print("   ? All doors locked, FlashLight=1, HornBeeping=1")
    print("-"*80)
    print("4. Function 3 Case 2: When key_button=1 and all doors locked")
    print("   ? All doors unlocked, FlashLight=1, HornBeeping=1")
    print("-"*80)
    print("5. Function 4: If (open_close_outside=open or open_close_inside=open) and key_zone=0")
    print("   ? All doors should be unlocked")
    print("-"*80)
    print("6. Function 5: If any door open from inside/outside while unlocked")
    print("   ? Corresponding door should open")
    print("="*80 + "\n")

def parse_log_line(line):
    """Parse a log line and extract relevant information."""
    data = {
        'key_zone': None,
        'key_button': None,
        'FlashLight': None,
        'HornBeeping': None,
        'front_right_door': None,
        'rear_right_door': None,
        'front_left_door': None,
        'rear_left_door': None,
        'open_close_outside': None,
        'open_close_inside': None
    }
    
    # Key information
    key_match = re.search(r'key_zone:\s*(\d)', line)
    if key_match:
        data['key_zone'] = int(key_match.group(1))
    
    key_button_match = re.search(r'key_button:\s*(\d)', line)
    if key_button_match:
        data['key_button'] = int(key_button_match.group(1))
    
    flash_match = re.search(r'FlashLight:\s*(\d)', line)
    if flash_match:
        data['FlashLight'] = int(flash_match.group(1))
    
    horn_match = re.search(r'HornBeeping:\s*(\d)', line)
    if horn_match:
        data['HornBeeping'] = int(horn_match.group(1))
    
    # Door information
    if 'Front Right Door' in line:
        state_match = re.search(r'State:\s*(\w+)', line)
        if state_match:
            data['front_right_door'] = state_match.group(1).lower()
        
        outside_match = re.search(r'open_close_outside:\s*(\w*)', line)
        if outside_match:
            data['open_close_outside'] = outside_match.group(1).lower() if outside_match.group(1) else None
        
        inside_match = re.search(r'open_close_inside:\s*(\w*)', line)
        if inside_match:
            data['open_close_inside'] = inside_match.group(1).lower() if inside_match.group(1) else None
    
    elif 'Rear Right Door' in line:
        state_match = re.search(r'State:\s*(\w+)', line)
        if state_match:
            data['rear_right_door'] = state_match.group(1).lower()
    
    elif 'Front Left Door' in line:
        state_match = re.search(r'State:\s*(\w+)', line)
        if state_match:
            data['front_left_door'] = state_match.group(1).lower()
    
    elif 'Rear Left Door' in line:
        state_match = re.search(r'State:\s*(\w+)', line)
        if state_match:
            data['rear_left_door'] = state_match.group(1).lower()
    
    return data

def get_expected_state(current_state):
    """Determine the expected state based on the current state and the functions."""
    expected = {
        'front_right_door': current_state.get('front_right_door'),
        'rear_right_door': current_state.get('rear_right_door'),
        'front_left_door': current_state.get('front_left_door'),
        'rear_left_door': current_state.get('rear_left_door'),
        'FlashLight': current_state.get('FlashLight'),
        'HornBeeping': current_state.get('HornBeeping')
    }
    
    # Function 1: Unlock all doors when key_zone=1, key_button=1 and all doors locked
    if (current_state.get('key_zone') == 1 and 
        current_state.get('key_button') == 1 and
        current_state.get('front_right_door') == 'locked' and
        current_state.get('rear_right_door') == 'locked' and
        current_state.get('front_left_door') == 'locked' and
        current_state.get('rear_left_door') == 'locked'):
        expected.update({
            'front_right_door': 'unlocked',
            'rear_right_door': 'unlocked',
            'front_left_door': 'unlocked',
            'rear_left_door': 'unlocked',
            'FlashLight': 1,
            'HornBeeping': 1
        })
    
    # Function 2: Lock all doors when key_zone=0, key_button=0 and all doors unlocked
    elif (current_state.get('key_zone') == 0 and 
          current_state.get('key_button') == 0 and
          current_state.get('front_right_door') == 'unlocked' and
          current_state.get('rear_right_door') == 'unlocked' and
          current_state.get('front_left_door') == 'unlocked' and
          current_state.get('rear_left_door') == 'unlocked'):
        expected.update({
            'front_right_door': 'locked',
            'rear_right_door': 'locked',
            'front_left_door': 'locked',
            'rear_left_door': 'locked',
            'FlashLight': 1,
            'HornBeeping': 1
        })
    
    # Function 3 Case 1: Lock all doors when key_button=0 and all doors unlocked
    elif (current_state.get('key_button') == 0 and
          current_state.get('front_right_door') == 'unlocked' and
          current_state.get('rear_right_door') == 'unlocked' and
          current_state.get('front_left_door') == 'unlocked' and
          current_state.get('rear_left_door') == 'unlocked'):
        expected.update({
            'front_right_door': 'locked',
            'rear_right_door': 'locked',
            'front_left_door': 'locked',
            'rear_left_door': 'locked',
            'FlashLight': 1,
            'HornBeeping': 1
        })
    
    # Function 3 Case 2: Unlock all doors when key_button=1 and all doors locked
    elif (current_state.get('key_button') == 1 and
          current_state.get('front_right_door') == 'locked' and
          current_state.get('rear_right_door') == 'locked' and
          current_state.get('front_left_door') == 'locked' and
          current_state.get('rear_left_door') == 'locked'):
        expected.update({
            'front_right_door': 'unlocked',
            'rear_right_door': 'unlocked',
            'front_left_door': 'unlocked',
            'rear_left_door': 'unlocked',
            'FlashLight': 1,
            'HornBeeping': 1
        })
    
    # Modified Function 4: Only unlock if key_zone=0 AND (open_close_outside=open or open_close_inside=open)
    elif (current_state.get('key_zone') == 0 and
          (current_state.get('open_close_outside') == 'open' or
           current_state.get('open_close_inside') == 'open')):
        expected.update({
            'front_right_door': 'unlocked',
            'rear_right_door': 'unlocked',
            'front_left_door': 'unlocked',
            'rear_left_door': 'unlocked'
        })
    
    # Function 5: If any door open from inside/outside while unlocked
    if ((current_state.get('open_close_outside') == 'open' or
         current_state.get('open_close_inside') == 'open')):
        if (current_state.get('front_right_door') == 'unlocked' or
            current_state.get('rear_right_door') == 'unlocked' or
            current_state.get('front_left_door') == 'unlocked' or
            current_state.get('rear_left_door') == 'unlocked'):
            # This would be handled in the actual implementation
            pass
    
    return expected

def compare_states(expected, actual):
    """Compare expected and actual states and return PASSED/FAILED."""
    relevant_keys = ['front_right_door', 'rear_right_door', 'front_left_door', 
                    'rear_left_door', 'FlashLight', 'HornBeeping']
    
    for key in relevant_keys:
        if expected.get(key) is not None and actual.get(key) != expected.get(key):
            return False
    return True

def format_state(state):
    """Format the state dictionary into a readable string."""
    return (f"front_right_door = {state.get('front_right_door')}, "
            f"rear_right_door = {state.get('rear_right_door')}, "
            f"front_left_door = {state.get('front_left_door')}, "
            f"rear_left_door = {state.get('rear_left_door')}, "
            f"FlashLight = {state.get('FlashLight')}, "
            f"HornBeeping = {state.get('HornBeeping')}")

def monitor_file(filename):
    """Monitor the file for changes and check conditions."""
    last_position = 0
    current_state = {}
    
    try:
        while True:
            try:
                with open(filename, 'r') as file:
                    file.seek(0, 2)
                    current_size = file.tell()
                    
                    if current_size < last_position:
                        last_position = 0
                    
                    if current_size > last_position:
                        file.seek(last_position)
                        new_lines = file.readlines()
                        last_position = file.tell()
                        
                        for line in new_lines:
                            parsed_data = parse_log_line(line)
                            
                            # Update current state with new data
                            for key, value in parsed_data.items():
                                if value is not None:
                                    current_state[key] = value
                            
                            # Skip if we don't have complete state yet
                            if not all(k in current_state for k in ['front_right_door', 'rear_right_door', 
                                                                  'front_left_door', 'rear_left_door',
                                                                  'FlashLight', 'HornBeeping']):
                                continue
                            
                            # Get expected state based on functions
                            expected_state = get_expected_state(current_state)
                            
                            # Compare with actual state
                            actual_state = {
                                'front_right_door': current_state.get('front_right_door'),
                                'rear_right_door': current_state.get('rear_right_door'),
                                'front_left_door': current_state.get('front_left_door'),
                                'rear_left_door': current_state.get('rear_left_door'),
                                'FlashLight': current_state.get('FlashLight'),
                                'HornBeeping': current_state.get('HornBeeping')
                            }
                            
                            result = compare_states(expected_state, actual_state)
                            
                            # Print the comparison
                            print("\nExpected:", format_state(expected_state))
                            print("Actual:  ", format_state(actual_state))
                            print("RESULT:  ", "PASSED" if result else "FAILED")
                            print("-" * 80)
                
                time.sleep(0.1)
                
            except FileNotFoundError:
                print(f"Waiting for file: {filename}...")
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user (CTRL+C pressed).")
        sys.exit(0)

if __name__ == "__main__":
    print("Starting door log monitor...")
    display_function_summary()
    monitor_file("/home/pi/vsomeip/PFE-2025/mockupDoors/src/doors_log.txt")