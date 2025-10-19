import tkinter as tk
from tkinter import Toplevel, scrolledtext, messagebox
import os
import tempfile
import subprocess
import sys
import json  # Nodig voor json.loads van extras
from PIL import Image, ImageTk  # Importeer Image en ImageTk expliciet
import qrcode
import urllib

# Importeer generate_bon_text van de bon_generator module
from bon_generator import generate_bon_text


def open_bon_viewer(root_window, klant_data, bestelregels, bonnummer, menu_data_global, extras_data_global,
                    app_settings_global):
    """
    Opent een Toplevel venster om een bon weer te geven en aan te bieden voor afdrukken.

    Args:
        root_window: Het hoofd Tkinter venster (root).
        klant_data (dict): De gegevens van de klant voor de bon.
        bestelregels (list): De bestelregels voor de bon.
        bonnummer (int): Het bonnummer.
        menu_data_global (dict): De globale menu_data.
        extras_data_global (dict): De globale EXTRAS data.
        app_settings_global (dict): De globale app_settings.
    """

    parts = generate_bon_text(
        klant_data, bestelregels, bonnummer, menu_data_for_drinks=menu_data_global, extras_data=extras_data_global
    )
    header_str, info_str, address_str, details_str, total_header, total_row, te_betalen_str, totaal_bedrag_str, footer_str, address_for_qr = parts

    bon_win = Toplevel(root_window)
    bon_win.title(f"Bon {bonnummer}")
    bon_win.geometry("300x680")
    bon_win.resizable(False, True)

    main_bon_frame = tk.Frame(bon_win)
    main_bon_frame.pack(padx=5, pady=5, fill="both", expand=True)

    col = tk.Frame(main_bon_frame)
    col.pack(fill="both", expand=True)

    qr_addr_frame = tk.Frame(col)
    qr_addr_frame.pack(fill="x", pady=(2, 10))
    try:
        # Check if PIL.ImageTk is loaded, else ImportError
        # from PIL import ImageTk # Already imported at the top
        # import qrcode # Already imported at the top
        # import urllib # Already imported at the top

        maps_url = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(address_for_qr)
        qr = qrcode.QRCode(version=1, box_size=1, border=1)
        qr.add_data(maps_url)
        qr.make(fit=True)
        # Gebruik PIL.Image.ANTIALIAS of Image.LANCZOS voor betere kwaliteit bij resizen
        qr_img = qr.make_image(fill_color='black', back_color='white').resize((50, 50), Image.LANCZOS)
        bon_win.qr_photo = ImageTk.PhotoImage(qr_img)  # Opslaan referentie om GC te voorkomen

        qr_lbl = tk.Label(qr_addr_frame, image=bon_win.qr_photo, anchor="center")
        qr_lbl.pack(anchor="center")
        tk.Label(qr_addr_frame, text="Scan adres", font=("Courier New", 6), anchor="center").pack(
            anchor="center", pady=(0, 3))
    except ImportError:
        tk.Label(qr_addr_frame, text="[QR-fout]", fg='red', anchor="center").pack(anchor="center")
    except Exception as e:
        tk.Label(qr_addr_frame, text=f"[QR-fout: {e}]", fg='red', anchor="center").pack(anchor="center")

    addr_lbl = tk.Label(qr_addr_frame, text=address_str, font=("Courier New", 8), justify=tk.CENTER,
                        anchor="center")
    addr_lbl.pack(anchor="center", pady=(0, 8))

    bon_display = scrolledtext.ScrolledText(
        col,
        wrap=tk.WORD,
        font=("Courier New", 8),
        width=42,
        height=34
    )
    bon_display.pack(fill="both", expand=True)
    # Tabs aanpassen aan vaste breedtes in bon_generator
    bon_display.config(tabs=(6 * 8, (6 + 11) * 8, (6 + 11 + 11) * 8,
                             (6 + 11 + 11 + 14) * 8))  # Aangepast om overeen te komen met print.

    bon_display.insert(tk.END, header_str + "\n")
    bon_display.insert(tk.END, info_str + "\n")
    bon_display.insert(tk.END, address_str + "\n\n")
    bon_display.insert(tk.END, details_str + "\n\n")

    idx_total_start = bon_display.index(tk.END)
    bon_display.insert(tk.END, total_header + "\n")
    bon_display.insert(tk.END, total_row + "\n")
    idx_total_end = bon_display.index(tk.END)

    bon_display.insert(tk.END, "\n")
    idx_tebetalen_start = bon_display.index(tk.END)
    bon_display.insert(tk.END, te_betalen_str + "\n")
    bon_display.insert(tk.END, totaal_bedrag_str + "\n")
    idx_tebetalen_end = bon_display.index(tk.END)
    bon_display.insert(tk.END, "\n" + footer_str)

    bon_display.tag_configure("center", justify='center')
    bon_display.tag_add("center", "1.0", tk.END)
    bon_display.tag_configure("columns", font=("Courier New", 8), justify='left')
    bon_display.tag_add("columns", idx_total_start, idx_total_end)
    bon_display.tag_configure("te_betalen", font=("Courier New", 10, "bold"), justify='center')
    bon_display.tag_add("te_betalen", idx_tebetalen_start, idx_tebetalen_end)

    bon_display.config(state='disabled')

    def print_bon():
        try:
            # We gebruiken hier een named temporary file zodat de printertoepassing deze kan lezen
            # en het bestand automatisch wordt verwijderd na gebruik.
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
            tmp.write("\n".join(
                [header_str, info_str, address_str, details_str, total_header, total_row, te_betalen_str,
                 totaal_bedrag_str, footer_str]))
            tmp.close()  # Belangrijk: sluit het bestand zodat de printer er toegang toe heeft

            printer_name = app_settings_global.get("thermal_printer_name", "Default")

            if os.name == "nt":  # Voor Windows
                if printer_name and printer_name.lower() != "default":
                    messagebox.showwarning("Print",
                                           f"Op Windows print de app momenteel alleen naar de standaardprinter. "
                                           f"De ingestelde printer '{printer_name}' kan niet direct gekozen worden zonder extra setup. "
                                           f"Bon wordt naar standaardprinter gestuurd via Notepad.")
                # Gebruik start-process om de printertaak op de achtergrond te starten en te voorkomen dat de UI blokkeert
                # De '/p' flag is voor printen
                subprocess.Popen(["notepad.exe", "/p", tmp.name], shell=True)
            else:  # Voor Linux/macOS
                if printer_name and printer_name.lower() != "default":
                    subprocess.run(["lpr", "-P", printer_name, tmp.name], check=False)
                else:
                    subprocess.run(["lpr", tmp.name], check=False)

            messagebox.showinfo("Print", "Bon naar printer gestuurd.")

        except FileNotFoundError:
            messagebox.showerror("Fout",
                                 "Printerprogramma (notepad.exe of lpr) niet gevonden. Zorg dat het correct geïnstalleerd en in PATH is.")
        except Exception as e:
            messagebox.showerror("Print",
                                 f"Printen mislukt: {e}\nControleer of de printer is aangesloten en geconfigureerd.")
        finally:
            # Zorg ervoor dat het tijdelijke bestand wordt verwijderd
            if tmp and os.path.exists(tmp.name):
                os.unlink(tmp.name)

    tk.Button(col, text="Print bon", command=print_bon, bg="#E1E1FF").pack(pady=(6, 2))
