import serial
import RPi.GPIO as GPIO

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
        if len(buffer) < 5:
            return None
        if buffer[0] != 0x00 or buffer[1] != 0x55:
            return None
            
        pid = buffer[2]
        id = pid & 0x3F
        data = buffer[3:-1]
        checksum = buffer[-1]
        
        frame = LINFrame(id, data)
        if frame.pid != pid or frame.checksum != checksum:
            return None
        return frame

class LINSlave:
    def __init__(self):
        self.LIN_MSG_ID = 0x01
        self.LED_PIN = 23
        self.serial = None
        self.lin_buffer = bytearray()
        self._initialize_lin()
        self._initialize_gpio()

    def _initialize_lin(self):
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

    def _initialize_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.LED_PIN, GPIO.OUT)
        GPIO.output(self.LED_PIN, GPIO.LOW)

    def process_frame(self):
        if self.serial and self.serial.in_waiting:
            byte = self.serial.read(1)
            if byte:
                self.lin_buffer.append(byte[0])
                if len(self.lin_buffer) >= 5:
                    if self.lin_buffer[0] == 0x00 and self.lin_buffer[1] == 0x55:
                        frame = LINFrame.from_bytes(self.lin_buffer)
                        if frame and frame.id == self.LIN_MSG_ID:
                            state = frame.data[0] if len(frame.data) > 0 else 0x00
                            GPIO.output(self.LED_PIN, GPIO.HIGH if state == 0x01 else GPIO.LOW)
                            print(f"Received LIN frame: LED {'ON' if state == 0x01 else 'OFF'}")
                            self.lin_buffer = bytearray()
                        else:
                            self.lin_buffer = bytearray()
                    else:
                        self.lin_buffer = bytearray()
                elif len(self.lin_buffer) > 10:
                    self.lin_buffer = bytearray()

    def shutdown(self):
        if self.serial:
            self.serial.close()
        GPIO.output(self.LED_PIN, GPIO.LOW)
        GPIO.cleanup()
        print("LIN receiver shutdown complete")