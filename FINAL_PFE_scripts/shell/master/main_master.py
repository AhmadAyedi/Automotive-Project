import threading
from master_light import CANLightMaster
from master_window import CANWindowMaster
import time

def run_light_master():
    light_master = CANLightMaster("light_analysis.txt")
    light_master.monitor_file()

def run_window_master():
    window_master = CANWindowMaster("windows_analysis.txt")
    window_master.monitor_file()

if __name__ == "__main__":
    print("Starting both master controllers...")
    
    # Create threads for each master
    light_thread = threading.Thread(target=run_light_master, daemon=True)
    window_thread = threading.Thread(target=run_window_master, daemon=True)
    
    # Start the threads
    light_thread.start()
    window_thread.start()
    
    try:
        # Keep the main thread alive while the others run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down both masters...")
        # The daemon threads will exit when the main thread exits
        print("Shutdown complete")