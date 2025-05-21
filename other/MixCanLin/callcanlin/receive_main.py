import time
from receive_can import CANSlave
from receive_lin import LINSlave

class ReceiveMain:
    def __init__(self):
        self.can_slave = CANSlave()
        self.lin_slave = LINSlave()
        self.running = True

    def monitor(self):
        print("Listening for CAN and LIN frames...")
        try:
            while self.running:
                self.can_slave.process_frame()
                self.lin_slave.process_frame()
                time.sleep(0.01)
        except Exception as e:
            print(f"Monitoring error: {e}")
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        self.running = False
        self.can_slave.shutdown()
        self.lin_slave.shutdown()
        print("Receiver shutdown complete")

if __name__ == "__main__":
    receiver = ReceiveMain()
    receiver.monitor()