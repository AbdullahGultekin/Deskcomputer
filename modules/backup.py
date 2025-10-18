import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import shutil
import datetime

FILES_TO_BACKUP = ["pizzeria.db", "menu.json", "extras.json"]


def open_backup_tool(root):
    win = tk.Toplevel(root)
    win.title("Backup & Restore")
    win.geometry("520x240")

    frame = tk.Frame(win, padx=12, pady=12)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(frame, text="Backup & Restore", font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 10))

    def do_backup():
        target = filedialog.askdirectory(title="Kies doelmap voor backup")
        if not target:
            return
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(target, f"backup_{stamp}")
        try:
            os.makedirs(dest, exist_ok=True)
            copied = []
            for f in FILES_TO_BACKUP:
                if os.path.exists(f):
                    shutil.copy2(f, os.path.join(dest, f))
                    copied.append(f)
            if not copied:
                messagebox.showwarning("Backup", "Geen bestanden gevonden om te backuppen.")
            else:
                messagebox.showinfo("Backup", f"Backup voltooid naar: {dest}\nBestanden: {', '.join(copied)}")
        except Exception as e:
            messagebox.showerror("Backup", f"Mislukt: {e}")

    def do_restore():
        source = filedialog.askdirectory(title="Kies backup map")
        if not source:
            return
        try:
            restored = []
            for f in FILES_TO_BACKUP:
                src = os.path.join(source, f)
                if os.path.exists(src):
                    shutil.copy2(src, f)
                    restored.append(f)
            if not restored:
                messagebox.showwarning("Restore", "Geen te herstellen bestanden gevonden in map.")
            else:
                messagebox.showinfo("Restore",
                                    f"Herstel voltooid.\nBestanden: {', '.join(restored)}\nHerstart de applicatie voor veiligheid.")
        except Exception as e:
            messagebox.showerror("Restore", f"Mislukt: {e}")

    btns = tk.Frame(frame)
    btns.pack(fill=tk.X)
    ttk.Button(btns, text="Backup maken", command=do_backup).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(btns, text="Backup terugzetten", command=do_restore).pack(side=tk.LEFT)