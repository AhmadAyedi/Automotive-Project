import serial
import time
import RPi.GPIO as GPIO
import threading

# LIN Constants
SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 19200
WAKEUP_PIN = 4
SYNC_BYTE = 0x55
BREAK_BYTE = 0x00

# Frame IDs
MASTER_FRAME_ID = 0x20
SLAVE_RESPONSE_ID = 0x21

class LINMaster:
    def __init__(self):
        self.running = True
        self.response_received = threading.Event()
        self.lock = threading.Lock()
        
        # Initialize GPIO and serial
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(WAKEUP_PIN, GPIO.OUT)
        GPIO.output(WAKEUP_PIN, GPIO.HIGH)
        
        self.ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0.1)
        
        # Start response monitoring thread
        self.response_thread = threading.Thread(target=self.monitor_responses, daemon=True)
        self.response_thread.start()
    
    def calculate_pid(self, frame_id):
        """Calculate LIN Protected Identifier"""
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
        self.ser.baudrate = BAUD_RATE // 4
        self.ser.write(bytes([BREAK_BYTE]))
        self.ser.flush()
        time.sleep(0.001)  # Short delay for break
        self.ser.baudrate = BAUD_RATE
    
    def wakeup_slave(self):
        """Pulse the wakeup pin to alert slave"""
        GPIO.output(WAKEUP_PIN, GPIO.LOW)
        time.sleep(0.01)
        GPIO.output(WAKEUP_PIN, GPIO.HIGH)
    
    def send_message(self):
        """Send 4-byte hex data to slave"""
        try:
            self.wakeup_slave()
            self.send_break()
            
            # Send sync byte
            self.ser.write(bytes([SYNC_BYTE]))
            
            # Send PID
            pid = self.calculate_pid(MASTER_FRAME_ID)
            self.ser.write(bytes([pid]))
            
            # Prepare 4-byte hex data (example: 0xDE, 0xAD, 0xBE, 0xEF)
            data = bytes([0xDE, 0xAD, 0xBE, 0xEF])
            
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
        print("Response monitor thread started")
        
        while self.running:
            if self.ser.in_waiting:
                byte = self.ser.read(1)
                if byte:
                    buffer += byte
                
                # Check for complete frame (break + sync + pid + 4 data + checksum = 8 bytes)
                if len(buffer) >= 8:
                    # Verify break and sync
                    if buffer[0] != BREAK_BYTE or buffer[1] != SYNC_BYTE:
                        print("Invalid frame start")
                        buffer = buffer[1:]  # Skip first byte and try again
                        continue
                    
                    pid = buffer[2]
                    frame_id = pid & 0x3F
                    
                    if frame_id != SLAVE_RESPONSE_ID:
                        print(f"Unexpected response frame ID: {frame_id:02X}")
                        buffer = buffer[3:]  # Skip this frame
                        continue
                    
                    # Get 4 bytes of data
                    data = buffer[3:7]
                    received_checksum = buffer[7]
                    
                    # Verify checksum
                    calc_checksum = self.calculate_checksum(pid, data)
                    if received_checksum != calc_checksum:
                        print(f"Checksum mismatch: received {received_checksum:02X}, calculated {calc_checksum:02X}")
                        buffer = buffer[8:]  # Skip this frame
                        continue
                    
                    # Display the response in hex
                    data_hex = ' '.join(f'{x:02X}' for x in data)
                    print(f"Received response: PID={pid:02X}, Data=[{data_hex}], Checksum={received_checksum:02X}")
                    self.response_received.set()
                    
                    # Clear processed frame from buffer
                    buffer = buffer[8:]
            
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
    master = LINMaster()
    master.run()