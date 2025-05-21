import serial
import time
import RPi.GPIO as GPIO
from .constants import *
from .exceptions import *

class LINMaster:
    def __init__(self, serial_port=DEFAULT_SERIAL_PORT, baud_rate=DEFAULT_BAUD_RATE, 
                 wakeup_pin=DEFAULT_WAKEUP_PIN):
        """
        Initialize LIN Master controller
        
        Args:
            serial_port: Serial port device path
            baud_rate: Communication baud rate
            wakeup_pin: GPIO pin for slave wakeup signal
        """
        self.ser = serial.Serial(serial_port, baudrate=baud_rate, timeout=0)
        self.baud_rate = baud_rate
        self.sleep_time_per_bit = 1.0 / baud_rate
        self.wakeup_pin = wakeup_pin
        
        # Configure GPIO for slave wakeup
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.wakeup_pin, GPIO.OUT)
        GPIO.output(self.wakeup_pin, GPIO.HIGH)
        
    def send_break(self):
        """Send LIN break signal (13 bits of dominant + 1 bit recessive)"""
        # Switch to lower baud rate for break
        self.ser.baudrate = self.baud_rate // 4
        self.ser.write(bytes([BREAK_BYTE]))
        self.ser.flush()
        time.sleep(13 * (1.0 / (self.baud_rate // 4)))
        # Return to normal baud rate
        self.ser.baudrate = self.baud_rate
        
    @staticmethod
    def calculate_pid(frame_id):
        """
        Calculate Protected Identifier with parity bits
        
        Args:
            frame_id: 6-bit LIN frame ID (0-63)
            
        Returns:
            byte: PID with parity bits
        """
        if frame_id > 0x3F:
            raise ValueError("Frame ID must be 6 bits (0-63)")
            
        p0 = (frame_id ^ (frame_id >> 1) ^ (frame_id >> 2) ^ (frame_id >> 4)) & 0x01
        p1 = ~((frame_id >> 1) ^ (frame_id >> 3) ^ (frame_id >> 4) ^ (frame_id >> 5)) & 0x01
        return (frame_id & 0x3F) | (p0 << 6) | (p1 << 7)
    
    @staticmethod
    def calculate_checksum(pid, data):
        """
        Calculate LIN 2.0 classic checksum
        
        Args:
            pid: Protected Identifier byte
            data: Data bytes to include in checksum
            
        Returns:
            byte: Calculated checksum
        """
        checksum = pid
        for byte in data:
            checksum += byte
            if checksum > 0xFF:
                checksum -= 0xFF
        return (0xFF - checksum) & 0xFF
    
    def send_frame(self, frame_id, data):
        """
        Send complete LIN frame
        
        Args:
            frame_id: 6-bit LIN frame ID (0-63)
            data: Data bytes to send (max 8 bytes)
            
        Raises:
            ValueError: If frame_id or data is invalid
        """
        if frame_id > 0x3F:
            raise ValueError("Frame ID must be 6 bits (0-63)")
        if len(data) > MAX_FRAME_DATA_LENGTH:
            raise ValueError(f"Data length exceeds maximum of {MAX_FRAME_DATA_LENGTH} bytes")
        
        # Wake up slave
        self._wakeup_slave()
        
        # Send break
        self.send_break()
        
        # Send sync
        self.ser.write(bytes([SYNC_BYTE]))
        self.ser.flush()
        
        # Send PID
        pid = self.calculate_pid(frame_id)
        self.ser.write(bytes([pid]))
        self.ser.flush()
        
        # Send data if present
        if data:
            self.ser.write(data)
            self.ser.flush()
            
            # Send checksum
            checksum = self.calculate_checksum(pid, data)
            self.ser.write(bytes([checksum]))
            self.ser.flush()
        
        # Inter-byte space
        time.sleep(0.001)
        
    def _wakeup_slave(self, pulse_duration=0.01):
        """Send wakeup pulse to slave"""
        GPIO.output(self.wakeup_pin, GPIO.LOW)
        time.sleep(pulse_duration)
        GPIO.output(self.wakeup_pin, GPIO.HIGH)
        
    def close(self):
        """Clean up resources"""
        self.ser.close()
        GPIO.cleanup()