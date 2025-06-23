import subprocess
import time
import sys
import mysql.connector
from mysql.connector import Error

# Database configuration
DB_CONFIG = {
    "host": "10.20.0.11",
    "user": "interface",
    "password": "khalil",
    "database": "khalil"
}

def get_active_systems():
    """Fetch systems with 'clicked' status from database"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT interface FROM interfaces WHERE status = 'clicked'"
        cursor.execute(query)
        active_systems = [row['interface'] for row in cursor]
        
        cursor.close()
        connection.close()
        
        return active_systems
        
    except Error as e:
        print(f"Database error: {e}")
        return []

def run_lighting_system():
    """Start the lighting system components"""
    try:
        print("\nStarting Lighting System...")
        # VSOMEIP application
        vsomeip_cmd = [
            "VSOMEIP_CONFIGURATION=../mockupLights.json",
            "VSOMEIP_APPLICATION_NAME=main",
            "./main"
        ]
        vsomeip_process = subprocess.Popen(
            " ".join(vsomeip_cmd),
            shell=True,
            cwd="/home/pi/vsomeip/PFE-2025/mockupLights/src/build"
        )
        
        time.sleep(2)
        
        # Python script
        python_process = subprocess.Popen(
            ["python", "master_light.py"],
            cwd="/home/pi/vsomeip/PFE-2025/mockupLights/src/CAN"
        )
        
        return vsomeip_process, python_process
        
    except Exception as e:
        print(f"Error starting Lighting System: {e}")
        return None, None

def run_window_system():
    """Start the window system components"""
    try:
        print("\nStarting Window System...")
        vsomeip_cmd = [
            "VSOMEIP_CONFIGURATION=../mockupWindow.json",
            "VSOMEIP_APPLICATION_NAME=main",
            "./main"
        ]
        vsomeip_process = subprocess.Popen(
            " ".join(vsomeip_cmd),
            shell=True,
            cwd="/home/pi/vsomeip/PFE-2025/mockupWindow/src/build"
        )
        
        time.sleep(2)
        
        python_process = subprocess.Popen(
            ["python", "master_window.py"],
            cwd="/home/pi/vsomeip/PFE-2025/mockupWindow/src/CAN"
        )
        
        return vsomeip_process, python_process
        
    except Exception as e:
        print(f"Error starting Window System: {e}")
        return None, None

def run_doors_system():
    """Start the doors system components"""
    try:
        print("\nStarting Doors System...")
        vsomeip_cmd = [
            "VSOMEIP_CONFIGURATION=../mockupDoors.json",
            "VSOMEIP_APPLICATION_NAME=main",
            "./main"
        ]
        vsomeip_process = subprocess.Popen(
            " ".join(vsomeip_cmd),
            shell=True,
            cwd="/home/pi/vsomeip/PFE-2025/mockupDoors/src/build"
        )
        
        time.sleep(2)
        
        python_process = subprocess.Popen(
            ["python", "master_doors.py"],
            cwd="/home/pi/vsomeip/PFE-2025/mockupDoors/src/LIN"
        )
        
        return vsomeip_process, python_process
        
    except Exception as e:
        print(f"Error starting Doors System: {e}")
        return None, None

def run_climate_system():
    """Start the climate system components"""
    try:
        print("\nStarting Climate System...")
        vsomeip_cmd = [
            "VSOMEIP_CONFIGURATION=../mockupClimate.json",
            "VSOMEIP_APPLICATION_NAME=main",
            "./main"
        ]
        vsomeip_process = subprocess.Popen(
            " ".join(vsomeip_cmd),
            shell=True,
            cwd="/home/pi/vsomeip/PFE-2025/mockupClimate/src/build"
        )
        
        return vsomeip_process, None
        
    except Exception as e:
        print(f"Error starting Climate System: {e}")
        return None, None

def monitor_systems():
    """Main function to monitor and launch systems based on database status"""
    active_processes = []
    
    try:
        while True:
            # Check database for active systems
            active_systems = get_active_systems()
            print(f"\nActive systems in database: {active_systems}")
            
            # Determine which systems need to be started
            systems_to_start = set(active_systems)
            currently_running = {proc[0] for proc in active_processes}
            
            # Start new systems
            for system in systems_to_start - currently_running:
                if system == "Lights":
                    vsomeip_proc, python_proc = run_lighting_system()
                    active_processes.append(("Lights", vsomeip_proc, python_proc))
                elif system == "Window":
                    vsomeip_proc, python_proc = run_window_system()
                    active_processes.append(("Window", vsomeip_proc, python_proc))
                elif system == "Doors":
                    vsomeip_proc, python_proc = run_doors_system()
                    active_processes.append(("Doors", vsomeip_proc, python_proc))
                elif system == "Climate":
                    vsomeip_proc, python_proc = run_climate_system()
                    active_processes.append(("Climate", vsomeip_proc, python_proc))
            
            # Stop systems that are no longer active
            for i, (system_name, vsomeip_proc, python_proc) in enumerate(active_processes[:]):
                if system_name not in active_systems:
                    print(f"\nStopping {system_name} system...")
                    if vsomeip_proc:
                        vsomeip_proc.terminate()
                    if python_proc:
                        python_proc.terminate()
                    active_processes.remove((system_name, vsomeip_proc, python_proc))
            
            time.sleep(5)  # Check database every 5 seconds
            
    except KeyboardInterrupt:
        print("\nShutting down all systems...")
        for _, vsomeip_proc, python_proc in active_processes:
            if vsomeip_proc:
                vsomeip_proc.terminate()
            if python_proc:
                python_proc.terminate()
        sys.exit(0)

if __name__ == "__main__":
    print("Starting System Launcher (Database-Driven)")
    print("Monitoring database for active systems...")
    print("Press Ctrl+C to exit")
    monitor_systems()