import time
import serial

# Dictionary to map attributes to LIN frame IDs
ATTRIBUTE_IDS = {
    "FR_Door_State": 0x01,
    "RR_Door_State": 0x02,
    "FL_Door_State": 0x03,
    "RL_Door_State": 0x04,
    "Key_Zone": 0x10,
    "Key_Button": 0x11,
    "Inside": 0x20,
    "Outside": 0x21,
    "HornBeeping": 0x22,
    "FlashLight": 0x23,
    "Result": 0x30
}

# UART configuration for LIN communication
uart = serial.Serial(
    port='/dev/serial0',
    baudrate=19200,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

# Dictionary to store previous key states
previous_key_states = {
    "key_zone": None,
    "key_button": None,
    "HornBeeping": None,
    "FlashLight": None
}

# Dictionary to store previous valid states (for rollback on failure)
previous_valid_states = {
    "doors": {},
    "keys": {}
}

def calculate_checksum(identifier, data_bytes, enhanced_mode=True):
    checksum = sum(data_bytes)
    if enhanced_mode:
        checksum += identifier
    checksum = (~checksum) & 0xFF
    return checksum

def create_lin_frame(identifier, data_bytes, enhanced_mode=True):
    sync = 0x55
    checksum = calculate_checksum(identifier, data_bytes, enhanced_mode)
    frame = [0x00, sync, identifier] + data_bytes + [checksum]
    return frame

def send_lin_frame(frame):
    try:
        uart.write(bytes(frame))
        hex_frame = [hex(byte) for byte in frame]
        print(f"Sent LIN frame in HEX: {hex_frame}")
    except Exception as e:
        print(f"Error sending LIN frame: {e}")

def parse_state(state_str):
    """Convert state string to numerical value (1 or 0). Handle empty strings."""
    state_str = state_str.lower().strip()
    if state_str in ["unlocked", "open"]:
        return 1
    elif state_str in ["locked", "close"]:
        return 0
    return 0  # Default to 'closed/locked' if unknown or empty

def process_new_lines(lines):
    global previous_key_states, previous_valid_states
    
    # Temporary storage for current batch of states
    current_batch = {
        "doors": {},
        "keys": {},
        "result": None
    }
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if "Door |" in line:
            try:
                # Initialize default values
                state = 0       # Default to locked
                outside = 0     # Default to closed
                inside = 0      # Default to closed
                
                # Split into main parts
                parts = [part.strip() for part in line.split("|")]
                
                if len(parts) < 2:
                    print(f"Error: Line does not have sufficient parts: {parts}")
                    continue
                
                door_part = parts[0]  # e.g., "FL Door"
                details_part = parts[1]  # e.g., "State: Locked, Outside: open, Inside"
                
                # Split details by comma
                details = [detail.strip() for detail in details_part.split(",")]
                
                for detail in details:
                    if "State:" in detail:
                        state_str = detail.split(":")[1].strip()
                        state = parse_state(state_str)
                    elif "Outside:" in detail:
                        outside_str = detail.split(":")[1].strip()
                        outside = parse_state(outside_str)
                    elif "Inside:" in detail:
                        inside_str = detail.split(":")[1].strip()
                        inside = parse_state(inside_str)
                
                # Get the correct identifier
                door_type = door_part.split()[0]  # e.g., "FL"
                identifier = f"{door_type}_Door_State"
                
                # Store in current batch
                current_batch["doors"][door_type] = {
                    "state": state,
                    "outside": outside,
                    "inside": inside,
                    "identifier": ATTRIBUTE_IDS.get(identifier)
                }
                
            except Exception as e:
                print(f"Error processing door line: {line}, Error: {e}")
        
        elif "Key |" in line:
            try:
                # Parse key-related attributes
                current_key_zone = int(line.split("key_zone:")[1].split(",")[0].strip())
                current_key_button = int(line.split("key_button:")[1].split(",")[0].strip())
                current_horn_beeping = int(line.split("HornBeeping:")[1].split(",")[0].strip())
                current_flashlight = int(line.split("FlashLight:")[1].split(",")[0].strip())
                
                # Store in current batch
                current_batch["keys"] = {
                    "key_zone": current_key_zone,
                    "key_button": current_key_button,
                    "HornBeeping": current_horn_beeping,
                    "FlashLight": current_flashlight
                }
                
            except (IndexError, ValueError) as e:
                print(f"Error parsing key attributes: {e}")
        
        elif "RESULT:" in line:
            try:
                # Parse result
                result = line.split("RESULT:")[1].strip().lower()
                current_batch["result"] = result
                
                # Process the entire batch now that we have the result
                if result == "passed":
                    # Process doors
                    for door_type, door_data in current_batch["doors"].items():
                        if door_data["identifier"] is not None:
                            data_bytes = [door_data["state"], door_data["outside"], door_data["inside"]]
                            lin_frame = create_lin_frame(door_data["identifier"], data_bytes)
                            send_lin_frame(lin_frame)
                            # Update previous valid states
                            previous_valid_states["doors"][door_type] = door_data
                    
                    # Process keys
                    if current_batch["keys"]:
                        keys = current_batch["keys"]
                        
                        # For FlashLight specifically, don't send initial 0 value
                        if previous_key_states["FlashLight"] is None and keys["FlashLight"] == 0:
                            previous_key_states["FlashLight"] = 0
                        else:
                            if (previous_key_states["FlashLight"] is None or 
                                previous_key_states["FlashLight"] != keys["FlashLight"]):
                                send_lin_frame(create_lin_frame(ATTRIBUTE_IDS["FlashLight"], [keys["FlashLight"]]))
                                previous_key_states["FlashLight"] = keys["FlashLight"]
                                previous_valid_states["keys"]["FlashLight"] = keys["FlashLight"]
                        
                        # Other key attributes
                        if (previous_key_states["key_zone"] is None or 
                            previous_key_states["key_zone"] != keys["key_zone"]):
                            send_lin_frame(create_lin_frame(ATTRIBUTE_IDS["Key_Zone"], [keys["key_zone"]]))
                            previous_key_states["key_zone"] = keys["key_zone"]
                            previous_valid_states["keys"]["key_zone"] = keys["key_zone"]
                        
                        if (previous_key_states["key_button"] is None or 
                            previous_key_states["key_button"] != keys["key_button"]):
                            send_lin_frame(create_lin_frame(ATTRIBUTE_IDS["Key_Button"], [keys["key_button"]]))
                            previous_key_states["key_button"] = keys["key_button"]
                            previous_valid_states["keys"]["key_button"] = keys["key_button"]
                        
                        if (previous_key_states["HornBeeping"] is None or 
                            previous_key_states["HornBeeping"] != keys["HornBeeping"]):
                            send_lin_frame(create_lin_frame(ATTRIBUTE_IDS["HornBeeping"], [keys["HornBeeping"]]))
                            previous_key_states["HornBeeping"] = keys["HornBeeping"]
                            previous_valid_states["keys"]["HornBeeping"] = keys["HornBeeping"]
                
                elif result == "failed":
                    # Revert to previous valid states
                    print("Result is FAILED - reverting to previous valid states")
                    
                    # Revert doors
                    for door_type, door_data in previous_valid_states["doors"].items():
                        if door_data["identifier"] is not None:
                            data_bytes = [door_data["state"], door_data["outside"], door_data["inside"]]
                            lin_frame = create_lin_frame(door_data["identifier"], data_bytes)
                            send_lin_frame(lin_frame)
                    
                    # Revert keys
                    if "key_zone" in previous_valid_states["keys"]:
                        send_lin_frame(create_lin_frame(ATTRIBUTE_IDS["Key_Zone"], [previous_valid_states["keys"]["key_zone"]]))
                        previous_key_states["key_zone"] = previous_valid_states["keys"]["key_zone"]
                    
                    if "key_button" in previous_valid_states["keys"]:
                        send_lin_frame(create_lin_frame(ATTRIBUTE_IDS["Key_Button"], [previous_valid_states["keys"]["key_button"]]))
                        previous_key_states["key_button"] = previous_valid_states["keys"]["key_button"]
                    
                    if "HornBeeping" in previous_valid_states["keys"]:
                        send_lin_frame(create_lin_frame(ATTRIBUTE_IDS["HornBeeping"], [previous_valid_states["keys"]["HornBeeping"]]))
                        previous_key_states["HornBeeping"] = previous_valid_states["keys"]["HornBeeping"]
                    
                    if "FlashLight" in previous_valid_states["keys"]:
                        send_lin_frame(create_lin_frame(ATTRIBUTE_IDS["FlashLight"], [previous_valid_states["keys"]["FlashLight"]]))
                        previous_key_states["FlashLight"] = previous_valid_states["keys"]["FlashLight"]
                
                # Always send the result frame
                result_byte = 1 if current_batch["result"] == "passed" else 0
                send_lin_frame(create_lin_frame(ATTRIBUTE_IDS["Result"], [result_byte]))
                
                # Reset current batch
                current_batch = {
                    "doors": {},
                    "keys": {},
                    "result": None
                }
                
            except (IndexError, ValueError) as e:
                print(f"Error parsing result: {e}")

def tail_file(file_path):
    try:
        with open(file_path, 'r') as file:
            file.seek(0, 2)
            print("Monitoring file for updates...")
            while True:
                lines = file.readlines()
                if lines:
                    process_new_lines(lines)
                time.sleep(0.5)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        uart.close()

if _name_ == "_main_":
    file_path = "doors_analysis.txt"
    tail_file(file_path)