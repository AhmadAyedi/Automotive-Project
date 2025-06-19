#!/usr/bin/env python3
import time
import can
import os
import re
import json
from req import WiperSystem

class CANWiperMaster:
    def __init__(self):
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        # Create a temporary input.txt that req.py can read
        self.convert_json_to_txt("message_catalog.json", "message_catalog.txt")
        self.wiper = WiperSystem("message_catalog.txt", "wiper_output.txt")
        self.CAN_MSG_ID = 0x100
        self.last_modified = 0
        
        self.init_can_bus()
    
    def convert_json_to_txt(self, json_file, txt_file):
        """Convert the JSON input to the text format that req.py expects"""
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                
            # Extract values from JSON
            ignition = "OFF"  # Default value
            wiper_op = 0
            rain = 0
            reverse = 0
            
            for service in data.get('services', []):
                for event in service.get('events', []):
                    if event.get('event_name') == 'WiperIgnition':
                        # Handle both "on"/"off" and "ON"/"OFF"
                        status = event.get('event_value', {}).get('status', 'off').lower()
                        ignition = "ON" if status == "on" else "OFF"
                    elif event.get('event_name') == 'WiperRequestOperation':
                        wiper_op = int(event.get('event_value', {}).get('status', 0))
                    elif event.get('event_name') == 'RainIntensity':
                        rain = int(event.get('event_value', {}).get('status', 0))
                    elif event.get('event_name') == 'ReverseGear':
                        reverse = int(event.get('event_value', {}).get('status', 0))
            
            # Write to text file in the expected format
            with open(txt_file, 'w') as f:
                f.write(f"ignition = '{ignition}'\n")
                f.write(f"wiperRequestOperation = {wiper_op}\n")
                f.write(f"rainIntensity = {rain}\n")
                f.write(f"ReverseGear = {reverse}\n")
                
        except Exception as e:
            print(f"Error converting JSON to text: {e}")
            raise
    
    def init_can_bus(self):
        try:
            os.system(f'sudo /sbin/ip link set {self.channel} up type can bitrate 500000')
            time.sleep(0.1)
            self.bus = can.interface.Bus(channel=self.channel, bustype=self.bustype)
            print("CAN initialized")
        except Exception as e:
            print(f"CAN init failed: {e}")
            raise
    
    def extract_signals(self, content):
        """Extract only the signals that appear in the output"""
        signals = {}
        # Find all key=value pairs
        matches = re.finditer(r'(\w+)\s*=\s*(\d+)', content)
        for match in matches:
            signals[match.group(1)] = int(match.group(2))
        return signals
    
    def create_can_frame(self, signals):
        """Create CAN frame from exact output signals"""
        data = bytearray(8)  # Initialize with zeros
        
        # Map output signals to CAN frame bytes
        if 'wiperMode' in signals:
            data[0] = signals['wiperMode']
        if 'wiperSpeed' in signals:
            data[1] = signals['wiperSpeed']
        if 'wiperCycleCount' in signals:
            data[2] = signals['wiperCycleCount']
        if 'WiperIntermittent' in signals:
            data[3] = signals['WiperIntermittent']
        if 'wipingCycle' in signals:
            data[4] = signals['wipingCycle'] & 0xFF
            data[5] = (signals['wipingCycle'] >> 8) & 0xFF
        
        return data
    
    def send_signals(self):
        """Process input and send exact output signals"""
        try:
            # First update the input.txt from the JSON
            self.convert_json_to_txt("message_catalog.json", "message_catalog.txt")
            
            # Process through requirements
            self.wiper.process_operation()
            
            # Read the generated output
            with open("wiper_output.txt", 'r') as f:
                content = f.read()
                print("\nGenerated Output:")
                print(content.strip())
                
                # Extract exact signals
                signals = self.extract_signals(content)
                print("\nSignals to transmit:", signals)
                
                # Create and send CAN frame
                can_data = self.create_can_frame(signals)
                self.send_can(can_data)
                
        except Exception as e:
            print(f"Error: {e}")
    
    def send_can(self, data):
        try:
            msg = can.Message(
                arbitration_id=self.CAN_MSG_ID,
                data=data,
                is_extended_id=False
            )
            self.bus.send(msg)
            print(f"Sent CAN: {data.hex()}")
        except Exception as e:
            print(f"CAN send error: {e}")
    
    def file_changed(self):
        try:
            mod_time = os.path.getmtime("message_catalog.json")
            if mod_time != self.last_modified:
                self.last_modified = mod_time
                return True
            return False
        except:
            return False
    
    def monitor(self):
        print("Monitoring message_catalog.json...")
        try:
            while True:
                if self.file_changed():
                    print("\n=== Input Changed ===")
                    self.send_signals()
                time.sleep(0.3)  # Fast polling
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        if self.bus:
            self.bus.shutdown()
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        print("Shutdown complete")

if __name__ == "__main__":
    master = CANWiperMaster()
    master.monitor()