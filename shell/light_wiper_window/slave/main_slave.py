#!/usr/bin/env python3
import threading
from slave_lighting import CANLightSlave
from slave_wiper import CANWiperSlave
from slave_window import CANWindowSlave
import time

class CANSlaveSystem:
    def __init__(self):
        # Initialize all systems
        self.light_slave = CANLightSlave()
        self.wiper_slave = CANWiperSlave()
        self.window_slave = CANWindowSlave()
        
        # Thread control
        self.running = True
    
    def start_lighting_system(self):
        """Run the lighting system"""
        self.light_slave.receive_messages()
    
    def start_wiper_system(self):
        """Run the wiper system"""
        # The wiper slave has its own run loop
        while self.running:
            time.sleep(1)
    
    def start_window_system(self):
        """Run the window system"""
        self.window_slave.receive_messages()
    
    def run(self):
        """Start all systems in separate threads"""
        light_thread = threading.Thread(target=self.start_lighting_system, daemon=True)
        wiper_thread = threading.Thread(target=self.start_wiper_system, daemon=True)
        window_thread = threading.Thread(target=self.start_window_system, daemon=True)
        
        light_thread.start()
        wiper_thread.start()
        window_thread.start()
        
        print("Lighting, wiper, and window slave systems are running...")
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
        self.light_slave.shutdown()
        self.wiper_slave.shutdown()
        self.window_slave.shutdown()
        print("All slave systems have been shut down")

if __name__ == "__main__":
    slave_system = CANSlaveSystem()
    slave_system.run()