import serial
import RPi.GPIO as GPIO
import time
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

class LINSlave:
    def __init__(self):
        self.running = True
        self.response_queue = []
        self.lock = threading.Lock()
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(WAKEUP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Initialize serial
        self.ser = serial.Serial(SERIAL_PORT, baudrate=BAUD_RATE, timeout=0.1)
        
        # Start response sending thread
        self.response_thread = threading.Thread(target=self.send_responses, daemon=True)
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
    
    def queue_response(self):
        """Queue a response to be sent by the response thread"""
        with self.lock:
            # Example 4-byte response: 0xCA, 0xFE, 0xBA, 0xBE
            self.response_queue.append(bytes([0xCA, 0xFE, 0xBA, 0xBE]))
    
    def send_responses(self):
        """Thread to send responses from the queue"""
        print("Response sender thread started")
        
        while self.running:
            with self.lock:
                if self.response_queue:
                    response_data = self.response_queue.pop(0)
                else:
                    response_data = None
            
            if response_data:
                try:
                    self.send_break()
                    
                    # Send sync byte
                    self.ser.write(bytes([SYNC_BYTE]))
                    
                    # Send PID
                    pid = self.calculate_pid(SLAVE_RESPONSE_ID)
                    self.ser.write(bytes([pid]))
                    
                    # Send 4-byte response data
                    self.ser.write(response_data)
                    
                    # Calculate and send checksum
                    checksum = self.calculate_checksum(pid, response_data)
                    self.ser.write(bytes([checksum]))
                    self.ser.flush()
                    
                    # Display in hex format
                    data_hex = ' '.join(f'{x:02X}' for x in response_data)
                    print(f"Sent response frame: PID={pid:02X}, Data=[{data_hex}], Checksum={checksum:02X}")
                
                except Exception as e:
                    print(f"Error sending LIN response: {e}")
            
            time.sleep(0.001)
    
    def receive_messages(self):
        """Main thread to receive and process LIN messages"""
        buffer = bytearray()
        print("LIN Slave - Listening for frames...")
        
        try:
            while self.running:
                if self.ser.in_waiting:
                    byte = self.ser.read(1)
                    if byte:
                        buffer += byte
                    
                    # Check for complete frame (break + sync + pid + 4 data + checksum = 8 bytes)
                    if len(buffer) >= 8:
                        # Verify break and sync
                        if buffer[0] != BREAK_BYTE or buffer[1] != SYNC_BYTE:
                            print("Invalid frame start (missing break or sync)")
                            buffer = buffer[1:]  # Skip first byte and try again
                            continue
                        
                        pid = buffer[2]
                        frame_id = pid & 0x3F
                        
                        if frame_id != MASTER_FRAME_ID:
                            print(f"Received frame for unexpected ID: {frame_id:02X}")
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
                        
                        # Display the message in hex
                        data_hex = ' '.join(f'{x:02X}' for x in data)
                        print(f"Received message: PID={pid:02X}, Data=[{data_hex}], Checksum={received_checksum:02X}")
                        
                        # Queue response
                        self.queue_response()
                        
                        # Clear processed frame from buffer
                        buffer = buffer[8:]
                
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            print("Received keyboard interrupt")
        except Exception as e:
            print(f"Error in receive_messages: {e}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Cleanup resources"""
        self.running = False
        if hasattr(self, 'response_thread') and self.response_thread.is_alive():
            self.response_thread.join(timeout=0.5)
        if self.ser:
            self.ser.close()
        GPIO.cleanup()
        print("Slave shutdown complete")

if __name__ == "__main__":
    slave = LINSlave()
    slave.receive_messages()