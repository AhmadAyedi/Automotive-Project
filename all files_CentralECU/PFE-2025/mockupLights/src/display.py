# -*- coding: utf-8 -*-


import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib
import re
from collections import defaultdict
import threading

matplotlib.rcParams.update({'font.size': 10, 'axes.titlesize': 12, 'axes.labelsize': 10})

# --- Analyse des données ---
def analyse_data(file):
    with open(file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    light_status = defaultdict(list)
    counter = defaultdict(int)

    for line in lines:
        match = re.search(r"(.*?) \| Status: (ON|OFF)", line)
        if match:
            light_name = match.group(1).strip()
            status = 1 if match.group(2) == "ON" else 0
            index = counter[light_name]
            light_status[light_name].append((index, status))
            counter[light_name] += 1

    return light_status

# --- Interface principale ---
def create_main_interface(light_status, file):
    root = tk.Tk()
    root.title(" Vehicle Lights Dashboard")
    root.configure(bg="#CBD4EA")
    root.geometry("1450x850")

    # --- Layout gauche ---
    left_frame = tk.Frame(root, bg="#f4f7fa", padx=20, pady=20)
    left_frame.pack(side=tk.LEFT, fill=tk.Y)

    group_box = tk.LabelFrame(left_frame, text=" Lights Selector", bg="#ffffff", fg="#C2EAE8",
                              font=("Segoe UI", 11, "bold"), padx=15, pady=15, bd=2)
    group_box.pack(fill=tk.X, pady=(0, 20))

    stats_box = tk.LabelFrame(left_frame, text=" Statistics", bg="#ffffff", fg="#C2EAE8",
                              font=("Segoe UI", 11, "bold"), padx=15, pady=10, bd=2)
    stats_box.pack(fill=tk.BOTH, expand=True)

    # --- Partie graphique ---
    main_frame = tk.Frame(root, bg="#f4f7fa")
    main_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    figure, axes = plt.subplots(nrows=3, ncols=3, figsize=(14, 8), dpi=100)
    figure.tight_layout(pad=4.5)
    canvas = FigureCanvasTkAgg(figure, master=main_frame)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    axes = [ax for row in axes for ax in row]
    for i in range(7, 9):  # Masquer les 2 derniers graphes
        axes[i].axis('off')

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']
    visibility = {}
    stats_labels = {}
    plots = {}

    light_names = list(light_status.keys())

    # --- Affichage des courbes ---
    def toggle_plot():
        for idx, light_name in enumerate(light_names[:7]):
            ax = axes[idx]
            ax.clear()
            if visibility[light_name].get():
                data = light_status[light_name]
                x = [i for i, _ in data]
                y = [v for _, v in data]
                plots[light_name], = ax.plot(x, y, label=light_name, marker='o', color=colors[idx])
                ax.set_title(light_name, fontsize=11, fontweight='bold')
                ax.set_ylim(-0.1, 1.1)
                ax.grid(True, linestyle='--', alpha=0.5)
            else:
                ax.set_title(light_name, fontsize=11, fontweight='bold')
                ax.set_ylim(-0.1, 1.1)
                ax.grid(True, linestyle='--', alpha=0.2)
        canvas.draw()

    # --- Mise à jour des statistiques ---
    def update_stats():
        for light_name in light_names[:7]:
            if visibility[light_name].get():
                data = light_status[light_name]
                on_count = sum(1 for _, state in data if state == 1)
                off_count = len(data) - on_count
                stats_labels[light_name].config(text=f"{light_name}: ON: {on_count}  |  OFF: {off_count}")

    # --- Checkboxes et stats ---
    for idx, light_name in enumerate(light_names[:7]):
        visibility[light_name] = tk.BooleanVar(value=False)

        cb = tk.Checkbutton(group_box, text=light_name, variable=visibility[light_name],
                            command=lambda name=light_name: [toggle_plot(), update_stats()],
                            bg="#ffffff", anchor='w', font=("Segoe UI", 10))
        cb.pack(fill=tk.X, padx=5, pady=3)

        label = tk.Label(stats_box, text=f"{light_name}: ON: 0  |  OFF: 0", anchor="w",
                         bg="#ffffff", fg="#333333", font=("Segoe UI", 10))
        label.pack(fill=tk.X, padx=5, pady=3)
        stats_labels[light_name] = label

    toggle_plot()
    update_stats()

    # --- Rafraîchissement auto ---
    def update_plot_realtime():
        while True:
            updated = analyse_data(file)
            for key in light_status:
                light_status[key] = updated.get(key, [])
            toggle_plot()
            update_stats()

    threading.Thread(target=update_plot_realtime, daemon=True).start()

    root.mainloop()

# --- Programme principal ---
if __name__ == "__main__":
    file = "lights_log.txt"  # Assure-toi que ce fichier est dans le même dossier
    light_status = analyse_data(file)
    create_main_interface(light_status, file)
