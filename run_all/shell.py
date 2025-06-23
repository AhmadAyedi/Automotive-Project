import subprocess
import time
import sys

def run_lighting_system():
    try:
        print("\nStarting Lighting System...")
        # First command: VSOMEIP application
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
        
        time.sleep(2)  # Give it a moment to start
        
        # Second command: Python script
        python_process = subprocess.Popen(
            ["python", "master_light.py"],
            cwd="/home/pi/vsomeip/PFE-2025/mockupLights/src/CAN"
        )
        
        return vsomeip_process, python_process
        
    except Exception as e:
        print(f"Error starting Lighting System: {e}")
        return None, None

def run_window_system():
    try:
        print("\nStarting Window System...")
        # First command: VSOMEIP application
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
        
        # Second command: Python script
        python_process = subprocess.Popen(
            ["python", "master_window.py"],
            cwd="/home/pi/vsomeip/PFE-2025/mockupWindow/src/CAN"
        )
        
        return vsomeip_process, python_process
        
    except Exception as e:
        print(f"Error starting Window System: {e}")
        return None, None

def run_doors_system():
    try:
        print("\nStarting Doors System...")
        # First command: VSOMEIP application
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
        
        # Second command: Python script
        python_process = subprocess.Popen(
            ["python", "master_doors.py"],
            cwd="/home/pi/vsomeip/PFE-2025/mockupDoors/src/LIN"
        )
        
        return vsomeip_process, python_process
        
    except Exception as e:
        print(f"Error starting Doors System: {e}")
        return None, None

def run_climate_system():
    try:
        print("\nStarting Climate System...")
        # Only VSOMEIP application for climate
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

def show_menu():
    print("\n" + "="*40)
    print("SYSTEM LAUNCHER MENU".center(40))
    print("="*40)
    print("1. Lighting System")
    print("2. Window System")
    print("3. Doors System")
    print("4. Climate System")
    print("5. Quit")
    print("="*40)
    
    while True:
        choice = input("Please select a system to run (1-5): ")
        if choice in ['1', '2', '3', '4', '5']:
            return choice
        print("Invalid input. Please enter a number between 1 and 5.")

def main():
    while True:
        choice = show_menu()
        
        if choice == '5':
            print("\nExiting System Launcher...")
            sys.exit(0)
            
        processes = []
        
        try:
            if choice == '1':
                vsomeip_proc, python_proc = run_lighting_system()
            elif choice == '2':
                vsomeip_proc, python_proc = run_window_system()
            elif choice == '3':
                vsomeip_proc, python_proc = run_doors_system()
            elif choice == '4':
                vsomeip_proc, python_proc = run_climate_system()
            
            if vsomeip_proc:
                processes.append(vsomeip_proc)
            if python_proc:
                processes.append(python_proc)
            
            print("\nSystem started successfully. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nStopping system...")
            for proc in processes:
                if proc:
                    proc.terminate()
            time.sleep(1)
            
        except Exception as e:
            print(f"\nError: {e}")
            for proc in processes:
                if proc:
                    proc.terminate()

if __name__ == "__main__":
    main()