import threading
import os
import time
import importlib.util
import sys
from pathlib import Path
import logging

# Configure logging for the main controller
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('can_slave_controller.log'),
        logging.StreamHandler()
    ]
)

class SlaveController:
    def __init__(self, module_name, script_path):
        self.module_name = module_name
        self.script_path = script_path
        self.running = False
        self.thread = None
        self.slave_instance = None
        
    def load_module(self):
        """Dynamically load the module from the script path"""
        spec = importlib.util.spec_from_file_location(self.module_name, self.script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[self.module_name] = module
        spec.loader.exec_module(module)
        return module
    
    def start(self):
        """Start the slave in a separate thread"""
        if self.running:
            logging.info(f"{self.module_name} is already running")
            return
            
        try:
            module = self.load_module()
            slave_class = getattr(module, self.module_name)
            self.slave_instance = slave_class()
            
            self.running = True
            self.thread = threading.Thread(target=self.run_slave, daemon=True)
            self.thread.start()
            logging.info(f"Started {self.module_name} controller")
        except Exception as e:
            logging.error(f"Failed to start {self.module_name}: {e}")
            self.running = False
    
    def run_slave(self):
        """Run the slave's receive_messages method"""
        try:
            self.slave_instance.receive_messages()
        except Exception as e:
            logging.error(f"Error in {self.module_name}: {e}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the slave instance"""
        if not self.running:
            logging.info(f"{self.module_name} is not running")
            return
            
        if self.slave_instance:
            try:
                self.slave_instance.shutdown()
            except Exception as e:
                logging.error(f"Error shutting down {self.module_name}: {e}")
        
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        logging.info(f"Stopped {self.module_name} controller")

def setup_can_interface():
    """Ensure CAN interface is properly set up"""
    try:
        # Bring down can0 if it's up
        os.system('sudo /sbin/ip link set can0 down 2>/dev/null')
        time.sleep(0.1)
        
        # Set up can0 interface
        os.system('sudo /sbin/ip link set can0 up type can bitrate 500000')
        time.sleep(0.1)
        
        logging.info("CAN interface set up successfully")
    except Exception as e:
        logging.error(f"Error setting up CAN interface: {e}")
        raise

def main():
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    
    # Initialize controllers for each slave
    light_controller = SlaveController(
        module_name="CANLightSlave",
        script_path=script_dir / "slave_light.py"
    )
    
    window_controller = SlaveController(
        module_name="CANWindowSlave",
        script_path=script_dir / "slave_window.py"
    )
    
    # Set up CAN interface
    setup_can_interface()
    
    try:
        # Start both controllers
        light_controller.start()
        window_controller.start()
        
        logging.info("Both slave controllers are running. Press Ctrl+C to stop.")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
            # Check if either thread has died and restart if needed
            if not light_controller.running and light_controller.thread and not light_controller.thread.is_alive():
                logging.warning("Light slave thread died, restarting...")
                light_controller.start()
                
            if not window_controller.running and window_controller.thread and not window_controller.thread.is_alive():
                logging.warning("Window slave thread died, restarting...")
                window_controller.start()
                
    except KeyboardInterrupt:
        logging.info("\nShutting down...")
    finally:
        # Clean up
        light_controller.stop()
        window_controller.stop()
        
        # Bring down CAN interface
        os.system('sudo /sbin/ip link set can0 down')
        logging.info("CAN interface brought down")
        logging.info("Main CAN slave shutdown complete")

if __name__ == "__main__":
    main()