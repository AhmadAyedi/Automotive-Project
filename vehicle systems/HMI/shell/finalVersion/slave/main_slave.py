import threading
from slave_light import CANLightSlave
from slave_window import CANWindowSlave
import time

def run_light_slave():
    light_slave = CANLightSlave()
    light_slave.receive_messages()

def run_window_slave():
    window_slave = CANWindowSlave()
    window_slave.receive_messages()

if __name__ == "__main__":
    print("Starting both slave controllers...")
    
    # Create threads for each slave
    light_thread = threading.Thread(target=run_light_slave, daemon=True)
    window_thread = threading.Thread(target=run_window_slave, daemon=True)
    
    # Start the threads
    light_thread.start()
    window_thread.start()
    
    try:
        # Keep the main thread alive while the others run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down both slaves...")
        # The daemon threads will exit when the main thread exits
        print("Shutdown complete")