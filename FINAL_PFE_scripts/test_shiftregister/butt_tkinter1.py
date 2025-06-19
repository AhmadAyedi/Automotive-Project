import tkinter as tk
from functools import partial
import RPi.GPIO as GPIO
from time import sleep

# GPIO Pins for 74HC595
Latch = 13
Clock = 15
Serial_Input = 11
Clear = 7

# Initial LED status (all OFF)
LEDs_status = [0] * 40

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

# Toggle LED and update shift register
def toggle_led(index, button):
    LEDs_status[index] = 1 - LEDs_status[index]  # Toggle 0/1
    button.config(bg="green" if LEDs_status[index] else "red")
    shift_out(LEDs_status)

# GUI Setup
def create_gui():
    root = tk.Tk()
    root.title("LED Controller - 40 LEDs")

    buttons = []
    for i in range(40):
        btn = tk.Button(root, text=f"LED {i+1}", width=10, height=2,
                        bg="red", command=partial(toggle_led, i, None))
        btn.grid(row=i//8, column=i%8, padx=5, pady=5)
        buttons.append(btn)

    # Update command with correct button reference after creation
    for i, btn in enumerate(buttons):
        btn.config(command=partial(toggle_led, i, btn))

    # Close handler
    def on_close():
        print("Cleaning up GPIO...")
        GPIO.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

# Run the app
if __name__ == "__main__":
    setup_gpio()
    clear_register()
    shift_out(LEDs_status)
    create_gui()
