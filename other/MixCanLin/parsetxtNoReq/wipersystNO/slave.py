import can
import serial
import os
import RPi.GPIO as GPIO
import time
import threading

FRONT_LEDS = [23, 24, 25]  # Right to left
BACK_LEDS = [16, 20, 21]   # Right to left
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
        print(f"Parsing LIN buffer: {[hex(b) for b in buffer]}")
        if len(buffer) < 3 or 0x55 not in buffer:
            print("Invalid LIN frame: missing sync (0x55) or too short")
            return None
        sync_idx = buffer.index(0x55)
        if len(buffer) - sync_idx < 6:  # Need Sync, PID, 4 data, Checksum
            print("Incomplete LIN frame: not enough bytes after sync")
            return None
        pid = buffer[sync_idx + 1]
        id = pid & 0x3F
        data = buffer[sync_idx + 2:sync_idx + 6]
        if len(data) < 4:
            print("Invalid LIN frame: insufficient data bytes")
            return None
        checksum = buffer[sync_idx + 6]
        frame = LINFrame(id, data)
        if frame.pid != pid:
            print(f"PID mismatch: expected {hex(frame.pid)}, got {hex(pid)}")
            return None
        if frame.checksum != checksum:
            print(f"Checksum mismatch: expected {hex(frame.checksum)}, got {hex(checksum)}")
            return None
        print(f"Valid LIN frame: ID={hex(id)}, Data={data}")
        return frame

class Slave:
    def __init__(self):
        try:
            os.system('sudo /sbin/ip link set can0 up type can bitrate 500000')
            self.can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
            print("CAN initialized")
        except Exception as e:
            print(f"CAN init failed: {e}")
            self.can_bus = None

        try:
            self.serial = serial.Serial(
                port='/dev/serial0',
                baudrate=9600,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=0.1
            )
            print("LIN initialized")
        except Exception as e:
            print(f"LIN init failed: {e}")
            self.serial = None

        GPIO.setmode(GPIO.BCM)
        for pin in FRONT_LEDS + BACK_LEDS:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

        self.lin_buffer = []
        self.running = True
        self.stop_event = threading.Event()
        self.active_threads = []
        self.operation_lock = threading.Lock()
        self.last_byte_time = time.time()

    def wiper_sweep(self, leds, speed, stop_event):
        delay = {1: 0.3, 2: 0.2, 3: 0.1}[speed]
        for led in leds:
            if stop_event.is_set():
                return False
            GPIO.output(led, GPIO.HIGH)
            time.sleep(delay)
        for led in reversed(leds):
            if stop_event.is_set():
                return False
            GPIO.output(led, GPIO.LOW)
            time.sleep(delay)
        return True

    def activate_wiper(self, leds, speed, cycles):
        count = 0
        try:
            while (cycles == 0 or count < cycles) and not self.stop_event.is_set():
                if not self.wiper_sweep(leds, speed, self.stop_event):
                    break
                if cycles > 0:
                    count += 1
        finally:
            for led in leds:
                GPIO.output(led, GPIO.LOW)

    def stop_wipers(self):
        with self.operation_lock:
            self.stop_event.set()
            for t in self.active_threads:
                t.join(timeout=0.1)
            for pin in FRONT_LEDS + BACK_LEDS:
                GPIO.output(pin, GPIO.LOW)
            self.stop_event.clear()
            self.active_threads = []
            print("Wipers stopped")

    def process_frame(self, data, protocol):
        if len(data) < 3:
            print(f"Invalid {protocol} frame data: {data}")
            return
        wiper_status = data[0]
        cycles = data[1]
        speed = data[2]

        if wiper_status not in [1, 2, 3] or cycles not in [0, 1, 2] or speed not in [1, 2, 3]:
            print(f"Invalid frame parameters: status={wiper_status}, cycles={cycles}, speed={speed}")
            return

        status_str = ['front', 'back', 'both'][wiper_status-1]
        print(f"Received {protocol} frame: wiperStatus={status_str}, cycles={cycles}, speed={speed}")

        self.stop_wipers()
        if wiper_status in [1, 3]:
            thread = threading.Thread(
                target=self.activate_wiper,
                args=(FRONT_LEDS, speed, cycles),
                daemon=True
            )
            self.active_threads.append(thread)
            thread.start()
            print(f"Started front wiper: cycles={cycles}, speed={speed}")
        if wiper_status in [2, 3]:
            thread = threading.Thread(
                target=self.activate_wiper,
                args=(BACK_LEDS, speed, cycles),
                daemon=True
            )
            self.active_threads.append(thread)
            thread.start()
            print(f"Started back wiper: cycles={cycles}, speed={speed}")

    def monitor(self):
        print("Listening for CAN and LIN frames...")
        try:
            while self.running:
                if self.can_bus:
                    msg = self.can_bus.recv(timeout=0.1)
                    if msg and msg.arbitration_id == CAN_MSG_ID:
                        print(f"Received CAN frame: ID={hex(msg.arbitration_id)}, Data={list(msg.data)}")
                        self.process_frame(msg.data, "CAN")

                if self.serial and self.serial.in_waiting:
                    byte = self.serial.read(1)
                    if byte:
                        byte = byte[0]
                        print(f"Received LIN byte: {hex(byte)}")
                        self.lin_buffer.append(byte)
                        self.last_byte_time = time.time()
                        if 0x55 in self.lin_buffer and len(self.lin_buffer) >= 8:
                            frame = LINFrame.from_bytes(self.lin_buffer)
                            if frame and frame.id == LIN_MSG_ID:
                                self.process_frame(frame.data, "LIN")
                                self.lin_buffer = []
                            else:
                                self.lin_buffer = self.lin_buffer[1:]
                        elif len(self.lin_buffer) > 12:
                            print("LIN buffer overflow, resetting")
                            self.lin_buffer = []
                    else:
                        if self.lin_buffer and time.time() - self.last_byte_time > 0.5:
                            print("LIN buffer timeout, clearing")
                            self.lin_buffer = []

                time.sleep(0.01)
        except Exception as e:
            print(f"Monitoring error: {e}")

    def shutdown(self):
        self.running = False
        self.stop_wipers()
        if self.can_bus:
            self.can_bus.shutdown()
            os.system('sudo /sbin/ip link set can0 down')
        if self.serial:
            self.serial.close()
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