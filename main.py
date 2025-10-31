import tkinter as tk
from tkinter import messagebox, Toplevel, scrolledtext, ttk, simpledialog
from PIL import Image
import tkinter as tk
import json
import qrcode
import random
import datetime
from datetime import timedelta
import os
import csv
import win32print
import database
import tempfile
import subprocess
from bon_generator import generate_bon_text
from modules.koeriers import open_koeriers
from modules.geschiedenis import open_geschiedenis
from modules.klanten import open_klanten_zoeken, voeg_klant_toe_indien_nodig
from modules.menu_management import open_menu_management
from modules.extras_management import open_extras_management
from modules.klant_management import open_klant_management
from modules.rapportage import open_rapportage
from modules.backup import open_backup_tool
from modules.voorraad import open_voorraad
from modules.bon_viewer import open_bon_viewer
import sys
import platform
from database import get_db_connection

# ============ WINDOWS PRINT SUPPORT ============
# Conditionele import voor Windows-only modules
if platform.system() == "Windows":
    try:
        import win32print

        WIN32PRINT_AVAILABLE = True
    except ImportError:
        WIN32PRINT_AVAILABLE = False
        print("Waarschuwing: pywin32 niet geïnstalleerd. Windows printer support niet beschikbaar.")
else:
    WIN32PRINT_AVAILABLE = False
    print("Info: win32print is alleen beschikbaar op Windows.")

# Voeg toe bij je andere imports bovenaan (VEROUDERD - NIET MEER NODIG)
# try:
#     from escpos.printer import Usb
#     ESCPOS_AVAILABLE = True
# except ImportError:
#     ESCPOS_AVAILABLE = False
#     print("Waarschuwing: python-escpos niet geïnstalleerd. Thermisch printen niet beschikbaar.")

# Globale variabelen initialisatie (niet-Tkinter gerelateerd)

def vul_klantgegevens_automatisch():
    telefoon = telefoon_entry.get().strip()
    if not telefoon:
        return

    conn = database.get_db_connection()
    klant = conn.execute("SELECT * FROM klanten WHERE telefoon = ?", (telefoon,)).fetchone()
    conn.close()

    if klant:
        naam_entry.delete(0, tk.END)
        naam_entry.insert(0, klant['naam'] or "")
        adres_entry.delete(0, tk.END)
        adres_entry.insert(0, klant['straat'] or "")
        nr_entry.delete(0, tk.END)
        nr_entry.insert(0, klant['huisnummer'] or "")

        plaats = klant['plaats'] or ""
        gevonden_postcode = ""
        for p in postcodes:
            if plaats in p:
                gevonden_postcode = p
                break
        postcode_var.set(gevonden_postcode if gevonden_postcode else postcodes[0])
    else:
        naam_entry.delete(0, tk.END)
        adres_entry.delete(0, tk.END)
        nr_entry.delete(0, tk.END)
        postcode_var.set(postcodes[0])


# 1x laden!
with open("straatnamen.json", "r", encoding="utf-8") as f:
    straatnamen = json.load(f)


def suggest_straat(zoekterm):
    zoekterm = zoekterm.lower().strip()
    return [naam for naam in straatnamen if zoekterm in naam.lower()]


def on_adres_entry(event):
    typed_str = adres_entry.get()
    lb_suggesties.delete(0, tk.END)
    suggesties = suggest_straat(typed_str)
    if suggesties:
        for s in suggesties:
            lb_suggesties.insert(tk.END, s)
        lb_suggesties.grid()
    else:
        lb_suggesties.grid_remove()


def selectie_suggestie(event):
    if lb_suggesties.curselection():
        keuze = lb_suggesties.get(lb_suggesties.curselection())
        adres_entry.delete(0, tk.END)
        adres_entry.insert(0, keuze)
        lb_suggesties.grid_remove()


def suggest_postcode(zoekterm):
    zoekterm = zoekterm.strip().lower()
    return [pc for pc, plaats in postcodes.items()
            if zoekterm in pc.lower() or zoekterm in plaats.lower()]


def voeg_adres_toe(straat, postcode, gemeente):
    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO adressen (straat, postcode, gemeente) VALUES (?, ?, ?)",
        (straat, postcode, gemeente)
    )
    conn.commit()
    conn.close()


def update_straatnamen_json(nieuwe_straat, json_path="straatnamen.json"):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if nieuwe_straat not in data:
        data.append(nieuwe_straat)
        with open(json_path, "w", encoding="utf-8") as f2:
            json.dump(data, f2, ensure_ascii=False, indent=2)


EXTRAS = {}
menu_data = {}
app_settings = {}
SETTINGS_FILE = "settings.json"
postcodes = [
    "2070 Zwijndrecht", "4568 Nieuw-Namen", "9100 Nieuwkerken-Waas",
    "9100 Sint-Niklaas", "9120 Beveren", "9120 Vrasene", "9120 Haasdonk",
    "9120 Kallo", "9120 Melsele", "9130 Verrebroek", "9130 Kieldrecht",
    "9130 Doel", "9170 Klein meerdonk", "9170 Meerdonk",
    "9170 Sint-Gillis-Waas", "9170 De Klinge"
]
bestelregels = []

# Globale UI-elementen die door meerdere functies worden gebruikt
# Deze worden in setup_menu_interface geïnitialiseerd
product_grid_holder = None
producten_titel = None
opties_frame = None
opt_title = None
right_overview = None
menu_main_panel = None  # Nodig om globaal te zijn als setup_menu_interface deze vult
bestel_frame = None  # Nodig om globaal te zijn als setup_menu_interface deze vult
dynamic_product_options_frame = None  # Nieuw frame voor dynamische product opties

# Globale variabele om het huidige pop-up optievenster bij te houden
current_options_popup_window = None

# Controlevariabelen voor opties (leeg declareren, later initialiseren met root)
ctrl = {}
half1_var = None
half2_var = None

# State voor menu navigatie (categorie, gekozen product)
state = {
    "categorie": None,
    "producten": [],
    "page": 0,
    "page_size": 10,
    "gekozen_product": None
}


def print_bon_with_qr(full_bon_text_for_print, qr_data_string):
    VENDOR_ID = 0x04b8  # Epson (controleer eventueel)
    PRODUCT_ID = 0x0e15  # TM-T20II (controleer met pyusb of boekje)
    try:
        qr_img = qrcode.make(qr_data_string)
        qr_img = qr_img.resize((180, 180), Image.LANCZOS)
        p = Usb(VENDOR_ID, PRODUCT_ID, timeout=0)
        p.set(align='left')
        p.text(full_bon_text_for_print + "\n")
        p.image(qr_img)
        p.cut()
    except Exception as e:
        messagebox.showerror("Print Error", f"QR/ESC/POS print niet gelukt: {e}")


def _initialize_app_variables(root_window):
    """
    Initialiseert de Tkinter Control variabelen en andere globale Tkinter-gerelateerde variabelen.
    Deze functie moet worden aangeroepen nadat tk.Tk() is gemaakt.
    """
    global ctrl, half1_var, half2_var

    ctrl["aantal"] = tk.IntVar(master=root_window, value=1)
    ctrl["vlees"] = tk.StringVar(master=root_window)
    ctrl["bijgerecht_combos"] = []
    ctrl["saus_combos"] = []
    ctrl["garnering"] = []
    ctrl["opmerking"] = tk.StringVar(master=root_window)

    half1_var = tk.StringVar(master=root_window, value="1")
    half2_var = tk.StringVar(master=root_window, value="2")


def load_json_file(path, fallback_data=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if fallback_data is not None:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(fallback_data, f, ensure_ascii=False, indent=2)
            return fallback_data
        messagebox.showerror("Fout", f"{path} niet gevonden!")
        return {}
    except json.JSONDecodeError:
        messagebox.showerror("Fout", f"{path} is geen geldige JSON!")
        return {}


def save_json_file(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        messagebox.showerror("Fout", f"Kon {path} niet opslaan: {e}")
        return False


def load_menu_categories():
    """Laadt beschikbare categorieën uit menu.json"""
    try:
        with open("menu.json", "r", encoding="utf-8") as f:
            menu_data = json.load(f)
            return list(menu_data.keys())
    except FileNotFoundError:
        print("Fout: menu.json is niet gevonden.")
        return []
    except json.JSONDecodeError:
        print("Fout: menu.json is geen geldige JSON-indeling. Controleer de inhoud.")
        return []
    except Exception as e:
        print(f"Een onverwachte fout is opgetreden bij het laden van menu.json: {e}")
        return []


def load_data():
    global EXTRAS, menu_data, app_settings
    extras_fallback = {}
    EXTRAS = load_json_file("extras.json", fallback_data=extras_fallback)
    try:
        with open("menu.json", "r", encoding="utf-8") as f:
            menu_data = json.load(f)
    except FileNotFoundError:
        messagebox.showerror("Fout", "menu.json niet gevonden!")
        menu_data = {}
    except json.JSONDecodeError:
        messagebox.showerror("Fout", "menu.json is geen geldige JSON!")
        menu_data = {}
    settings_fallback = {"thermal_printer_name": "Default"}
    app_settings = load_json_file(SETTINGS_FILE, fallback_data=settings_fallback)


load_data()
database.initialize_database()


# Functie om printerinstellingen te openen (onveranderd)
def open_printer_settings():
    settings_win = tk.Toplevel(root)
    settings_win.title("Printer Instellingen")
    settings_win.geometry("400x150")
    settings_win.transient(root)
    settings_win.grab_set()

    tk.Label(settings_win, text="Naam thermische printer (of 'Default'):", font=("Arial", 11, "bold")).pack(pady=10)

    printer_name_var = tk.StringVar(value=app_settings.get("thermal_printer_name", "Default"), master=settings_win)
    printer_entry = tk.Entry(settings_win, textvariable=printer_name_var, width=40, font=("Arial", 11))
    printer_entry.pack(pady=5)

    def save_settings():
        app_settings["thermal_printer_name"] = printer_name_var.get().strip()
        if save_json_file(SETTINGS_FILE, app_settings):
            messagebox.showinfo("Opgeslagen", "Printerinstellingen succesvol opgeslagen!")
            settings_win.destroy()

    tk.Button(settings_win, text="Opslaan", command=save_settings, bg="#D1FFD1", font=("Arial", 10)).pack(pady=10)


# NIEUW: Helper functie om huidige bestelgegevens te verzamelen
def _get_current_order_data():
    global bestelregels

    if not bestelregels:
        messagebox.showerror("Fout", "Er zijn geen producten toegevoegd aan de bestelling!")
        return None, None, None  # Geen data

    telefoon = telefoon_entry.get().strip()
    if not telefoon:
        messagebox.showerror("Fout", "Vul een telefoonnummer in!")
        return None, None, None  # Geen data

    klant_data = {
        "naam": naam_entry.get().strip(),
        "telefoon": telefoon,
        "adres": adres_entry.get(),
        "nr": nr_entry.get(),
        "postcode_gemeente": postcode_var.get(),
        "opmerking": opmerkingen_entry.get().strip()
    }

    # Bonnummer wordt pas bij opslaan definitief, maar we hebben een tijdelijke nodig voor preview
    temp_bonnummer = database.get_next_bonnummer(peek_only=True)  # Aangenomen dat database.py een peek_only optie heeft

    return klant_data, list(bestelregels), temp_bonnummer


def voeg_klant_toe_of_update(telefoon, adres, nr, postcode_plaats, naam):
    if not telefoon:
        return
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM klanten WHERE telefoon = ?", (telefoon,))
    bestaande_klant = cursor.fetchone()
    if bestaande_klant:
        # Update altijd het actuele adres, nr, naam en plaats!
        cursor.execute(
            "UPDATE klanten SET straat = ?, huisnummer = ?, plaats = ?, naam = ? WHERE telefoon = ?",
            (adres, nr, postcode_plaats, naam, telefoon)
        )
    else:
        cursor.execute(
            "INSERT INTO klanten (telefoon, straat, huisnummer, plaats, naam) VALUES (?, ?, ?, ?, ?)",
            (telefoon, adres, nr, postcode_plaats, naam)
        )
    conn.commit()
    conn.close()


# REFACtORED: bestelling_opslaan zal nu alleen opslaan en de UI opschonen, NIET direct printen of preview tonen
def bestelling_opslaan(show_confirmation=True):
    global bestelregels

    klant_data, order_items, _ = _get_current_order_data()
    if klant_data is None:  # Geen geldige data verzameld
        return False, None  # Geef aan dat opslaan mislukt is en geen bontekst

    telefoon = klant_data["telefoon"]
    naam = klant_data["naam"]
    voeg_klant_toe_of_update(
        telefoon=klant_data["telefoon"],
        adres=klant_data["adres"],
        nr=klant_data["nr"],
        postcode_plaats=klant_data["postcode_gemeente"],
        naam=naam
    )

    conn = database.get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM klanten WHERE telefoon = ?", (klant_data["telefoon"],))
        klant_id_row = cursor.fetchone()
        if not klant_id_row:
            messagebox.showerror("Database Fout", "Kon de klant niet vinden of aanmaken.")
            conn.rollback()
            conn.close()
            return False, None

        klant_id = klant_id_row[0]
        nu = datetime.datetime.now()
        totaal_prijs = sum(item['prijs'] * item['aantal'] for item in order_items)
        bonnummer = database.get_next_bonnummer()  # Haal het definitieve bonnummer op

        cursor.execute(
            "INSERT INTO bestellingen (klant_id, datum, tijd, totaal, opmerking, bonnummer) VALUES (?, ?, ?, ?, ?, ?)",
            (klant_id, nu.strftime('%Y-%m-%d'), nu.strftime('%H:%M'), totaal_prijs, klant_data["opmerking"], bonnummer)
        )
        bestelling_id = cursor.lastrowid

        for regel in order_items:
            cursor.execute(
                "INSERT INTO bestelregels (bestelling_id, categorie, product, aantal, prijs, extras) VALUES (?, ?, ?, ?, ?, ?)",
                (bestelling_id, regel['categorie'], regel['product'], regel['aantal'], regel['prijs'],
                 json.dumps(regel.get('extras', {})))
            )

        conn.commit()
        database.update_klant_statistieken(klant_id)
        database.boek_voorraad_verbruik(bestelling_id)


        # UI opschonen na bestelling
        telefoon_entry.delete(0, tk.END)
        naam_entry.delete(0, tk.END)
        adres_entry.delete(0, tk.END)
        nr_entry.delete(0, tk.END)
        postcode_var.set(postcodes[0])
        opmerkingen_entry.delete(0, tk.END)
        ctrl["opmerking"].set("")
        bestelregels.clear()
        update_overzicht()

        return True, bonnummer  # Geef aan dat opslaan gelukt is

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Fout bij opslaan", f"Er is een fout opgetreden: {str(e)}")
        try:
            with open("app_errors.log", "a", encoding="utf-8") as lf:
                import traceback, datetime as dt
                lf.write(f"[{dt.datetime.now()}] bestelling_opslaan: {traceback.format_exc()}\n")
        except:
            pass
        return False, None
    finally:
        conn.close()


# ... existing code ...

def _save_and_print_from_preview(full_bon_text_for_print, address_for_qr=None):
    import re
    if not WIN32PRINT_AVAILABLE:
        messagebox.showerror("Platform Error", "Windows printer support niet beschikbaar.")
        return

    success, bonnummer = bestelling_opslaan(show_confirmation=False)
    if not success:
        messagebox.showerror("Fout", "Bestelling kon niet worden opgeslagen.")
        return

    printer_name = "EPSON TM-T20II Receipt5"

    try:
        hprinter = win32print.OpenPrinter(printer_name)
        try:
            hjob = win32print.StartDocPrinter(hprinter, 1, ("Bon", None, "RAW"))
            win32print.StartPagePrinter(hprinter)
            ESC = b'\x1b'
            GS = b'\x1d'

            # Header
            win32print.WritePrinter(hprinter, ESC + b'a' + b'\x01')
            win32print.WritePrinter(hprinter, GS + b'!' + b'\x11')
            win32print.WritePrinter(hprinter, b'PITA PIZZA NAPOLI\n')
            win32print.WritePrinter(hprinter, GS + b'!' + b'\x00')
            win32print.WritePrinter(hprinter, b'\n')

            header_info = """Brugstraat 12 - 9120 Vrasene
TEL: 03 / 775 72 28
FAX: 03 / 755 52 22
BTW: BE 0479.048.950

Bestel online
www.pitapizzanapoli.be
info@pitapizzanapoli.be

"""
            win32print.WritePrinter(hprinter, header_info.encode('cp437', errors='replace'))

            bon_lines = full_bon_text_for_print.split('\n')
            bonnummer_idx = bezorgtijd_idx = address_idx = dhr_mvr_idx = details_idx = 0
            for i, line in enumerate(bon_lines):
                if 'Bonnummer' in line: bonnummer_idx = i
                if 'Bezorgtijd' in line: bezorgtijd_idx = i
                if 'Leveringsadres:' in line: address_idx = i
                if ('Dhr.' in line or 'Mvr.' in line): dhr_mvr_idx = i
                if 'Details bestelling' in line: details_idx = i; break

            # Bestelinfo printen, tot bezorgtijd
            win32print.WritePrinter(hprinter, ESC + b'a' + b'\x00')
            win32print.WritePrinter(hprinter, '\n'.join(bon_lines[bonnummer_idx:bezorgtijd_idx]).encode('cp437',
                                                                                                        errors='replace'))

            # Bezorgtijd vet drukken
            win32print.WritePrinter(hprinter, ESC + b'E' + b'\x01')
            win32print.WritePrinter(hprinter, bon_lines[bezorgtijd_idx].encode('cp437', errors='replace'))
            win32print.WritePrinter(hprinter, b'\n')
            win32print.WritePrinter(hprinter, ESC + b'E' + b'\x00')
            win32print.WritePrinter(hprinter, b'\n')

            # Klantnaam betrouwbaar ophalen uit GUI (globals()) of uit bontekst
            klantnaam = ""
            try:
                if 'naam_entry' in globals() and isinstance(naam_entry, tk.Entry):
                    klantnaam = naam_entry.get().strip()
            except Exception:
                pass
            if not klantnaam:
                # Val terug op bontekst: zoek regel na "Dhr. / Mvr."
                if dhr_mvr_idx and dhr_mvr_idx + 1 < len(bon_lines):
                    possible_name = bon_lines[dhr_mvr_idx + 1].strip()
                    # Alleen nemen als niet leeg en niet meteen een nieuwe sectie
                    if possible_name and ("Details bestelling" not in possible_name):
                        klantnaam = possible_name

            win32print.WritePrinter(hprinter, 'Leveringsadres:\n'.encode('cp858'))

            # Klantnaam expliciet printen indien beschikbaar
            if klantnaam:
                win32print.WritePrinter(hprinter, (klantnaam + '\n').encode('cp858', errors='replace'))

            ## Daarna het adres
            adres_end = dhr_mvr_idx if (dhr_mvr_idx > 0 and dhr_mvr_idx > address_idx) else details_idx
            address_content = bon_lines[address_idx + 1:adres_end] if address_idx > 0 and adres_end > 0 else []
            # Maak adres vet en 2x groter
            ESC = b'\x1b'
            GS = b'\x1d'
            win32print.WritePrinter(hprinter, ESC + b'E' + b'\x01')  # Bold aan
            win32print.WritePrinter(hprinter, GS + b'!' + b'\x11')  # Dubbele hoogte+breedte
            for addr_line in address_content:
                win32print.WritePrinter(hprinter, addr_line.encode('cp858', errors='replace'))
                win32print.WritePrinter(hprinter, b'\n')
            # Reset stijl
            win32print.WritePrinter(hprinter, GS + b'!' + b'\x00')  # Normale grootte
            win32print.WritePrinter(hprinter, ESC + b'E' + b'\x00')  # Bold uit

            # Bestel-details
            win32print.WritePrinter(hprinter, b'\x1B\x74\x13')  # CP858
            if details_idx > 0:
                # bereken einde van details sectie
                details_end_idx = len(bon_lines)
                for i in range(details_idx, len(bon_lines)):
                    if 'Tarief' in bon_lines[i] or ('Totaal' in bon_lines[i] and i > details_idx + 2):
                        details_end_idx = i
                        break
                # "Details bestelling" vet
                ESC = b'\x1b'
                win32print.WritePrinter(hprinter, ESC + b'E' + b'\x01')  # Bold aan
                win32print.WritePrinter(hprinter, 'Details bestelling\n'.encode('cp858'))
                win32print.WritePrinter(hprinter, ESC + b'E' + b'\x00')  # Bold uit
                win32print.WritePrinter(hprinter, ('-' * 42 + '\n').encode('cp858'))

                current_item_lines = []
                for line in bon_lines[details_idx + 1:details_end_idx]:
                    stripped_line = line.strip()
                    if stripped_line and (stripped_line[0].isdigit() and 'x' in line[:5]):
                        if current_item_lines:
                            win32print.WritePrinter(hprinter, '\n'.join(current_item_lines).encode('cp858'))
                            win32print.WritePrinter(hprinter, ('\n' + '-' * 42 + '\n').encode('cp858'))
                            current_item_lines = []
                        current_item_lines.append(line.replace('?', '€'))
                    else:
                        if "TE BETALEN" in line:
                            continue
                        if stripped_line:
                            current_item_lines.append(f"> {stripped_line}")
                if current_item_lines:
                    win32print.WritePrinter(hprinter, '\n'.join(current_item_lines).encode('cp858'))
                    win32print.WritePrinter(hprinter, b'\n')

            # Totaal
            ESC = b'\x1B'
            GS = b'\x1D'
            totaal_line = ""
            for i in range(len(bon_lines) - 1, -1, -1):
                if 'Totaal' in bon_lines[i] and ('€' in bon_lines[i] or '?' in bon_lines[i]):
                    totaal_line = bon_lines[i]
                    break

            if totaal_line:
                totaal_line = totaal_line.replace('\u20ac', '€').replace('\xe2\x82\xac', '€').replace('?', '€')
                win32print.WritePrinter(hprinter, b'\n')
                win32print.WritePrinter(hprinter, ESC + b'a' + b'\x01')
                win32print.WritePrinter(hprinter, ESC + b'E' + b'\x01')
                win32print.WritePrinter(hprinter, GS + b'!' + b'\x01')
                win32print.WritePrinter(hprinter, totaal_line.encode('cp858', errors='replace'))
                win32print.WritePrinter(hprinter, b'\n')
                win32print.WritePrinter(hprinter, GS + b'!' + b'\x00')
                win32print.WritePrinter(hprinter, ESC + b'E' + b'\x00')
                win32print.WritePrinter(hprinter, ESC + b'a' + b'\x00')

            # Footer (geen dubbele "Eet smakelijk!" hier)
            footer = """
"""
            win32print.WritePrinter(hprinter, ESC + b'a' + b'\x01')
            win32print.WritePrinter(hprinter, footer.encode('cp437', errors='replace'))

            ESC = b'\x1B'
            GS = b'\x1D'

            # TE BETALEN! (groot/vet) + exact 1 lege lijn erna
            win32print.WritePrinter(hprinter, ESC + b'a' + b'\x01')
            win32print.WritePrinter(hprinter, ESC + b'E' + b'\x01')
            win32print.WritePrinter(hprinter, GS + b'!' + b'\x01')
            win32print.WritePrinter(hprinter, b'TE BETALEN!\n')
            # Reset grootte/vet, blijven gecentreerd
            win32print.WritePrinter(hprinter, GS + b'!' + b'\x00')
            win32print.WritePrinter(hprinter, ESC + b'E' + b'\x00')
            # Precies één lege lijn na "TE BETALEN!"
            win32print.WritePrinter(hprinter, b'\n')

            # Centraal "Eet smakelijk"
            win32print.WritePrinter(hprinter, ESC + b'E' + b'\x01')
            win32print.WritePrinter(hprinter, b'Eet smakelijk\n')
            win32print.WritePrinter(hprinter, ESC + b'E' + b'\x00')

            # Openingsuren
            win32print.WritePrinter(hprinter, b'Van Dins- tot Zon\n vanaf 17 u Tot 20u30\n')

            # Reset uitlijning
            win32print.WritePrinter(hprinter, ESC + b'a' + b'\x00')

            # QR code (ongewijzigd)
            if address_for_qr:
                win32print.WritePrinter(hprinter, b'\n')
                win32print.WritePrinter(hprinter, ESC + b'a' + b'\x01')
                win32print.WritePrinter(hprinter, GS + b'(' + b'k' + b'\x04\x00' + b'1A2\x00')
                win32print.WritePrinter(hprinter, GS + b'(' + b'k' + b'\x03\x00' + b'1C\x06')
                win32print.WritePrinter(hprinter, GS + b'(' + b'k' + b'\x03\x00' + b'1E0')
                qr_data = address_for_qr.encode('utf-8')
                qr_len = len(qr_data) + 3
                win32print.WritePrinter(hprinter, GS + b'(' + b'k' + qr_len.to_bytes(2, 'little') + b'1P0' + qr_data)
                win32print.WritePrinter(hprinter, GS + b'(' + b'k' + b'\x03\x00' + b'1Q0')
                win32print.WritePrinter(hprinter, b'\n')
                win32print.WritePrinter(hprinter, ESC + b'a' + b'\x00')

            win32print.WritePrinter(hprinter, b'\n\n\n')
            win32print.WritePrinter(hprinter, GS + b'V' + b'\x00')
            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
            messagebox.showinfo("Voltooid", f"Bon {bonnummer} opgeslagen en naar printer gestuurd!")

        finally:
            win32print.ClosePrinter(hprinter)
    except Exception as e:
        messagebox.showerror("Fout bij afdrukken", f"Kon de bon niet afdrukken.\n\nFoutdetails: {e}")


# ... existing code ...

def find_printer_usb_ids():
    """
    Helperfunctie om USB ID's van aangesloten printers te vinden.
    Roep aan via een debug-knop of via de Python console.
    """
    try:
        import usb.core
        devices = usb.core.find(find_all=True)

        printer_info = []
        for device in devices:
            try:
                vendor = f"0x{device.idVendor:04x}"
                product = f"0x{device.idProduct:04x}"
                try:
                    manufacturer = usb.util.get_string(device, device.iManufacturer)
                    prod_name = usb.util.get_string(device, device.iProduct)
                    info = f"Vendor: {vendor}, Product: {product}\n  {manufacturer} - {prod_name}"
                except:
                    info = f"Vendor: {vendor}, Product: {product}"
                printer_info.append(info)
            except:
                pass

        if printer_info:
            messagebox.showinfo("USB Apparaten", "\n\n".join(printer_info))
        else:
            messagebox.showinfo("USB Apparaten", "Geen USB-apparaten gevonden.")

    except ImportError:
        messagebox.showerror("Fout", "PyUSB niet geïnstalleerd. Installeer met: pip install pyusb")


# NIEUW: Functie om het afdrukvoorbeeld te tonen (triggered door Ctrl+P)
def show_print_preview(event=None):
    klant_data, order_items, temp_bonnummer = _get_current_order_data()
    if klant_data is None:  # Geen geldige data om te previewen
        return

    # Toon het afdrukvoorbeeld
    open_bon_viewer(
        root,
        klant_data,
        order_items,
        temp_bonnummer,
        menu_data,
        EXTRAS,
        app_settings,
        _save_and_print_from_preview  # Geef de callback mee
    )


def update_overzicht():
    global overzicht
    overzicht.delete(1.0, tk.END)
    overzicht.insert(tk.END, "Bestellingsoverzicht\n----------------------\n")
    totaal = 0
    for regel in bestelregels:
        lijn = f"{regel['categorie']} - {regel['product']} x{regel['aantal']} €{regel['prijs'] * regel['aantal']:.2f}"
        if 'extras' in regel:
            for key, val in regel['extras'].items():
                if key == 'half_half' and isinstance(val, list):
                    lijn += f"\n  {key}: pizza {val[0]} & {val[1]}"
                elif isinstance(val, list):
                    if val:
                        lijn += f"\n  {key}: {', '.join(map(str, val))}"
                elif val:
                    lijn += f"\n  {key}: {val}"
        if regel.get('opmerking'):
            lijn += f"\n  Opmerking: {regel['opmerking']}"
        overzicht.insert(tk.END, lijn + "\n")
        totaal += regel['prijs'] * regel['aantal']
    overzicht.insert(tk.END, f"\nTotaal: €{totaal:.2f}")


def update_right_overview(extra_keuze, product):
    global right_overview, ctrl
    right_overview.delete(1.0, tk.END)
    lines = [f"{product['naam']} x{ctrl['aantal'].get()} — €{product['prijs']:.2f}"]
    for k, v in extra_keuze.items():
        if k == 'half_half' and isinstance(v, list):
            if v and len(v) == 2:
                lines.append(f"  Half-Half: Pizza {v[0]} & {v[1]}")
        elif isinstance(v, list):
            if v:
                lines.append(f"  {k}: {', '.join(map(str, v))}")
        elif v:
            lines.append(f"  {k}: {v}")
    right_overview.insert(tk.END, "\n".join(lines))


def clear_opties():
    global ctrl, half1_var, half2_var

    ctrl["aantal"].set(1)
    ctrl["vlees"].set("")
    # Clear de lijsten van StringVar objecten, zodat ze opnieuw gevuld kunnen worden
    # bij het renderen van nieuwe opties
    for var in ctrl["bijgerecht_combos"]:
        if var: var.set("")  # Reset de waarde van elke StringVar in de lijst
    ctrl["bijgerecht_combos"].clear()

    for var in ctrl["saus_combos"]:
        if var: var.set("")  # Reset de waarde van elke StringVar in de lijst
    ctrl["saus_combos"].clear()

    for naam, var in ctrl["garnering"]:
        if var: var.set(False)  # Reset de waarde van elke BooleanVar in de lijst
    ctrl["garnering"].clear()

    ctrl["opmerking"].set("")
    if half1_var: half1_var.set("1")  # Stel een default in of leeg maken
    if half2_var: half2_var.set("2")  # Stel een default in of leeg maken


# ... existing code ...

def render_opties(product):
    global current_options_popup_window, state, EXTRAS, menu_data, ctrl, half1_var, half2_var, right_overview, bestelregels, producten_titel, opt_title, root

    if current_options_popup_window and current_options_popup_window.winfo_exists():
        current_options_popup_window.destroy()
        current_options_popup_window = None

    state["gekozen_product"] = product
    if not product:
        if opt_title:
            opt_title.config(text="Opties Product")
        if right_overview:
            right_overview.delete(1.0, tk.END)
        return

    clear_opties()

    options_window = tk.Toplevel(root, bg="#F9F9F9")
    options_window.title(f"Opties — {product['naam']}")
    options_window.transient(root)
    options_window.grab_set()

    width, height = 700, 540
    sw, sh = options_window.winfo_screenwidth(), options_window.winfo_screenheight()
    x, y = (sw // 2) - (width // 2), max(40, (sh // 2) - (height // 2))
    options_window.geometry(f"{width}x{height}+{x}+{y}")
    options_window.resizable(False, False)

    # Hoofdcontainer
    root_frame = tk.Frame(options_window, bg="#F9F9F9", padx=10, pady=8)
    root_frame.pack(fill=tk.BOTH, expand=True)

    # Bovenbalk: titel links, knoppen rechts (altijd zichtbaar)
    topbar = tk.Frame(root_frame, bg="#F9F9F9")
    topbar.pack(fill=tk.X, side=tk.TOP)

    title_lbl = tk.Label(topbar, text=f"{product['naam']}", font=("Arial", 12, "bold"), bg="#F9F9F9")
    title_lbl.pack(side=tk.LEFT, anchor="w")

    # Placeholder; functies worden later gedefinieerd maar knoppen alvast maken
    acties_frame = tk.Frame(topbar, bg="#F9F9F9")
    acties_frame.pack(side=tk.RIGHT, anchor="e")

    # Content eronder
    content = tk.Frame(root_frame, bg="#F9F9F9")
    content.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

    # Aantal
    tk.Label(content, text="Aantal:", font=("Arial", 10, "bold"), bg="#F9F9F9").grid(row=0, column=0, sticky="w")
    tk.Spinbox(content, from_=1, to=30, width=5, textvariable=ctrl["aantal"], font=("Arial", 10)).grid(
        row=0, column=1, sticky="w", pady=(0, 4)
    )

    cat_key = (state["categorie"] or "").lower()
    extras_cat = EXTRAS.get(cat_key, {}) if isinstance(EXTRAS, dict) else {}
    product_extras = {}
    if product.get('naam') and isinstance(extras_cat, dict) and product['naam'] in extras_cat:
        product_extras = extras_cat[product['naam']]
    elif isinstance(extras_cat, dict) and 'default' in extras_cat:
        product_extras = extras_cat['default']

    is_pizza = cat_key in ("small pizza's", "medium pizza's", "large pizza's")
    is_half_half = is_pizza and ("half" in product['naam'].lower())

    def section_label(parent, text):
        return tk.Label(parent, text=text, font=("Arial", 10, "bold"), bg="#F9F9F9")

    row_idx = 1

    # Half-half
    if is_half_half:
        section_label(content, "Half-half pizza: kies 2 nummers").grid(row=row_idx, column=0, columnspan=2, sticky="w",
                                                                       pady=(6, 4))
        row_idx += 1
        half_grid = tk.Frame(content, bg="#F9F9F9")
        half_grid.grid(row=row_idx, column=0, columnspan=2, sticky="w")
        row_idx += 1

        def create_pizza_number_grid(parent, selected_var, labeltext, default):
            frame = tk.LabelFrame(parent, text=labeltext, padx=6, pady=4, font=("Arial", 9, "bold"), bg="#F9F9F9",
                                  fg="#555")
            frame.pack(side=tk.LEFT, padx=8)
            btn_font = ("Arial", 9, "bold")
            max_num, cols = 49, 14
            for i in range(1, max_num + 1):
                btn = tk.Radiobutton(
                    frame, text=str(i), value=str(i), variable=selected_var,
                    font=btn_font, width=2, indicatoron=0, bg="#EDEBFE",
                    selectcolor="#FFDD44", relief=tk.RIDGE, padx=0, pady=0
                )
                r, c = (i - 1) // cols, (i - 1) % cols
                btn.grid(row=r, column=c, padx=1, pady=1, sticky="nsew")
            selected_var.set(str(default))
            return frame

        create_pizza_number_grid(half_grid, half1_var, "Pizza 1", default=1)
        create_pizza_number_grid(half_grid, half2_var, "Pizza 2", default=2)

    # Vlees (niet-pizza)
    if (not is_pizza) and isinstance(extras_cat, dict) and extras_cat.get('vlees'):
        section_label(content, "Vlees:").grid(row=row_idx, column=0, sticky="w", pady=(6, 2))
        vlees_frame = tk.Frame(content, bg="#F9F9F9")
        vlees_frame.grid(row=row_idx, column=1, sticky="w")
        for i, v in enumerate(extras_cat['vlees']):
            tk.Radiobutton(vlees_frame, text=v, variable=ctrl["vlees"], value=v, font=("Arial", 9), bg="#F9F9F9").grid(
                row=0, column=i, padx=3, sticky="w"
            )
        ctrl["vlees"].set(extras_cat['vlees'][0])
        row_idx += 1

    # Bijgerecht(en)
    bron_bijgerecht = product_extras.get('bijgerecht', extras_cat.get('bijgerecht', [])) if isinstance(extras_cat,
                                                                                                       dict) else []
    bijgerecht_aantal = product_extras.get('bijgerecht_aantal', 1) if isinstance(product_extras, dict) else 1
    if bron_bijgerecht:
        section_label(content, f"Bijgerecht{'en' if bijgerecht_aantal > 1 else ''}:").grid(row=row_idx, column=0,
                                                                                           sticky="w", pady=(6, 2))
        bg_frame = tk.Frame(content, bg="#F9F9F9")
        bg_frame.grid(row=row_idx, column=1, sticky="w")
        ctrl["bijgerecht_combos"].clear()
        for i in range(bijgerecht_aantal):
            var = tk.StringVar(value=bron_bijgerecht[0])
            cb = ttk.Combobox(bg_frame, textvariable=var, values=bron_bijgerecht, state="readonly", width=18,
                              font=("Arial", 9))
            cb.grid(row=i // 2, column=i % 2, padx=3, pady=2, sticky="w")
            ctrl["bijgerecht_combos"].append(var)
        row_idx += 1

    # Sauzen
    saus_key_in_extras = None
    if isinstance(product_extras, dict) and 'sauzen' in product_extras:
        saus_key_in_extras = 'sauzen'
    elif isinstance(product_extras, dict) and 'saus' in product_extras:
        saus_key_in_extras = 'saus'
    elif isinstance(extras_cat, dict) and 'sauzen' in extras_cat:
        saus_key_in_extras = 'sauzen'
    elif isinstance(extras_cat, dict) and 'saus' in extras_cat:
        saus_key_in_extras = 'saus'

    bron_sauzen = (product_extras.get(saus_key_in_extras, extras_cat.get(saus_key_in_extras, []))
                   if saus_key_in_extras and isinstance(extras_cat, dict) else [])
    sauzen_aantal = (product_extras.get('sauzen_aantal',
                                        extras_cat.get('sauzen_aantal', 1)) if isinstance(extras_cat, dict) else 1)

    if saus_key_in_extras and bron_sauzen and sauzen_aantal > 0:
        section_label(content, f"Sauzen ({sauzen_aantal}):").grid(row=row_idx, column=0, sticky="w", pady=(6, 2))
        s_frame = tk.Frame(content, bg="#F9F9F9")
        s_frame.grid(row=row_idx, column=1, sticky="w")
        ctrl["saus_combos"].clear()
        for i in range(sauzen_aantal):
            var = tk.StringVar(value=bron_sauzen[0])
            cb = ttk.Combobox(s_frame, textvariable=var, values=bron_sauzen, state="readonly", width=18,
                              font=("Arial", 9))
            cb.grid(row=i // 2, column=i % 2, padx=3, pady=2, sticky="w")
            ctrl["saus_combos"].append(var)
        row_idx += 1

    # Garnering
    bron_garnering = product_extras.get('garnering', extras_cat.get('garnering', {})) if isinstance(extras_cat,
                                                                                                    dict) else {}
    if bron_garnering:
        section_label(content, "Garnering:").grid(row=row_idx, column=0, sticky="nw", pady=(6, 2))
        g_frame = tk.Frame(content, bg="#F9F9F9")
        g_frame.grid(row=row_idx, column=1, sticky="w")
        ctrl["garnering"].clear()
        if isinstance(bron_garnering, list):
            # 3 kolommen
            for i, naam in enumerate(bron_garnering):
                var = tk.BooleanVar(value=False)
                tk.Checkbutton(g_frame, text=f"{naam}", variable=var, font=("Arial", 9), bg="#F9F9F9").grid(
                    row=i // 3, column=i % 3, padx=3, pady=2, sticky="w"
                )
                ctrl["garnering"].append((naam, var))
        elif isinstance(bron_garnering, dict):
            items = list(bron_garnering.items())
            # 3 kolommen
            for i, (naam, prijs) in enumerate(items):
                var = tk.BooleanVar(value=False)
                tk.Checkbutton(g_frame, text=f"{naam} (+€{prijs:.2f})", variable=var, font=("Arial", 9),
                               bg="#F9F9F9").grid(
                    row=i // 3, column=i % 3, padx=3, pady=2, sticky="w"
                )
                ctrl["garnering"].append((naam, var))
        row_idx += 1
    # Opmerking
    section_label(content, "Opmerking:").grid(row=row_idx, column=0, sticky="w", pady=(6, 2))
    tk.Entry(content, textvariable=ctrl["opmerking"], font=("Arial", 9), width=42).grid(
        row=row_idx, column=1, sticky="we", pady=(2, 2)
    )
    row_idx += 1

    # Overzicht live bijwerken
    def build_extra_keuze():
        extra = {}
        if is_half_half:
            extra['half_half'] = [half1_var.get(), half2_var.get()]
        if ctrl["vlees"].get():
            extra['vlees'] = ctrl["vlees"].get()
        if ctrl["bijgerecht_combos"]:
            extra['bijgerecht'] = ctrl["bijgerecht_combos"][0].get() if len(ctrl["bijgerecht_combos"]) == 1 else [
                v.get() for v in ctrl["bijgerecht_combos"]]
        if ctrl["saus_combos"] and saus_key_in_extras:
            extra[saus_key_in_extras] = [v.get() for v in ctrl["saus_combos"]]
        if ctrl["garnering"]:
            g_list = [naam for (naam, var) in ctrl["garnering"] if var.get()]
            if g_list:
                extra['garnering'] = g_list
        return extra

    def on_any_change(*_):
        p = state["gekozen_product"]
        if not p:
            return
        update_right_overview(build_extra_keuze(), p)

    ctrl["aantal"].trace_add("write", on_any_change)
    ctrl["vlees"].trace_add("write", on_any_change)
    for var in ctrl["bijgerecht_combos"]:
        var.trace_add("write", on_any_change)
    for _, var in ctrl["garnering"]:
        var.trace_add("write", on_any_change)
    if is_half_half:
        half1_var.trace_add("write", on_any_change)
        half2_var.trace_add("write", on_any_change)
    ctrl["opmerking"].trace_add("write", on_any_change)
    on_any_change()

    # Acties
    def voeg_toe_current():
        p = state["gekozen_product"]
        if not p:
            return
        extra = build_extra_keuze()

        if is_half_half:
            h1_val, h2_val = half1_var.get(), half2_var.get()
            valid_vals = {str(n) for n in range(1, 50)}
            if not (h1_val in valid_vals and h2_val in valid_vals):
                messagebox.showwarning("Waarschuwing", "Kies twee geldige pizza-nummers voor de Half-Half optie.")
                return
            if h1_val == h2_val:
                messagebox.showwarning("Waarschuwing", "Kies twee verschillende pizza-nummers voor de Half-Half optie.")
                return
            extra['half_half'] = [h1_val, h2_val]

        bron_bijgerecht_local = bron_bijgerecht
        if bron_bijgerecht_local and bijgerecht_aantal > 0:
            gekozen_bij = extra.get('bijgerecht', [])
            if isinstance(gekozen_bij, list):
                if len(gekozen_bij) != bijgerecht_aantal or any(not x for x in gekozen_bij):
                    messagebox.showwarning("Waarschuwing", f"Kies precies {bijgerecht_aantal} bijgerechten.")
                    return
            elif not gekozen_bij:
                messagebox.showwarning("Waarschuwing", "Kies een bijgerecht.")
                return

        if saus_key_in_extras and bron_sauzen and sauzen_aantal > 0:
            gekozen_sauzen = extra.get(saus_key_in_extras, [])
            if isinstance(gekozen_sauzen, list):
                if len(gekozen_sauzen) != sauzen_aantal or any(not x for x in gekozen_sauzen):
                    messagebox.showwarning("Waarschuwing", f"Kies precies {sauzen_aantal} sauzen.")
                    return
            elif not gekozen_sauzen:
                messagebox.showwarning("Waarschuwing", "Kies een saus.")
                return

        extras_price = 0
        if 'garnering' in extra and isinstance(bron_garnering, dict):
            for naam in extra['garnering']:
                extras_price += bron_garnering.get(naam, 0)

        final_price = p['prijs'] + extras_price

        bestelregels.append({
            'categorie': state["categorie"],
            'product': p['naam'],
            'aantal': ctrl["aantal"].get(),
            'prijs': final_price,
            'base_price': p['prijs'],
            'extras': extra,
            'opmerking': ctrl["opmerking"].get()
        })
        update_overzicht()
        messagebox.showinfo("Toegevoegd", f"{ctrl['aantal'].get()} x {p['naam']} toegevoegd.")
        on_options_window_close()

    def on_options_window_close():
        global current_options_popup_window
        state["gekozen_product"] = None
        if current_options_popup_window == options_window:
            current_options_popup_window = None
        options_window.destroy()
        if opt_title:
            opt_title.config(text="Opties Product")

    options_window.protocol("WM_DELETE_WINDOW", on_options_window_close)
    current_options_popup_window = options_window

    # Knoppen RECHTSBOVEN
    tk.Button(acties_frame, text="Toevoegen", command=voeg_toe_current,
              bg="#D1FFD1", width=14, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(acties_frame, text="Sluiten", command=on_options_window_close,
              bg="#FFADAD", width=10, font=("Arial", 10)).pack(side=tk.LEFT)

    # Kolombreedtes
    content.grid_columnconfigure(0, weight=0, minsize=170)
    content.grid_columnconfigure(1, weight=1, minsize=440)


# ... existing code ...

def render_producten():
    global product_grid_holder, state, menu_data
    cat = state["categorie"] or "-"
    items = state["producten"]
    columns = 5

    # Vaste lijst van accentkleuren, herhaald op volgorde
    kleuren_lijst = [
        "#FFDD44",  # Geel
        "#6BE3C1",  # Mint
        "#FF9A8B",  # Oranje/Rood
        "#84B6F4",  # Blauw
        "#FFD6E5",  # Pastel roze
    ]

    if product_grid_holder:
        for w in product_grid_holder.winfo_children():
            w.destroy()

    is_pizza_category = "pizza's" in (cat or "").lower()

    for i, product in enumerate(items):
        # Selecteer kleur per index
        bg_color = kleuren_lijst[i % len(kleuren_lijst)]

        card_frame = tk.Frame(product_grid_holder, bd=1, relief=tk.RAISED, padx=2, pady=2, bg=bg_color)
        card_frame.grid(row=i // columns, column=i % columns, padx=2, pady=2, sticky="nsew")
        card_frame.grid_propagate(False)

        if is_pizza_category:
            # Toon enkel het pizzanummer voor deze categorie
            pizza_number = product['naam'].split('.')[0].strip()
            btn = tk.Button(
                card_frame,
                text=pizza_number,
                font=("Arial", 14, "bold"),
                bg=bg_color,
                command=lambda p=product: render_opties(p)
            )
            btn.pack(fill="both", expand=True)
            card_frame.config(width=80, height=80)
        else:
            btn_text = f"{product['naam']}\n€{product['prijs']:.2f}"
            btn = tk.Button(
                card_frame,
                text=btn_text,
                font=("Arial", 10),
                bg=bg_color,
                command=lambda p=product: render_opties(p)
            )
            btn.pack(fill="both", expand=True)
            card_frame.config(width=120, height=60)

    for c in range(columns):
        if product_grid_holder:
            product_grid_holder.grid_columnconfigure(c, weight=1)


def on_select_categorie(category_name):
    global state, menu_data, producten_titel, current_options_popup_window
    print(f"Geselecteerde categorie: {category_name}")
    state["categorie"] = category_name
    state["producten"] = menu_data.get(category_name, [])
    print(f"Producten in categorie: {len(state['producten'])} items geladen.")
    state["gekozen_product"] = None

    # Sluit eventuele openstaande optievensters
    if current_options_popup_window and current_options_popup_window.winfo_exists():
        current_options_popup_window.destroy()
        current_options_popup_window = None

    clear_opties()  # Reset de control variabelen

    if producten_titel:
        producten_titel.config(text=category_name)

    # Zorg ervoor dat render_producten wordt aangeroepen na eventuele UI-updates
    # Dit wordt doorgaans beheerd door de Tkinter mainloop, maar update_idletasks kan helpen
    # bij het sneller weergeven van veranderingen in complexe layouts.
    # Echter, in de button command hoeft dit niet direct, Tkinter plant het zelf in.
    render_producten()


# NIEUWE FUNCTIE: Om de menu functionaliteit in het hoofdvenster te beheren
def setup_menu_interface():
    global product_grid_holder, producten_titel, opties_frame, right_overview, menu_main_panel, bestel_frame, dynamic_product_options_frame, opt_title  # <-- opt_title hier toegevoegd

    # HOOFDPANEEL VOOR MENU SELECTIE EN BESTELOVERZICHT
    menu_main_panel = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashpad=4)
    menu_main_panel.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    # LINKER ZIJDE VAN HOOFDPANEEL: CATEGORIEËN EN PRODUCTEN
    menu_selection_frame = tk.Frame(menu_main_panel)
    menu_main_panel.add(menu_selection_frame, minsize=800)

    # CATEGORIE KNOPPEN BOVENAAN
    category_buttons_frame = tk.Frame(menu_selection_frame, padx=4, pady=4, bg="#ECECEC")
    category_buttons_frame.pack(fill=tk.X)

    categories = list(menu_data.keys())
    categorie_kleuren = [
        "#B4DAF3", "#D1FFD1", "#FAF0C7", "#FFD1E1",
        "#D6EAF8", "#F7F7D7", "#F5CBA7", "#F9E79F"
    ]

    for i, cat_name in enumerate(categories):
        row_num = i // 8
        col_num = i % 8
        kleur = categorie_kleuren[i % len(categorie_kleuren)]
        btn = tk.Button(
            category_buttons_frame, text=cat_name.upper(),
            bg=kleur, fg="#295147",
            font=("Arial", 10, "bold"), padx=5, pady=5,
            command=lambda cn=cat_name: on_select_categorie(cn)
        )
        btn.grid(row=row_num, column=col_num, sticky="nsew", padx=2, pady=2)
        category_buttons_frame.grid_columnconfigure(col_num, weight=1)

    # PRODUCTEN GRID ONDER CATEGORIE KNOPPEN
    product_display_frame = tk.Frame(menu_selection_frame, padx=5, pady=5)
    product_display_frame.pack(fill=tk.BOTH, expand=True)

    producten_titel = tk.Label(product_display_frame, text="Selecteer Categorie", font=("Arial", 13, "bold"))
    producten_titel.pack(anchor="w")

    product_grid_holder = tk.Frame(product_display_frame)
    product_grid_holder.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    # RECHTER ZIJDE VAN HOOFDPANEEL: OPTIES EN HUIDIGE BESTELLING
    options_and_order_summary_frame = tk.Frame(menu_main_panel)
    menu_main_panel.add(options_and_order_summary_frame, minsize=400)

    # Besteloverzicht aan de bovenkant van de rechterkolom
    bestel_frame = tk.LabelFrame(options_and_order_summary_frame, text="Besteloverzicht", padx=10, pady=10)
    bestel_frame.pack(fill=tk.X, pady=(0, 10))
    # overzicht is een globale variabele die hier wordt geïnitialiseerd
    global overzicht
    overzicht = tk.Text(bestel_frame, height=10, width=40)
    overzicht.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
    update_overzicht()

    opt_title = tk.Label(options_and_order_summary_frame, text="Opties Product", font=("Arial", 13, "bold"))
    opt_title.pack(anchor="w", pady=(10, 0))

    opt_canvas = tk.Canvas(options_and_order_summary_frame, highlightthickness=0)
    opt_scroll = tk.Scrollbar(opt_canvas, orient=tk.VERTICAL, command=opt_canvas.yview)
    opties_frame = tk.Frame(opt_canvas)  # Dit is de frame die scrollbaar is

    # We moeten ervoor zorgen dat opties_frame de breedte van de canvas volgt
    def _on_opt_canvas_configure(event):
        opt_canvas.itemconfigure(opt_canvas_window_id, width=event.width)
        opt_canvas.config(scrollregion=opt_canvas.bbox("all"))

    opt_canvas_window_id = opt_canvas.create_window((0, 0), window=opties_frame, anchor="nw",
                                                    width=options_and_order_summary_frame.winfo_width())
    opt_canvas.configure(yscrollcommand=opt_scroll.set)

    opt_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    opt_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Bind _on_opt_canvas_configure aan het <Configure> event van de canvas zelf
    opt_canvas.bind("<Configure>", _on_opt_canvas_configure)

    # Huidige selectie - deze blijft bestaan
    right_overview_title = tk.Label(opties_frame, text="Huidige selectie", font=("Arial", 12, "bold"))
    right_overview_title.pack(anchor="w", pady=(8, 2))
    right_overview = tk.Text(opties_frame, height=8, width=40, font=("Arial", 10))
    right_overview.pack(fill=tk.X, padx=5, pady=2)

    # Dit frame blijft leeg, de dynamische opties worden nu in een Toplevel venster geplaatst
    dynamic_product_options_frame = tk.Frame(opties_frame)
    dynamic_product_options_frame.pack(fill=tk.BOTH, expand=True)

    # De initiële selectie van de categorie wordt nu uitgesteld tot na mainloop() start
    # if categories:
    #     on_select_categorie(categories[0])


def test_bestellingen_vullen():
    global bestelregels
    telefoon_entry.delete(0, tk.END)
    telefoon_entry.insert(0, "037757228")

    adres_entry.delete(0, tk.END)
    adres_entry.insert(0, "Brugstraat")

    nr_entry.delete(0, tk.END)
    nr_entry.insert(0, "12")

    postcode_var.set("9120 Vrasene")

    opmerkingen_entry.delete(0, tk.END)
    opmerkingen_entry.insert(0, "Dit is een testbestelling")

    bestelregels = [
        {
            'categorie': 'Large pizza\'s',
            'product': 'Margherita',
            'aantal': 2,
            'prijs': 20.00,
            'extras': {'garnering': ['Champignons', 'Extra kaas']}
        },
        {
            'categorie': 'schotels',
            'product': 'Natuur',
            'aantal': 1,
            'prijs': 20.00,
            'extras': {
                'vlees': 'Pita',
                'bijgerecht': 'Frieten',
                'sauzen': ['Looksaus', 'Samurai']
            }
        },
        {
            'categorie': 'mix schotels',
            'product': 'Napoli speciaal 2 personen',
            'aantal': 1,
            'prijs': 45.00,
            'extras': {
                'bijgerecht': ['Frieten', 'Brood'],
                'sauzen': ['Looksaus', 'Samurai', 'Cocktail', 'Andalouse']
            }
        },
        {
            'categorie': 'dranken',
            'product': 'Coca cola',
            'aantal': 3,
            'prijs': 2.50
        }
    ]
    update_overzicht()
    messagebox.showinfo("Test", "Testgegevens zijn ingevuld!")



# GUI opzet START
root = tk.Tk()
_initialize_app_variables(root)
root.title("Pizzeria Bestelformulier")
root.geometry("1400x900")
root.minsize(1200, 800)
root.configure(bg="#F3F2F1")  # Hoofdachtergrond

main_frame = tk.Frame(root, padx=10, pady=10, bg="#F3F2F1")
main_frame.pack(fill=tk.BOTH, expand=True)

klant_frame = tk.LabelFrame(main_frame, text="Klantgegevens", padx=10, pady=10, bg="#E1FFE1", fg="#26734D")
klant_frame.pack(fill=tk.X, pady=(0, 10))
tel_adres_frame = tk.Frame(klant_frame, bg="#E1FFE1")
tel_adres_frame.pack(fill=tk.X)

tk.Label(tel_adres_frame, text="Telefoon:", bg="#E1FFE1", fg="#215468").grid(row=0, column=0, sticky="w", padx=(0, 5))
telefoon_entry = tk.Entry(tel_adres_frame, width=15, bg="#F9F9FF")
telefoon_entry.grid(row=0, column=1, sticky="w")
telefoon_entry.bind("<Return>", lambda e: vul_klantgegevens_automatisch())
telefoon_entry.bind("<FocusOut>", lambda e: vul_klantgegevens_automatisch())

tk.Label(tel_adres_frame, text="Naam:", bg="#E1FFE1", fg="#215468").grid(row=0, column=2, sticky="w", padx=(0, 5))
naam_entry = tk.Entry(tel_adres_frame, width=17, bg="#FFFDE1")
naam_entry.grid(row=0, column=3, sticky="w", padx=(0, 10))

tk.Button(
    tel_adres_frame, text="Zoek",
    command=lambda: open_klanten_zoeken(root, telefoon_entry, naam_entry, adres_entry, nr_entry, postcode_var,
                                        postcodes),
    padx=5, bg="#FFD1E1", fg="#7C1230"
).grid(row=0, column=4, sticky="w", padx=(2, 15))

tk.Label(tel_adres_frame, text="Adres:", bg="#E1FFE1", fg="#215468").grid(row=0, column=5, sticky="w", padx=(0, 5))
adres_entry = tk.Entry(tel_adres_frame, width=25, bg="#F9F9FF")
adres_entry.grid(row=0, column=6, sticky="w", padx=(0, 15))
adres_entry.bind("<KeyRelease>", on_adres_entry)

lb_suggesties = tk.Listbox(tel_adres_frame, height=4, width=28, bg="#FFFDE1")
lb_suggesties.grid(row=1, column=6, sticky="w", padx=(0, 15))
lb_suggesties.bind("<<ListboxSelect>>", selectie_suggestie)
lb_suggesties.grid_remove()

tk.Label(tel_adres_frame, text="Nr:", bg="#E1FFE1", fg="#215468").grid(row=0, column=7, sticky="w", padx=(0, 5))
nr_entry = tk.Entry(tel_adres_frame, width=5, bg="#F9F9FF")
nr_entry.grid(row=0, column=8, sticky="w")

postcode_opmerking_frame = tk.Frame(klant_frame, bg="#E1FFE1")
postcode_opmerking_frame.pack(fill=tk.X, pady=(10, 0))
tk.Label(postcode_opmerking_frame, text="Postcode/Gemeente:", bg="#E1FFE1", fg="#215468").grid(row=0, column=0,
                                                                                               sticky="w", padx=(0, 5))
postcode_var = tk.StringVar(master=root)
postcode_var.set(postcodes[0])
postcode_optionmenu = tk.OptionMenu(postcode_opmerking_frame, postcode_var, *postcodes)
postcode_optionmenu.config(width=20, bg="#E1FFE1")
postcode_optionmenu.grid(row=0, column=1, sticky="w", padx=(0, 15))
tk.Label(postcode_opmerking_frame, text="Opmerking:", bg="#E1FFE1", fg="#215468").grid(row=0, column=2, sticky="w",
                                                                                       padx=(0, 5))
opmerkingen_entry = tk.Entry(postcode_opmerking_frame, width=30, bg="#FFFDE1")
opmerkingen_entry.grid(row=0, column=3, sticky="we")
postcode_opmerking_frame.grid_columnconfigure(3, weight=1)

setup_menu_interface()

knoppen_frame = tk.Frame(root, bg="#ECF5FF")
knoppen_frame.pack(fill=tk.X, pady=10)

tk.Button(knoppen_frame, text="Menu beheren", command=lambda: open_menu_management(root),
          bg="#D6EAF8", fg="#174F20", font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Extras beheren", command=lambda: open_extras_management(root),
          bg="#FCF3CF", fg="#B7950B", font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Klanten beheren", command=lambda: open_klant_management(root),
          bg="#D5F5E3", fg="#0E6655", font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Geschiedenis", command=lambda: open_geschiedenis(root, menu_data, EXTRAS, app_settings),
          bg="#F9E79F", fg="#B7950B", font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Rapportage", command=lambda: open_rapportage(root),
          bg="#E1E1FF", fg="#413E94", font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Backup/Restore", command=lambda: open_backup_tool(root),
          bg="#FADBD8", fg="#7C1230", font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Printer Instellingen", command=open_printer_settings,
          bg="#D6DBDF", fg="#626567", font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Koeriers", command=lambda: open_koeriers(root),
          bg="#D5F5E3", fg="#0E6655", font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(10, 0))
tk.Button(knoppen_frame, text="Bon Afdrukken/Opslaan", command=show_print_preview,
          bg="#ABEBC6", fg="#225722", font=("Arial", 11), padx=10, pady=5).pack(side=tk.RIGHT)
tk.Button(knoppen_frame, text="TEST", command=test_bestellingen_vullen, bg="#FFD700", fg="#867B17",
          font=("Arial", 10), padx=5, pady=2).pack(side=tk.RIGHT, padx=(0, 10))

root.bind("<Control-p>", show_print_preview)
root.bind("<Command-p>", show_print_preview)

categories = load_menu_categories()
if categories:
    root.after(100, lambda: on_select_categorie(categories[0]))


root.mainloop()
