#!/usr/bin/env python3
import time
import can
import os
import re
from req import WiperSystem

class CANWiperMaster:
    def __init__(self):
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        self.wiper = WiperSystem("input.txt", "wiper_output.txt")
        self.CAN_MSG_ID = 0x100
        self.last_modified = 0
        
        self.init_can_bus()
    
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
            mod_time = os.path.getmtime("input.txt")
            if mod_time != self.last_modified:
                self.last_modified = mod_time
                return True
            return False
        except:
            return False
    
    def monitor(self):
        print("Monitoring input.txt...")
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