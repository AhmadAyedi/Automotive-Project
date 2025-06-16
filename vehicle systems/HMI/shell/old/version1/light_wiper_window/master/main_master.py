#!/usr/bin/env python3
import threading
from master_lighting import CANLightMaster
from master_wiper import CANWiperMaster
from master_window import CANWindowMaster
import time

class CANMasterSystem:
    def __init__(self):
        # Initialize all systems
        self.light_master = CANLightMaster("analysis_results.txt")
        self.wiper_master = CANWiperMaster()
        self.window_master = CANWindowMaster("windows_analysis.txt")
        
        # Thread control
        self.running = True
    
    def start_lighting_system(self):
        """Run the lighting system monitoring"""
        self.light_master.monitor_file()
    
    def start_wiper_system(self):
        """Run the wiper system monitoring"""
        self.wiper_master.monitor()
    
    def start_window_system(self):
        """Run the window system monitoring"""
        self.window_master.monitor_file()
    
    def run(self):
        """Start all systems in separate threads"""
        light_thread = threading.Thread(target=self.start_lighting_system, daemon=True)
        wiper_thread = threading.Thread(target=self.start_wiper_system, daemon=True)
        window_thread = threading.Thread(target=self.start_window_system, daemon=True)
        
        light_thread.start()
        wiper_thread.start()
        window_thread.start()
        
        print("Lighting, wiper, and window systems are running...")
        print("Press Ctrl+C to stop")
        
        try:
            while self.running:
                # Keep the main thread alive
                light_thread.join(timeout=0.5)
                wiper_thread.join(timeout=0.5)
                window_thread.join(timeout=0.5)
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown of all systems"""
        self.running = False
        self.light_master.shutdown()
        self.wiper_master.shutdown()
        self.window_master.shutdown()
        print("All systems have been shut down")

if __name__ == "__main__":
    master_system = CANMasterSystem()
    master_system.run()