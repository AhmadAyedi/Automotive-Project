import can
import os
import RPi.GPIO as GPIO

class CANSlave:
    def __init__(self):
        self.CAN_MSG_ID = 0x100
        self.LED_PIN = 23
        self.can_bus = None
        self._initialize_can()
        self._initialize_gpio()

    def _initialize_can(self):
        try:
            os.system('sudo /sbin/ip link set can0 up type can bitrate 500000')
            self.can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
            print("CAN initialized")
        except Exception as e:
            print(f"CAN init failed: {e}")
            self.can_bus = None

    def _initialize_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.LED_PIN, GPIO.OUT)
        GPIO.output(self.LED_PIN, GPIO.LOW)

    def process_frame(self):
        try:
            if self.can_bus:
                msg = self.can_bus.recv(timeout=0.1)
                if msg and msg.arbitration_id == self.CAN_MSG_ID:
                    state = msg.data[0] if len(msg.data) > 0 else 0x00
                    GPIO.output(self.LED_PIN, GPIO.HIGH if state == 0x01 else GPIO.LOW)
                    print(f"Received CAN frame: LED {'ON' if state == 0x01 else 'OFF'}")
        except Exception as e:
            print(f"CAN receive error: {e}")

    def shutdown(self):
        if self.can_bus:
            self.can_bus.shutdown()
            os.system('sudo /sbin/ip link set can0 down')
        GPIO.output(self.LED_PIN, GPIO.LOW)
        GPIO.cleanup()
        print("CAN receiver shutdown complete")