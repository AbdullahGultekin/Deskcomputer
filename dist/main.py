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
from modules.klanten import open_klanten_zoeken
from modules.menu_management import open_menu_management
from modules.extras_management import open_extras_management
from modules.klant_management import open_klant_management
from modules.rapportage import open_rapportage
from modules.backup import open_backup_tool
from modules.voorraad import open_voorraad
from modules.bon_viewer import open_bon_viewer
from modules.klanten import open_klanten_zoeken

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

def get_pizza_num(naam):
    """Haalt het nummer voor de punt uit een pizzanaam."""
    if '.' in naam:
        return naam.split('.')[0].strip()
    return naam.strip()


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

def _save_and_print_from_preview(full_bon_text_for_print, address_for_qr=None, klant_data=None):
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
                # kleine ruimte
                win32print.WritePrinter(hprinter, b'\n')

                # Stijl voor besteldetails aanzetten (enkel vet)
                win32print.WritePrinter(hprinter, ESC + b'E' + b'\x01')  # Bold aan

                dot_line = ('.' * 42 + '\n').encode('cp858')  # stippellijn tussen items

                current_item_lines = []
                for line in bon_lines[details_idx + 1:details_end_idx]:
                    stripped_line = line.strip()

                    # Start van een nieuw item (bijv. "2x ...")
                    if stripped_line and (stripped_line[0].isdigit() and 'x' in line[:5]):
                        # Flush vorig item
                        if current_item_lines:
                            win32print.WritePrinter(hprinter, '\n'.join(current_item_lines).encode('cp858'))
                            # Stippellijn tussen producten
                            win32print.WritePrinter(hprinter, dot_line)
                            current_item_lines = []

                        # Hoofdregel van item
                        current_item_lines.append(line.replace('?', '€'))
                    else:
                        # Sla totaal/te betalen regels in details-blok over
                        if "TE BETALEN" in line or "Totaal" in line:
                            continue
                        # Subregel (bullet)
                        if stripped_line:
                            current_item_lines.append(f"> {stripped_line}")

                # Laatste item flushen (zonder extra stippellijn erna)
                if current_item_lines:
                    win32print.WritePrinter(hprinter, '\n'.join(current_item_lines).encode('cp858'))

                # Reset stijl
                win32print.WritePrinter(hprinter, ESC + b'E' + b'\x00')  # Bold uit

                # Eén duidelijke scheidingslijn na alle items
                win32print.WritePrinter(hprinter, ('\n' + '-' * 42 + '\n').encode('cp858'))
                # ==== HIER: Tarief-sectie printen ====
                tarief_start = -1
                sep_line = "-" * 42
                for i in range(details_end_idx, len(bon_lines)):
                    line = bon_lines[i]
                    if ("Tarief" in line and "Basis" in line and "BTW" in line and "Totaal" in line):
                        # neem scheidingslijn erboven mee als die exact '----------...'
                        tarief_start = i - 1 if i > 0 and bon_lines[i - 1].strip() == sep_line else i
                        break

                if tarief_start >= 0:
                    tarief_end = len(bon_lines)
                    for j in range(tarief_start + 1, len(bon_lines)):
                        if bon_lines[j].strip() == "" or bon_lines[j].startswith("Totaal"):
                            tarief_end = j
                            break
                    tarief_block = "\n".join(bon_lines[tarief_start:tarief_end]).encode('cp858', errors='replace')
                    win32print.WritePrinter(hprinter, tarief_block)
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
                win32print.WritePrinter(hprinter, GS + b'!' + b'\x11')
                win32print.WritePrinter(hprinter, totaal_line.encode('cp858', errors='replace'))
                win32print.WritePrinter(hprinter, b'\n')
                win32print.WritePrinter(hprinter, GS + b'!' + b'\x00')
                win32print.WritePrinter(hprinter, ESC + b'E' + b'\x00')
                win32print.WritePrinter(hprinter, ESC + b'a' + b'\x00')

            # HIER: Algemene opmerking printen (indien aanwezig) met de lokaal opgehaalde data
            if klant_data:
                klant_opm = (klant_data.get("opmerking") or "").strip()
                if klant_opm:
                    win32print.WritePrinter(hprinter, b'\n')
                    win32print.WritePrinter(hprinter, ESC + b'a' + b'\x01')  # Centreren
                    win32print.WritePrinter(hprinter, ESC + b'E' + b'\x01')  # Vet aan
                    win32print.WritePrinter(hprinter, GS + b'!' + b'\x01')  # Dubbele hoogte aan
                    opmerking_text = f"Opmerking:\n{klant_opm}"
                    win32print.WritePrinter(hprinter, opmerking_text.encode('cp858', errors='replace'))
                    win32print.WritePrinter(hprinter, b'\n')
                    win32print.WritePrinter(hprinter, GS + b'!' + b'\x00')  # Reset grootte
                    win32print.WritePrinter(hprinter, ESC + b'E' + b'\x00')  # Vet uit
                    win32print.WritePrinter(hprinter, ESC + b'a' + b'\x00')  # Links uitlijnen

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


def update_overzicht():
    global overzicht, bestelregels
    overzicht.delete(1.0, tk.END)
    overzicht.insert(tk.END, "Bestellingsoverzicht\n----------------------\n")

    # 1) Groepeer identieke regels (zelfde product + dezelfde extras + dezelfde opmerking)
    import json
    grouped = {}
    order_keys = []  # om volgorde te bewaren
    for item in bestelregels:
        extras_key = json.dumps(item.get('extras', {}), sort_keys=True, ensure_ascii=False)
        key = (item.get('categorie'), item.get('product'), extras_key, item.get('opmerking', ''))
        if key not in grouped:
            grouped[key] = {
                'categorie': item.get('categorie'),
                'product': item.get('product'),
                'aantal': 0,
                'prijs': float(item.get('prijs', 0.0)),
                'extras': item.get('extras', {}),
                'opmerking': item.get('opmerking', '')
            }
            order_keys.append(key)
        grouped[key]['aantal'] += int(item.get('aantal', 0))

    # 2) Nettere weergave met uitlijning
    totaal = 0.0
    line_no = 1
    name_col_width = 38  # kolombreedte voor naamsegment voordat de prijs komt

    for key in order_keys:
        item = grouped[key]
        aantal = item['aantal']
        totaal_regel = item['prijs'] * aantal
        totaal += totaal_regel

        # --- Logica voor weergavenaam (display_name), vergelijkbaar met bon_generator ---
        product_naam = item['product']
        cat = (item['categorie'] or '').lower()
        prefix = ""
        display_name = ""

        # Bepaal prefix op basis van categorie
        if "small" in cat:
            prefix = "Small"
        elif "medium" in cat:
            prefix = "Medium"
        elif "large" in cat:
            prefix = "Large"
        elif "grote-broodjes" in cat:
            prefix = "Groot"
        elif "klein-broodjes" in cat:
            prefix = "Klein"
        elif "turks-brood" in cat:
            prefix = "Turks"
        elif "durum" in cat:
            prefix = "Durum"
        elif "pasta" in cat:
            prefix = "Pasta"
        elif "schotel" in cat and "mix" not in cat:
            prefix = "Schotel"
        elif "vegetarisch broodjes" in cat:
            prefix = "Broodje"

        extras = item.get('extras', {})
        half_half = extras.get('half_half')
        is_mixschotel = "mix schotel" in cat

        # Logica voor pizza's
        if any(x in cat for x in ("pizza's", "pizza")):
            formaat = prefix if prefix else "Pizza"
            if half_half and isinstance(half_half, list) and len(half_half) == 2:
                display_name = f"{formaat} {half_half[0]}/{half_half[1]}"
            else:
                nummer = get_pizza_num(product_naam)
                display_name = f"{formaat} {nummer}"
        # Logica voor andere items
        else:
            if is_mixschotel:
                display_name = product_naam.strip()
            elif prefix:  # Gebruik prefix als die is ingesteld
                display_name = f"{prefix} {product_naam}".strip()
            else:  # Fallback voor dranken, desserts etc.
                display_name = product_naam.strip()

        header_left = f"[{line_no}] {display_name} x{aantal}"
        header_right = f"€{totaal_regel:.2f}"
        # afkappen indien te lang, laat ruimte voor prijs
        if len(header_left) > name_col_width:
            header_left = header_left[:name_col_width - 3] + "..."
        lijn = f"{header_left:<{name_col_width}} {header_right}"

        overzicht.insert(tk.END, lijn + "\n")

        # Extras onder bullets
        extras = item.get('extras', {}) or {}
        if extras:
            # half_half is al verwerkt in de hoofdnaam en wordt hier dus overgeslagen.
            # saus/sauzen/garnering/bijgerecht normaliseren
            for k in ['vlees', 'bijgerecht', 'saus', 'sauzen', 'garnering']:
                if k in extras and extras[k]:
                    val = extras[k]
                    if isinstance(val, list):
                        for v in val:
                            if v:
                                overzicht.insert(tk.END, f"  • {v}\n")
                    else:
                        overzicht.insert(tk.END, f"  • {val}\n")
            # toeslag expliciet tonen
            if 'sauzen_toeslag' in extras and extras['sauzen_toeslag']:
                try:
                    toeslag = float(extras['sauzen_toeslag'])
                    if toeslag > 0:
                        overzicht.insert(tk.END, f"  • Sauzen extra: €{toeslag:.2f}\n")
                except Exception:
                    pass

        # Opmerking
        if item.get('opmerking'):
            overzicht.insert(tk.END, f"  • Opmerking: {item['opmerking']}\n")

        line_no += 1

    overzicht.insert(tk.END, f"\nTotaal: €{totaal:.2f}")


def update_right_overview(extra_keuze, product):
    global right_overview, ctrl
    # Als het rechter preview-veld niet meer bestaat, niets doen
    if right_overview is None:
        return
    try:
        right_overview.delete(1.0, tk.END)
    except Exception:
        # Widget kan verwijderd zijn: veilig afbreken
        return

    base_line = f"{product['naam']} x{ctrl['aantal'].get()} — €{product['prijs']:.2f}"
    lines = [base_line]

    for k, v in extra_keuze.items():
        if k == 'half_half' and isinstance(v, list) and len(v) == 2:
            lines.append(f"  Half-Half: Pizza {v[0]} & {v[1]}")
        elif k == 'sauzen_toeslag':
            lines.append(f"  Sauzen extra: €{float(v):.2f}")
        elif isinstance(v, list) and v:
            lines.append(f"  {k}: {', '.join(map(str, v))}")
        elif v and k not in ('sauzen_toeslag',):
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

    width, height = 700, 560
    sw, sh = options_window.winfo_screenwidth(), options_window.winfo_screenheight()
    x, y = (sw // 2) - (width // 2), max(40, (sh // 2) - (height // 2))
    options_window.geometry(f"{width}x{height}+{x}+{y}")
    options_window.resizable(False, False)

    # Hoofdcontainer
    root_frame = tk.Frame(options_window, bg="#F9F9F9", padx=10, pady=8)
    root_frame.pack(fill=tk.BOTH, expand=True)

    # Bovenbalk
    topbar = tk.Frame(root_frame, bg="#F9F9F9")
    topbar.pack(fill=tk.X, side=tk.TOP)
    tk.Label(topbar, text=f"{product['naam']}", font=("Arial", 12, "bold"), bg="#F9F9F9").pack(side=tk.LEFT, anchor="w")
    acties_frame = tk.Frame(topbar, bg="#F9F9F9")
    acties_frame.pack(side=tk.RIGHT, anchor="e")

    # Content
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

    # ---------- Toggle helpers ----------
    def make_toggle_button(parent, text, on, width=10):
        btn = tk.Button(parent, text=text, width=width, anchor="w",
                        padx=6, pady=2, font=("Arial", 9),
                        fg="#111111", activeforeground="#111111",
                        relief=tk.RAISED, bd=1)
        style_on(btn, on)
        return btn

    def style_on(btn, on):
        if on:
            btn.configure(
                bg="#2B6CB0",
                activebackground="#265A99",
                fg="#EAF2FF",
                activeforeground="#FFFFFF",
                relief=tk.SOLID,
                bd=1,
                highlightthickness=0
            )
        else:
            btn.configure(
                bg="#F3F4F6",
                activebackground="#E9ECEF",
                fg="#111111",
                activeforeground="#111111",
                relief=tk.RAISED,
                bd=1,
                highlightthickness=0
            )

    # ---------- Half-half ----------
    row_idx = 1
    if is_half_half:
        section_label(content, "Half-half pizza: kies 2 nummers").grid(row=row_idx, column=0, columnspan=2, sticky="w",
                                                                       pady=(6, 4))
        row_idx += 1
        half_grid = tk.Frame(content, bg="#F9F9F9")
        half_grid.grid(row=row_idx, column=0, columnspan=2, sticky="w")
        row_idx += 1

        def create_pizza_number_grid(parent, selected_var, labeltext, default):
            frame = tk.LabelFrame(parent, text=labeltext, padx=6, pady=4, bg="#F9F9F9", fg="#555")
            frame.pack(side=tk.LEFT, padx=8)
            max_num, cols = 49, 10
            for i in range(1, max_num + 1):
                b = tk.Radiobutton(frame, text=str(i), value=str(i), variable=selected_var,
                                   width=2, indicatoron=0, bg="#EDEBFE",
                                   selectcolor="#FFDD44", relief=tk.RIDGE, padx=0, pady=0)
                r, c = (i - 1) // cols, (i - 1) % cols
                b.grid(row=r, column=c, padx=1, pady=1, sticky="nsew")
            selected_var.set(str(default))
            return frame

        create_pizza_number_grid(half_grid, half1_var, "Pizza 1", default=1)
        create_pizza_number_grid(half_grid, half2_var, "Pizza 2", default=2)

    # ---------- Vlees (single-select via toggles) ----------
    if (not is_pizza) and isinstance(extras_cat, dict) and extras_cat.get('vlees'):
        section_label(content, "Vlees:").grid(row=row_idx, column=0, sticky="w", pady=(6, 2))
        vlees_frame = tk.Frame(content, bg="#F9F9F9")
        vlees_frame.grid(row=row_idx, column=1, sticky="w")
        row_idx += 1

        vlees_buttons = {}
        default_vlees = extras_cat['vlees'][0]
        if not ctrl["vlees"].get():
            ctrl["vlees"].set(default_vlees)

        def pick_vlees(naam):
            ctrl["vlees"].set(naam)
            for k, b in vlees_buttons.items():
                style_on(b, k == naam)
            options_on_any_change()

        for i, v in enumerate(extras_cat['vlees']):
            r, c = divmod(i, 4)
            btn = make_toggle_button(vlees_frame, v, v == ctrl["vlees"].get(), width=6)
            btn.configure(command=lambda n=v: pick_vlees(n))
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="w")
            vlees_buttons[v] = btn

    # ---------- Bijgerecht(en) (toggle met limiet) ----------
    bron_bijgerecht = product_extras.get('bijgerecht', extras_cat.get('bijgerecht', [])) if isinstance(extras_cat,
                                                                                                       dict) else []
    bijgerecht_aantal = product_extras.get('bijgerecht_aantal', 1) if isinstance(product_extras, dict) else 1
    if bron_bijgerecht:
        section_label(content, f"Bijgerecht{'en' if bijgerecht_aantal > 1 else ''} ({bijgerecht_aantal}):").grid(
            row=row_idx, column=0, sticky="w", pady=(6, 2))
        bg_frame = tk.Frame(content, bg="#F9F9F9")
        bg_frame.grid(row=row_idx, column=1, sticky="w")
        row_idx += 1

        selected_bij = set()
        if ctrl["bijgerecht_combos"]:
            vals = [v.get() for v in ctrl["bijgerecht_combos"] if v.get()]
            selected_bij.update(vals[:bijgerecht_aantal])

        def toggle_bij(naam, btn):
            if naam in selected_bij:
                selected_bij.remove(naam)
                style_on(btn, False)
            else:
                if len(selected_bij) >= bijgerecht_aantal:
                    old = btn.cget("bg")
                    btn.configure(bg="#FFE8E8")
                    btn.after(180, lambda: btn.configure(bg=old))
                    return
                selected_bij.add(naam)
                style_on(btn, True)
            ctrl["bijgerecht_combos"].clear()
            if bijgerecht_aantal == 1:
                sv = tk.StringVar(value=next(iter(selected_bij), ""))
                ctrl["bijgerecht_combos"].append(sv)
            else:
                for v in list(selected_bij)[:bijgerecht_aantal]:
                    ctrl["bijgerecht_combos"].append(tk.StringVar(value=v))
            options_on_any_change()

        for i, naam in enumerate(bron_bijgerecht):
            r, c = divmod(i, 4)
            btn = make_toggle_button(bg_frame, naam, naam in selected_bij, width=6)
            btn.configure(command=lambda n=naam, b=btn: toggle_bij(n, b))
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="w")

    # ---------- Sauzen keys bepalen (voor overview helpers) ----------
    saus_key_in_extras = None
    if isinstance(product_extras, dict) and 'sauzen' in product_extras:
        saus_key_in_extras = 'sauzen'
    elif isinstance(product_extras, dict) and 'saus' in product_extras:
        saus_key_in_extras = 'saus'
    elif isinstance(extras_cat, dict) and 'sauzen' in extras_cat:
        saus_key_in_extras = 'sauzen'
    elif isinstance(extras_cat, dict) and 'saus' in extras_cat:
        saus_key_in_extras = 'saus'

    # ---------- Overzicht live bijwerken (VÓÓR sauzen sectie) ----------
    def build_extra_keuze():
        extra = {}
        if is_half_half:
            extra['half_half'] = [half1_var.get(), half2_var.get()]
        if ctrl["vlees"].get():
            extra['vlees'] = ctrl["vlees"].get()
        if ctrl["bijgerecht_combos"]:
            vals = [v.get() for v in ctrl["bijgerecht_combos"] if v.get()]
            if vals:
                extra['bijgerecht'] = vals if len(vals) > 1 else vals[0]
        if saus_key_in_extras:
            dup_sauzen = [v.get() for v in ctrl.get("saus_combos", []) if v.get()]
            if dup_sauzen:
                extra[saus_key_in_extras] = dup_sauzen
            toeslag = float(ctrl.get("_sauzen_toeslag_cache", 0.0) or 0.0)
            if toeslag > 0:
                extra['sauzen_toeslag'] = round(toeslag, 2)
        if ctrl["garnering"]:
            g_list = [naam for (naam, var) in ctrl["garnering"] if var.get()]
            if g_list:
                extra['garnering'] = g_list
        return extra

    def options_on_any_change(*_):
        p = state["gekozen_product"]
        if not p:
            return
        update_right_overview(build_extra_keuze(), p)

    ctrl["aantal"].trace_add("write", options_on_any_change)
    if is_half_half:
        half1_var.trace_add("write", options_on_any_change)
        half2_var.trace_add("write", options_on_any_change)
    ctrl["vlees"].trace_add("write", options_on_any_change)
    ctrl["opmerking"].trace_add("write", options_on_any_change)
    options_on_any_change()

    # ---------- Sauzen (toggle met limiet) ----------
    bron_sauzen = (product_extras.get(saus_key_in_extras, extras_cat.get(saus_key_in_extras, []))
                   if saus_key_in_extras and isinstance(extras_cat, dict) else [])
    sauzen_aantal = (product_extras.get('sauzen_aantal', extras_cat.get('sauzen_aantal', 1))
                     if isinstance(extras_cat, dict) else 1)

    def _dup_list_from_counts(counts):
        out = []
        for naam, cnt in counts.items():
            out.extend([naam] * max(0, cnt))
        return out

    if saus_key_in_extras and bron_sauzen and sauzen_aantal > 0:
        tk.Label(content, text=f"Sauzen (eerste {sauzen_aantal} inbegrepen, extra +€1,50/st):",
                 font=("Arial", 10, "bold"), bg="#F9F9F9").grid(row=row_idx, column=0, sticky="w", pady=(6, 2))
        s_frame = tk.Frame(content, bg="#F9F9F9")
        s_frame.grid(row=row_idx, column=1, sticky="w")
        row_idx += 1

        current_list = [v.get() for v in ctrl.get("saus_combos", []) if v.get()]
        counts = {naam: 0 for naam in bron_sauzen}
        for naam in current_list:
            if naam in counts:
                counts[naam] += 1

        total_var = tk.IntVar(value=sum(counts.values()))
        total_lbl = tk.Label(s_frame, text=f"Gekozen: {total_var.get()} (inclusief {sauzen_aantal} gratis)",
                             font=("Arial", 9, "bold"), bg="#F9F9F9", fg="#0D47A1")
        total_lbl.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        toeslag_lbl = tk.Label(s_frame, text="", font=("Arial", 9), bg="#F9F9F9", fg="#7A2E00")
        toeslag_lbl.grid(row=1, column=0, columnspan=4, sticky="w")

        EXTRA_SAUS_PRIJS = 1.50

        def refresh_total_and_ctrl():
            t = sum(counts.values())
            total_var.set(t)
            extra_cnt = max(0, t - sauzen_aantal)
            toeslag = round(extra_cnt * EXTRA_SAUS_PRIJS, 2)
            toeslag_lbl.config(
                text=(f"Extra sauzen: {extra_cnt} × €{EXTRA_SAUS_PRIJS:.2f} = €{toeslag:.2f}") if extra_cnt > 0 else "")
            total_lbl.config(text=f"Gekozen: {t} (inclusief {sauzen_aantal} gratis)")
            ctrl["saus_combos"].clear()
            dup_list = _dup_list_from_counts(counts)
            for naam in dup_list:
                ctrl["saus_combos"].append(tk.StringVar(value=naam))
            ctrl["_sauzen_toeslag_cache"] = toeslag
            options_on_any_change()

        def dec(naam, amt_lbl):
            if counts[naam] > 0:
                counts[naam] -= 1
                amt_lbl.config(text=str(counts[naam]))
                refresh_total_and_ctrl()

        def inc(naam, amt_lbl):
            counts[naam] += 1
            amt_lbl.config(text=str(counts[naam]))
            refresh_total_and_ctrl()

        for i, naam in enumerate(bron_sauzen):
            r, c = divmod(i, 2)
            row_base = r + 2
            col_base = c * 4
            btn_minus = tk.Button(s_frame, text="−", width=1, padx=1, pady=1, command=lambda n=naam: None, bg="#F3F4F6",
                                  relief=tk.RAISED, bd=1)
            name_lbl = tk.Label(s_frame, text=naam, bg="#F9F9F9", fg="#111111", font=("Arial", 9))
            amt_lbl = tk.Label(s_frame, text=str(counts[naam]), bg="#F9F9F9", fg="#0D47A1", width=2,
                               font=("Arial", 6, "bold"))
            btn_plus = tk.Button(s_frame, text="+", width=1, padx=1, pady=1, command=lambda n=naam: None, bg="#F3F4F6",
                                 relief=tk.RAISED, bd=1)

            btn_minus.configure(command=lambda n=naam, al=amt_lbl: dec(n, al))
            btn_plus.configure(command=lambda n=naam, al=amt_lbl: inc(n, al))

            btn_minus.grid(row=row_base, column=col_base + 0, padx=2, pady=2, sticky="w")
            name_lbl.grid(row=row_base, column=col_base + 1, padx=(2, 6), pady=2, sticky="w")
            amt_lbl.grid(row=row_base, column=col_base + 2, padx=2, pady=2, sticky="w")
            btn_plus.grid(row=row_base, column=col_base + 3, padx=(2, 8), pady=2, sticky="w")

        refresh_total_and_ctrl()

    # ---------- Garnering ----------
    bron_garnering = None
    if isinstance(product_extras, dict) and 'garnering' in product_extras:
        bron_garnering = product_extras['garnering']
    elif isinstance(extras_cat, dict) and 'garnering' in extras_cat:
        bron_garnering = extras_cat['garnering']

    if bron_garnering:
        if isinstance(bron_garnering, list):
            items = [(naam, 0.0) for naam in bron_garnering]
        elif isinstance(bron_garnering, dict):
            items = list(bron_garnering.items())
        else:
            items = []

        tk.Label(content, text="Garnering:", font=("Arial", 10, "bold"), bg="#F9F9F9").grid(row=row_idx, column=0,
                                                                                            sticky="nw", pady=(6, 2))
        g_frame = tk.Frame(content, bg="#F9F9F9")
        g_frame.grid(row=row_idx, column=1, sticky="w")
        row_idx += 1

        selected_g = set([naam for (naam, var) in ctrl.get("garnering", []) if var.get()])
        ctrl["garnering"].clear()

        def toggle_g(naam, btn):
            if naam in selected_g:
                selected_g.remove(naam)
                style_on(btn, False)
            else:
                selected_g.add(naam)
                style_on(btn, True)
            ctrl["garnering"].clear()
            for nm, _pr in items:
                var = tk.BooleanVar(value=(nm in selected_g))
                ctrl["garnering"].append((nm, var))
            options_on_any_change()

        for i, (naam, prijs) in enumerate(items):
            r, c = divmod(i, 5)
            # Toon enkel de naam, geen prijs
            label = f"{naam}"
            btn = make_toggle_button(g_frame, label, naam in selected_g, width=6)
            btn.configure(command=lambda n=naam, b=btn: toggle_g(n, b))
            btn.grid(row=r, column=c, padx=2, pady=2, sticky="w")

        if not ctrl["garnering"]:
            for nm, _pr in items:
                var = tk.BooleanVar(value=(nm in selected_g))
                ctrl["garnering"].append((nm, var))

    # Opmerking
    tk.Label(content, text="Opmerking:", font=("Arial", 10, "bold"), bg="#F9F9F9").grid(row=row_idx, column=0,
                                                                                        sticky="w", pady=(6, 2))
    tk.Entry(content, textvariable=ctrl["opmerking"], font=("Arial", 9), width=42).grid(row=row_idx, column=1,
                                                                                        sticky="we", pady=(2, 2))
    row_idx += 1

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

        if 'bijgerecht' in extra:
            gekozen_bij = extra.get('bijgerecht', [])
            if isinstance(gekozen_bij, list):
                if bron_bijgerecht and bijgerecht_aantal > 0:
                    if len(gekozen_bij) != bijgerecht_aantal or any(not x for x in gekozen_bij):
                        messagebox.showwarning("Waarschuwing", f"Kies precies {bijgerecht_aantal} bijgerechten.")
                        return
            elif not gekozen_bij and bron_bijgerecht:
                messagebox.showwarning("Waarschuwing", "Kies een bijgerecht.")
                return

        extras_price = 0.0
        if 'garnering' in extra and isinstance(bron_garnering, dict):
            for naam in extra['garnering']:
                extras_price += float(bron_garnering.get(naam, 0.0))
        extras_price += float(extra.get('sauzen_toeslag', 0.0))

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
    tk.Button(acties_frame, text="Toevoegen", command=voeg_toe_current, bg="#D1FFD1", width=14,
              font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(acties_frame, text="Sluiten", command=on_options_window_close, bg="#FFADAD", width=10,
              font=("Arial", 10)).pack(side=tk.LEFT)

    # Kolombreedtes
    content.grid_columnconfigure(0, weight=0, minsize=170)
    content.grid_columnconfigure(1, weight=1, minsize=440)

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
    global state, menu_data, producten_titel, current_options_popup_window, product_grid_holder
    print(f"Geselecteerde categorie: {category_name}")
    # Herlaad menu_data voor de zekerheid en zorg dat we de exacte sleutel gebruiken
    if category_name not in menu_data:
        try:
            with open("menu.json", "r", encoding="utf-8") as f:
                menu_data = json.load(f)
        except Exception as e:
            print(f"Kon menu.json niet herladen: {e}")
    # Zet state en producten
    state["categorie"] = category_name
    state["producten"] = list(menu_data.get(category_name, []))
    print(f"Producten in categorie: {len(state['producten'])} items geladen.")
    state["gekozen_product"] = None

    # Sluit eventuele openstaande optievensters
    if current_options_popup_window and current_options_popup_window.winfo_exists():
        current_options_popup_window.destroy()
        current_options_popup_window = None

    clear_opties()  # Reset de control variabelen

    # Verzeker dat de UI-referenties bestaan voordat we ze updaten
    if producten_titel and producten_titel.winfo_exists():
        producten_titel.config(text=category_name)
    # Render altijd opnieuw
    if product_grid_holder and product_grid_holder.winfo_exists():
        render_producten()
    else:
        # Als het grid nog niet klaar is, plan render nadat mainloop de UI heeft gebouwd
        root.after(50, render_producten)


def setup_menu_interface():
    global product_grid_holder, producten_titel, menu_main_panel, bestel_frame, menu_selection_frame, overzicht

    # Hoofdpaneel (links: menu/producten, rechts: besteloverzicht)
    menu_main_panel = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashpad=4)
    menu_main_panel.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    # ========== LINKERKANT ==========
    menu_selection_frame = tk.Frame(menu_main_panel)
    menu_main_panel.add(menu_selection_frame, minsize=950)

    preferred_order = app_settings.get("category_order", [])

    def get_ordered_categories():
        cats = list(menu_data.keys())
        ordered = [c for c in preferred_order if c in cats]
        ordered += [c for c in cats if c not in ordered]
        return ordered

    # Header
    header_bar = tk.Frame(menu_selection_frame, padx=4, pady=4, bg="#ECECEC")
    header_bar.pack(fill=tk.X)
    tk.Label(header_bar, text="Categorieën", font=("Arial", 11, "bold"), bg="#ECECEC").pack(side=tk.LEFT)
    tk.Label(header_bar, text="Kolommen:", bg="#ECECEC").pack(side=tk.LEFT, padx=(12, 4))
    category_columns_var = tk.IntVar(master=header_bar, value=5)
    tk.Spinbox(header_bar, from_=1, to=10, width=3, textvariable=category_columns_var).pack(side=tk.LEFT)

    def open_cat_order_dialog():
        top = tk.Toplevel(menu_selection_frame)
        top.title("Categorie-volgorde")
        top.transient(menu_selection_frame)
        top.grab_set()

        lb = tk.Listbox(top, height=16, exportselection=False)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        for c in get_ordered_categories():
            lb.insert(tk.END, c)

        btns = tk.Frame(top)
        btns.pack(side=tk.RIGHT, fill=tk.Y, padx=6, pady=6)

        def _move(delta):
            sel = lb.curselection()
            if not sel:
                return
            i = sel[0]
            j = i + delta
            if 0 <= j < lb.size():
                val = lb.get(i)
                lb.delete(i)
                lb.insert(j, val)
                lb.selection_clear(0, tk.END)
                lb.selection_set(j)

        tk.Button(btns, text="Omhoog", command=lambda: _move(-1)).pack(fill=tk.X, pady=2)
        tk.Button(btns, text="Omlaag", command=lambda: _move(1)).pack(fill=tk.X, pady=2)

        def _save():
            app_settings["category_order"] = list(lb.get(0, tk.END))
            if save_json_file(SETTINGS_FILE, app_settings):
                render_category_buttons()
            top.destroy()

        tk.Button(btns, text="Opslaan", bg="#D1FFD1", command=_save).pack(fill=tk.X, pady=(8, 2))
        tk.Button(btns, text="Sluiten", bg="#FFADAD", command=top.destroy).pack(fill=tk.X)

    tk.Button(header_bar, text="Volgorde aanpassen", command=open_cat_order_dialog, bg="#E1E1FF").pack(side=tk.LEFT,
                                                                                                       padx=8)

    # Categorieknoppen
    category_buttons_frame = tk.Frame(menu_selection_frame, padx=4, pady=4, bg="#ECECEC")
    category_buttons_frame.pack(fill=tk.X)
    categorie_kleuren = ["#B4DAF3", "#D1FFD1", "#FAF0C7", "#FFD1E1", "#D6EAF8", "#F7F7D7", "#F5CBA7", "#F9E79F"]

    def render_category_buttons():
        for w in category_buttons_frame.winfo_children():
            w.destroy()
        for c in range(20):
            try:
                category_buttons_frame.grid_columnconfigure(c, weight=0)
            except:
                pass
        cats = get_ordered_categories()
        cols = max(1, int(category_columns_var.get() or 1))
        for i, cat_name in enumerate(cats):
            r, c = divmod(i, cols)
            kleur = categorie_kleuren[i % len(categorie_kleuren)]
            tk.Button(
                category_buttons_frame, text=cat_name.upper(),
                bg=kleur, fg="#295147", font=("Arial", 10, "bold"), padx=5, pady=5,
                command=lambda cn=cat_name: on_select_categorie(cn)
            ).grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
            category_buttons_frame.grid_columnconfigure(c, weight=1)

    render_category_buttons()
    category_columns_var.trace_add("write", lambda *_: render_category_buttons())

    # Productgrid
    product_display_frame = tk.Frame(menu_selection_frame, padx=5, pady=5)
    product_display_frame.pack(fill=tk.BOTH, expand=True)

    producten_titel = tk.Label(product_display_frame, text="Selecteer Categorie", font=("Arial", 13, "bold"))
    producten_titel.pack(anchor="w")

    product_grid_holder = tk.Frame(product_display_frame)
    product_grid_holder.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    # ========== RECHTERKANT: BESTELOVERZICHT ==========
    right_panel = tk.Frame(menu_main_panel)
    menu_main_panel.add(right_panel, minsize=400)

    bestel_frame = tk.LabelFrame(right_panel, text="Besteloverzicht", padx=10, pady=10)
    bestel_frame.pack(fill=tk.BOTH, expand=True)

    overzicht = tk.Text(bestel_frame, height=10, width=40)
    overzicht.pack(fill=tk.BOTH, expand=True, pady=(0, 6))  # mee-uitrekken

    # Duidelijke regel-selectie in het besteloverzicht
    overzicht.tag_configure("sel_line", background="#FFF3CD")  # zacht geel
    overzicht.tag_configure("sel_line_text", foreground="#0D47A1")  # donkerblauw tekst

    def _clear_line_highlight():
        overzicht.tag_remove("sel_line", "1.0", tk.END)
        overzicht.tag_remove("sel_line_text", "1.0", tk.END)

    def _highlight_line(line_index_str):
        # line_index_str zoals "12.0"
        line_start = f"{line_index_str.split('.')[0]}.0"
        line_end = f"{line_index_str.split('.')[0]}.end"
        overzicht.tag_add("sel_line", line_start, line_end)
        overzicht.tag_add("sel_line_text", line_start, line_end)

    def _on_click_select_line(event):
        try:
            index = overzicht.index(f"@{event.x},{event.y}")
            _clear_line_highlight()
            _highlight_line(index)
        except Exception:
            pass

    def _on_key_move_selection(event):
        # pijltjestoetsen: hou selectie op huidige cursorregel
        try:
            overzicht.after_idle(lambda: (_clear_line_highlight(),
                                          _highlight_line(overzicht.index(tk.INSERT))))
        except Exception:
            pass

    overzicht.bind("<Button-1>", _on_click_select_line)
    overzicht.bind("<Up>", _on_key_move_selection)
    overzicht.bind("<Down>", _on_key_move_selection)
    overzicht.bind("<Home>", _on_key_move_selection)
    overzicht.bind("<End>", _on_key_move_selection)

    # Bewerkingknoppen
    btns = tk.Frame(bestel_frame)
    btns.pack(fill=tk.X)

                                                                               

    def _get_selected_indices_from_text():
        try:
            index = overzicht.index("insert")
            line_no = int(index.split('.')[0]) - 2
            if line_no >= 0:
                line_text = overzicht.get(f"{int(index.split('.')[0])}.0", f"{int(index.split('.')[0])}.end")
                if line_text.startswith('['):
                    shown = int(line_text.split(']')[0][1:])
                    return [shown - 1]
            return []
        except:
            return []

    def verwijder_geselecteerd():
        idxs = _get_selected_indices_from_text()
        if not idxs:
            messagebox.showinfo("Selectie", "Plaats de cursor op de regel die je wilt verwijderen.")
            return
        for i in sorted(idxs, reverse=True):
            if 0 <= i < len(bestelregels):
                bestelregels.pop(i)
        update_overzicht()

    def wis_alles():
        if bestelregels and messagebox.askyesno("Bevestigen", "Alle items uit de bestelling verwijderen?"):
            bestelregels.clear()
            update_overzicht()

    def verplaats_omhoog():
        idxs = _get_selected_indices_from_text()
        if idxs:
            i = idxs[0]
            if 0 < i < len(bestelregels):
                bestelregels[i - 1], bestelregels[i] = bestelregels[i], bestelregels[i - 1]
                update_overzicht()

    def verplaats_omlaag():
        idxs = _get_selected_indices_from_text()
        if idxs:
            i = idxs[0]
            if 0 <= i < len(bestelregels) - 1:
                bestelregels[i + 1], bestelregels[i] = bestelregels[i], bestelregels[i + 1]
                update_overzicht()

    def wijzig_aantal():
        idxs = _get_selected_indices_from_text()
        if not idxs:
            messagebox.showinfo("Selectie", "Plaats de cursor op de regel die je wilt wijzigen.")
            return
        i = idxs[0]
        if 0 <= i < len(bestelregels):
            nieuw = simpledialog.askinteger("Aantal wijzigen", "Nieuw aantal:", minvalue=1, maxvalue=99,
                                            initialvalue=bestelregels[i]['aantal'])
            if nieuw:
                bestelregels[i]['aantal'] = int(nieuw)
                update_overzicht()

    tk.Button(btns, text="Verwijder regel", command=verwijder_geselecteerd, bg="#FFADAD").pack(side=tk.LEFT)
    tk.Button(btns, text="Alles wissen", command=wis_alles, bg="#FFD1D1").pack(side=tk.LEFT, padx=6)
    tk.Button(btns, text="Omhoog", command=verplaats_omhoog, bg="#E1E1FF").pack(side=tk.LEFT, padx=(12, 2))
    tk.Button(btns, text="Omlaag", command=verplaats_omlaag, bg="#E1E1FF").pack(side=tk.LEFT, padx=2)
    tk.Button(btns, text="Wijzig aantal", command=wijzig_aantal, bg="#D1FFD1").pack(side=tk.RIGHT)

    overzicht.config(cursor="arrow")
    update_overzicht()


# GUI opzet START
root = tk.Tk()
_initialize_app_variables(root)
root.title("Pizzeria Bestelformulier")
root.geometry("1400x900")
root.minsize(1200, 800)
root.configure(bg="#F3F2F1")

# Eén hoofd-Notebook
app_tabs = ttk.Notebook(root)
app_tabs.pack(fill=tk.BOTH, expand=True)

# ========== TAB: BESTELLEN ==========
bestellen_tab = tk.Frame(app_tabs, bg="#F3F2F1")
app_tabs.add(bestellen_tab, text="Bestellen")

# Hoofdcontainer in Bestellen
main_frame = tk.Frame(bestellen_tab, padx=10, pady=10, bg="#F3F2F1")
main_frame.pack(fill=tk.BOTH, expand=True)

# Klantgegevens
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

# Menu/producten UI
setup_menu_interface()

# ========== TABS VOOR OVERIGE MODULES (LAZY LOAD) ==========
tabs_map = {}


def add_tab(title):
    frame = tk.Frame(app_tabs)
    app_tabs.add(frame, text=title)
    tabs_map[title] = {"frame": frame, "loaded": False}
    return frame


# Gewenste volgorde: Koeriers direct na Bestellen, daarna Menu Management, dan overige
koeriers_frame_tab = add_tab("Koeriers")
menu_mgmt_frame_tab = add_tab("Menu Management")
extras_frame = add_tab("Extras")
klanten_frame_tab = add_tab("Klanten")
geschiedenis_frame_tab = add_tab("Geschiedenis")
rapportage_frame_tab = add_tab("Rapportage")
backup_frame_tab = add_tab("Backup/Restore")
voorraad_frame_tab = add_tab("Voorraad")


def load_tab_content(title):
    info = tabs_map.get(title)
    if not info or info["loaded"]:
        return
    parent = info["frame"]
    try:
        if title == "Extras":
            open_extras_management(parent)
        elif title == "Klanten":
            open_klant_management(parent)
        elif title == "Geschiedenis":
            open_geschiedenis(parent, menu_data, EXTRAS, app_settings)
        elif title == "Rapportage":
            open_rapportage(parent)
        elif title == "Backup/Restore":
            open_backup_tool(parent)
        elif title == "Koeriers":
            open_koeriers(parent)
        elif title == "Voorraad":
            open_voorraad(parent)
        elif title == "Menu Management":
            open_menu_management(parent)
        info["loaded"] = True
    except Exception:
        info["loaded"] = True


def on_tab_changed(event):
    current = event.widget.select()
    idx = event.widget.index(current)
    title = event.widget.tab(idx, "text")
    load_tab_content(title)


app_tabs.bind("<<NotebookTabChanged>>", on_tab_changed)



# Startcategorie
categories = load_menu_categories()
if categories:
    root.after(100, lambda: on_select_categorie(categories[0]))

root.mainloop()

