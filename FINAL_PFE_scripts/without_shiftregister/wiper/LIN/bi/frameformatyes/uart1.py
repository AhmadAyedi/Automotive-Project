#!/usr/bin/env python3
import time
import serial
import os
import re
import threading
from req import WiperSystem
from datetime import datetime

class UARTWiperMaster:
    def __init__(self):
        self.uart_port = '/dev/serial0'
        self.baudrate = 115200
        self.serial = None
        self.wiper = WiperSystem("input.txt", "wiper_output.txt")
        self.last_modified = 0
        self.running = True
        
        self.init_uart()
        self.start_response_monitor()
    
    def init_uart(self):
        try:
            self.serial = serial.Serial(
                port=self.uart_port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1
            )
            print("UART initialized")
        except Exception as e:
            print(f"UART init failed: {e}")
            raise
    
    def extract_signals(self, content):
        """Extract signals from wiper_output.txt including Wiper_Function_Enabled"""
        signals = {}
        matches = re.finditer(r'(\w+)\s*=\s*(\d+)', content)
        for match in matches:
            signals[match.group(1)] = int(match.group(2))
        return signals
    
    def create_uart_frame(self, signals):
        """Create UART frame from exact output signals"""
        # Format: <STX>wiperMode,wiperSpeed,wiperCycleCount,WiperIntermittent,wipingCycle,Wiper_Function_Enabled<ETX>
        frame = f"<STX>{signals.get('wiperMode', 0)}," \
                f"{signals.get('wiperSpeed', 1)}," \
                f"{signals.get('wiperCycleCount', 0)}," \
                f"{signals.get('WiperIntermittent', 0)}," \
                f"{signals.get('wipingCycle', 0)}," \
                f"{signals.get('Wiper_Function_Enabled', 1)}<ETX>"
        return frame.encode('utf-8')
    
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
                
                uart_data = self.create_uart_frame(signals)
                self.send_uart(uart_data)
                
        except Exception as e:
            print(f"Error: {e}")
    
    def send_uart(self, data):
        try:
            self.serial.write(data)
            print(f"Sent UART: {data.decode('utf-8')}")
        except Exception as e:
            print(f"UART send error: {e}")
    
    def parse_response_frame(self, data):
        """Parse response UART data into signals"""
        try:
            # Expected format: <STX>WiperStatus,wiperCurrentSpeed,wiperCurrentPosition,currentWiperMode,consumedPower,isWiperBlocked,blockageReason,hwError<ETX>
            decoded = data.decode('utf-8').strip()
            if not decoded.startswith("<STX>") or not decoded.endswith("<ETX>"):
                return None
                
            values = decoded[5:-5].split(',')
            if len(values) != 8:
                return None
                
            signals = {
                'WiperStatus': int(values[0]),
                'wiperCurrentSpeed': int(values[1]),
                'wiperCurrentPosition': int(values[2]),
                'currentWiperMode': int(values[3]),
                'consumedPower': int(values[4]),
                'isWiperBlocked': int(values[5]),
                'blockageReason': int(values[6]),
                'hwError': int(values[7])
            }
            return signals
        except Exception as e:
            print(f"Error parsing response: {e}")
            return None
    
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
        """Monitor UART for response messages from slave"""
        print("Listening for response UART messages...")
        buffer = ""
        try:
            while self.running:
                data = self.serial.read_until(b'<ETX>')
                if data:
                    signals = self.parse_response_frame(data)
                    if signals:
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
        if self.serial and self.serial.is_open:
            self.serial.close()
        print("Shutdown complete")

if __name__ == "__main__":
    master = UARTWiperMaster()
    master.monitor()