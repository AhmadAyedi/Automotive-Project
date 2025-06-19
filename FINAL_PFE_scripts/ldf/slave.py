import serial
import RPi.GPIO as GPIO
import time
import threading
import ldfparser
import os

class LINSlave:
    def __init__(self, ldf_path):
        self.running = True
        self.response_queue = []
        self.lock = threading.Lock()
        
        # Parse LDF file
        self.ldf = ldfparser.parse_ldf(ldf_path)
        self.baud_rate = int(float(self.ldf['LIN_protocol_version']['LIN_speed'].split()[0]) * 1000)
        
        # Get frame and signal information from LDF
        self.master_frame = self.ldf['frames']['Master_Frame']
        self.slave_frame = self.ldf['frames']['Slave_Frame']
        self.master_signal = self.ldf['signals']['MasterCommand']
        self.slave_signal = self.ldf['signals']['SlaveResponse']
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        self.wakeup_pin = 4  # Default, can be configured in LDF
        GPIO.setup(self.wakeup_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Initialize serial
        self.ser = serial.Serial('/dev/serial0', baudrate=self.baud_rate, timeout=0.1)
        
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
        self.ser.baudrate = self.baud_rate // 4
        self.ser.write(bytes([0x00]))
        self.ser.flush()
        time.sleep(0.001)
        self.ser.baudrate = self.baud_rate
    
    def queue_response(self, data=None):
        """Queue a response to be sent by the response thread"""
        with self.lock:
            if data is None:
                # Default response data (4 bytes in our case)
                data = bytes([0xCA, 0xFE, 0xBA, 0xBE])
            self.response_queue.append(data)
    
    def send_responses(self):
        """Thread to send responses from the queue"""
        slave_frame_id = self.slave_frame['frame_id']
        
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
                    self.ser.write(bytes([0x55]))
                    
                    # Send PID
                    pid = self.calculate_pid(slave_frame_id)
                    self.ser.write(bytes([pid]))
                    
                    # Send response data
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
        master_frame_id = self.master_frame['frame_id']
        expected_length = 3 + self.master_frame['length'] + 1  # break(1) + sync(1) + pid(1) + data + checksum(1)
        
        print("LIN Slave - Listening for frames...")
        
        try:
            while self.running:
                if self.ser.in_waiting:
                    byte = self.ser.read(1)
                    if byte:
                        buffer += byte
                    
                    # Check for complete frame
                    if len(buffer) >= expected_length:
                        # Verify break and sync
                        if buffer[0] != 0x00 or buffer[1] != 0x55:
                            print("Invalid frame start (missing break or sync)")
                            buffer = buffer[1:]
                            continue
                        
                        pid = buffer[2]
                        frame_id = pid & 0x3F
                        
                        if frame_id != master_frame_id:
                            print(f"Received frame for unexpected ID: {frame_id:02X}")
                            buffer = buffer[3:]
                            continue
                        
                        # Get data bytes
                        data_start = 3
                        data_end = data_start + self.master_frame['length']
                        data = buffer[data_start:data_end]
                        received_checksum = buffer[data_end]
                        
                        # Verify checksum
                        calc_checksum = self.calculate_checksum(pid, data)
                        if received_checksum != calc_checksum:
                            print(f"Checksum mismatch: received {received_checksum:02X}, calculated {calc_checksum:02X}")
                            buffer = buffer[expected_length:]
                            continue
                        
                        # Display the message
                        data_hex = ' '.join(f'{x:02X}' for x in data)
                        print(f"Received message: PID={pid:02X}, Data=[{data_hex}], Checksum={received_checksum:02X}")
                        
                        # Queue response
                        self.queue_response()
                        
                        # Clear processed frame from buffer
                        buffer = buffer[expected_length:]
                
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
    ldf_path = os.path.join(os.path.dirname(__file__), 'master_slave.ldf')
    slave = LINSlave(ldf_path)
    slave.receive_messages()