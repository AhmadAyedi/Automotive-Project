import can
import serial
import os
import RPi.GPIO as GPIO
import time

LED_PIN = 23
CAN_MSG_ID = 0x100
LIN_MSG_ID = 0x01

class LINFrame:
    def __init__(self, id, data):
        self.id = id & 0x3F
        self.data = data[:8]
        self.pid = self._calculate_pid()
        self.checksum = self._calculate_checksum()

    def _calculate_pid(self):
        id_bits = [self.id >> i & 1 for i in range(6)]
        p0 = id_bits[0] ^ id_bits[1] ^ id_bits[2] ^ id_bits[4]
        p1 = ~(id_bits[1] ^ id_bits[3] ^ id_bits[4] ^ id_bits[5]) & 1
        return (self.id | (p0 << 6) | (p1 << 7)) & 0xFF

    def _calculate_checksum(self):
        sum = self.pid
        for byte in self.data:
            sum += byte
            if sum > 0xFF:
                sum = (sum & 0xFF) + 1
        return (~sum) & 0xFF

    @staticmethod
    def from_bytes(buffer):
        # Minimum frame: Break(1) + Sync(1) + PID(1) + Data(1) + Checksum(1) = 5 bytes
        if len(buffer) < 5:
            return None
        if buffer[0] != 0x00 or buffer[1] != 0x55:
            return None
            
        pid = buffer[2]
        id = pid & 0x3F
        data = buffer[3:-1]  # Get all data bytes
        checksum = buffer[-1]
        
        frame = LINFrame(id, data)
        # Verify PID and checksum
        if frame.pid != pid or frame.checksum != checksum:
            return None
        return frame

class Slave:
    def __init__(self):
        # Initialize CAN
        try:
            os.system('sudo /sbin/ip link set can0 up type can bitrate 500000')
            self.can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
            print("CAN initialized")
        except Exception as e:
            print(f"CAN init failed: {e}")
            self.can_bus = None

        # Initialize LIN
        try:
            self.serial = serial.Serial(
                port='/dev/serial0',
                baudrate=19200,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=0.1
            )
            print("LIN initialized")
        except Exception as e:
            print(f"LIN init failed: {e}")
            self.serial = None

        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LED_PIN, GPIO.OUT)
        GPIO.output(LED_PIN, GPIO.LOW)
        self.lin_buffer = bytearray()
        self.running = True

    def process_frame(self, data, protocol):
        if not data:
            return
        state = data[0] if len(data) > 0 else 0x00
        GPIO.output(LED_PIN, GPIO.HIGH if state == 0x01 else GPIO.LOW)
        print(f"Received {protocol} frame: LED {'ON' if state == 0x01 else 'OFF'}")

    def monitor(self):
        print("Listening for CAN and LIN frames...")
        try:
            while self.running:
                # Check CAN
                if self.can_bus:
                    msg = self.can_bus.recv(timeout=0.1)
                    if msg and msg.arbitration_id == CAN_MSG_ID:
                        self.process_frame(msg.data, "CAN")

                # Check LIN
                if self.serial and self.serial.in_waiting:
                    byte = self.serial.read(1)
                    if byte:
                        self.lin_buffer.append(byte[0])
                        #print(f"Received byte: {hex(byte[0])}")  # Debug
                        
                        # Check for complete frame
                        if len(self.lin_buffer) >= 5:
                            # Verify break and sync fields
                            if self.lin_buffer[0] == 0x00 and self.lin_buffer[1] == 0x55:
                                frame = LINFrame.from_bytes(self.lin_buffer)
                                if frame and frame.id == LIN_MSG_ID:
                                    self.process_frame(frame.data, "LIN")
                                    self.lin_buffer = bytearray()
                                else:
                                    # Invalid frame, clear buffer
                                    self.lin_buffer = bytearray()
                            else:
                                # No valid break/sync, clear buffer
                                self.lin_buffer = bytearray()
                        elif len(self.lin_buffer) > 10:
                            # Buffer too long without valid frame, reset
                            self.lin_buffer = bytearray()

                time.sleep(0.01)
        except Exception as e:
            print(f"Monitoring error: {e}")

    def shutdown(self):
        self.running = False
        if self.can_bus:
            self.can_bus.shutdown()
            os.system('sudo /sbin/ip link set can0 down')
        if self.serial:
            self.serial.close()
        GPIO.output(LED_PIN, GPIO.LOW)
        GPIO.cleanup()
        print("Shutdown complete")

if __name__ == "__main__":
    try:
        slave = Slave()
        slave.monitor()
    except KeyboardInterrupt:
        print("Received keyboard interrupt")
    finally:
        slave.shutdown()