import os
import time
from send_can import CANMaster
from send_lin import LINMaster

class SendMain:
    def __init__(self):
        self.input_file = "input.txt"
        self.last_modified = 0
        self.can_master = None
        self.lin_master = None

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
                        if protocol == 'CAN':
                            if not self.can_master:
                                self.can_master = CANMaster()
                            self.can_master.send_frame(led_state)
                        elif protocol == 'LIN':
                            if not self.lin_master:
                                self.lin_master = LINMaster()
                            self.lin_master.send_frame(led_state)
                        else:
                            print(f"Unknown protocol: {protocol}")
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        if self.can_master:
            self.can_master.shutdown()
        if self.lin_master:
            self.lin_master.shutdown()
        print("Sender shutdown complete")

if __name__ == "__main__":
    sender = SendMain()
    sender.monitor()