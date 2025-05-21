import can
import time
import os

# CAN IDs for each window type
WINDOW_IDS = {
    "DR": 0x201,
    "PS": 0x202,
    "DRS": 0x203,
    "PRS": 0x204
}

def send_can_message(window, level):
    try:
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        msg = can.Message(
            arbitration_id=WINDOW_IDS[window],
            data=[level],
            is_extended_id=False
        )
        bus.send(msg)
        print(f"Sent: {window} - Level: {level}% (ID: {hex(WINDOW_IDS[window])}, Data: {level})")
        bus.shutdown()
    except Exception as e:
        print(f"Error sending CAN message: {e}")

def monitor_file(filename):
    print(f"Monitoring {filename} for new window status updates...")
    print("Add new lines to the file to send CAN messages")
    
    # Get initial file size
    last_size = os.path.getsize(filename)
    
    try:
        while True:
            current_size = os.path.getsize(filename)
            
            # Only check if file has grown
            if current_size > last_size:
                with open(filename, 'r') as f:
                    # Read just the new portion
                    f.seek(last_size)
                    new_content = f.read()
                    last_size = current_size
                    
                    # Process all new lines
                    lines = new_content.split('\n')
                    for line in lines:
                        if line.strip() and line.startswith("Window:"):
                            try:
                                parts = line.split('|')
                                window = parts[0].split(':')[1].strip()
                                level_part = parts[2].split(':')[1].strip()
                                level = int(level_part.replace('%', ''))
                                
                                if window in WINDOW_IDS and 0 <= level <= 100:
                                    send_can_message(window, level)
                                else:
                                    print(f"Ignoring unknown window/level: {line}")
                            except (IndexError, ValueError) as e:
                                print(f"Malformed line: {line} - Error: {e}")
            
            time.sleep(0.1)  # Check 10 times per second
            
    except KeyboardInterrupt:
        print("\nStopped monitoring")

if __name__ == "__main__":
    monitor_file("windows_analysis.txt")