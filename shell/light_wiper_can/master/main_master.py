#!/usr/bin/env python3
import threading
from master_lighting import CANLightMaster
from master_wiper import CANWiperMaster
import time

class CANMasterSystem:
    def __init__(self):
        # Initialize both systems
        self.light_master = CANLightMaster("analysis_results.txt")
        self.wiper_master = CANWiperMaster()
        
        # Thread control
        self.running = True
    
    def start_lighting_system(self):
        """Run the lighting system monitoring"""
        self.light_master.monitor_file()
    
    def start_wiper_system(self):
        """Run the wiper system monitoring"""
        self.wiper_master.monitor()
    
    def run(self):
        """Start both systems in separate threads"""
        light_thread = threading.Thread(target=self.start_lighting_system, daemon=True)
        wiper_thread = threading.Thread(target=self.start_wiper_system, daemon=True)
        
        light_thread.start()
        wiper_thread.start()
        
        print("Both lighting and wiper systems are running...")
        print("Press Ctrl+C to stop")
        
        try:
            while self.running:
                # Keep the main thread alive
                light_thread.join(timeout=0.5)
                wiper_thread.join(timeout=0.5)
        except KeyboardInterrupt:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown of both systems"""
        self.running = False
        self.light_master.shutdown()
        self.wiper_master.shutdown()
        print("Both systems have been shut down")

if __name__ == "__main__":
    master_system = CANMasterSystem()
    master_system.run()