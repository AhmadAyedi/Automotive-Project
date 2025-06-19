import serial
import time
import RPi.GPIO as GPIO
import threading
import ldfparser
import os

class LINMaster:
    def __init__(self, ldf_path):
        self.running = True
        self.response_received = threading.Event()
        self.lock = threading.Lock()
        
        # Parse LDF file
        self.ldf = ldfparser.parse_ldf(ldf_path)
        self.baud_rate = int(float(self.ldf['LIN_protocol_version']['LIN_speed'].split()[0]) * 1000)
        
        # Get frame and signal information from LDF
        self.master_frame = self.ldf['frames']['Master_Frame']
        self.slave_frame = self.ldf['frames']['Slave_Frame']
        self.master_signal = self.ldf['signals']['MasterCommand']
        self.slave_signal = self.ldf['signals']['SlaveResponse']
        
        # Initialize GPIO and serial
        GPIO.setmode(GPIO.BCM)
        self.wakeup_pin = 4  # Default, can be configured in LDF
        GPIO.setup(self.wakeup_pin, GPIO.OUT)
        GPIO.output(self.wakeup_pin, GPIO.HIGH)
        
        self.ser = serial.Serial('/dev/serial0', baudrate=self.baud_rate, timeout=0.1)
        
        # Start response monitoring thread
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()
    
    def calculate_pid(self, frame_id):
        """Calculate LIN Protected Identifier from LDF frame"""
        if frame_id > 0x3F:
            raise ValueError("Frame ID must be 6 bits (0-63)")
        p0 = (frame_id ^ (frame_id >> 1) ^ (frame_id >> 2) ^ (frame_id >> 4)) & 0x01
        p1 = ~((frame_id >> 1) ^ (frame_id >> 3) ^ (frame_id >> 4) ^ (frame_id >> 5)) & 0x01
        return (frame_id & 0x3F) | (p0 << 6) | (p1 << 7)
    
    def calculate_checksum(self, pid, data):
        """Calculate LIN checksum (classic checksum)"""
        checksum = pid
        for byte in data:
            checksum += byte
            if checksum > 0xFF:
                checksum -= 0xFF
        return (0xFF - checksum) & 0xFF
    
    def send_break(self):
        """Send LIN break signal (13 bits of 0)"""
        self.ser.baudrate = self.baud_rate // 4
        self.ser.write(bytes([0x00]))  # Break byte
        self.ser.flush()
        time.sleep(0.001)
        self.ser.baudrate = self.baud_rate
    
    def wakeup_slave(self):
        """Pulse the wakeup pin to alert slave"""
        GPIO.output(self.wakeup_pin, GPIO.LOW)
        time.sleep(0.01)
        GPIO.output(self.wakeup_pin, GPIO.HIGH)
    
    def send_message(self, data=None):
        """Send data to slave using information from LDF"""
        try:
            if data is None:
                # Default data from LDF frame size (4 bytes in our case)
                data = bytes([0xDE, 0xAD, 0xBE, 0xEF])
            
            self.wakeup_slave()
            self.send_break()
            
            # Send sync byte
            self.ser.write(bytes([0x55]))
            
            # Send PID (from LDF frame ID)
            frame_id = self.master_frame['frame_id']
            pid = self.calculate_pid(frame_id)
            self.ser.write(bytes([pid]))
            
            # Send data
            self.ser.write(data)
            
            # Calculate and send checksum
            checksum = self.calculate_checksum(pid, data)
            self.ser.write(bytes([checksum]))
            self.ser.flush()
            
            # Display in hex format
            data_hex = ' '.join(f'{x:02X}' for x in data)
            print(f"Sent LIN frame: PID={pid:02X}, Data=[{data_hex}], Checksum={checksum:02X}")
            
        except Exception as e:
            print(f"Error sending LIN message: {e}")
    
    def monitor_responses(self):
        """Thread to monitor for responses from slave"""
        buffer = bytearray()
        slave_frame_id = self.slave_frame['frame_id']
        
        while self.running:
            if self.ser.in_waiting:
                byte = self.ser.read(1)
                if byte:
                    buffer += byte
                
                # Check for complete frame (break + sync + pid + data + checksum)
                expected_length = 3 + self.slave_frame['length'] + 1  # break(1) + sync(1) + pid(1) + data + checksum(1)
                if len(buffer) >= expected_length:
                    # Verify break and sync
                    if buffer[0] != 0x00 or buffer[1] != 0x55:
                        print("Invalid frame start")
                        buffer = buffer[1:]
                        continue
                    
                    pid = buffer[2]
                    frame_id = pid & 0x3F
                    
                    if frame_id != slave_frame_id:
                        print(f"Unexpected response frame ID: {frame_id:02X}")
                        buffer = buffer[3:]
                        continue
                    
                    # Get data bytes
                    data_start = 3
                    data_end = data_start + self.slave_frame['length']
                    data = buffer[data_start:data_end]
                    received_checksum = buffer[data_end]
                    
                    # Verify checksum
                    calc_checksum = self.calculate_checksum(pid, data)
                    if received_checksum != calc_checksum:
                        print(f"Checksum mismatch: received {received_checksum:02X}, calculated {calc_checksum:02X}")
                        buffer = buffer[expected_length:]
                        continue
                    
                    # Display the response
                    data_hex = ' '.join(f'{x:02X}' for x in data)
                    print(f"Received response: PID={pid:02X}, Data=[{data_hex}], Checksum={received_checksum:02X}")
                    self.response_received.set()
                    
                    # Clear processed frame from buffer
                    buffer = buffer[expected_length:]
            
            time.sleep(0.001)
    
    def run(self):
        """Main loop to send messages"""
        try:
            while self.running:
                self.response_received.clear()
                self.send_message()
                
                # Wait for response with timeout
                if self.response_received.wait(timeout=1.0):
                    print("Successful communication cycle")
                else:
                    print("Timeout waiting for response")
                
                time.sleep(2)  # Send every 2 seconds
                
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Cleanup resources"""
        self.running = False
        if hasattr(self, 'response_thread') and self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        if self.ser and self.ser.is_open:
            self.ser.close()
        GPIO.cleanup()
        print("Master shutdown complete")

if __name__ == "__main__":
    ldf_path = os.path.join(os.path.dirname(__file__), 'master_slave.ldf')
    master = LINMaster(ldf_path)
    master.run()