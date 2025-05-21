import serial
import time
import RPi.GPIO as GPIO
from .constants import *
from .exceptions import *

class LINSlave:
    def __init__(self, serial_port=DEFAULT_SERIAL_PORT, baud_rate=DEFAULT_BAUD_RATE,
                 wakeup_pin=DEFAULT_WAKEUP_PIN):
        """
        Initialize LIN Slave controller
        
        Args:
            serial_port: Serial port device path
            baud_rate: Communication baud rate
            wakeup_pin: GPIO pin for wakeup signal
        """
        self.ser = serial.Serial(serial_port, baudrate=baud_rate, timeout=0.1)
        self.baud_rate = baud_rate
        self.wakeup_pin = wakeup_pin
        
        # Configure GPIO for wakeup
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.wakeup_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
    @staticmethod
    def verify_checksum(pid, data, received_checksum):
        """
        Verify LIN 2.0 classic checksum
        
        Args:
            pid: Protected Identifier byte
            data: Received data bytes
            received_checksum: Received checksum byte
            
        Returns:
            bool: True if checksum matches, False otherwise
        """
        calculated_checksum = pid
        for byte in data:
            calculated_checksum += byte
            if calculated_checksum > 0xFF:
                calculated_checksum -= 0xFF
        calculated_checksum = (0xFF - calculated_checksum) & 0xFF
        return calculated_checksum == received_checksum
    
    @staticmethod
    def parse_pid(pid_byte):
        """
        Extract frame ID and verify parity
        
        Args:
            pid_byte: Received PID byte
            
        Returns:
            int: Frame ID if parity is valid, None otherwise
        """
        frame_id = pid_byte & 0x3F
        p0 = (pid_byte >> 6) & 0x01
        p1 = (pid_byte >> 7) & 0x01
        
        # Verify parity
        calc_p0 = (frame_id ^ (frame_id >> 1) ^ (frame_id >> 2) ^ (frame_id >> 4)) & 0x01
        calc_p1 = ~((frame_id >> 1) ^ (frame_id >> 3) ^ (frame_id >> 4) ^ (frame_id >> 5)) & 0x01
        
        if p0 != calc_p0 or p1 != calc_p1:
            return None
        return frame_id
    
    def receive_frame(self, expected_data_length=3):
        """
        Receive and process LIN frame
        
        Args:
            expected_data_length: Expected number of data bytes
            
        Returns:
            tuple: (frame_id, data) if frame is valid, None otherwise
            
        Raises:
            LINError: If frame validation fails
        """
        # Wait for break
        while True:
            if self.ser.in_waiting:
                try:
                    byte = self.ser.read(1)
                    if byte == bytes([BREAK_BYTE]):
                        break
                except:
                    break
        
        # Read sync
        sync = self.ser.read(1)
        if sync != bytes([SYNC_BYTE]):
            raise LINSyncError("Invalid sync byte")
        
        # Read PID
        pid_byte = ord(self.ser.read(1))
        frame_id = self.parse_pid(pid_byte)
        if frame_id is None:
            raise LINParityError("PID parity check failed")
        
        # Read data
        data = self.ser.read(expected_data_length)
        if len(data) != expected_data_length:
            raise LINFrameError(f"Expected {expected_data_length} data bytes, got {len(data)}")
        
        # Read checksum
        checksum = ord(self.ser.read(1))
        
        # Verify checksum
        if not self.verify_checksum(pid_byte, data, checksum):
            raise LINChecksumError("Checksum verification failed")
        
        return (frame_id, data)
    
    def close(self):
        """Clean up resources"""
        self.ser.close()
        GPIO.cleanup()