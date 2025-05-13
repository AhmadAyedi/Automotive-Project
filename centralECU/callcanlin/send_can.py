import can
import os

class CANMaster:
    def __init__(self):
        self.CAN_MSG_ID = 0x100
        self.can_bus = None
        self._initialize_can()

    def _initialize_can(self):
        try:
            os.system('sudo /sbin/ip link set can0 up type can bitrate 500000')
            self.can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
            print("CAN initialized")
        except Exception as e:
            print(f"CAN init failed: {e}")
            self.can_bus = None

    def send_frame(self, led_state):
        if led_state not in ['ON', 'OFF']:
            print(f"Invalid ledState: {led_state}")
            return
        
        data = [0x01] if led_state == 'ON' else [0x00]
        
        try:
            if self.can_bus:
                msg = can.Message(
                    arbitration_id=self.CAN_MSG_ID,
                    data=data,
                    is_extended_id=False
                )
                self.can_bus.send(msg)
                print(f"Sent CAN frame: ID={hex(self.CAN_MSG_ID)}, Data={data}")
            else:
                print("CAN bus not initialized")
        except Exception as e:
            print(f"CAN send error: {e}")

    def shutdown(self):
        if self.can_bus:
            self.can_bus.shutdown()
            os.system('sudo /sbin/ip link set can0 down')
            print("CAN shutdown complete")