# -*- coding: utf-8 -*-
import serial
import time
from collections import OrderedDict
import os

# LIN Configuration
LIN_SYNC = 0x55
LIN_ID = 0x12
LIN_BAUD = 19200

SIGNALS = OrderedDict([
    ("Low Beam Headlights", 0x01),
    ("Hazard Lights", 0x02),
    ("Right Turn Signal", 0x04),
    ("Left Turn Signal", 0x08),
    ("High Beam Headlights Signal", 0x10),
    ("Parking left Signal", 0x20),
    ("Parking right", 0x40)
])

def print_signal_states(states):
    
    print("\n--- Current Signal States ---")
    max_len = max(len(name) for name in SIGNALS)
    for name, state in states.items():
        print(f"{name.ljust(max_len)} : {state}")
    print("----------------------------")

def send_lin_frame(ser, states):
    """Envoie une trame LIN"""
    lin_byte = sum(mask for name, mask in SIGNALS.items() if states.get(name) == "ON")
    checksum = (~(LIN_ID + lin_byte)) & 0xFF
    
    frame = bytes([LIN_SYNC, LIN_ID, lin_byte, checksum])
    
    try:
        ser.write(frame)
        print(f"Sent LIN: 0x{LIN_ID:02X} 0x{lin_byte:02X} 0x{checksum:02X}")
    except Exception as e:
        print(f"LIN Send Error: {e}")

def process_line(line, current_states, ser):
    
    if "| Status:" not in line:
        return
    
    try:
        parts = line.split("|")
        signal = parts[0].strip()
        if signal in SIGNALS:
            state = parts[1].split("Status:")[1].split("Mode:")[0].strip()
            current_states[signal] = state
            print_signal_states(current_states)
            send_lin_frame(ser, current_states)
    except Exception as e:
        print(f"Erreur traitement ligne: {e}")

def monitor_log_file(filename, current_states, ser):
    
    # Position initiale à la fin du fichier
    file = open(filename, 'r')
    file.seek(0, os.SEEK_END)
    
    while True:
        line = file.readline()
        if line:
            process_line(line, current_states, ser)
        else:
            time.sleep(0.1)

def main():
    # Initialisation port série
    try:
        ser = serial.Serial(
            port='/dev/serial0',
            baudrate=LIN_BAUD,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )
        print("Port serie ouvert - en attente des changements...")

        current_states = OrderedDict.fromkeys(SIGNALS, "OFF")
        
        try:
            monitor_log_file("lights_log.txt", current_states, ser)
        except KeyboardInterrupt:
            print("\nArret demande par lutilisateur")
        finally:
            ser.close()
            print("Port serie ferme")
            
    except Exception as e:
        print(f"Erreur initialisation: {e}")

if __name__ == "__main__":
    main()