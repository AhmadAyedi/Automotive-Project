import time
import os
import json

class WiperSystem:
    def __init__(self, input_file_path="input.json", output_file_path="wiper_output.txt"):
        self.input_file_path = input_file_path
        self.output_file_path = output_file_path
        self.last_modified_time = 0

    def _read_json_input(self):
        """Read and parse the JSON input file."""
        try:
            with open(self.input_file_path, 'r') as file:
                data = json.load(file)
                # Initialize default values
                ignition = 'OFF'
                wiper_request = 0
                rain_intensity = 0
                reverse_gear = 0
                
                # Extract values from JSON
                for service in data.get('services', []):
                    for event in service.get('events', []):
                        event_name = event.get('event_name', '')
                        status = event.get('event_value', {}).get('status', '')
                        
                        if event_name == 'WiperIgnition':
                            ignition = 'ON' if status.lower() == 'on' else 'OFF'
                        elif event_name == 'WiperRequestOperation':
                            wiper_request = int(status) if status.isdigit() else 0
                        elif event_name == 'RainIntensity':
                            rain_intensity = int(status) if status.isdigit() else 0
                        elif event_name == 'ReverseGear':
                            reverse_gear = int(status) if status.isdigit() else 0
                
                return {
                    'ignition': ignition,
                    'wiperRequestOperation': wiper_request,
                    'rainIntensity': rain_intensity,
                    'ReverseGear': reverse_gear
                }
        except FileNotFoundError:
            print(f"Error: File '{self.input_file_path}' not found.")
            return None
        except Exception as e:
            print(f"Error reading JSON file: {e}")
            return None

    def check_wiper_status(self):
        """Check if ignition is ON (returns 1) or OFF (returns 0)."""
        input_data = self._read_json_input()
        if input_data is None:
            return 0
            
        if input_data['ignition'] == 'ON':
            print("Wiper function enabled - ignition ON")
            status = 1
        else:
            print("Wiper function disabled - ignition OFF")
            status = 0
            
        output_data = f"""Wiper_Function_Enabled = {status}"""
        with open(self.output_file_path, 'w') as output_file:
            output_file.write(output_data)
            
        return status

    def check_touch_mode(self):
        """Process wiper operation if ignition is ON and request is valid."""
        if self.check_wiper_status() != 1:
            print("System not operational - ignition is OFF")
            return False
        
        input_data = self._read_json_input()
        if input_data is None:
            return False
            
        if input_data['wiperRequestOperation'] == 1:
            output_data = """Touch Mode On:{ 
    wiperMode=1,
    wiperCycleCount=1,
    wiperSpeed=1,;}"""
            
            with open(self.output_file_path, 'w') as output_file:
                output_file.write(output_data)
            
            print(f"Touch Mode: ON")
            return True
        return False

    def check_speed1_mode(self):
        """Process wiper operation if ignition is ON and request is valid."""
        if self.check_wiper_status() != 1:
            print("System not operational - ignition is OFF")
            return False
        
        input_data = self._read_json_input()
        if input_data is None:
            return False
            
        if input_data['wiperRequestOperation'] == 2:
            output_data = """Speed 1 Mode On:{ 
    wiperMode=2,
    wiperSpeed=1;}"""
            
            with open(self.output_file_path, 'w') as output_file:
                output_file.write(output_data)
            
            print(f"Speed 1 Mode: ON")
            return True
        return False

    def check_speed2_mode(self):
        """Process wiper operation if ignition is ON and request is valid."""
        if self.check_wiper_status() != 1:
            print("System not operational - ignition is OFF")
            return False
        
        input_data = self._read_json_input()
        if input_data is None:
            return False
            
        if input_data['wiperRequestOperation'] == 3:
            output_data = """Speed 2 Mode On:{ 
    wiperMode=2,
    wiperSpeed=2;}"""
            
            with open(self.output_file_path, 'w') as output_file:
                output_file.write(output_data)
            
            print(f"Speed 2 Mode: ON")
            return True
        return False

    def check_automatic_mode(self):
        """Process wiper operation if ignition is ON and request is valid."""
        if self.check_wiper_status() != 1:
            print("System not operational - ignition is OFF")
            return False
        
        input_data = self._read_json_input()
        if input_data is None:
            return False
            
        if input_data['wiperRequestOperation'] == 4:
            rain_intensity = input_data['rainIntensity']
            
            # Determine wiper speed based on rain intensity
            if rain_intensity < 20:
                wiper_speed = 1
                print(f"Light rain detected ({rain_intensity}) - using speed 1")
            else:
                wiper_speed = 2
                print(f"Heavy rain detected ({rain_intensity}) - using speed 2")
            
            output_data = f"""Automatic Mode On:{{
    wiperMode=4,
    wiperSpeed={wiper_speed};}}"""
            
            with open(self.output_file_path, 'w') as output_file:
                output_file.write(output_data)
            
            print(f"Automatic Mode: ON (Rain: {rain_intensity}, Speed: {wiper_speed})")
            return True
        return False

    def check_intermittent_mode(self):
        """Process intermittent wiper operation when in reverse gear."""
        if self.check_wiper_status() != 1:
            print("System not operational - ignition is OFF")
            return False
        
        input_data = self._read_json_input()
        if input_data is None:
            return False
            
        if input_data['wiperRequestOperation'] == 4 and input_data['ReverseGear'] == 1:
            output_data = """Intermittent Mode On (Reverse Gear):{
    wiperMode=2,
    wiperSpeed=1,
    WiperIntermittent=1
    wipingCycle=1700;}"""
            
            with open(self.output_file_path, 'w') as output_file:
                output_file.write(output_data)
            
            print("Intermittent Mode: ON (Reverse Gear Active)")
            return True
        return False
            
    def file_has_changed(self):
        """Check if the input file has been modified since last check."""
        try:
            current_modified_time = os.path.getmtime(self.input_file_path)
            if current_modified_time != self.last_modified_time:
                self.last_modified_time = current_modified_time
                return True
            return False
        except:
            return False

    def process_operation(self):
        """Determine which operation to execute based on input file content."""
        input_data = self._read_json_input()
        if input_data is None:
            return
            
        if input_data['wiperRequestOperation'] == 4 and input_data['ReverseGear'] == 1:
            self.check_intermittent_mode()
        elif input_data['wiperRequestOperation'] == 1:
            self.check_touch_mode()                    
        elif input_data['wiperRequestOperation'] == 2:
            self.check_speed1_mode()
        elif input_data['wiperRequestOperation'] == 3:
            self.check_speed2_mode()
        elif input_data['wiperRequestOperation'] == 4:
            self.check_automatic_mode()                                        
        else:
            print("No valid wiper operation requested")

    def monitor_input_file(self):
        """Continuously monitor the input file for changes."""
        try:
            while True:
                if self.file_has_changed():
                    print("\n--- Detected file change ---")
                    self.process_operation()
                time.sleep(1)  # Check every second
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user.")

if __name__ == "__main__":
    wiper = WiperSystem("input.json", "wiper_output.txt")
    wiper.monitor_input_file()