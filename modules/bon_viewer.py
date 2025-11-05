import tkinter as tk
from tkinter import Toplevel, scrolledtext, messagebox, Frame, Button, Label
import os
import tempfile
import subprocess
import sys
import json
from PIL import Image, ImageTk
import qrcode
import urllib

# Importeer generate_bon_text van de bon_generator module
from bon_generator import generate_bon_text


def open_bon_viewer(root_window, klant_data, bestelregels, bonnummer, menu_data_global, extras_data_global,
                    app_settings_global, save_and_print_callback):  # <-- save_and_print_callback toegevoegd
    """
    Opent een Toplevel venster om een bon weer te geven en aan te bieden voor afdrukken.
    Dit venster fungeert nu als een direct afdrukvoorbeeld.

    Args:
        root_window: Het hoofd Tkinter venster (root).
        klant_data (dict): De gegevens van de klant voor de bon.
        bestelregels (list): De bestelregels voor de bon.
        bonnummer (int): Het bonnummer.
        menu_data_global (dict): De globale menu_data.
        extras_data_global (dict): De globale EXTRAS data.
        app_settings_global (dict): De globale app_settings.
        save_and_print_callback: Een callback functie uit main.py om de bestelling op te slaan en af te drukken.
    """

    # De tekst voor de bon wordt één keer gegenereerd.
    parts = generate_bon_text(
        klant_data, bestelregels, bonnummer, menu_data_for_drinks=menu_data_global, extras_data=extras_data_global
    )
    # total_header en total_row zijn nu leeg in bon_generator.py, de inhoud zit in details_str
    header_str, info_str, address_str, details_str, tarief_str, totaal_label, totaal_waarde, te_betalen_str, footer_str, address_for_qr, bon_width_from_generator = parts

    # Construct the full text for printing, carefully managing newlines.
    # Each 'part_str' from generate_bon_text already contains its internal newlines
    # and has been formatted for the exact BON_WIDTH.
    # We explicitly add blank lines *between* these major sections for visual separation.
    full_bon_text_for_print = (
            header_str + "\n" +  # Header block, then a single newline for separation
            info_str.strip() + "\n" +  # Info block, then a single newline
            address_str + "\n" +  # Address block, then a single newline
            details_str.strip() + "\n" +  # Details block (already includes the BTW table and ends nicely), then one newline
            tarief_str.strip() + "\n" +  # <-- BTW/ Tarief tabel meenemen in preview/print
            f"{totaal_label}: {totaal_waarde}\n" +  # Totaal regel correct opgebouwd
            f"{te_betalen_str}\n" +  # "TE BETALEN!"
            footer_str  # Footer block (contains internal blank lines)
    )

    bon_win = Toplevel(root_window)
    bon_win.title(f"Afdrukvoorbeeld Bon {bonnummer}")
    bon_win.geometry("350x700")  # Iets breder voor leesbaarheid, en de breedte van de tekst is bon_width_from_generator
    bon_win.resizable(False, True)  # Horizontaal niet resizebaar, verticaal wel

    main_bon_frame = Frame(bon_win)
    main_bon_frame.pack(padx=5, pady=5, fill="both", expand=True)

    # ... existing code ...
    # Frame voor de QR-code en adres bovenaan
    qr_addr_frame = Frame(main_bon_frame)
    qr_addr_frame.pack(fill="x", pady=(2, 10))

    try:
        # Bouw drie navigatie-URLs voor hetzelfde adres
        encoded_addr = urllib.parse.quote_plus(address_for_qr)
        maps_url_google = f"https://www.google.com/maps/dir/?api=1&destination={encoded_addr}&dir_action=navigate"
        maps_url_apple = f"https://maps.apple.com/?daddr={encoded_addr}&dirflg=d"
        # Waze: gebruik q=adres (werkt zonder coördinaten)
        maps_url_waze = f"https://waze.com/ul?q={encoded_addr}&navigate=yes"

        # Maak eenvoudige HTML-landing met drie knoppen/links
        html_content = f"""<!doctype html>
    <html lang="nl">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Navigatie kiezen</title>
      <style>
        body {{ font-family: Arial, sans-serif; padding: 16px; }}
        h1 {{ font-size: 18px; margin-bottom: 12px; }}
        .btn {{ display: block; padding: 12px 14px; margin: 8px 0; text-decoration: none; color: #fff; border-radius: 6px; text-align:center; }}
        .google {{ background:#4285F4; }}
        .apple {{ background:#000000; }}
        .waze {{ background:#33CC99; }}
        .addr {{ font-size: 13px; color:#444; margin-top: 6px; }}
      </style>
    </head>
    <body>
      <h1>Kies navigatie-app</h1>
      <div class="addr">{address_for_qr}</div>
      <a class="btn google" href="{maps_url_google}">Open in Google Maps</a>
      <a class="btn apple" href="{maps_url_apple}">Open in Apple Maps</a>
      <a class="btn waze" href="{maps_url_waze}">Open in Waze</a>
    </body>
    </html>"""

        # Schrijf HTML naar tijdelijk bestand en maak file-URL
        tmp_dir = tempfile.mkdtemp(prefix="bon_nav_")
        landing_path = os.path.join(tmp_dir, "nav.html")
        with open(landing_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # file:// URL voor lokale landing page
        if sys.platform.startswith("win"):
            landing_url = "file:///" + landing_path.replace("\\", "/")
        else:
            landing_url = "file://" + landing_path

        # Genereer QR naar de landing page
        qr = qrcode.QRCode(version=1, box_size=1, border=1)
        qr.add_data(landing_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color='black', back_color='white').resize((50, 50), Image.LANCZOS)
        bon_win.qr_photo = ImageTk.PhotoImage(qr_img)

        qr_lbl = Label(qr_addr_frame, image=bon_win.qr_photo, anchor="center")
        qr_lbl.pack(anchor="center")
        Label(qr_addr_frame, text="Scan voor navigatie-keuze", font=("Courier New", 6), anchor="center").pack(
            anchor="center", pady=(0, 3))
    except ImportError:
        Label(qr_addr_frame, text="[QR-fout: PIL of qrcode ontbreekt]", fg='red', anchor="center").pack(anchor="center")
    except Exception as e:
        Label(qr_addr_frame, text=f"[QR-fout: {e}]", fg='red', anchor="center").pack(anchor="center")
    # ... existing code ...
    # Adres onder de QR-code in het preview venster (visueel, hoort niet bij de print-string)
    Label(qr_addr_frame, text=address_str, font=("Courier New", 8), justify="center",
          anchor="center").pack(anchor="center", pady=(0, 8))

    # Knoppen voor Printen en Sluiten - aan de onderkant plaatsen zodat ze altijd zichtbaar zijn.
    button_frame = Frame(main_bon_frame, pady=5)
    button_frame.pack(side="bottom", fill="x")

    # ScrolledText widget voor het afdrukvoorbeeld (vult de rest van de ruimte)
    bon_display = scrolledtext.ScrolledText(
        main_bon_frame,
        wrap=tk.NONE,  # GEEN WORD WRAPPING! De tekst is al geformatteerd.
        font=("Courier New", 8),  # Gebruik Courier New voor monospace font
        width=bon_width_from_generator,  # Gebruik de dynamische breedte van de bon_generator
        height=34  # Voldoende hoogte voor de meeste bonnen
    )
    bon_display.pack(fill="both", expand=True)

    # Vul de bon_display met de volledige, voor-geformatteerde tekst
    bon_display.insert(tk.END, full_bon_text_for_print)

    bon_display.config(state='disabled')  # Maak de tekst alleen-lezen

    def print_bon_action():
        # De extra bevestiging is verwijderd. De actie wordt direct uitgevoerd.
        save_and_print_callback(full_bon_text_for_print, address_for_qr, klant_data)
        bon_win.destroy()

    # De knoppen toevoegen aan het button_frame (dat al gepackt is)
    Button(button_frame, text="Afdrukken", command=print_bon_action, bg="#D1FFD1").pack(side="left", padx=(0, 5))
    Button(button_frame, text="Sluiten", command=bon_win.destroy, bg="#FFADAD").pack(side="right")

    # Extra: Binding voor Ctrl+P / Cmd+P om af te drukken vanuit het preview venster
    def handle_print_shortcut(event=None):
        print_bon_action()

    bon_win.bind("<Control-p>", handle_print_shortcut)  # Voor Windows/Linux
    bon_win.bind("<Command-p>", handle_print_shortcut)  # Voor macOS