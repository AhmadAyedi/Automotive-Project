import time
import serial
import subprocess
import mysql.connector
from datetime import datetime
from mysql.connector import Error

# Database configuration
DB_CONFIG = {
    'host': '10.20.0.119',
    'user': 'monuserrs',
    'password': 'khalil',
    'database': 'khalil'
}

ATTRIBUTE_IDS = {
    "FR_Door_State": 0x01,
    "RR_Door_State": 0x02,
    "FL_Door_State": 0x03,
    "RL_Door_State": 0x04,
    "key_zone": 0x10,
    "key_button": 0x11,
    "Inside": 0x20,
    "Outside": 0x21,
    "HornBeeping": 0x22,
    "FlashLight": 0x23,
    "Result": 0x30
}

uart = serial.Serial(
    port='/dev/serial0',
    baudrate=19200,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

previous_key_states = {
    "key_zone": None,
    "key_button": None,
    "HornBeeping": None,
    "FlashLight": None
}

previous_valid_states = {
    "doors": {},
    "keys": {}
}

def create_db_connection():
    """Create and return a MySQL database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None

def init_db():
    """Initialize the database and create tables if they don't exist"""
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS protocol_data (id INT AUTO_INCREMENT PRIMARY KEY,event_id INT NOT NULL,message INT NOT NULL,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, UNIQUE KEY unique_event_id (event_id))")
            connection.commit()
            print("Database table initialized successfully")
        except Error as e:
            print(f"Error initializing database: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

def update_frame_event(event_id, message):
    """Update the existing record for this event_id or create if it doesn't exist"""
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            
            # Get current time with microsecond precision
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            # First try to update existing record with explicit timestamp
            update_query = "UPDATE protocol_data SET message = %s, timestamp = %s WHERE event_id = %s"
            cursor.execute(update_query, (message, current_time, event_id))
            
            # If no rows were updated, insert a new record
            if cursor.rowcount == 0:
                insert_query = "INSERT INTO protocol_data (event_id, message, timestamp) VALUES (%s, %s, %s)"
                cursor.execute(insert_query, (event_id, message, current_time))
            
            connection.commit()
            print(f"Received frame and database update - event_id: {event_id}, message: {message} at {current_time}")
        except Error as e:
            print(f"Error updating database: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

def calculate_checksum(identifier, data_bytes, enhanced_mode=True):
    checksum = sum(data_bytes)
    if enhanced_mode:
        checksum += identifier
    return (~checksum) & 0xFF

def create_lin_frame(identifier, data_bytes, enhanced_mode=True):
    sync = 0x55
    checksum = calculate_checksum(identifier, data_bytes, enhanced_mode)
    return [0x00, sync, identifier] + data_bytes + [checksum]

def send_lin_frame(frame, description=None):
    try:
        uart.write(bytes(frame))
        hex_frame = [hex(byte) for byte in frame]
        print(f"Sent LIN frame in HEX: {hex_frame}")
        
        # Database update logic
        frame_id = frame[2]  # Frame ID is the 3rd byte
        time.sleep(0.1)
        # For frame ID 1 (0x01)
        if frame_id == 0x01:
            event_id = 101
            # Check data bytes (positions 4 and 5 in frame)
            data1 = frame[4] if len(frame) > 4 else 0
            data2 = frame[5] if len(frame) > 5 else 0
            message = 1 if (data1 == 1 or data2 == 1) else 0
            update_frame_event(event_id, message)
        
        # For frame ID 2 (0x02)
        elif frame_id == 0x02:
            event_id = 102
            data1 = frame[4] if len(frame) > 4 else 0
            data2 = frame[5] if len(frame) > 5 else 0
            message = 1 if (data1 == 1 or data2 == 1) else 0
            update_frame_event(event_id, message)
        
        # For frame ID 3 (0x03)
        elif frame_id == 0x03:
            event_id = 106
            data1 = frame[4] if len(frame) > 4 else 0
            data2 = frame[5] if len(frame) > 5 else 0
            message = 1 if (data1 == 1 or data2 == 1) else 0
            update_frame_event(event_id, message)
        
        # For frame ID 4 (0x04)
        elif frame_id == 0x04:
            event_id = 107
            data1 = frame[4] if len(frame) > 4 else 0
            data2 = frame[5] if len(frame) > 5 else 0
            message = 1 if (data1 == 1 or data2 == 1) else 0
            update_frame_event(event_id, message)
        
        # For frame ID 30 (0x1E)
        elif frame_id == 0x1E:
            event_id = 30
            data = frame[3] if len(frame) > 3 else 0
            update_frame_event(event_id, data)
        
        if description:
            log_frame_to_file(description, frame)
    except Exception as e:
        print(f"Error sending LIN frame: {e}")

def log_frame_to_file(description, frame):
    with open("sent_frames_log.txt", "a") as log_file:
        if description:
            log_file.write(description + "\n")
        log_file.write(f"Frame HEX: {' '.join([hex(b) for b in frame])}\n\n")

def state_to_text(state_value, context=""):
    if state_value is None or state_value == "":
        return ""
    
    state_value = int(state_value)
    
    if context == "door_state":
        return "Unlocked" if state_value == 1 else "Locked"
    elif context == "door_contact":
        return "open" if state_value == 1 else "close"
    elif context == "result":
        return "PASSED" if state_value == 1 else "FAILED"
    else:
        return str(state_value)

def parse_state(state_str):
    if not state_str or state_str.strip() == "":
        return None
    state_str = state_str.lower().strip()
    if state_str in ["unlocked", "open", "1"]:
        return 1
    elif state_str in ["locked", "close", "0"]:
        return 0
    return None

def process_new_lines(lines):
    global previous_key_states, previous_valid_states

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
                state = outside = inside = None
                parts = [part.strip() for part in line.split("|")]
                if len(parts) < 2:
                    print(f"Error: Line does not have sufficient parts: {parts}")
                    continue

                door_part = parts[0]
                details = [detail.strip() for detail in parts[1].split(",")]

                for detail in details:
                    if "State:" in detail:
                        state = parse_state(detail.split(":")[1])
                    elif "Outside:" in detail:
                        outside = parse_state(detail.split(":")[1])
                    elif "Inside:" in detail:
                        inside = parse_state(detail.split(":")[1])

                door_type = door_part.split()[0]
                identifier = f"{door_type}_Door_State"

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
                print(f"Parsing key line: {line}")
                keys = {}
                parts = line.split("|", 1)[1].strip()
                for pair in parts.split(","):
                    if ":" in pair:
                        key, value = pair.strip().split(":")
                        keys[key.strip()] = int(value.strip())

                required_keys = ["key_zone", "key_button", "HornBeeping", "FlashLight"]
                if all(k in keys for k in required_keys):
                    current_batch["keys"] = {
                        "key_zone": keys["key_zone"],
                        "key_button": keys["key_button"],
                        "HornBeeping": keys["HornBeeping"],
                        "FlashLight": keys["FlashLight"]
                    }
                else:
                    missing = [k for k in required_keys if k not in keys]
                    print(f"Missing keys in Key line: {missing}")

            except Exception as e:
                print(f"Error parsing key attributes: {e}")

        elif "RESULT:" in line:
            try:
                result = line.split("RESULT:")[1].strip().lower()
                current_batch["result"] = result

                structured_log = []
                if current_batch["keys"]:
                    k = current_batch["keys"]
                    structured_log.append(
                        f"Key | key_zone: {k['key_zone']}, key_button: {k['key_button']}, "
                        f"FlashLight: {k['FlashLight']}, HornBeeping: {k['HornBeeping']}"
                    )

                for door in ["FR", "RR", "FL", "RL"]:
                    d = current_batch["doors"].get(door)
                    if d:
                        state = state_to_text(d['state'], "door_state")
                        outside = state_to_text(d['outside'], "door_contact") if d['outside'] is not None else ""
                        inside = state_to_text(d['inside'], "door_contact") if d['inside'] is not None else ""
                        if outside and inside:
                            inside = ""
                        structured_log.append(
                            f"{door} Door | State: {state}, "
                            f"Outside: {outside}, "
                            f"Inside: {inside}"
                        )
                    else:
                        structured_log.append(f"{door} Door | State: , Outside: , Inside: ")

                structured_log.append(f"RESULT: {state_to_text(1 if result == 'passed' else 0, 'result')}")
                description = "\n".join(structured_log)

                frames_to_send = []

                if result == "passed":
                    for door_type, door_data in current_batch["doors"].items():
                        if door_data["identifier"] is not None:
                            data_bytes = [
                                door_data["state"] if door_data["state"] is not None else 0,
                                door_data["outside"] if door_data["outside"] is not None else 0,
                                door_data["inside"] if door_data["inside"] is not None else 0
                            ]
                            lin_frame = create_lin_frame(door_data["identifier"], data_bytes)
                            frames_to_send.append((f"{door_type} Door", lin_frame))
                            previous_valid_states["doors"][door_type] = door_data

                    if current_batch["keys"]:
                        keys = current_batch["keys"]

                        if previous_key_states["FlashLight"] is None and keys["FlashLight"] == 0:
                            previous_key_states["FlashLight"] = 0
                        else:
                            if previous_key_states["FlashLight"] != keys["FlashLight"]:
                                frames_to_send.append(("FlashLight", create_lin_frame(ATTRIBUTE_IDS["FlashLight"], [keys["FlashLight"]])))
                                previous_key_states["FlashLight"] = keys["FlashLight"]
                                previous_valid_states["keys"]["FlashLight"] = keys["FlashLight"]

                        for key in ["key_zone", "key_button", "HornBeeping"]:
                            if previous_key_states[key] != keys[key]:
                                frames_to_send.append((key, create_lin_frame(ATTRIBUTE_IDS[key], [keys[key]])))
                                previous_key_states[key] = keys[key]
                                previous_valid_states["keys"][key] = keys[key]

                elif result == "failed":
                    print("Result is FAILED - reverting to previous valid states")
                    for door_type, door_data in previous_valid_states["doors"].items():
                        if door_data["identifier"] is not None:
                            data_bytes = [
                                door_data["state"] if door_data["state"] is not None else 0,
                                door_data["outside"] if door_data["outside"] is not None else 0,
                                door_data["inside"] if door_data["inside"] is not None else 0
                            ]
                            frames_to_send.append((f"{door_type} Door", create_lin_frame(door_data["identifier"], data_bytes)))

                    for key in previous_valid_states["keys"]:
                        frames_to_send.append((key, create_lin_frame(ATTRIBUTE_IDS[key], [previous_valid_states["keys"][key]])))
                        previous_key_states[key] = previous_valid_states["keys"][key]

                result_byte = 1 if result == "passed" else 0
                frames_to_send.append(("Result", create_lin_frame(ATTRIBUTE_IDS["Result"], [result_byte])))

                for frame_name, frame in frames_to_send:
                    send_lin_frame(frame)

                with open("sent_frames_log.txt", "a") as log_file:
                    log_file.write(description + "\n\n")

                current_batch = {"doors": {}, "keys": {}, "result": None}

            except Exception as e:
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

if __name__ == "__main__":
    # Initialize the database first
    init_db()
    
    # Start monitoring the file
    file_path = "/home/pi/vsomeip/PFE-2025/mockupDoors/src/HMI/doors_analysis.txt"
    tail_file(file_path)