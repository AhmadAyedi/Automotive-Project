import multiprocessing
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
    
    # Create processes for each slave
    light_process = multiprocessing.Process(
        target=run_light_slave,
        daemon=True
    )
    window_process = multiprocessing.Process(
        target=run_window_slave,
        daemon=True
    )
    
    # Start the processes
    light_process.start()
    window_process.start()
    
    try:
        # Keep the main process alive while the others run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down both slaves...")
        # The daemon processes will exit when the main process exits
        print("Shutdown complete")