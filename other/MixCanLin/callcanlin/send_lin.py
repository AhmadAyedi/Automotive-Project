import serial
import time

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

    def to_bytes(self):
        break_field = b'\x00'
        sync_field = b'\x55'
        pid_field = bytes([self.pid])
        data_field = bytes(self.data)
        checksum_field = bytes([self.checksum])
        return break_field + sync_field + pid_field + data_field + checksum_field

class LINMaster:
    def __init__(self):
        self.LIN_MSG_ID = 0x01
        self.serial = None
        self._initialize_lin()

    def _initialize_lin(self):
        try:
            self.serial = serial.Serial(
                port='/dev/serial0',
                baudrate=19200,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1
            )
            print("LIN initialized")
        except Exception as e:
            print(f"LIN init failed: {e}")
            self.serial = None

    def send_frame(self, led_state):
        if led_state not in ['ON', 'OFF']:
            print(f"Invalid ledState: {led_state}")
            return
        
        data = [0x01] if led_state == 'ON' else [0x00]
        
        try:
            if self.serial:
                frame = LINFrame(id=self.LIN_MSG_ID, data=data)
                frame_bytes = frame.to_bytes()
                self.serial.write(frame_bytes)
                print(f"Sent LIN frame: {frame_bytes.hex(' ')}")
                time.sleep(0.1)
            else:
                print("LIN serial not initialized")
        except Exception as e:
            print(f"LIN send error: {e}")

    def shutdown(self):
        if self.serial:
            self.serial.close()
            print("LIN shutdown complete")