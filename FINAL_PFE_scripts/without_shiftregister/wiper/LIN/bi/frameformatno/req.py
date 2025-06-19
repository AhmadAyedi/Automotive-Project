##############################################################
import time
import os

class WiperSystem:
    def __init__(self, input_file_path="input.txt", output_file_path="wiper_output.txt"):
        self.input_file_path = input_file_path
        self.output_file_path = output_file_path
        self.last_modified_time = 0

    def check_wiper_status(self):
        """Check if ignition is ON (returns 1) or OFF (returns 0)."""
        try:
            with open(self.input_file_path, 'r') as file:
                content = file.read()
                
                if 'ignition = \'ON\'' in content or 'ignition = "ON"' in content:
                    print("Wiper function enabled - ignition ON")
                    status = 1
                else:
                    print("Wiper function disabled - ignition OFF")
                    status = 0
                output_data = f"""Wiper_Function_Enabled = {status}"""
                with open(self.output_file_path, 'w') as output_file:
                    output_file.write(output_data)
                    
                return status

                    
        except FileNotFoundError:
            print(f"Error: File '{self.input_file_path}' not found.")
            return 0
        except Exception as e:
            print(f"Error reading file: {e}")
            return 0
#____________________________________touch mode_______________________________
    def check_touch_mode(self):
        """Process wiper operation if ignition is ON and request is valid."""
        if self.check_wiper_status() != 1:
            print("System not operational - ignition is OFF")
            return False
        
        try:
            with open(self.input_file_path, 'r') as file:
                content = file.read()
                
                if 'wiperRequestOperation = 1' in content:
                    output_data = """Touch Mode On:{ 
    wiperMode=1,
    wiperCycleCount=1,
    wiperSpeed=1,;}"""
                    
                    with open(self.output_file_path, 'w') as output_file:
                        output_file.write(output_data)
                    
                    print(f"Touch Mode: ON")
                    return True
                return False
                    
        except Exception as e:
            print(f"Error processing wiper operation: {e}")
            return False
#______________________________________speed1 mode_______________________________
    def check_speed1_mode(self):
        """Process wiper operation if ignition is ON and request is valid."""
        if self.check_wiper_status() != 1:  # Changed from 2 to 1 to be consistent
            print("System not operational - ignition is OFF")
            return False
        
        try:
            with open(self.input_file_path, 'r') as file:
                content = file.read()
                
                if 'wiperRequestOperation = 2' in content:
                    output_data = """Speed 1 Mode On:{ 
    wiperMode=2,
    wiperSpeed=1;}"""
                    
                    with open(self.output_file_path, 'w') as output_file:
                        output_file.write(output_data)
                    
                    print(f"Speed 1 Mode: ON")
                    return True
                return False
                    
        except Exception as e:
            print(f"Error processing wiper operation: {e}")
            return False
#__________________________________Speed2 MODE_____________________________________________
    def check_speed2_mode(self):
        """Process wiper operation if ignition is ON and request is valid."""
        if self.check_wiper_status() != 1:  # Changed from 2 to 1 to be consistent
            print("System not operational - ignition is OFF")
            return False
        
        try:
            with open(self.input_file_path, 'r') as file:
                content = file.read()
                
                if 'wiperRequestOperation = 3' in content:
                    output_data = """Speed 2 Mode On:{ 
    wiperMode=2,
    wiperSpeed=2;}"""
                    
                    with open(self.output_file_path, 'w') as output_file:
                        output_file.write(output_data)
                    
                    print(f"Speed 2 Mode: ON")
                    return True
                return False
                    
        except Exception as e:
            print(f"Error processing wiper operation: {e}")
            return False

#_________________________________Automatic mode____________________________________________
         
    def check_automatic_mode(self):
        """Process wiper operation if ignition is ON and request is valid."""
        if self.check_wiper_status() != 1:
            print("System not operational - ignition is OFF")
            return False
        
        try:
            with open(self.input_file_path, 'r') as file:
                content = file.read()
                
                if 'wiperRequestOperation = 4' in content:
                    # Initialize rain_intensity with a default value
                    rain_intensity = 0
                    
                    # Try to extract rain intensity value
                    try:
                        # Find the rain intensity line (handles multiple formats)
                        rain_line = [line for line in content.split('\n') 
                                   if 'rainIntensity' in line][0]
                        # Extract the numeric value
                        rain_intensity = int(''.join(filter(str.isdigit, rain_line)))
                    except (ValueError, IndexError, AttributeError) as e:
                        print(f"Warning: Could not parse rain intensity, using default (0). Error: {e}")
                    
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
                    
        except Exception as e:
            print(f"Error processing wiper operation: {e}")
            return False
#________________________Intermittent mode______________________________________
    def check_intermittent_mode(self):
        """Process intermittent wiper operation when in reverse gear."""
        if self.check_wiper_status() != 1:
            print("System not operational - ignition is OFF")
            return False
        
        try:
            with open(self.input_file_path, 'r') as file:
                content = file.read()
                
                # Check for both conditions
                if 'wiperRequestOperation = 4' in content and 'ReverseGear = 1' in content:
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
                    
        except Exception as e:
            print(f"Error processing intermittent wiper operation: {e}")
            return False
            
#_____________________________________________________________________
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
#______________________________________________________________________
    def process_operation(self):
        """Determine which operation to execute based on input file content."""
        try:
            with open(self.input_file_path, 'r') as file:
                content = file.read()
                
                if 'wiperRequestOperation = 4' in content and 'ReverseGear = 1' in content:
                    self.check_intermittent_mode()
                elif 'wiperRequestOperation = 1' in content:
                    self.check_touch_mode()                    
                elif 'wiperRequestOperation = 2' in content:
                    self.check_speed1_mode()
                elif 'wiperRequestOperation = 3' in content:
                    self.check_speed2_mode()
                elif 'wiperRequestOperation = 4' in content:
                    self.check_automatic_mode()                                        
                else:
                    print("No valid wiper operation requested")
                    
        except Exception as e:
            print(f"Error reading file: {e}")
#_________________________________________________________________
    def monitor_input_file(self):
        """Continuously monitor the input file for changes."""
        #print(f"Monitoring {self.input_file_path} for changes... (Press Ctrl+C to stop)")
        try:
            while True:
                if self.file_has_changed():
                    print("\n--- Detected file change ---")
                    self.process_operation()  # Changed to use process_operation instead of check_touch_mode
                time.sleep(1)  # Check every second
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user.")

if __name__ == "__main__":
    wiper = WiperSystem("input.txt", "wiper_output.txt")
    wiper.monitor_input_file()
