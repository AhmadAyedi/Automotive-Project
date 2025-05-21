import can
import serial
import tkinter as tk
from tkinter import messagebox
import time
import struct

class LINFrame:
    def __init__(self, id, data):
        self.id = id & 0x3F
        self.data = data[:8]
        self.pid = self._calculate_pid()
        self.checksum = self._calculate_checksum()

    def _calculate_pid(self):
        id_bits = [self.id >> i & 1 for i in range(6)]
        p0 = id_bits[0] ^ id_bits[1] ^ id_bits[2] ^ id_bits[4]
        p1 = ~(id_bits[1] ^ id_bits[3] ^ id_bits[4] ^ id_bits[5]) & 1
        return (self.id | (p0 << 6) | (p1 << 7)) & 0xFF

    def _calculate_checksum(self):
        sum = self.pid
        for byte in self.data:
            sum += byte
            if sum > 0xFF:
                sum = (sum & 0xFF) + 1
        return (~sum) & 0xFF

    def to_bytes(self):
        break_field = b'\x00'
        sync_field = b'\x55'
        pid_field = bytes([self.pid])
        data_field = bytes(self.data)
        checksum_field = bytes([self.checksum])
        return break_field + sync_field + pid_field + data_field + checksum_field

class MasterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CAN/LIN Frame Sender")
        self.protocol = None

        # Initialize interfaces
        try:
            self.can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
            self.serial = serial.Serial(
                port='/dev/serial0',
                baudrate=19200,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize interfaces: {e}")
            self.root.quit()

        # GUI elements
        tk.Label(root, text="Select Protocol:").pack(pady=10)

        self.can_button = tk.Button(root, text="CAN", command=self.select_can)
        self.can_button.pack(pady=5)

        self.lin_button = tk.Button(root, text="LIN", command=self.select_lin)
        self.lin_button.pack(pady=5)

        self.send_button = tk.Button(root, text="Send Frame", command=self.send_frame, state=tk.DISABLED)
        self.send_button.pack(pady=20)

        self.status_label = tk.Label(root, text="No protocol selected")
        self.status_label.pack(pady=10)

    def select_can(self):
        self.protocol = "CAN"
        self.send_button.config(state=tk.NORMAL)
        self.status_label.config(text="Protocol: CAN")
        self.can_button.config(relief=tk.SUNKEN)
        self.lin_button.config(relief=tk.RAISED)

    def select_lin(self):
        self.protocol = "LIN"
        self.send_button.config(state=tk.NORMAL)
        self.status_label.config(text="Protocol: LIN")
        self.lin_button.config(relief=tk.SUNKEN)
        self.can_button.config(relief=tk.RAISED)

    def send_frame(self):
        try:
            if self.protocol == "CAN":
                msg = can.Message(
                    arbitration_id=0x123,
                    data=[0x01, 0x02, 0x03, 0x04],
                    is_extended_id=False
                )
                self.can_bus.send(msg)
                messagebox.showinfo("Success", "Sent CAN frame: ID=0x123, Data=[1, 2, 3, 4]")
            elif self.protocol == "LIN":
                frame = LINFrame(id=0x01, data=[0xAA, 0xBB])
                self.serial.write(frame.to_bytes())
                messagebox.showinfo("Success", f"Sent LIN frame: ID=0x01, Data=[170, 187]")
            else:
                messagebox.showwarning("Warning", "No protocol selected")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send frame: {e}")

    def close(self):
        try:
            if hasattr(self, 'can_bus'):
                self.can_bus.shutdown()
            if hasattr(self, 'serial'):
                self.serial.close()
        except:
            pass
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = MasterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()