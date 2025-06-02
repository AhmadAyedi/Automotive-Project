import multiprocessing
from master_light import CANLightMaster
from master_window import CANWindowMaster
import time
import os
import watchdog.observers
import watchdog.events

class FileChangeHandler(watchdog.events.FileSystemEventHandler):
    def __init__(self, light_event, window_event):
        super().__init__()
        self.light_event = light_event
        self.window_event = window_event

    def on_modified(self, event):
        if not event.is_directory:
            if "light_analysis.txt" in event.src_path:
                self.light_event.set()
            elif "windows_analysis.txt" in event.src_path:
                self.window_event.set()

def run_light_master(light_event):
    light_master = CANLightMaster("light_analysis.txt")
    while True:
        light_event.wait()  # Wait for the event to be set
        light_master.monitor_file()
        light_event.clear()  # Reset the event for next time

def run_window_master(window_event):
    window_master = CANWindowMaster("windows_analysis.txt")
    while True:
        window_event.wait()  # Wait for the event to be set
        window_master.monitor_file()
        window_event.clear()  # Reset the event for next time

if __name__ == "__main__":
    print("Starting master controller with event-driven processes...")
    
    # Create events for inter-process communication
    light_event = multiprocessing.Event()
    window_event = multiprocessing.Event()
    
    # Create processes for each master
    light_process = multiprocessing.Process(
        target=run_light_master, 
        args=(light_event,),
        daemon=True
    )
    window_process = multiprocessing.Process(
        target=run_window_master, 
        args=(window_event,),
        daemon=True
    )
    
    # Start the processes
    light_process.start()
    window_process.start()
    
    # Set up file system observer
    event_handler = FileChangeHandler(light_event, window_event)
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    
    try:
        # Keep the main process alive while the others run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down master controller...")
        observer.stop()
        observer.join()
        print("Shutdown complete")