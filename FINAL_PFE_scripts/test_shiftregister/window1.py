# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk
import RPi.GPIO as GPIO
from time import sleep

# GPIO Pins for 74HC595
Latch = 13
Clock = 15
Serial_Input = 11
Clear = 7

# Initial LED status (all OFF)
LEDs_status = [0] * 40

# Mapping window names to LED indices (0-based)
windows = {
    "Driver Window": [11, 12, 13, 14],           # LED 12–15
    "Passenger Window": [27, 26, 25, 24],        # LED 28–25
    "Rear Driver Window": [2, 8, 9, 10],         # LED 3, 9–11
    "Rear Passenger Window": [15, 30, 29, 28]    # LED 16, 31, 30, 29
}

# GPIO Setup
def setup_gpio():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(Clock, GPIO.OUT)
    GPIO.setup(Latch, GPIO.OUT)
    GPIO.setup(Clear, GPIO.OUT)
    GPIO.setup(Serial_Input, GPIO.OUT)

def clear_register():
    GPIO.output(Clear, 0)
    GPIO.output(Clear, 1)

def shift_out(data):
    for state in data:
        GPIO.output(Serial_Input, state)
        GPIO.output(Clock, 0)
        GPIO.output(Clock, 1)
    GPIO.output(Latch, 0)
    GPIO.output(Latch, 1)

# Animate the change in LEDs with delay
def animate_led_change(window_name, target_level_percent):
    global LEDs_status
    leds = windows[window_name]

    # Determine how many LEDs to turn on based on level
    if target_level_percent < 25:
        target_on = 0
    elif target_level_percent < 50:
        target_on = 1
    elif target_level_percent < 75:
        target_on = 2
    elif target_level_percent < 100:
        target_on = 3
    else:
        target_on = 4

    # Determine current on count
    current_on = sum([LEDs_status[i] for i in leds])

    if target_on == current_on:
        return  # No change

    # Turning LEDs on
    if target_on > current_on:
        for i in range(current_on, target_on):
            LEDs_status[leds[i]] = 1
            shift_out(LEDs_status)
            sleep(1)
    # Turning LEDs off
    else:
        for i in range(current_on - 1, target_on - 1, -1):
            LEDs_status[leds[i]] = 0
            shift_out(LEDs_status)
            sleep(1)

# GUI Setup
def create_gui():
    root = tk.Tk()
    root.title("Vehicle Window LED Control")

    # Window selection
    window_label = tk.Label(root, text="Select Window:")
    window_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
    window_var = tk.StringVar()
    window_dropdown = ttk.Combobox(root, textvariable=window_var, values=list(windows.keys()), state="readonly")
    window_dropdown.grid(row=0, column=1, padx=5, pady=5)
    window_dropdown.current(0)

    # Level entry
    level_label = tk.Label(root, text="Level (%):")
    level_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
    level_var = tk.IntVar()
    level_entry = tk.Entry(root, textvariable=level_var)
    level_entry.grid(row=1, column=1, padx=5, pady=5)
    level_var.set(0)

    # Submit button
    def submit():
        window = window_var.get()
        try:
            level = int(level_var.get())
            if 0 <= level <= 100:
                animate_led_change(window, level)
            else:
                print("Enter a level between 0 and 100")
        except ValueError:
            print("Invalid input for level")

    submit_btn = tk.Button(root, text="Set Level", command=submit)
    submit_btn.grid(row=2, column=0, columnspan=2, pady=10)

    # Exit and cleanup
    def on_close():
        print("Cleaning up GPIO...")
        GPIO.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

# Main
if __name__ == "__main__":
    setup_gpio()
    clear_register()
    shift_out(LEDs_status)
    create_gui()
