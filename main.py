import tkinter as tk
from tkinter import messagebox, Toplevel, scrolledtext, ttk, simpledialog
import json
import random
import datetime
from datetime import timedelta
import os
import csv
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
from modules.bon_viewer import open_bon_viewer  # <-- NIEUW: Importeer de bon_viewer

# Globale variabelen initialisatie (niet-Tkinter gerelateerd)
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
        "telefoon": telefoon,
        "adres": adres_entry.get(),
        "nr": nr_entry.get(),
        "postcode_gemeente": postcode_var.get(),
        "opmerking": ctrl["opmerking"].get()
    }

    # Bonnummer wordt pas bij opslaan definitief, maar we hebben een tijdelijke nodig voor preview
    temp_bonnummer = database.get_next_bonnummer(peek_only=True)  # Aangenomen dat database.py een peek_only optie heeft

    return klant_data, list(bestelregels), temp_bonnummer


# REFACtORED: bestelling_opslaan zal nu alleen opslaan en de UI opschonen, NIET direct printen of preview tonen
def bestelling_opslaan():
    global bestelregels

    klant_data, order_items, _ = _get_current_order_data()
    if klant_data is None:  # Geen geldige data verzameld
        return False, None  # Geef aan dat opslaan mislukt is en geen bontekst

    telefoon = klant_data["telefoon"]
    klant_naam_of_opmerking = ctrl["opmerking"].get() if ctrl[
        "opmerking"].get() else telefoon

    voeg_klant_toe_indien_nodig(
        telefoon=klant_data["telefoon"],
        adres=klant_data["adres"],
        nr=klant_data["nr"],
        postcode_plaats=klant_data["postcode_gemeente"],
        naam_of_opmerking=klant_naam_of_opmerking
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

        messagebox.showinfo("Bevestiging", "Bestelling succesvol opgeslagen!")

        # UI opschonen na bestelling
        telefoon_entry.delete(0, tk.END)
        adres_entry.delete(0, tk.END)
        nr_entry.delete(0, tk.END)
        postcode_var.set(postcodes[0])
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


# NIEUW: Callback functie die door bon_viewer wordt aangeroepen om op te slaan en af te drukken
def _save_and_print_from_preview(full_bon_text_for_print):
    # Eerst opslaan
    success, bonnummer = bestelling_opslaan()
    if not success:
        messagebox.showerror("Fout", "Bestelling kon niet worden opgeslagen. Afdruk geannuleerd.")
        return

    # Daarna afdrukken
    tmp = None  # Initialiseer tmp
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
        tmp.write(full_bon_text_for_print)
        tmp.close()

        printer_name = app_settings.get("thermal_printer_name", "Default")
        printed_successfully = False

        if os.name == "nt":  # Voor Windows
            if printer_name and printer_name.lower() != "default":
                try:
                    # De 'print' command is zeer basic en werkt niet altijd betrouwbaar.
                    # Sommige moderne printers reageren hier niet goed op.
                    # Het werkt alleen voor tekstbestanden.
                    # Check=True om een CalledProcessError te krijgen als het commando mislukt.
                    subprocess.run(['print', '/d:' + printer_name, tmp.name], check=True, shell=True)
                    printed_successfully = True
                    messagebox.showinfo("Print", f"Bon {bonnummer} naar '{printer_name}' gestuurd.")
                except subprocess.CalledProcessError as e:
                    # Dit betekent dat het 'print' commando wel is uitgevoerd, maar een fout gaf.
                    messagebox.showwarning("Printfout (Windows)",
                                           f"Kon niet direct naar '{printer_name}' printen via 'print' commando. "
                                           f"Mogelijke oorzaken: printernaam onjuist, printer niet klaar, of driverprobleem. "
                                           f"Fout: {e.stderr.decode().strip() if e.stderr else e.returncode}. "
                                           f"Wordt nu geprobeerd naar de standaardprinter te sturen via Notepad.")
                except FileNotFoundError:
                    # Dit kan gebeuren als 'print' zelf niet gevonden wordt, of de printer niet bestaat als 'file'.
                    messagebox.showwarning("Printfout (Windows)",
                                           f"Het 'print' commando of de opgegeven printer '{printer_name}' is niet gevonden/toegankelijk. "
                                           f"Controleer de printernaam en systeeminstellingen. "
                                           f"Wordt nu geprobeerd naar de standaardprinter te sturen via Notepad.")
                except Exception as e:
                    messagebox.showwarning("Printfout (Windows)",
                                           f"Een onverwachte fout trad op bij het printen naar '{printer_name}': {e}. "
                                           f"Wordt nu geprobeerd naar de standaardprinter te sturen via Notepad.")

            if not printed_successfully:
                # Terugval naar notepad.exe /p, wat altijd naar de standaardprinter print.
                messagebox.showwarning("Print naar standaardprinter (Windows)",
                                       f"De bon wordt nu naar uw standaardprinter gestuurd via Notepad. "
                                       f"Als dit niet de gewenste thermische printer is, stel deze dan in als uw standaardprinter in Windows-instellingen, of controleer de ingevoerde printernaam.")
                subprocess.Popen(["notepad.exe", "/p", tmp.name], shell=True)
                messagebox.showinfo("Print", f"Bon {bonnummer} naar standaardprinter gestuurd.")

        else:  # Voor Linux/macOS
            try:
                if printer_name and printer_name.lower() != "default":
                    subprocess.run(["lpr", "-P", printer_name, tmp.name], check=True, capture_output=True,
                                   text=True)  # check=True om fouten te vangen
                    messagebox.showinfo("Print", f"Bon {bonnummer} naar '{printer_name}' gestuurd.")
                else:
                    subprocess.run(["lpr", tmp.name], check=True, capture_output=True, text=True)
                    messagebox.showinfo("Print", f"Bon {bonnummer} naar standaardprinter gestuurd.")
                printed_successfully = True
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Printfout (Linux/macOS)",
                                     f"Kon niet printen met 'lpr'. Controleer printer '{printer_name}' (indien gespecificeerd) en CUPS configuratie. "
                                     f"Foutmelding: {e.stderr.strip()}")
            except FileNotFoundError:
                messagebox.showerror("Printfout (Linux/macOS)",
                                     "Het 'lpr' commando is niet gevonden. Zorg dat CUPS is geïnstalleerd en geconfigureerd.")
            except Exception as e:
                messagebox.showerror("Printfout (Linux/macOS)", f"Een onverwachte fout trad op bij het printen: {e}.")

    except Exception as e:  # Algemene catch voor problemen met tijdelijk bestand of initialisatie
        messagebox.showerror("Print",
                             f"Printen mislukt: {e}\nControleer of de printer is aangesloten en geconfigureerd.")
    finally:
        if tmp and os.path.exists(tmp.name):
            os.unlink(tmp.name)  # Zorg ervoor dat het tijdelijke bestand wordt verwijderd


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


def render_opties(product):
    global current_options_popup_window, state, EXTRAS, menu_data, ctrl, half1_var, half2_var, right_overview, bestelregels, producten_titel, opt_title

    # Sluit een eventueel bestaand pop-up venster voor opties
    if current_options_popup_window and current_options_popup_window.winfo_exists():
        current_options_popup_window.destroy()
        current_options_popup_window = None

    state["gekozen_product"] = product
    if not product:
        # Dit deel werkt de titel in het hoofdvenster bij als er geen product is gekozen
        if opt_title:  # Controleer of opt_title is geïnitialiseerd
            opt_title.config(text="Opties Product")
        if right_overview:  # Controleer of right_overview is geïnitialiseerd
            right_overview.delete(1.0, tk.END)
        return

    # Reset de control variabelen voordat het nieuwe venster wordt geopend
    clear_opties()

    # Creëer een nieuw Toplevel venster voor de productopties
    options_window = tk.Toplevel(root)
    options_window.title(f"Opties voor {product['naam']}")
    options_window.transient(root)  # Zorgt ervoor dat het pop-up venster boven het hoofdvenster blijft
    options_window.grab_set()  # Maakt het venster modaal (blokkeert interactie met het hoofdvenster)
    options_window.geometry("550x600")  # Stel een standaardgrootte in
    options_window.resizable(True, True)

    # Dwing Tkinter om het venster te updaten zodat winfo_width() een correcte waarde geeft
    options_window.update_idletasks()

    # Creëer een scrollbaar gebied in het Toplevel venster
    opt_canvas_toplevel = tk.Canvas(options_window, highlightthickness=0)
    opt_scroll_toplevel = tk.Scrollbar(opt_canvas_toplevel, orient=tk.VERTICAL, command=opt_canvas_toplevel.yview)

    # Dit frame zal alle dynamische opties bevatten
    dynamic_product_options_frame_toplevel = tk.Frame(opt_canvas_toplevel)

    # Plaats het frame in de canvas en sla de ID op
    # Geef het frame een initiële breedte, gebaseerd op de breedte van het Toplevel venster
    canvas_frame_id = opt_canvas_toplevel.create_window(0, 0, window=dynamic_product_options_frame_toplevel,
                                                        anchor="nw",
                                                        width=options_window.winfo_width())

    opt_canvas_toplevel.configure(yscrollcommand=opt_scroll_toplevel.set)
    opt_canvas_toplevel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    opt_scroll_toplevel.pack(side=tk.RIGHT, fill=tk.Y)

    # Functie om de breedte van het interne frame aan te passen wanneer de canvas groter/kleiner wordt
    def _on_canvas_configure(event):
        # Update de breedte van het interne frame op de canvas
        opt_canvas_toplevel.itemconfigure(canvas_frame_id, width=event.width)
        # Update de scrollregion op basis van de grootte van het frame
        opt_canvas_toplevel.configure(scrollregion=opt_canvas_toplevel.bbox("all"))

    # Bind _on_canvas_configure aan het <Configure> event van de canvas zelf.
    # Hiermee reageert het scrollgebied correct op veranderingen in de grootte van de canvas.
    opt_canvas_toplevel.bind("<Configure>", _on_canvas_configure)

    # Wanneer het venster wordt gesloten, reset dan ook de gekozen product staat
    def on_options_window_close():
        global current_options_popup_window
        state["gekozen_product"] = None
        if current_options_popup_window == options_window:  # Alleen resetten als dit het actieve venster is
            current_options_popup_window = None
        options_window.destroy()
        if opt_title:  # Controleer of opt_title is geïnitialiseerd
            opt_title.config(text="Opties Product")  # Reset de titel in het hoofdvenster

    options_window.protocol("WM_DELETE_WINDOW", on_options_window_close)
    current_options_popup_window = options_window  # Sla de referentie globaal op

    # Update de titel in het hoofdvenster om het geselecteerde product te reflecteren
    if opt_title:  # Controleer of opt_title is geïnitialiseerd
        opt_title.config(text=f"Opties — {product['naam']}")

    # --- Start met het plaatsen van de optie-widgets in dynamic_product_options_frame_toplevel ---
    tk.Label(dynamic_product_options_frame_toplevel, text="Aantal:", font=("Arial", 11, "bold")).grid(row=0, column=0,
                                                                                                      sticky="w",
                                                                                                      pady=(2, 2))
    tk.Spinbox(dynamic_product_options_frame_toplevel, from_=1, to=30, width=5, textvariable=ctrl["aantal"],
               font=("Arial", 11)).grid(row=0,
                                        column=1,
                                        sticky="w",
                                        pady=(2, 2))

    cat_key = (state["categorie"] or "").lower()
    extras_cat = EXTRAS.get(cat_key, {})

    product_extras = {}
    if product.get('naam') and isinstance(extras_cat, dict) and product['naam'] in extras_cat:
        product_extras = extras_cat[product['naam']]
    elif isinstance(extras_cat, dict) and 'default' in extras_cat:
        product_extras = extras_cat['default']

    is_pizza = cat_key in ("small pizza's", "medium pizza's", "large pizza's")
    is_half_half = is_pizza and ("half" in product['naam'].lower())

    row_idx = 1

    if is_half_half:
        tk.Label(dynamic_product_options_frame_toplevel, text="Half-Half (kies 2 pizza's):",
                 font=("Arial", 11, "bold")).grid(
            row=row_idx,
            column=0,
            sticky="w",
            pady=(8, 2))
        row_idx += 1
        half_frame = tk.Frame(dynamic_product_options_frame_toplevel)
        half_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10)

        all_pizzas_in_cat = menu_data.get(state["categorie"], [])
        selectable_pizza_names = [p['naam'] for p in all_pizzas_in_cat if
                                  not ("half half" in p['naam'].lower() and p['naam'].startswith("50."))]

        tk.Label(half_frame, text="Pizza 1:").grid(row=0, column=0, padx=(0, 5), sticky="w")
        half1_cb = ttk.Combobox(half_frame, textvariable=half1_var, values=selectable_pizza_names, state="readonly",
                                width=15, font=("Arial", 10))
        half1_cb.grid(row=0, column=1, padx=(0, 15), sticky="w")
        if selectable_pizza_names: half1_cb.set(selectable_pizza_names[0])

        tk.Label(half_frame, text="Pizza 2:").grid(row=0, column=2, padx=(0, 5), sticky="w")
        half2_cb = ttk.Combobox(half_frame, textvariable=half2_var, values=selectable_pizza_names, state="readonly",
                                width=15, font=("Arial", 10))
        half2_cb.grid(row=0, column=3, sticky="w")
        if len(selectable_pizza_names) > 1: half2_cb.set(selectable_pizza_names[1])
        row_idx += 1

    if not is_pizza and isinstance(extras_cat, dict) and 'vlees' in extras_cat and extras_cat['vlees']:
        tk.Label(dynamic_product_options_frame_toplevel, text="Vlees:", font=("Arial", 11, "bold")).grid(row=row_idx,
                                                                                                         column=0,
                                                                                                         sticky="w",
                                                                                                         pady=(8, 2))
        row_idx += 1
        vlees_frame = tk.Frame(dynamic_product_options_frame_toplevel)
        vlees_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10)
        for i, v in enumerate(extras_cat['vlees']):
            tk.Radiobutton(vlees_frame, text=v, variable=ctrl["vlees"], value=v, font=("Arial", 10)).grid(row=0,
                                                                                                          column=i,
                                                                                                          padx=4,
                                                                                                          sticky="w")
        ctrl["vlees"].set(extras_cat['vlees'][0])
        row_idx += 1

    bron_bijgerecht = product_extras.get('bijgerecht', extras_cat.get('bijgerecht', []))
    bijgerecht_aantal = product_extras.get('bijgerecht_aantal', 1)

    if bron_bijgerecht:
        tk.Label(dynamic_product_options_frame_toplevel, text=f"Bijgerecht{'en' if bijgerecht_aantal > 1 else ''}:",
                 font=("Arial", 11, "bold")).grid(row=row_idx, column=0, sticky="w", pady=(8, 2))
        row_idx += 1
        bg_frame = tk.Frame(dynamic_product_options_frame_toplevel)
        bg_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10)
        # ctrl["bijgerecht_combos"].clear() # Verplaatst naar clear_opties
        for i in range(bijgerecht_aantal):
            var = tk.StringVar(value=bron_bijgerecht[0] if bron_bijgerecht else "")
            cb = ttk.Combobox(bg_frame, textvariable=var, values=bron_bijgerecht, state="readonly", width=18,
                              font=("Arial", 10))
            cb.grid(row=i // 2, column=i % 2, padx=5, pady=2, sticky="w")
            ctrl["bijgerecht_combos"].append(var)
        row_idx += 1 + (bijgerecht_aantal + 1) // 2

    saus_key_in_extras = None
    if 'sauzen' in product_extras:
        saus_key_in_extras = 'sauzen'
    elif 'saus' in product_extras:
        saus_key_in_extras = 'saus'
    elif 'sauzen' in extras_cat:
        saus_key_in_extras = 'sauzen'
    elif 'saus' in extras_cat:
        saus_key_in_extras = 'saus'

    bron_sauzen = product_extras.get(saus_key_in_extras,
                                     extras_cat.get(saus_key_in_extras, [])) if saus_key_in_extras else []
    sauzen_aantal = product_extras.get('sauzen_aantal',
                                       extras_cat.get('sauzen_aantal', 1) if isinstance(extras_cat, dict) else 1)

    if saus_key_in_extras and bron_sauzen and sauzen_aantal > 0:
        tk.Label(dynamic_product_options_frame_toplevel, text=f"Sauzen ({sauzen_aantal}):",
                 font=("Arial", 11, "bold")).grid(
            row=row_idx,
            column=0, sticky="w",
            pady=(8, 2))
        row_idx += 1
        s_frame = tk.Frame(dynamic_product_options_frame_toplevel)
        s_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10)
        # ctrl["saus_combos"].clear() # Verplaatst naar clear_opties
        for i in range(sauzen_aantal):
            var = tk.StringVar(value=bron_sauzen[0] if bron_sauzen else "")
            cb = ttk.Combobox(s_frame, textvariable=var, values=bron_sauzen, state="readonly", width=18,
                              font=("Arial", 10))
            cb.grid(row=i // 2, column=i % 2, padx=5, pady=2, sticky="w")
            ctrl["saus_combos"].append(var)
        row_idx += 1 + (sauzen_aantal + 1) // 2

    bron_garnering = product_extras.get('garnering', extras_cat.get('garnering', {}))
    if bron_garnering:
        tk.Label(dynamic_product_options_frame_toplevel, text="Garnering:", font=("Arial", 11, "bold")).grid(
            row=row_idx,
            column=0,
            sticky="w",
            pady=(8, 2))
        row_idx += 1
        g_frame = tk.Frame(dynamic_product_options_frame_toplevel)
        g_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10)
        # ctrl["garnering"].clear() # Verplaatst naar clear_opties
        if isinstance(bron_garnering, list):
            for i, naam in enumerate(bron_garnering):
                var = tk.BooleanVar()
                tk.Checkbutton(g_frame, text=f"{naam}", variable=var, font=("Arial", 10)).grid(row=i // 2, column=i % 2,
                                                                                               padx=4, pady=2,
                                                                                               sticky="w")
                ctrl["garnering"].append((naam, var))
        elif isinstance(bron_garnering, dict):
            items = list(bron_garnering.items())
            for i, (naam, prijs) in enumerate(items):
                var = tk.BooleanVar()
                tk.Checkbutton(g_frame, text=f"{naam} (+€{prijs:.2f})", variable=var, font=("Arial", 10)).grid(
                    row=i // 2, column=i % 2, padx=4, pady=2, sticky="w")
                ctrl["garnering"].append((naam, var))
        row_idx += 1 + ((len(ctrl["garnering"]) if ctrl["garnering"] else 0) + 1) // 2

    tk.Label(dynamic_product_options_frame_toplevel, text="Opmerking:", font=("Arial", 11, "bold")).grid(row=row_idx,
                                                                                                         column=0,
                                                                                                         sticky="w",
                                                                                                         pady=(8, 2))
    row_idx += 1
    opmerking_entry = tk.Entry(dynamic_product_options_frame_toplevel, textvariable=ctrl["opmerking"],
                               font=("Arial", 10),
                               width=40)
    opmerking_entry.grid(row=row_idx, column=0, columnspan=2, sticky="we", padx=10, pady=2)
    row_idx += 1

    def build_extra_keuze():
        extra = {}
        if is_half_half: extra['half_half'] = [half1_var.get(), half2_var.get()]
        if ctrl["vlees"].get(): extra['vlees'] = ctrl["vlees"].get()
        if ctrl["bijgerecht_combos"]:
            if bijgerecht_aantal == 1:
                extra['bijgerecht'] = ctrl["bijgerecht_combos"][0].get()
            else:
                extra['bijgerecht'] = [v.get() for v in ctrl["bijgerecht_combos"]]
        if ctrl["saus_combos"]:
            if sauzen_aantal == 1:
                extra[saus_key_in_extras] = [ctrl["saus_combos"][0].get()]
            else:
                extra[saus_key_in_extras] = [v.get() for v in ctrl["saus_combos"]]
        if ctrl["garnering"]:
            g_list = [naam for (naam, var) in ctrl["garnering"] if var.get()]
            if g_list: extra['garnering'] = g_list
        return extra

    def on_any_change(*_):
        p = state["gekozen_product"]
        if not p: return
        extra = build_extra_keuze()
        update_right_overview(extra, p)

    # Deze trace_add calls moeten pas gebeuren nadat de StringVar/BooleanVar objecten
    # voor de nieuwe set opties zijn aangemaakt.
    ctrl["aantal"].trace_add("write", on_any_change)
    ctrl["vlees"].trace_add("write", on_any_change)
    # Zorg ervoor dat de lijsten niet leeg zijn voordat je erover itereert
    for var in ctrl["bijgerecht_combos"]:
        if var: var.trace_add("write", on_any_change)
    for var in ctrl["saus_combos"]:
        if var: var.trace_add("write", on_any_change)
    for _, var in ctrl["garnering"]:
        if var: var.trace_add("write", on_any_change)
    if is_half_half:
        if half1_var: half1_var.trace_add("write", on_any_change)
        if half2_var: half2_var.trace_add("write", on_any_change)
    ctrl["opmerking"].trace_add("write", on_any_change)

    # Voer de eerste update uit om de overzichtsweergave te initialiseren
    on_any_change()

    row_idx += 1
    add_frame = tk.Frame(dynamic_product_options_frame_toplevel)
    add_frame.grid(row=row_idx, column=0, columnspan=2, sticky="we", pady=10, padx=10)

    def voeg_toe_current():
        p = state["gekozen_product"]
        if not p: return
        extra = build_extra_keuze()

        extras_price = 0
        if 'garnering' in extra and isinstance(bron_garnering, dict):
            for garnituur_naam in extra['garnering']:
                extras_price += bron_garnering.get(garnituur_naam, 0)

        final_price = p['prijs'] + extras_price

        if is_half_half:
            h1_val = half1_var.get()
            h2_val = half2_var.get()
            all_pizzas_in_cat = menu_data.get(state["categorie"], [])
            selectable_pizza_names = [p['naam'] for p in all_pizzas_in_cat if
                                      not ("half half" in p['naam'].lower() and p['naam'].startswith("50."))]
            if h1_val not in selectable_pizza_names or h2_val not in selectable_pizza_names:
                messagebox.showwarning("Waarschuwing", "Kies twee geldige pizza's voor de Half-Half optie.")
                return
            if h1_val == h2_val:
                messagebox.showwarning("Waarschuwing", "Kies twee verschillende pizza's voor de Half-Half optie.")
                return
            extra['half_half'] = [h1_val, h2_val]

        if bron_bijgerecht and bijgerecht_aantal > 0:
            gekozen_bij = extra.get('bijgerecht', [])
            if isinstance(gekozen_bij, list):
                if len(gekozen_bij) != bijgerecht_aantal or any(not x for x in gekozen_bij):
                    messagebox.showwarning("Waarschuwing", f"Kies precies {bijgerecht_aantal} bijgerechten.")
                    return
            elif not gekozen_bij:
                messagebox.showwarning("Waarschuwing", f"Kies een bijgerecht.")
                return

        if saus_key_in_extras and bron_sauzen and sauzen_aantal > 0:
            gekozen_sauzen = extra.get(saus_key_in_extras, [])
            if isinstance(gekozen_sauzen, list):
                if len(gekozen_sauzen) != sauzen_aantal or any(not x for x in gekozen_sauzen):
                    messagebox.showwarning("Waarschuwing", f"Kies precies {sauzen_aantal} sauzen.")
                    return
            elif not gekozen_sauzen:
                messagebox.showwarning("Waarschuwing", f"Kies een saus.")
                return

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

        # Sluit het optievenster na het toevoegen
        on_options_window_close()  # Roep de sluitfunctie aan

    tk.Button(add_frame, text="Toevoegen aan bestelling", command=voeg_toe_current, bg="#D1FFD1", width=28,
              font=("Arial", 11, "bold")) \
        .pack(side=tk.LEFT, expand=True)


def render_producten():
    global product_grid_holder, state, menu_data
    cat = state["categorie"] or "-"

    if product_grid_holder:
        for w in product_grid_holder.winfo_children():
            w.destroy()

    items = state["producten"]
    columns = 5

    is_pizza_category = "pizza's" in (cat or "").lower()

    for i, product in enumerate(items):
        card_frame = tk.Frame(product_grid_holder, bd=1, relief=tk.RAISED, padx=2, pady=2)
        card_frame.grid(row=i // columns, column=i % columns, padx=2, pady=2, sticky="nsew")
        card_frame.grid_propagate(False)

        bg_color = "lightgrey"
        if "natuur" in product['naam'].lower():
            bg_color = "#FFFF99"
        elif "mexicano" in product['naam'].lower():
            bg_color = "#FF9999"
        elif "tropical" in product['naam'].lower():
            bg_color = "#99CCFF"
        elif "special" in product['naam'].lower():
            bg_color = "#CC99FF"

        if is_pizza_category:
            pizza_number = product['naam'].split('.')[0].strip()
            btn = tk.Button(card_frame, text=pizza_number, font=("Arial", 14, "bold"), bg=bg_color,
                            command=lambda p=product: render_opties(p))
            btn.pack(fill="both", expand=True)
            card_frame.config(width=80, height=80)
        else:
            btn_text = f"{product['naam']}\n€{product['prijs']:.2f}"
            btn = tk.Button(card_frame, text=btn_text, font=("Arial", 10), bg=bg_color,
                            command=lambda p=product: render_opties(p))
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
    category_buttons_frame = tk.Frame(menu_selection_frame, padx=5, pady=5, bg="#ECECEC")
    category_buttons_frame.pack(fill=tk.X)

    categories = list(menu_data.keys())
    for i, cat_name in enumerate(categories):
        row_num = i // 8
        col_num = i % 8
        btn = tk.Button(category_buttons_frame, text=cat_name.upper(), bg="lightgreen",
                        font=("Arial", 10, "bold"), padx=5, pady=5,
                        command=lambda cn=cat_name: on_select_categorie(cn))
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
    telefoon_entry.insert(0, "0499123456")

    adres_entry.delete(0, tk.END)
    adres_entry.insert(0, "Teststraat")

    nr_entry.delete(0, tk.END)
    nr_entry.insert(0, "42")

    postcode_var.set("9120 Beveren")

    opmerkingen_entry.delete(0, tk.END)
    opmerkingen_entry.insert(0, "Dit is een testbestelling")

    bestelregels = [
        {
            'categorie': 'Large pizza\'s',
            'product': 'Margherita',
            'aantal': 2,
            'prijs': 9.00,
            'extras': {'garnering': ['Champignons', 'Extra kaas']}
        },
        {
            'categorie': 'schotels',
            'product': 'Natuur',
            'aantal': 1,
            'prijs': 13.50,
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
            'prijs': 25.00,
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

main_frame = tk.Frame(root, padx=10, pady=10)
main_frame.pack(fill=tk.BOTH, expand=True)

klant_frame = tk.LabelFrame(main_frame, text="Klantgegevens", padx=10, pady=10)
klant_frame.pack(fill=tk.X, pady=(0, 10))

tel_adres_frame = tk.Frame(klant_frame)
tel_adres_frame.pack(fill=tk.X)
telefoon_entry = tk.Entry(tel_adres_frame, width=15)
telefoon_entry.grid(row=0, column=1, sticky="w")
tk.Label(tel_adres_frame, text="Telefoon:").grid(row=0, column=0, sticky="w", padx=(0, 5))
tk.Button(tel_adres_frame, text="Zoek",
          command=lambda: open_klanten_zoeken(root, telefoon_entry, adres_entry, nr_entry, postcode_var, postcodes),
          padx=5).grid(row=0, column=2, sticky="w", padx=(2, 15))

tk.Label(tel_adres_frame, text="Adres:").grid(row=0, column=3, sticky="w", padx=(0, 5))
adres_entry = tk.Entry(tel_adres_frame, width=25)
adres_entry.grid(row=0, column=4, sticky="w", padx=(0, 15))
tk.Label(tel_adres_frame, text="Nr:").grid(row=0, column=5, sticky="w", padx=(0, 5))
nr_entry = tk.Entry(tel_adres_frame, width=5)
nr_entry.grid(row=0, column=6, sticky="w")

postcode_opmerking_frame = tk.Frame(klant_frame)
postcode_opmerking_frame.pack(fill=tk.X, pady=(10, 0))
tk.Label(postcode_opmerking_frame, text="Postcode/Gemeente:").grid(row=0, column=0,

                                                                   sticky="w",
                                                                   padx=(0, 5))
postcode_var = tk.StringVar(master=root)
postcode_var.set(postcodes[0])
postcode_optionmenu = tk.OptionMenu(postcode_opmerking_frame, postcode_var, *postcodes)
postcode_optionmenu.config(width=20)
postcode_optionmenu.grid(row=0, column=1, sticky="w", padx=(0, 15))
tk.Label(postcode_opmerking_frame, text="Opmerking:").grid(row=0, column=2, sticky="w",
                                                           padx=(0, 5))
opmerkingen_entry = tk.Entry(postcode_opmerking_frame, width=30)
opmerkingen_entry.grid(row=0, column=3, sticky="we")
postcode_opmerking_frame.grid_columnconfigure(3, weight=1)

setup_menu_interface()

knoppen_frame = tk.Frame(root)
knoppen_frame.pack(fill=tk.X, pady=10)
tk.Button(knoppen_frame, text="Menu beheren", command=lambda: open_menu_management(root), bg="#E1FFFF",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Extras beheren", command=lambda: open_extras_management(root), bg="#FFFFE1",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Klanten beheren", command=lambda: open_klant_management(root), bg="#E1FFE1",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Geschiedenis",
          command=lambda: open_geschiedenis(root, menu_data, EXTRAS, app_settings),
          bg="#E1FFE1",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Rapportage", command=lambda: open_rapportage(root), bg="#E1E1FF",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Backup/Restore", command=lambda: open_backup_tool(root), bg="#E1E1FF",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Printer Instellingen", command=open_printer_settings, bg="#E1E1FF",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Koeriers",
          command=lambda: open_koeriers(root),
          bg="#E1FFE1", font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(10, 0))
# Bestelling opslaan knop roept nu de print_preview functie aan
tk.Button(knoppen_frame, text="Bon Afdrukken/Opslaan", command=show_print_preview, bg="#D1FFD1",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.RIGHT)
tk.Button(knoppen_frame, text="TEST", command=test_bestellingen_vullen, bg="yellow",
          font=("Arial", 10), padx=5, pady=2).pack(side=tk.RIGHT, padx=(0, 10))

# BINDING VOOR CTRL+P / CMD+P
root.bind("<Control-p>", show_print_preview)  # Voor Windows/Linux
root.bind("<Command-p>", show_print_preview)  # Voor macOS

# Stel de initiële categorie in nadat de mainloop is gestart
categories = load_menu_categories()
if categories:
    root.after(100, lambda: on_select_categorie(categories[0]))

root.mainloop()