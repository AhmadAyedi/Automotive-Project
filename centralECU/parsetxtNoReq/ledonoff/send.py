import can
import serial
import time
import os

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

class Master:
    def __init__(self):
        self.input_file = "input.txt"
        self.last_modified = 0
        self.CAN_MSG_ID = 0x100
        self.LIN_MSG_ID = 0x01

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
                timeout=1
            )
            print("LIN initialized")
        except Exception as e:
            print(f"LIN init failed: {e}")
            self.serial = None

    def parse_input(self):
        try:
            with open(self.input_file, 'r') as f:
                content = f.read()
                led_state = None
                protocol = None
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('ledState'):
                        led_state = line.split('=')[1].strip().strip("'")
                    elif line.startswith('protocol'):
                        protocol = line.split('=')[1].strip().strip("'")
                return led_state, protocol
        except Exception as e:
            print(f"Error reading input file: {e}")
            return None, None

    def send_frame(self, led_state, protocol):
        if led_state not in ['ON', 'OFF'] or protocol not in ['CAN', 'LIN']:
            print(f"Invalid input: ledState={led_state}, protocol={protocol}")
            return
        
        data = [0x01] if led_state == 'ON' else [0x00]
        
        try:
            if protocol == 'CAN' and self.can_bus:
                msg = can.Message(
                    arbitration_id=self.CAN_MSG_ID,
                    data=data,
                    is_extended_id=False
                )
                self.can_bus.send(msg)
                print(f"Sent CAN frame: ID={hex(self.CAN_MSG_ID)}, Data={data}")
            elif protocol == 'LIN' and self.serial:
                frame = LINFrame(id=self.LIN_MSG_ID, data=data)
                frame_bytes = frame.to_bytes()
                self.serial.write(frame_bytes)
                print(f"Sent LIN frame: {frame_bytes.hex(' ')}")
                time.sleep(0.1)  # Small delay between LIN frames
            else:
                print(f"Cannot send: protocol={protocol}, CAN={bool(self.can_bus)}, LIN={bool(self.serial)}")
        except Exception as e:
            print(f"Send error: {e}")

    def file_changed(self):
        try:
            mod_time = os.path.getmtime(self.input_file)
            if mod_time != self.last_modified:
                self.last_modified = mod_time
                return True
            return False
        except:
            return False

    def monitor(self):
        print(f"Monitoring {self.input_file}...")
        try:
            while True:
                if self.file_changed():
                    print("\n=== Input Changed ===")
                    led_state, protocol = self.parse_input()
                    if led_state and protocol:
                        print(f"Parsed: ledState={led_state}, protocol={protocol}")
                        self.send_frame(led_state, protocol)
                time.sleep(0.5)  # Reduced sleep time for more responsive monitoring
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        if self.can_bus:
            self.can_bus.shutdown()
            os.system('sudo /sbin/ip link set can0 down')
        if self.serial:
            self.serial.close()
        print("Shutdown complete")

if __name__ == "__main__":
    master = Master()
    master.monitor()