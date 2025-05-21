import re
import time
import os
import sys

class VehicleLightingSystem:
    # Constants for modes
    PARKEN = "P"       # Parking mode
    STANDBY = "S"      # Standby mode
    WOHNEN = "W"       # Wohnen mode
    FAHREN = "F"       # Fahren mode
   
    ON = "ON"
    OFF = "OFF"

    def __init__(self):
        self.current_mode = self.PARKEN
        self.low_beam = self.OFF
        self.high_beam = self.OFF
        self.parking_left = self.OFF
        self.parking_right = self.OFF
        self.hazard_lights = self.OFF
        self.right_turn = self.OFF
        self.left_turn = self.OFF
        self.previous_mode = None
        self.mode_sequence = [self.PARKEN, self.STANDBY, self.WOHNEN, self.FAHREN]

    def set_initial_parken_state(self):
        self.current_mode = self.PARKEN
        self.low_beam = self.OFF
        self.high_beam = self.OFF
        self.parking_left = self.OFF
        self.parking_right = self.OFF
        self.hazard_lights = self.OFF
        self.right_turn = self.OFF
        self.left_turn = self.OFF
        self.previous_mode = None

    def validate_mode_transition(self, new_mode):
        if self.current_mode == new_mode:
            return True  # No transition needed
        
        current_index = self.mode_sequence.index(self.current_mode)
        new_index = self.mode_sequence.index(new_mode)
        
        # Check if transition is sequential (either increasing or decreasing by 1)
        if abs(current_index - new_index) == 1:
            return True
        
        return False

    def update_low_beam(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.WOHNEN, self.FAHREN]:
            self.low_beam = self.ON
        elif new_mode in [self.PARKEN, self.STANDBY]:
            self.low_beam = self.OFF
        return self.low_beam

    def update_high_beam(self, new_mode):
        self.current_mode = new_mode
        self.high_beam = self.ON  # Always ON regardless of mode
        return self.high_beam

    def update_parking_lights(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.PARKEN, self.STANDBY, self.WOHNEN]:
            self.parking_left = self.ON
            self.parking_right = self.ON
        elif new_mode == self.FAHREN:
            self.parking_left = self.OFF
            self.parking_right = self.OFF
        return (self.parking_left, self.parking_right)

    def update_hazard_lights(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.FAHREN, self.WOHNEN]:
            self.hazard_lights = self.ON  # ON in both FAHREN and WOHNEN modes
        else:  # PARKEN and STANDBY
            self.hazard_lights = self.OFF
        return self.hazard_lights

    def update_turn_signals(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.WOHNEN, self.FAHREN]:
            self.right_turn = self.ON
            self.left_turn = self.ON
        elif new_mode in [self.PARKEN, self.STANDBY]:
            self.right_turn = self.OFF
            self.left_turn = self.OFF
        return (self.right_turn, self.left_turn)

def parse_lights_log(filename, last_position=0):
    """Extracts all light status entries since last read"""
    patterns = {
        'low_beam': r"Low Beam Headlights\s*\|\s*Status:\s*(\w+)\s*Mode:\s*(\w+)",
        'high_beam': r"High Beam Headlights Signal\s*\|\s*Status:\s*(\w+)\s*Mode:\s*(\w+)",
        'parking_left': r"Parking left Signal\s*\|\s*Status:\s*(\w+)\s*Mode:\s*(\w+)",
        'parking_right': r"Parking right\s*\|\s*Status:\s*(\w+)\s*Mode:\s*(\w+)",
        'hazard': r"Hazard Lights\s*\|\s*Status:\s*(\w+)\s*Mode:\s*(\w+)",
        'right_turn': r"Right Turn Signal\s*\|\s*Status:\s*(\w+)\s*Mode:\s*(\w+)",
        'left_turn': r"Left Turn Signal\s*\|\s*Status:\s*(\w+)\s*Mode:\s*(\w+)",
        'mode': r"Mode:\s*(\w+)"
    }
    log_entries = {light_type: [] for light_type in patterns}
    mode_transitions = []
    previous_mode = None
   
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            file.seek(last_position)
            for line in file:
                line = line.strip()
                if line.startswith("CLIENT: received a notification") or "=" in line:
                    continue
                
                # Check for mode in each line
                mode_match = re.search(patterns['mode'], line)
                if mode_match:
                    current_mode = mode_match.group(1).strip()
                    if previous_mode is not None and current_mode != previous_mode:
                        mode_transitions.append((previous_mode, current_mode))
                    previous_mode = current_mode
                
                for light_type, pattern in patterns.items():
                    if light_type == 'mode':
                        continue
                    match = re.search(pattern, line)
                    if match:
                        status = match.group(1).strip()
                        mode = match.group(2).strip()
                        log_entries[light_type].append((status, mode))
            last_position = file.tell()
    except Exception as e:
        print(f"Error reading log file: {e}")
    
    log_entries['mode_transition'] = mode_transitions
    return log_entries, last_position

def analyze_lights(log_entries, output_file=None, simple_file_output=False):
    system = VehicleLightingSystem()
    system.set_initial_parken_state()
    
    mode_mapping = {
        "Parking": system.PARKEN,
        "Standby": system.STANDBY,
        "Wohnen": system.WOHNEN,
        "Whonen": system.WOHNEN,
        "Fahren": system.FAHREN,
        "StandBy": system.STANDBY,
        "Stand By": system.STANDBY
    }
    
    console_results = []
    file_results = []
    
    # First check mode transitions (only for console output)
    transition_messages = []
    for from_mode, to_mode in log_entries['mode_transition']:
        normalized_from = from_mode.replace(" ", "")
        normalized_to = to_mode.replace(" ", "")
        
        system_from = mode_mapping.get(normalized_from, system.PARKEN)
        system_to = mode_mapping.get(normalized_to, system.PARKEN)
        
        # Simulate the current mode for validation
        system.current_mode = system_from
        valid_transition = system.validate_mode_transition(system_to)
        
        if valid_transition:
            result = f"VALID transition: {from_mode} → {to_mode}"
        else:
            result = f"INVALID transition: {from_mode} → {to_mode} (must follow sequence: Parking → Stand By → Wohnen → Fahren or reverse)"
        
        transition_messages.append(result)
    
    # Add transition messages to console only
    if transition_messages:
        console_results.append("\n=== Mode Transition Analysis ===")
        for msg in transition_messages:
            console_results.append(msg)
    else:
        console_results.append("\nNo mode transitions found in log")
    
    # Analyze Low Beam
    for status, mode in log_entries['low_beam']:
        normalized_mode = mode.replace(" ", "")
        system_mode = mode_mapping.get(normalized_mode, system.PARKEN)
        expected_status = system.update_low_beam(system_mode)
        if system_mode in [system.WOHNEN, system.FAHREN]:
            if status == "ON":
                result = "activated"
            elif status == "OFF":
                result = "desactivated"
        else:  # PARKEN and STANDBY
            if status == "OFF":
                result = "desactivated"
            elif status == "ON":
                result = "FAILED"
        
        console_results.append(f"Light: Low Beam | Mode: {mode} | Status: {status} | Expected: {expected_status} | Result: {result}")
        file_results.append(f"Light: Low Beam | Result: {result}")
    
    # High Beam analysis
    for status, mode in log_entries['high_beam']:
        normalized_mode = mode.replace(" ", "")
        system_mode = mode_mapping.get(normalized_mode, system.PARKEN)
        expected_status = system.update_high_beam(system_mode)
        result = "activated" if status == expected_status else "FAILED"
        
        console_results.append(f"Light: High Beam | Mode: {mode} | Status: {status} | Expected: {expected_status} | Result: {result}")
        file_results.append(f"Light: High Beam | Result: {result}")
    
    # Parking Lights
    for status, mode in log_entries['parking_left']:
        normalized_mode = mode.replace(" ", "")
        system_mode = mode_mapping.get(normalized_mode, system.PARKEN)
        expected_left, _ = system.update_parking_lights(system_mode)
        if system_mode in [system.PARKEN, system.STANDBY, system.WOHNEN]:
            if status == "ON":
                result = "activated"
            elif status == "OFF":
                result = "desactivated"
        else:  # FAHREN mode
            if status == "OFF":
                result = "desactivated"
            elif status == "ON":
                result = "FAILED"
        
        console_results.append(f"Light: Parking Left | Mode: {mode} | Status: {status} | Expected: {expected_left} | Result: {result}")
        file_results.append(f"Light: Parking Left | Result: {result}")
    
    for status, mode in log_entries['parking_right']:
        normalized_mode = mode.replace(" ", "")
        system_mode = mode_mapping.get(normalized_mode, system.PARKEN)
        _, expected_right = system.update_parking_lights(system_mode)
        if system_mode in [system.PARKEN, system.STANDBY, system.WOHNEN]:
            if status == "ON":
                result = "activated"
            elif status == "OFF":
                result = "desactivated"
        else:  # FAHREN mode
            if status == "OFF":
                result = "desactivated"
            elif status == "ON":
                result = "FAILED"
        
        console_results.append(f"Light: Parking Right | Mode: {mode} | Status: {status} | Expected: {expected_right} | Result: {result}")
        file_results.append(f"Light: Parking Right | Result: {result}")
    
    # Hazard Lights Analysis
    for status, mode in log_entries['hazard']:
        normalized_mode = mode.replace(" ", "")
        system_mode = mode_mapping.get(normalized_mode, system.PARKEN)
        expected_status = system.update_hazard_lights(system_mode)
        
        if system_mode in [system.FAHREN, system.WOHNEN]:
            if status == "ON":
                result = "activated"
            elif status == "OFF":
                result = "desactivated"
        else:  # PARKEN and STANDBY
            if status == "OFF":
                result = "desactivated"
            elif status == "ON":
                result = "FAILED"
        
        console_results.append(f"Light: Hazard Lights | Mode: {mode} | Status: {status} | Expected: {expected_status} | Result: {result}")
        file_results.append(f"Light: Hazard Lights | Result: {result}")
    
    # Turn Signals
    for status, mode in log_entries['right_turn']:
        normalized_mode = mode.replace(" ", "")
        system_mode = mode_mapping.get(normalized_mode, system.PARKEN)
        expected_right, _ = system.update_turn_signals(system_mode)
        if system_mode in [system.WOHNEN, system.FAHREN]:
            if status == "ON":
                result = "activated"
            elif status == "OFF":
                result = "desactivated"
        else:  # PARKEN and STANDBY
            if status == "OFF":
                result = "desactivated"
            elif status == "ON":
                result = "FAILED"
        
        console_results.append(f"Light: Right Turn | Mode: {mode} | Status: {status} | Expected: {expected_right} | Result: {result}")
        file_results.append(f"Light: Right Turn | Result: {result}")
    
    for status, mode in log_entries['left_turn']:
        normalized_mode = mode.replace(" ", "")
        system_mode = mode_mapping.get(normalized_mode, system.PARKEN)
        _, expected_left = system.update_turn_signals(system_mode)
        if system_mode in [system.WOHNEN, system.FAHREN]:
            if status == "ON":
                result = "activated"
            elif status == "OFF":
                result = "desactivated"
        else:  # PARKEN and STANDBY
            if status == "OFF":
                result = "desactivated"
            elif status == "ON":
                result = "FAILED"
        
        console_results.append(f"Light: Left Turn | Mode: {mode} | Status: {status} | Expected: {expected_left} | Result: {result}")
        file_results.append(f"Light: Left Turn | Result: {result}")
    
    # Output results
    if output_file:
        if simple_file_output:
            for line in file_results:
                print(line, file=output_file)
        else:
            for line in console_results:
                if not line.startswith("=== Mode Transition Analysis ===") and not line.startswith("INVALID transition") and not line.startswith("VALID transition"):
                    print(line, file=output_file)
    else:
        for line in console_results:
            print(line)
    
    return file_results if simple_file_output else console_results

def monitor_log_file(filename):
    """Continuously monitors the log file for new entries"""
    print(f"\nStarting real-time monitoring of: {filename}")
    print("\nLighting System Requirements Summary:")
    print("- Mode transitions must follow sequence: P → S → W → F or F → W → S → P")
    print("- Low Beam: ON in Wohnen/Fahren, OFF in Parking/Standby")
    print("- High Beam: ON in all modes")
    print("- Parking Lights: ON in Parking/Standby/Wohnen, OFF in Fahren")
    print("- Hazard Lights: ON in Fahren/Wohnen, OFF in Parking/Standby")
    print("- Turn Signals: ON in Wohnen/Fahren, OFF in Parking/Standby")
    print("\nPress Ctrl+C to stop monitoring...\n")
    
    with open("analysis_results.txt", "a") as output_file:
        output_file.write(f"\n\n=== New Monitoring Session === {time.ctime()}\n")
        
        last_position = 0 if not os.path.exists(filename) else os.path.getsize(filename)
        try:
            while True:
                new_entries, last_position = parse_lights_log(filename, last_position)
                if any(new_entries.values()):
                    # Print detailed output to console
                    print("\nNew entries detected:")
                    analyze_lights(new_entries)
                    
                    # Write simple output to file (without transition messages)
                    with open("analysis_results.txt", "a") as f:
                        analyze_lights(new_entries, output_file=f, simple_file_output=True)
                    
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")

if __name__ == "__main__":
    log_file = "lights_log.txt"
    
    # Initialize results file
    with open("analysis_results.txt", "w") as f:
        f.write("Vehicle Lighting System Analysis Results\n")
        f.write("="*50 + "\n")
    
    print(f"Initial analysis of {log_file}...")
    entries, _ = parse_lights_log(log_file)
    if any(entries.values()):
        # Print detailed output to console
        print("\n=== Initial Analysis ===")
        analyze_lights(entries)
        
        # Write simple output to file
        with open("analysis_results.txt", "a") as f:
            f.write("\n=== Initial Analysis ===\n")
            analyze_lights(entries, output_file=f, simple_file_output=True)
    else:
        print("No initial light entries found.")
    
    monitor_log_file(log_file)