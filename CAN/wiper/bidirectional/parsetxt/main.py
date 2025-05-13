#!/usr/bin/env python3
import time
import can
import os
import re
import threading
from req import WiperSystem
from datetime import datetime

class CANWiperMaster:
    def __init__(self):
        self.channel = 'can0'
        self.bustype = 'socketcan'
        self.bus = None
        self.wiper = WiperSystem("input.txt", "wiper_output.txt")
        self.CAN_MSG_ID = 0x100
        self.RESPONSE_MSG_ID = 0x101
        self.last_modified = 0
        self.running = True
        
        self.init_can_bus()
        self.start_response_monitor()
    
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
        matches = re.finditer(r'(\w+)\s*=\s*(\d+)', content)
        for match in matches:
            signals[match.group(1)] = int(match.group(2))
        return signals
    
    def create_can_frame(self, signals):
        """Create CAN frame from exact output signals"""
        data = bytearray(8)
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
            self.wiper.process_operation()
            with open("wiper_output.txt", 'r') as f:
                content = f.read()
                print("\nGenerated Output:")
                print(content.strip())
                
                signals = self.extract_signals(content)
                print("\nSignals to transmit:", signals)
                
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
    
    def parse_response_frame(self, data):
        """Parse response CAN data into signals"""
        signals = {}
        signals['WiperStatus'] = data[0]  # 1=ready, 0=fault
        signals['wiperCurrentSpeed'] = data[1]  # 0=stopped, 1=slow, 2=fast
        signals['wiperCurrentPosition'] = data[2]  # 0-100%
        signals['currentWiperMode'] = data[3]  # Matches wiperMode
        signals['consumedPower'] = data[4]  # Watts (0-255)
        signals['isWiperBlocked'] = data[5]  # 0=no, 1=yes
        signals['blockageReason'] = data[6]  # 0=none, 1=obstacle, 2=motor_fault
        signals['hwError'] = data[7]  # 0=no error
        return signals
    
    def write_response_to_file(self, signals):
        """Write response signals to response_signals.txt with timestamp"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open("response_signals.txt", 'a') as f:
                f.write(f"\n--- Response at {timestamp} ---\n")
                for key, value in signals.items():
                    f.write(f"{key} = {value}\n")
                f.write("\n")
            print(f"Response signals written to response_signals.txt at {timestamp}")
        except Exception as e:
            print(f"Error writing to response_signals.txt: {e}")
    
    def monitor_responses(self):
        """Monitor CAN bus for response messages from slave"""
        print("Listening for response CAN messages...")
        try:
            while self.running:
                msg = self.bus.recv(timeout=1.0)
                if msg and msg.arbitration_id == self.RESPONSE_MSG_ID:
                    signals = self.parse_response_frame(msg.data)
                    print("\nReceived Response Signals:")
                    for key, value in signals.items():
                        print(f"{key}: {value}")
                    self.write_response_to_file(signals)
        except Exception as e:
            print(f"Response monitoring error: {e}")
    
    def start_response_monitor(self):
        """Start a thread to monitor response messages"""
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()
    
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
            while self.running:
                if self.file_changed():
                    print("\n=== Input Changed ===")
                    self.send_signals()
                time.sleep(0.3)
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        self.running = False
        if self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        if self.bus:
            self.bus.shutdown()
        os.system(f'sudo /sbin/ip link set {self.channel} down')
        print("Shutdown complete")

if __name__ == "__main__":
    master = CANWiperMaster()
    master.monitor()