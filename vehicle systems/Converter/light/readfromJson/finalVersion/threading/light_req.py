import json
import os
import time

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

    def set_low_beam(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.WOHNEN, self.FAHREN]:
            self.low_beam = self.ON
        elif new_mode in [self.PARKEN, self.STANDBY]:
            self.low_beam = self.OFF
        return self.low_beam

    def set_high_beam(self, new_mode):
        self.current_mode = new_mode
        self.high_beam = self.ON  # Always ON regardless of mode
        return self.high_beam

    def set_parking_lights(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.PARKEN, self.STANDBY, self.WOHNEN]:
            self.parking_left = self.ON
            self.parking_right = self.ON
        elif new_mode == self.FAHREN:
            self.parking_left = self.OFF
            self.parking_right = self.OFF
        return (self.parking_left, self.parking_right)

    def set_hazard_lights(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.FAHREN, self.WOHNEN]:
            self.hazard_lights = self.ON
        else:  # PARKEN and STANDBY
            self.hazard_lights = self.OFF
        return self.hazard_lights

    def set_turn_signals(self, new_mode):
        self.current_mode = new_mode
        if new_mode in [self.WOHNEN, self.FAHREN]:
            self.right_turn = self.ON
            self.left_turn = self.ON
        elif new_mode in [self.PARKEN, self.STANDBY]:
            self.right_turn = self.OFF
            self.left_turn = self.OFF
        return (self.right_turn, self.left_turn)

def parse_message_catalog(filename):
    """Extracts light status from message_catalog.json"""
    light_status = {
        'low_beam': None,
        'high_beam': None,
        'hazard': None,
        'left_turn': None,
        'right_turn': None,
        'break_light': None
    }
    
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            
            # Find the LightsStatus service
            for service in data['services']:
                if service['service_name'] == "LightsStatus":
                    for event in service['events']:
                        status = "ON" if event['event_value']['status'] == "1" else "OFF"
                        
                        if event['event_name'] == "Low_Beam_HeadlightStatus":
                            light_status['low_beam'] = status
                        elif event['event_name'] == "High_Beam_HeadlightStatus":
                            light_status['high_beam'] = status
                        elif event['event_name'] == "HazardStatus":
                            light_status['hazard'] = status
                        elif event['event_name'] == "LeftTurnStatus":
                            light_status['left_turn'] = status
                        elif event['event_name'] == "RightTurnStatus":
                            light_status['right_turn'] = status
                        elif event['event_name'] == "BreakLightStatus":
                            light_status['break_light'] = status
                    break
                    
    except Exception as e:
        print(f"Error reading JSON file: {e}")
    
    return light_status

def analyze_lights(light_status):
    system = VehicleLightingSystem()
    system.set_initial_parken_state()
    
    results = []
    
    # Low Beam analysis
    if light_status['low_beam'] is not None:
        expected_status = system.set_low_beam(system.PARKEN)
        result = "activated" if light_status['low_beam'] == "ON" else "FAILED"
        results.append(f"Light: Low Beam | Result: {result}")
    
    # High Beam analysis
    if light_status['high_beam'] is not None:
        expected_status = system.set_high_beam(system.PARKEN)
        result = "activated" if light_status['high_beam'] == expected_status else "FAILED"
        results.append(f"Light: High Beam | Result: {result}")
    
    # Hazard Lights analysis
    if light_status['hazard'] is not None:
        expected_status = system.set_hazard_lights(system.PARKEN)
        result = "activated" if light_status['hazard'] == "ON" else "deactivated"
        results.append(f"Light: Hazard Lights | Result: {result}")
    
    # Turn Signals analysis
    if light_status['left_turn'] is not None:
        _, expected_left = system.set_turn_signals(system.PARKEN)
        result = "activated" if light_status['left_turn'] == "ON" else "deactivated"
        results.append(f"Light: Left Turn | Result: {result}")
    
    if light_status['right_turn'] is not None:
        expected_right, _ = system.set_turn_signals(system.PARKEN)
        result = "activated" if light_status['right_turn'] == "ON" else "deactivated"
        results.append(f"Light: Right Turn | Result: {result}")
    
    # Parking Lights (not in JSON, but keeping for compatibility)
    parking_left, parking_right = system.set_parking_lights(system.PARKEN)
    results.append(f"Light: Parking Left | Result: deactivated")
    results.append(f"Light: Parking Right | Result: deactivated")
    
    return results

def monitor_json_file(filename):
    """Continuously monitors the JSON file for changes"""
    print(f"\nStarting real-time monitoring of: {filename}")
    print("\nLighting System Requirements Summary:")
    print("- Low Beam: ON in Wohnen/Fahren, OFF in Parking/Standby")
    print("- High Beam: ON in all modes")
    print("- Hazard Lights: ON in Fahren/Wohnen, OFF in Parking/Standby")
    print("- Turn Signals: ON in Wohnen/Fahren, OFF in Parking/Standby")
    print("\nPress Ctrl+C to stop monitoring...\n")
    
    # Initialize results file with a header only if it doesn't exist
    if not os.path.exists("analysis_results.txt"):
        with open("analysis_results.txt", "w") as f:
            f.write("Vehicle Lighting System Analysis Results\n")
    
    last_modified = 0
    last_content_hash = None
    
    try:
        while True:
            current_modified = os.path.getmtime(filename)
            if current_modified > last_modified:
                last_modified = current_modified
                
                light_status = parse_message_catalog(filename)
                current_hash = str(light_status)
                
                if current_hash != last_content_hash:
                    last_content_hash = current_hash
                    results = analyze_lights(light_status)
                    
                    print("\nNew entries detected:")
                    for line in results:
                        print(line)
                    
                    with open("analysis_results.txt", "a") as f:
                        for line in results:
                            f.write(line + "\n")
                    
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    json_file = "message_catalog.json"
    
    print(f"Initial analysis of {json_file}...")
    light_status = parse_message_catalog(json_file)
    if any(light_status.values()):
        print("\n=== Initial Analysis ===")
        results = analyze_lights(light_status)
        for line in results:
            print(line)
        
        with open("analysis_results.txt", "a") as f:
            for line in results:
                f.write(line + "\n")
    else:
        print("No light status information found in the JSON file.")
    
    monitor_json_file(json_file)