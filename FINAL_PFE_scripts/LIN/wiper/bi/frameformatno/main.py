#!/usr/bin/env python3
import time
import os
import re
import threading
import serial
from req import WiperSystem
from datetime import datetime

class LINWiperMaster:
    def __init__(self):
        self.serial_port = '/dev/serial0'
        self.baudrate = 9600
        self.ser = None
        self.wiper = WiperSystem("input.txt", "wiper_output.txt")
        self.last_modified = 0
        self.running = True
        self.response_signals = {}
        
        # LIN frame IDs (PIDs)
        self.MASTER_REQUEST_PID = 0x30
        self.SLAVE_RESPONSE_PID = 0x31
        
        self.init_lin_interface()
        self.start_response_monitor()
    
    def init_lin_interface(self):
        """Initialize the serial interface for LIN communication"""
        try:
            # Enable UART and disable Bluetooth
            os.system('sudo raspi-config nonint do_serial 0')
            os.system('sudo dtoverlay disable-bt')
            os.system('sudo systemctl disable hciuart')
            
            # Ensure port permissions
            if os.path.exists(self.serial_port):
                os.system(f'sudo chmod 777 {self.serial_port}')
            
            self.ser = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1,
                write_timeout=1
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"LIN interface initialized on {self.serial_port}")
        except Exception as e:
            print(f"LIN init failed: {e}")
            raise
    
    def calculate_checksum(self, pid, data):
        """Calculate LIN classic checksum (for LIN 1.x)"""
        checksum = pid
        for byte in data:
            checksum += byte
            if checksum > 0xFF:
                checksum -= 0xFF
        checksum = (~checksum) & 0xFF
        return checksum
    
    def create_lin_frame(self, pid, data):
        """Create a complete LIN frame"""
        # Ensure data is exactly 8 bytes
        if len(data) < 8:
            data = data + bytes([0] * (8 - len(data)))
        elif len(data) > 8:
            data = data[:8]
            
        checksum = self.calculate_checksum(pid, data)
        
        # Build frame
        frame = bytearray()
        frame.append(0x00)  # Break
        frame.append(0x55)  # Sync
        frame.append(pid)   # PID
        frame.extend(data)  # Data
        frame.append(checksum)  # Checksum
        
        return frame
    
    def send_lin_frame(self, pid, data):
        """Send a LIN frame with proper timing"""
        frame = self.create_lin_frame(pid, data)
        try:
            # Clear buffers before sending
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            # Send with small delays between bytes
            for byte in frame:
                self.ser.write(bytes([byte]))
                time.sleep(0.001)
            
            print(f"Sent LIN frame: PID={hex(pid)}, Data={bytes(data).hex()}, Checksum={hex(frame[-1])}")
        except Exception as e:
            print(f"LIN send error: {e}")
    
    def extract_signals(self, content):
        """Extract signals from wiper_output.txt"""
        signals = {}
        matches = re.finditer(r'(\w+)\s*=\s*(\d+)', content)
        for match in matches:
            signals[match.group(1)] = int(match.group(2))
        return signals
    
    def create_request_data(self, signals):
        """Create LIN data payload from signals"""
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
        data[6] = signals.get('Wiper_Function_Enabled', 1)
        return data
    
    def send_signals(self):
        """Process input and send signals via LIN"""
        try:
            self.wiper.process_operation()
            with open("wiper_output.txt", 'r') as f:
                content = f.read()
                print("\nGenerated Output:")
                print(content.strip())
                
                signals = self.extract_signals(content)
                print("\nSignals to transmit:", signals)
                
                lin_data = self.create_request_data(signals)
                self.send_lin_frame(self.MASTER_REQUEST_PID, lin_data)
                
        except Exception as e:
            print(f"Error: {e}")
    
    def parse_response_data(self, data):
        """Parse response LIN data into signals"""
        signals = {}
        signals['WiperStatus'] = data[0]
        signals['wiperCurrentSpeed'] = data[1]
        signals['wiperCurrentPosition'] = data[2]
        signals['currentWiperMode'] = data[3]
        signals['consumedPower'] = data[4]
        signals['isWiperBlocked'] = data[5]
        signals['blockageReason'] = data[6]
        signals['hwError'] = data[7]
        return signals
    
    def write_response_to_file(self, signals):
        """Write response signals to file"""
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
        """Monitor LIN bus for responses"""
        print("Listening for LIN response messages...")
        buffer = bytearray()
        
        try:
            while self.running:
                # Read available data
                data = self.ser.read(self.ser.in_waiting or 1)
                if data:
                    buffer.extend(data)
                    
                    # Process complete frames in buffer
                    while len(buffer) >= 11:  # sync + pid + 8 data + checksum
                        # Find sync byte
                        sync_pos = -1
                        for i, byte in enumerate(buffer):
                            if byte == 0x55:
                                sync_pos = i
                                break
                        
                        if sync_pos == -1:
                            buffer.clear()
                            continue
                        
                        # Check if we have a complete frame
                        if len(buffer) >= sync_pos + 11:
                            frame = buffer[sync_pos:sync_pos+11]
                            pid = frame[1]
                            data = frame[2:10]
                            checksum = frame[10]
                            
                            # Verify checksum
                            calculated = self.calculate_checksum(pid, data)
                            if checksum == calculated:
                                if pid == self.SLAVE_RESPONSE_PID:
                                    signals = self.parse_response_data(data)
                                    print("\nReceived Response Signals:")
                                    for key, value in signals.items():
                                        print(f"{key}: {value}")
                                    self.write_response_to_file(signals)
                                buffer = buffer[sync_pos+11:]
                            else:
                                print(f"Checksum error: expected {hex(calculated)}, got {hex(checksum)}")
                                buffer = buffer[sync_pos+1:]
                        else:
                            break
                
                time.sleep(0.01)
        except Exception as e:
            print(f"Response monitoring error: {e}")
    
    def start_response_monitor(self):
        """Start response monitoring thread"""
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
        if hasattr(self, 'response_thread') and self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        if self.ser and self.ser.is_open:
            self.ser.close()
        print("Shutdown complete")

if __name__ == "__main__":
    master = LINWiperMaster()
    try:
        master.monitor()
    except KeyboardInterrupt:
        master.shutdown()