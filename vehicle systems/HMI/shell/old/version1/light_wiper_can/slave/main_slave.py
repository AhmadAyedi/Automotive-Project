#!/usr/bin/env python3
import threading
from slave_lighting import CANLightSlave
from slave_wiper import CANWiperSlave
import time

class CANSlaveSystem:
    def __init__(self):
        # Initialize both systems
        self.light_slave = CANLightSlave()
        self.wiper_slave = CANWiperSlave()
        
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
    
    def run(self):
        """Start both systems in separate threads"""
        light_thread = threading.Thread(target=self.start_lighting_system, daemon=True)
        wiper_thread = threading.Thread(target=self.start_wiper_system, daemon=True)
        
        light_thread.start()
        wiper_thread.start()
        
        print("Both lighting and wiper slave systems are running...")
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
        self.light_slave.shutdown()
        self.wiper_slave.shutdown()
        print("Both slave systems have been shut down")

if __name__ == "__main__":
    slave_system = CANSlaveSystem()
    slave_system.run()