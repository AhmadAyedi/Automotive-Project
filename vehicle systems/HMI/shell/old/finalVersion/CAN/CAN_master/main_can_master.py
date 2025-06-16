import threading
import os
import time
import importlib.util
import sys
from pathlib import Path

class MasterController:
    def __init__(self, module_name, script_path, config_file):
        self.module_name = module_name
        self.script_path = script_path
        self.config_file = config_file
        self.running = False
        self.thread = None
        self.master_instance = None
        
    def load_module(self):
        """Dynamically load the module from the script path"""
        spec = importlib.util.spec_from_file_location(self.module_name, self.script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[self.module_name] = module
        spec.loader.exec_module(module)
        return module
    
    def start(self):
        """Start the master in a separate thread"""
        if self.running:
            print(f"{self.module_name} is already running")
            return
            
        module = self.load_module()
        master_class = getattr(module, self.module_name)
        self.master_instance = master_class(self.config_file)
        
        self.running = True
        self.thread = threading.Thread(target=self.run_master, daemon=True)
        self.thread.start()
        print(f"Started {self.module_name} controller")
    
    def run_master(self):
        """Run the master's monitor_file method"""
        try:
            self.master_instance.monitor_file()
        except Exception as e:
            print(f"Error in {self.module_name}: {e}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the master instance"""
        if not self.running:
            print(f"{self.module_name} is not running")
            return
            
        if self.master_instance:
            self.master_instance.shutdown()
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        print(f"Stopped {self.module_name} controller")

def setup_can_interface():
    """Ensure CAN interface is properly set up"""
    try:
        # Bring down can0 if it's up
        os.system('sudo /sbin/ip link set can0 down 2>/dev/null')
        time.sleep(0.1)
        
        # Set up can0 interface
        os.system('sudo /sbin/ip link set can0 up type can bitrate 500000')
        time.sleep(0.1)
        
        print("CAN interface set up successfully")
    except Exception as e:
        print(f"Error setting up CAN interface: {e}")
        raise

def main():
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    
    # Initialize controllers for each master
    light_controller = MasterController(
        module_name="CANLightMaster",
        script_path=script_dir / "master_light.py",
        config_file=script_dir / "lights_analysis.txt"
    )
    
    window_controller = MasterController(
        module_name="CANWindowMaster",
        script_path=script_dir / "master_window.py",
        config_file=script_dir / "windows_analysis.txt"
    )
    
    # Set up CAN interface
    setup_can_interface()
    
    try:
        # Start both controllers
        light_controller.start()
        window_controller.start()
        
        print("Both master controllers are running. Press Ctrl+C to stop.")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
            # Check if either thread has died and restart if needed
            if not light_controller.running and light_controller.thread and not light_controller.thread.is_alive():
                print("Light master thread died, restarting...")
                light_controller.start()
                
            if not window_controller.running and window_controller.thread and not window_controller.thread.is_alive():
                print("Window master thread died, restarting...")
                window_controller.start()
                
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Clean up
        light_controller.stop()
        window_controller.stop()
        
        # Bring down CAN interface
        os.system('sudo /sbin/ip link set can0 down')
        print("CAN interface brought down")
        print("Main CAN slave shutdown complete")

if __name__ == "__main__":
    main()