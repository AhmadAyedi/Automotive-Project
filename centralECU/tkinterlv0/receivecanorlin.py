import can
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

    @staticmethod
    def from_bytes(buffer):
        if len(buffer) < 3 or buffer[1] != 0x55:
            return None
        pid = buffer[2]
        id = pid & 0x3F
        data = buffer[3:-1] if len(buffer) > 3 else []
        if not data:
            return None
        checksum = buffer[-1]
        frame = LINFrame(id, data)
        if frame.pid != pid or frame.checksum != checksum:
            return None
        return frame

def slave_receiver():
    # Initialize CAN
    try:
        can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
    except Exception as e:
        print(f"Failed to initialize CAN: {e}")
        can_bus = None

    # Initialize LIN
    try:
        serial_port = serial.Serial(
            port='/dev/serial0',
            baudrate=19200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=0.1
        )
    except Exception as e:
        print(f"Failed to initialize LIN: {e}")
        serial_port = None

    lin_buffer = []
    try:
        print("Starting slave receiver (CAN and LIN)...")
        while True:
            # Check CAN
            if can_bus:
                msg = can_bus.recv(timeout=0.1)
                if msg:
                    print(f"Received CAN frame: ID={hex(msg.arbitration_id)}, Data={msg.data.hex()}")

            # Check LIN
            if serial_port and serial_port.in_waiting:
                byte = serial_port.read(1)
                if byte:
                    byte = byte[0]
                    lin_buffer.append(byte)
                    if byte == 0x00:
                        lin_buffer = [byte]
                    elif len(lin_buffer) >= 3 and lin_buffer[1] == 0x55:
                        if len(lin_buffer) >= 6:
                            frame = LINFrame.from_bytes(lin_buffer)
                            if frame:
                                print(f"Received LIN frame: ID={hex(frame.id)}, PID={hex(frame.pid)}, Data={frame.data}, Checksum={hex(frame.checksum)}")
                                lin_buffer = []
                            else:
                                lin_buffer = lin_buffer[1:]

            time.sleep(0.01)  # Prevent CPU overload

    except KeyboardInterrupt:
        print("Stopped by user")
    finally:
        if can_bus:
            can_bus.shutdown()
        if serial_port:
            serial_port.close()

if __name__ == "__main__":
    slave_receiver()