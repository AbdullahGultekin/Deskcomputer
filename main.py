import tkinter as tk
from tkinter import messagebox, Toplevel, scrolledtext, ttk, simpledialog
import json
import random
import datetime
from datetime import timedelta
import os
import csv
import database
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

EXTRAS = {}
menu_data = {}
app_settings = {}

# Pad naar instellingenbestand
SETTINGS_FILE = "settings.json"


def load_json_file(path, fallback_data=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if fallback_data is not None:
            # Als het bestand niet bestaat, schrijf de fallback_data
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


def load_data():
    # Fallback voor extras.json
    extras_fallback = {
        # ... bestaande inhoud van extras_fallback ...
    }
    global EXTRAS
    EXTRAS = load_json_file("extras.json", fallback_data=extras_fallback)

    # Alleen menu.json inlezen (zonder testmenu aan te maken)
    global menu_data
    try:
        with open("menu.json", "r", encoding="utf-8") as f:
            menu_data = json.load(f)
    except FileNotFoundError:
        messagebox.showerror("Fout", "menu.json niet gevonden!")
        menu_data = {}
    except json.JSONDecodeError:
        messagebox.showerror("Fout", "menu.json is geen geldige JSON!")
        menu_data = {}

    # Laad applicatie-instellingen
    global app_settings
    settings_fallback = {
        "thermal_printer_name": "Default"  # Standaard naar 'Default'
    }
    app_settings = load_json_file(SETTINGS_FILE, fallback_data=settings_fallback)


# Roep dit vroeg aan (voor open_menu)
load_data()
# Initialiseer de database bij het opstarten
database.initialize_database()

postcodes = [
    "2070 Zwijndrecht", "4568 Nieuw-Namen", "9100 Nieuwkerken-Waas",
    "9100 Sint-Niklaas", "9120 Beveren", "9120 Vrasene", "9120 Haasdonk",
    "9120 Kallo", "9120 Melsele", "9130 Verrebroek", "9130 Kieldrecht",
    "9130 Doel", "9170 Klein meerdonk", "9170 Meerdonk",
    "9170 Sint-Gillis-Waas", "9170 De Klinge"
]

bestelregels = []


# Functie om printerinstellingen te openen
def open_printer_settings():
    settings_win = tk.Toplevel(root)
    settings_win.title("Printer Instellingen")
    settings_win.geometry("400x150")
    settings_win.transient(root)
    settings_win.grab_set()

    tk.Label(settings_win, text="Naam thermische printer (of 'Default'):", font=("Arial", 11, "bold")).pack(pady=10)

    printer_name_var = tk.StringVar(value=app_settings.get("thermal_printer_name", "Default"))
    printer_entry = tk.Entry(settings_win, textvariable=printer_name_var, width=40, font=("Arial", 11))
    printer_entry.pack(pady=5)

    def save_settings():
        app_settings["thermal_printer_name"] = printer_name_var.get().strip()
        if save_json_file(SETTINGS_FILE, app_settings):
            messagebox.showinfo("Opgeslagen", "Printerinstellingen succesvol opgeslagen!")
            settings_win.destroy()

    tk.Button(settings_win, text="Opslaan", command=save_settings, bg="#D1FFD1", font=("Arial", 10)).pack(pady=10)


def bestelling_opslaan():
    """Slaat de huidige bestelling op in de database."""
    if not bestelregels:
        messagebox.showerror("Fout", "Er zijn geen producten toegevoegd aan de bestelling!")
        return

    telefoon = telefoon_entry.get().strip()
    if not telefoon:
        messagebox.showerror("Fout", "Vul een telefoonnummer in!")
        return

    # Klantgegevens verzamelen en klant toevoegen/updaten
    klant_data = {
        "telefoon": telefoon,
        "adres": adres_entry.get(),
        "nr": nr_entry.get(),
        "postcode_gemeente": postcode_var.get(),
        "opmerking": opmerkingen_entry.get()
    }
    voeg_klant_toe_indien_nodig(
        telefoon=klant_data["telefoon"],
        adres=klant_data["adres"],
        nr=klant_data["nr"],
        postcode_plaats=klant_data["postcode_gemeente"],
        naam_of_opmerking=klant_data["opmerking"]
    )

    conn = database.get_db_connection()
    cursor = conn.cursor()

    try:
        # Haal klant ID op
        cursor.execute("SELECT id FROM klanten WHERE telefoon = ?", (klant_data["telefoon"],))
        klant_id_row = cursor.fetchone()
        if not klant_id_row:
            messagebox.showerror("Database Fout", "Kon de klant niet vinden of aanmaken.")
            conn.close()
            return
        klant_id = klant_id_row[0]

        # Sla de hoofdbestelling op
        nu = datetime.datetime.now()
        totaal_prijs = sum(item['prijs'] * item['aantal'] for item in bestelregels)
        bonnummer = database.get_next_bonnummer()
        cursor.execute(
            "INSERT INTO bestellingen (klant_id, datum, tijd, totaal, opmerking, bonnummer) VALUES (?, ?, ?, ?, ?, ?)",
            (klant_id, nu.strftime('%Y-%m-%d'), nu.strftime('%H:%M'), totaal_prijs, klant_data["opmerking"], bonnummer)
        )
        bestelling_id = cursor.lastrowid

        # Sla elke bestelregel op
        for regel in bestelregels:
            cursor.execute(
                "INSERT INTO bestelregels (bestelling_id, categorie, product, aantal, prijs, extras) VALUES (?, ?, ?, ?, ?, ?)",
                (bestelling_id, regel['categorie'], regel['product'], regel['aantal'], regel['prijs'],
                 json.dumps(regel.get('extras', {})))
            )

        conn.commit()

        # Update klantstatistieken
        database.update_klant_statistieken(klant_id)

        # Voorraadverbruik boeken
        database.boek_voorraad_verbruik(bestelling_id)

        if messagebox.askyesno("Bevestiging", "Bestelling opgeslagen! Wilt u de bon bekijken?"):
            parts = generate_bon_text(
                klant_data, bestelregels, bonnummer, menu_data_for_drinks=menu_data, extras_data=EXTRAS
            )
            header_str, info_str, address_str, details_str, total_header, total_row, te_betalen_str, totaal_bedrag_str, footer_str, address_for_qr = parts
            # details_str = bestellingregels enz.
            # total_header = bv. "Tarief\tBasis\tBTW\tTotaal"
            # total_row = bv. "6%\t€ 60.38\t€ 3.62\t€ 64.00"
            # te_betalen_str = bv "TE BETALEN!"
            # totaal_bedrag_str = bv "Totaal: € 64.00"

            bon_win = Toplevel(root)
            bon_win.title(f"Bon {bonnummer}")
            bon_win.geometry("350x680")

            main_bon_frame = tk.Frame(bon_win)
            main_bon_frame.pack(padx=5, pady=5, fill="both", expand=True)
            font_bon = ("Courier New", 10)

            col = tk.Frame(main_bon_frame)
            col.pack(fill="both", expand=True)

            # QR code & adres gecentreerd
            qr_addr_frame = tk.Frame(col)
            qr_addr_frame.pack(fill="x", pady=(2, 10))
            try:
                import qrcode
                from PIL import ImageTk
                import urllib

                maps_url = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(address_for_qr)
                qr = qrcode.QRCode(version=1, box_size=2, border=1)
                qr.add_data(maps_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color='black', back_color='white').resize((60, 60))
                bon_win.qr_photo = ImageTk.PhotoImage(qr_img)

                qr_lbl = tk.Label(qr_addr_frame, image=bon_win.qr_photo, anchor="center")
                qr_lbl.pack(anchor="center")
                tk.Label(qr_addr_frame, text="Scan adres", font=("Arial", 8), anchor="center").pack(anchor="center",
                                                                                                    pady=(0, 3))
            except ImportError:
                tk.Label(qr_addr_frame, text="[QR-fout]", fg='red', anchor="center").pack(anchor="center")

            addr_lbl = tk.Label(qr_addr_frame, text=address_str, font=font_bon, justify=tk.CENTER, anchor="center")
            addr_lbl.pack(anchor="center", pady=(0, 8))

            # Scrollbare bontekst, tabs geconfigureerd
            bon_display = scrolledtext.ScrolledText(
                col,
                wrap=tk.WORD, font=font_bon,
                width=36, height=34
            )
            bon_display.pack(fill="both", expand=True)
            bon_display.config(tabs=("40", "120", "180", "255"))  # Pas desgewenst aan

            # Inhoud bouwen, met indexen voor tags!
            bon_display.insert(tk.END, header_str + "\n")
            bon_display.insert(tk.END, info_str + "\n")
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

            # Alles centreren
            bon_display.tag_configure("center", justify='center')
            bon_display.tag_add("center", "1.0", tk.END)
            # Tariefrijen netjes uitlijnen (tab!)
            bon_display.tag_configure("columns", font=font_bon, justify='center')
            bon_display.tag_add("columns", idx_total_start, idx_total_end)
            # Extra markering voor Totaal: vet/groot
            bon_display.tag_configure("te_betalen", font=("Courier New", 12, "bold"), justify='center')
            bon_display.tag_add("te_betalen", idx_tebetalen_start, idx_tebetalen_end)

            bon_display.config(state='disabled')

            # Print-knop
            def print_bon():
                try:
                    import tempfile, subprocess, sys
                    # Maak een tijdelijk bestand aan om de bontekst in op te slaan
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
                    tmp.write("\n".join(
                        [header_str, info_str, address_str, details_str, total_header, total_row, te_betalen_str,
                         totaal_bedrag_str, footer_str]))
                    tmp.close()  # Sluit het bestand zodat andere programma's het kunnen lezen

                    printer_name = app_settings.get("thermal_printer_name", "Default")

                    if os.name == "nt":  # Controleer of het besturingssysteem Windows is
                        if printer_name and printer_name.lower() != "default":
                            # Op Windows is direct printen naar een specifieke NIET-standaard printer zonder
                            # externe modules (zoals pywin32) complex.
                            # notepad.exe /p print altijd naar de standaardprinter.
                            # os.startfile(tmp.name, "print") print ook naar de standaardprinter.
                            # Voor een specifieke printer op Windows zou je pywin32 nodig hebben:
                            # import win32print
                            # handle = win32print.OpenPrinter(printer_name)
                            # ... (complexer dan hier passend is) ...
                            messagebox.showwarning("Print",
                                                   f"Op Windows print de app momenteel alleen naar de standaardprinter. "
                                                   f"De ingestelde printer '{printer_name}' kan niet direct gekozen worden zonder extra setup. "
                                                   f"Bon wordt naar standaardprinter gestuurd via Notepad.")
                            subprocess.run(["notepad.exe", "/p", tmp.name], check=False)
                        else:
                            # Standaard gedrag: stuur naar standaardprinter via Notepad
                            subprocess.run(["notepad.exe", "/p", tmp.name], check=False)
                    else:  # macOS of Linux
                        if printer_name and printer_name.lower() != "default":
                            # Gebruik lpr met de opgegeven printernaam
                            subprocess.run(["lpr", "-P", printer_name, tmp.name], check=False)
                        else:
                            # Gebruik lpr met de standaardprinter
                            subprocess.run(["lpr", tmp.name], check=False)

                    messagebox.showinfo("Print", "Bon naar printer gestuurd.")

                except FileNotFoundError:
                    messagebox.showerror("Fout", "Printerprogramma (notepad.exe of lpr) niet gevonden.")
                except Exception as e:
                    messagebox.showerror("Print", f"Printen mislukt: {e}")
                finally:
                    # Verwijder het tijdelijke bestand na het afdrukken (of na de fout)
                    if tmp and os.path.exists(tmp.name):
                        os.unlink(tmp.name)

            tk.Button(col, text="Print bon", command=print_bon, bg="#E1E1FF").pack(pady=(6, 2))

        else:
            messagebox.showinfo("Bevestiging", "Bestelling opgeslagen!")

        # Velden wissen na succesvolle opslag
        telefoon_entry.delete(0, tk.END)
        adres_entry.delete(0, tk.END)
        nr_entry.delete(0, tk.END)
        postcode_var.set(postcodes[0])
        opmerkingen_entry.delete(0, tk.END)
        bestelregels.clear()
        update_overzicht()

    except Exception as e:
        conn.rollback()
        messagebox.showerror("Fout bij opslaan", f"Er is een fout opgetreden: {str(e)}")
    finally:
        conn.close()


def update_overzicht():
    """Werkt het besteloverzicht bij met alle huidige producten"""
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


def open_menu():
    """Opent het menuvenster in een 3-koloms PanedWindow layout (links categorie, midden producten met paginatie, rechts opties + overzicht)"""
    try:
        # Controleer of het menu.json bestand bestaat. Zo niet, maak een testmenu.
        if not os.path.isfile("menu.json"):
            test_menu = {
                "Schotels": [
                    {"naam": "Natuur", "prijs": 20.00,
                     "desc": "Schotel met vlees geserveerd met twee sauzen naar keuze"}
                ],
                "Mix Schotels": [
                    {"naam": "Napoli speciaal 2 personen", "prijs": 45.00, "desc": "Mix schotel voor 2 personen"},
                    {"naam": "Mix Grill", "prijs": 18.00, "desc": "Gevarieerde grill schotel"}
                ],
                "Large Pizza's": [
                    {"naam": "Margherita", "prijs": 20.00, "desc": "Tomatensaus en mozzarella"},
                    {"naam": "Half half", "prijs": 30.00, "desc": "Keuze uit twee genummerde pizza's"}
                ],
                "Vegetarisch Broodjes": [
                    {"naam": "Feta", "prijs": 4.00, "desc": "Broodje met feta"},
                    {"naam": "Kaas", "prijs": 4.00, "desc": "Broodje met jonge kaas"}
                ],
                "Dranken": [
                    {"naam": "Coca cola", "prijs": 2.50, "desc": "33cl"},
                    {"naam": "Water", "prijs": 2.00, "desc": "Flesje water"}
                ]
            }
            with open("menu.json", "w", encoding="utf-8") as f:
                json.dump(test_menu, f, ensure_ascii=False, indent=2)

        # Lees het menu bestand
        with open("menu.json", "r", encoding="utf-8") as f:
            menu_data = json.load(f)
    except json.JSONDecodeError:
        messagebox.showerror("Fout", "menu.json is geen geldige JSON!")
        return

    menu_win = tk.Toplevel(root)
    menu_win.title("Menukaart")
    menu_win.geometry("1100x720")
    menu_win.minsize(1000, 640)

    # State voor paginatie en selectie
    state = {
        "categorie": None,
        "producten": [],
        "page": 0,
        "page_size": 10,
        "gekozen_product": None
    }

    # PanedWindow met 3 delen
    paned = tk.PanedWindow(menu_win, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashpad=4)
    paned.pack(fill=tk.BOTH, expand=True)

    # Links: categorieën
    left_frame = tk.Frame(paned, padx=8, pady=8)
    paned.add(left_frame, minsize=220)
    tk.Label(left_frame, text="Categorieën", font=("Arial", 13, "bold")).pack(anchor="w")

    cat_listbox = tk.Listbox(left_frame, height=25, exportselection=False, font=("Arial", 11))
    cat_scroll = tk.Scrollbar(left_frame, orient=tk.VERTICAL, command=cat_listbox.yview)
    cat_listbox.configure(yscrollcommand=cat_scroll.set)
    cat_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    cat_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Vul categorieën
    categories = list(menu_data.keys())
    for c in categories:
        cat_listbox.insert(tk.END, c)

    def on_select_categorie(event=None):
        sel_indices = cat_listbox.curselection()
        if not sel_indices:
            return
        cat = categories[sel_indices[0]]
        state["categorie"] = cat
        state["producten"] = menu_data.get(cat, [])
        state["page"] = 0
        state["gekozen_product"] = None
        # Stel page_size dynamisch in op het totale aantal producten om alles op één pagina te tonen
        state["page_size"] = len(state["producten"]) if state["producten"] else 10
        render_producten()
        render_opties(None)  # wissen opties

    cat_listbox.bind("<<ListboxSelect>>", on_select_categorie)

    # Midden: productgrid + paginatie
    mid_frame = tk.Frame(paned, padx=8, pady=8)
    paned.add(mid_frame, minsize=480)

    mid_header = tk.Frame(mid_frame)
    mid_header.pack(fill=tk.X)
    producten_title = tk.Label(mid_header, text="Producten", font=("Arial", 13, "bold"))
    producten_title.pack(side=tk.LEFT)

    grid_holder = tk.Frame(mid_frame)
    grid_holder.pack(fill=tk.BOTH, expand=True)

    pagination = tk.Frame(mid_frame)
    pagination.pack(fill=tk.X, pady=(6, 0))
    prev_btn = tk.Button(pagination, text="Vorige", width=10, command=lambda: change_page(-1))
    next_btn = tk.Button(pagination, text="Volgende", width=10, command=lambda: change_page(+1))
    page_label = tk.Label(pagination, text="Pagina 1/1")
    prev_btn.pack(side=tk.LEFT)
    page_label.pack(side=tk.LEFT, padx=10)
    next_btn.pack(side=tk.LEFT)

    def change_page(delta):
        if not state["producten"]:
            return
        pages = max(1, (len(state["producten"]) + state["page_size"] - 1) // state["page_size"])
        new_page = max(0, min(state["page"] + delta, pages - 1))
        if new_page != state["page"]:
            state["page"] = new_page
            render_producten()

    def render_producten():
        # header updaten
        cat = state["categorie"] or "-"
        producten_title.config(text=f"Producten — {cat}")

        # grid leegmaken
        for w in grid_holder.winfo_children():
            w.destroy()
        # paginatie
        items = state["producten"]
        ps = state["page_size"]
        start = state["page"] * ps
        end = start + ps
        subset = items[start:end]

        columns = 5  # Vijf kolommen zoals gevraagd

        # Bepaal of de huidige categorie een pizza-categorie is (case-insensitive)
        is_pizza_category = "pizza's" in (cat or "").lower()

        for i, product in enumerate(subset):
            # Kleinere padding voor compactere kaarten
            card = tk.Frame(grid_holder, bd=1, relief=tk.GROOVE, padx=5, pady=5)
            card.grid(row=i // columns, column=i % columns, padx=8, pady=8, sticky="nsew")
            card.grid_propagate(False)  # Voorkomt dat de card groter wordt dan zijn content toelaat

            if is_pizza_category:
                # Voor pizza's: toon alleen het nummer en maak de kaart klein
                pizza_number = product['naam'].split('.')[0].strip()  # Haal het nummer op
                tk.Label(card, text=pizza_number, font=("Arial", 14, "bold")).pack(anchor="center", expand=True)
                # Stel een vaste, kleine grootte in voor de pizzakaarten
                card.config(width=80, height=80)  # Voorbeeldgrootte, kan verder aangepast worden indien nodig
            else:
                # Voor niet-pizza's: toon naam, prijs en, indien aanwezig, een beknopte beschrijving
                tk.Label(card, text=product['naam'], font=("Arial", 12, "bold")).pack(anchor="w")
                tk.Label(card, text=f"€{product['prijs']:.2f}", font=("Arial", 11)).pack(anchor="w")
                if product.get('desc'):
                    tk.Label(card, text=product['desc'], font=("Arial", 9, "italic"), wraplength=100, fg="#444").pack(
                        anchor="w", pady=(4, 6))

            # De "Kies" knop blijft altijd aanwezig
            # Voor pizzakaarten kan de knop smaller zijn
            button_width = 8 if is_pizza_category else 12
            tk.Button(card, text="Kies", width=button_width, command=lambda p=product: render_opties(p)).pack(
                anchor="s", pady=(2, 0))  # anchor="s" om onderaan te plaatsen

        # kolombreedtes
        for c in range(columns):
            grid_holder.grid_columnconfigure(c, weight=1)

        # paginatie-label en knoppen (hoewel bij page_size=alle producten, de paginatieknoppen vaak disabled zullen zijn)
        total = len(items)
        pages = max(1, (total + ps - 1) // ps)
        page_label.config(text=f"Pagina {state['page'] + 1}/{pages}")
        prev_btn.config(state=tk.NORMAL if state['page'] > 0 else tk.DISABLED)
        next_btn.config(state=tk.NORMAL if state['page'] < pages - 1 else tk.DISABLED)

    # Rechts: opties + snel toevoegen + lokaal overzicht
    right_frame = tk.Frame(paned, padx=8, pady=8)
    paned.add(right_frame, minsize=350)

    opt_title = tk.Label(right_frame, text="Opties", font=("Arial", 13, "bold"))
    opt_title.pack(anchor="w")

    opt_canvas = tk.Canvas(right_frame, highlightthickness=0)
    opt_scroll = tk.Scrollbar(right_frame, orient=tk.VERTICAL, command=opt_canvas.yview)
    opties_frame = tk.Frame(opt_canvas)

    opt_canvas.create_window((0, 0), window=opties_frame, anchor="nw")
    opt_canvas.configure(yscrollcommand=opt_scroll.set)

    opt_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    opt_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    opties_frame.bind("<Configure>", lambda e: opt_canvas.configure(scrollregion=opt_canvas.bbox("all")))

    # Lokaal overzicht aan rechterkant (enkel voor context tijdens bestellen)
    right_overview_title = tk.Label(right_frame, text="Huidige selectie", font=("Arial", 12, "bold"))
    right_overview_title.pack(anchor="w", pady=(8, 2))
    right_overview = tk.Text(right_frame, height=8, width=40, font=("Arial", 10))
    right_overview.pack(fill=tk.X)

    # Controlevariabelen voor opties (maak ze globaal of pas door via een object)
    ctrl = {
        "aantal": tk.IntVar(value=1),
        "vlees": tk.StringVar(),
        "bijgerecht_combos": [],  # list[ttk.Combobox] (widget refs)
        "saus_combos": [],  # list[ttk.Combobox] (widget refs)
        "garnering": [],  # list of (name, BooleanVar)
        "opmerking": tk.StringVar()
    }
    # Half-half vars
    half1_var = tk.StringVar(value="1")
    half2_var = tk.StringVar(value="2")

    def clear_opties():
        for w in opties_frame.winfo_children():
            w.destroy()
        ctrl["aantal"].set(1)
        ctrl["vlees"].set("")
        ctrl["bijgerecht_combos"].clear()  # clear widget refs, niet de StringVars direct
        ctrl["saus_combos"].clear()
        ctrl["garnering"].clear()
        ctrl["opmerking"].set("")
        half1_var.set("1")
        half2_var.set("2")
        right_overview.delete(1.0, tk.END)

    def update_right_overview(extra_keuze, product):
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

    def render_opties(product):
        clear_opties()
        state["gekozen_product"] = product
        if not product:
            opt_title.config(text="Opties")
            return

        opt_title.config(text=f"Opties — {product['naam']}")

        # Aantal
        tk.Label(opties_frame, text="Aantal:", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w",
                                                                                pady=(2, 2))
        tk.Spinbox(opties_frame, from_=1, to=30, width=5, textvariable=ctrl["aantal"], font=("Arial", 11)).grid(row=0,
                                                                                                                column=1,
                                                                                                                sticky="w",
                                                                                                                pady=(2,
                                                                                                                      2))

        cat_key = (state["categorie"] or "").lower()
        extras_cat = EXTRAS.get(cat_key, {})

        product_extras = {}
        if product.get('naam') and isinstance(extras_cat, dict) and product['naam'] in extras_cat:
            product_extras = extras_cat[product['naam']]
        elif isinstance(extras_cat, dict) and 'default' in extras_cat:
            product_extras = extras_cat['default']

        is_pizza = cat_key in ("small pizza's", "medium pizza's", "large pizza's")
        is_half_half = is_pizza and ("half" in product['naam'].lower())

        row_idx = 1  # Startrij voor opties

        # 0. HALF-HALF PIZZA
        if is_half_half:
            tk.Label(opties_frame, text="Half-Half (kies 2 pizza's):", font=("Arial", 11, "bold")).grid(row=row_idx,
                                                                                                        column=0,
                                                                                                        sticky="w",
                                                                                                        pady=(8, 2))
            row_idx += 1
            half_frame = tk.Frame(opties_frame)
            half_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10)

            # Genereer de lijst met beschikbare pizza's voor de comboboxen
            # Filter de "Half half" pizza zelf uit de keuzes
            all_pizzas_in_cat = menu_data.get(state["categorie"], [])
            selectable_pizza_names = [p['naam'] for p in all_pizzas_in_cat if
                                      not ("half half" in p['naam'].lower() and p['naam'].startswith("50."))]

            # Eerste helft
            tk.Label(half_frame, text="Pizza 1:").grid(row=0, column=0, padx=(0, 5), sticky="w")
            half1_cb = ttk.Combobox(half_frame, textvariable=half1_var, values=selectable_pizza_names, state="readonly",
                                    width=25,
                                    font=("Arial", 10))
            half1_cb.grid(row=0, column=1, padx=(0, 15), sticky="w")
            # Stel een standaard selectie in, indien beschikbaar
            if selectable_pizza_names:
                half1_cb.set(selectable_pizza_names[0])

            # Tweede helft
            tk.Label(half_frame, text="Pizza 2:").grid(row=0, column=2, padx=(0, 5), sticky="w")
            half2_cb = ttk.Combobox(half_frame, textvariable=half2_var, values=selectable_pizza_names, state="readonly",
                                    width=25,
                                    font=("Arial", 10))
            half2_cb.grid(row=0, column=3, sticky="w")
            # Stel een standaard selectie in, indien beschikbaar
            if len(selectable_pizza_names) > 1:
                half2_cb.set(selectable_pizza_names[1])

            row_idx += 1  # 1 rij gebruikt voor half_frame

        # 1. VLEES (niet voor pizza's)
        if not is_pizza and isinstance(extras_cat, dict) and 'vlees' in extras_cat and extras_cat['vlees']:
            tk.Label(opties_frame, text="Vlees:", font=("Arial", 11, "bold")).grid(row=row_idx, column=0, sticky="w",
                                                                                   pady=(8, 2))
            row_idx += 1
            vlees_frame = tk.Frame(opties_frame)
            vlees_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10)
            for i, v in enumerate(extras_cat['vlees']):
                tk.Radiobutton(vlees_frame, text=v, variable=ctrl["vlees"], value=v, font=("Arial", 10)).grid(row=0,
                                                                                                              column=i,
                                                                                                              padx=4,
                                                                                                              sticky="w")
            ctrl["vlees"].set(extras_cat['vlees'][0])
            row_idx += 1

        # 2. BIJGERECHT
        bron_bijgerecht = product_extras.get('bijgerecht', extras_cat.get('bijgerecht', []))
        bijgerecht_aantal = product_extras.get('bijgerecht_aantal', 1)  # Default 1

        if bron_bijgerecht:
            tk.Label(opties_frame, text=f"Bijgerecht{'en' if bijgerecht_aantal > 1 else ''}:",
                     font=("Arial", 11, "bold")).grid(row=row_idx, column=0, sticky="w", pady=(8, 2))
            row_idx += 1
            bg_frame = tk.Frame(opties_frame)
            bg_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10)

            ctrl["bijgerecht_combos"].clear()  # Maak leeg voor nieuwe productselectie
            for i in range(bijgerecht_aantal):
                var = tk.StringVar(value=bron_bijgerecht[0] if bron_bijgerecht else "")
                cb = ttk.Combobox(bg_frame, textvariable=var, values=bron_bijgerecht, state="readonly", width=18,
                                  font=("Arial", 10))
                cb.grid(row=i // 2, column=i % 2, padx=5, pady=2, sticky="w")
                ctrl["bijgerecht_combos"].append(var)  # Sla de StringVar op
            row_idx += 1 + (bijgerecht_aantal + 1) // 2

        # 3. SAUZEN
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

        # Toon alleen sauzen als er een saus_key is en de lijst niet leeg is en sauzen_aantal > 0
        if saus_key_in_extras and bron_sauzen and sauzen_aantal > 0:
            tk.Label(opties_frame, text=f"Sauzen ({sauzen_aantal}):", font=("Arial", 11, "bold")).grid(row=row_idx,
                                                                                                       column=0,
                                                                                                       sticky="w",
                                                                                                       pady=(8, 2))
            row_idx += 1
            s_frame = tk.Frame(opties_frame)
            s_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10)

            ctrl["saus_combos"].clear()  # Maak leeg voor nieuwe productselectie
            for i in range(sauzen_aantal):
                var = tk.StringVar(value=bron_sauzen[0] if bron_sauzen else "")
                cb = ttk.Combobox(s_frame, textvariable=var, values=bron_sauzen, state="readonly", width=18,
                                  font=("Arial", 10))
                cb.grid(row=i // 2, column=i % 2, padx=5, pady=2, sticky="w")
                ctrl["saus_combos"].append(var)  # Sla de StringVar op
            row_idx += 1 + (sauzen_aantal + 1) // 2

        # 4. GARNERING
        bron_garnering = product_extras.get('garnering', extras_cat.get('garnering', {}))
        if bron_garnering:
            tk.Label(opties_frame, text="Garnering:", font=("Arial", 11, "bold")).grid(row=row_idx, column=0,
                                                                                       sticky="w", pady=(8, 2))
            row_idx += 1
            g_frame = tk.Frame(opties_frame)
            g_frame.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10)

            ctrl["garnering"].clear()  # Maak leeg voor nieuwe productselectie
            if isinstance(bron_garnering, list):
                for i, naam in enumerate(bron_garnering):
                    var = tk.BooleanVar()
                    tk.Checkbutton(g_frame, text=naam, variable=var, font=("Arial", 10)).grid(row=i // 2, column=i % 2,
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

        # 5. OPMERKING (nu altijd zichtbaar)
        tk.Label(opties_frame, text="Opmerking:", font=("Arial", 11, "bold")).grid(row=row_idx, column=0,
                                                                                   sticky="w", pady=(8, 2))
        row_idx += 1
        opmerking_entry = tk.Entry(opties_frame, textvariable=ctrl["opmerking"], font=("Arial", 10), width=40)
        opmerking_entry.grid(row=row_idx, column=0, columnspan=2, sticky="we", padx=10, pady=2)
        row_idx += 1

        # Snel overzicht + toevoegen knop
        def build_extra_keuze():
            extra = {}
            if is_half_half:
                extra['half_half'] = [half1_var.get(), half2_var.get()]
            if ctrl["vlees"].get():
                extra['vlees'] = ctrl["vlees"].get()

            if ctrl["bijgerecht_combos"]:
                if bijgerecht_aantal == 1:
                    extra['bijgerecht'] = ctrl["bijgerecht_combos"][0].get()
                else:
                    extra['bijgerecht'] = [v.get() for v in ctrl["bijgerecht_combos"]]

            if ctrl["saus_combos"]:  # Gebruik saus_key_in_extras hier voor correcte sleutel
                if sauzen_aantal == 1:
                    extra[saus_key_in_extras] = [
                        ctrl["saus_combos"][0].get()]  # Altijd als lijst opslaan voor consistentie
                else:
                    extra[saus_key_in_extras] = [v.get() for v in ctrl["saus_combos"]]

            if ctrl["garnering"]:
                g_list = [naam for (naam, var) in ctrl["garnering"] if var.get()]
                if g_list:
                    extra['garnering'] = g_list
            return extra

        def on_any_change(*_):
            p = state["gekozen_product"]
            if not p: return
            extra = build_extra_keuze()
            update_right_overview(extra, p)

        # Bind variabelen voor live-overzicht
        ctrl["aantal"].trace_add("write", on_any_change)
        ctrl["vlees"].trace_add("write", on_any_change)
        for var in ctrl["bijgerecht_combos"]:
            var.trace_add("write", on_any_change)
        for var in ctrl["saus_combos"]:
            var.trace_add("write", on_any_change)
        for _, var in ctrl["garnering"]:
            var.trace_add("write", on_any_change)
        if is_half_half:
            half1_var.trace_add("write", on_any_change)
            half2_var.trace_add("write", on_any_change)
        ctrl["opmerking"].trace_add("write", on_any_change)

        # Eerste update
        on_any_change()

        # Toevoegen-knop
        row_idx += 1
        add_frame = tk.Frame(opties_frame)
        add_frame.grid(row=row_idx, column=0, columnspan=2, sticky="we", pady=10, padx=10)

        def voeg_toe_current():
            p = state["gekozen_product"]
            if not p: return
            extra = build_extra_keuze()

            # Bereken de prijs van de extra's
            extras_price = 0
            if 'garnering' in extra and isinstance(bron_garnering, dict):
                for garnituur_naam in extra['garnering']:
                    extras_price += bron_garnering.get(garnituur_naam, 0)

            final_price = p['prijs'] + extras_price

            # Valideer half-half
            if is_half_half:
                h1_val = half1_var.get()
                h2_val = half2_var.get()
                all_pizzas_in_cat = menu_data.get(state["categorie"], [])
                selectable_pizza_names = [p['naam'] for p in all_pizzas_in_cat if
                                          not ("half half" in p['naam'].lower() and p['naam'].startswith("50."))]
                # Controleer of er geldige pizza's zijn geselecteerd uit de lijst
                if h1_val not in selectable_pizza_names or h2_val not in selectable_pizza_names:
                    messagebox.showwarning("Waarschuwing", "Kies twee geldige pizza's voor de Half-Half optie.")
                    return
                if h1_val == h2_val:
                    messagebox.showwarning("Waarschuwing", "Kies twee verschillende pizza's voor de Half-Half optie.")
                    return
                # Update de extra's met de daadwerkelijk gekozen namen
                extra['half_half'] = [h1_val, h2_val]

            # Valideer bijgerecht aantal
            if bron_bijgerecht and bijgerecht_aantal > 0:
                gekozen_bij = extra.get('bijgerecht', [])
                if isinstance(gekozen_bij, list):
                    if len(gekozen_bij) != bijgerecht_aantal or any(not x for x in gekozen_bij):
                        messagebox.showwarning("Waarschuwing", f"Kies precies {bijgerecht_aantal} bijgerechten.")
                        return
                elif not gekozen_bij:  # Enkelvoudig, maar leeg gelaten
                    messagebox.showwarning("Waarschuwing", f"Kies een bijgerecht.")
                    return

            # Valideer sauzen aantal
            if saus_key_in_extras and bron_sauzen and sauzen_aantal > 0:
                gekozen_sauzen = extra.get(saus_key_in_extras, [])
                if isinstance(gekozen_sauzen, list):
                    if len(gekozen_sauzen) != sauzen_aantal or any(not x for x in gekozen_sauzen):
                        messagebox.showwarning("Waarschuwing", f"Kies precies {sauzen_aantal} sauzen.")
                        return
                elif not gekozen_sauzen:  # Enkelvoudig, maar leeg gelaten
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
            render_opties(None)  # Clear opties na toevoegen

        tk.Button(add_frame, text="Toevoegen aan bestelling", command=voeg_toe_current, bg="#D1FFD1", width=28,
                  font=("Arial", 11, "bold")) \
            .pack(side=tk.LEFT, expand=True)

    # Start: selecteer eerste categorie automatisch (indien beschikbaar)
    if categories:
        cat_listbox.selection_set(0)
        on_select_categorie()


def test_bestellingen_vullen():
    """Vult het bestelformulier met testgegevens voor sneller testen"""
    # Vul contactgegevens
    telefoon_entry.delete(0, tk.END)
    telefoon_entry.insert(0, "0499123456")

    adres_entry.delete(0, tk.END)
    adres_entry.insert(0, "Teststraat")

    nr_entry.delete(0, tk.END)
    nr_entry.insert(0, "42")

    postcode_var.set("9120 Beveren")

    opmerkingen_entry.delete(0, tk.END)
    opmerkingen_entry.insert(0, "Dit is een testbestelling")

    # Vul bestelregels met wat voorbeelden
    global bestelregels
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


# GUI opzet
root = tk.Tk()
root.title("Pizzeria Bestelformulier")
root.geometry("800x600")
root.minsize(600, 500)

# Hoofdframe
main_frame = tk.Frame(root, padx=10, pady=10)
main_frame.pack(fill=tk.BOTH, expand=True)

# KLANTGEGEVENS
klant_frame = tk.LabelFrame(main_frame, text="Klantgegevens", padx=10, pady=10)
klant_frame.pack(fill=tk.X, pady=(0, 10))

# Rij: telefoon - adres - nr
tel_adres_frame = tk.Frame(klant_frame)
tel_adres_frame.pack(fill=tk.X)
tk.Label(tel_adres_frame, text="Telefoon:").grid(row=0, column=0, sticky="w", padx=(0, 5))
telefoon_entry = tk.Entry(tel_adres_frame, width=15)
telefoon_entry.grid(row=0, column=1, sticky="w")

# Knop om klanten te zoeken
tk.Button(tel_adres_frame, text="Zoek",
          command=lambda: open_klanten_zoeken(root, telefoon_entry, adres_entry, nr_entry, postcode_var, postcodes),
          padx=5).grid(row=0, column=2, sticky="w", padx=(2, 15))

tk.Label(tel_adres_frame, text="Adres:").grid(row=0, column=3, sticky="w", padx=(0, 5))
adres_entry = tk.Entry(tel_adres_frame, width=25)
adres_entry.grid(row=0, column=4, sticky="w", padx=(0, 15))
tk.Label(tel_adres_frame, text="Nr:").grid(row=0, column=5, sticky="w", padx=(0, 5))
nr_entry = tk.Entry(tel_adres_frame, width=5)
nr_entry.grid(row=0, column=6, sticky="w")

# Rij: postcode/gemeente - opmerking
postcode_opmerking_frame = tk.Frame(klant_frame)
postcode_opmerking_frame.pack(fill=tk.X, pady=(10, 0))
tk.Label(postcode_opmerking_frame, text="Postcode/Gemeente:").grid(row=0, column=0, sticky="w", padx=(0, 5))
postcode_var = tk.StringVar(root)
postcode_var.set(postcodes[0])
postcode_optionmenu = tk.OptionMenu(postcode_opmerking_frame, postcode_var, *postcodes)
postcode_optionmenu.config(width=20)
postcode_optionmenu.grid(row=0, column=1, sticky="w", padx=(0, 15))
tk.Label(postcode_opmerking_frame, text="Opmerking:").grid(row=0, column=2, sticky="w", padx=(0, 5))
opmerkingen_entry = tk.Entry(postcode_opmerking_frame, width=30)
opmerkingen_entry.grid(row=0, column=3, sticky="we")
postcode_opmerking_frame.grid_columnconfigure(3, weight=1)

# BESTELREGELS
bestel_frame = tk.LabelFrame(main_frame, text="Besteloverzicht", padx=10, pady=10)
bestel_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
overzicht = tk.Text(bestel_frame, height=15, width=65)
overzicht.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
update_overzicht()

# KNOPPEN onderaan
knoppen_frame = tk.Frame(main_frame)
knoppen_frame.pack(fill=tk.X)
tk.Button(knoppen_frame, text="Menu openen", command=open_menu, bg="#E1E1FF",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Menu beheren", command=lambda: open_menu_management(root), bg="#E1FFFF",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Extras beheren", command=lambda: open_extras_management(root), bg="#FFFFE1",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Klanten beheren", command=lambda: open_klant_management(root), bg="#E1FFE1",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Geschiedenis", command=lambda: open_geschiedenis(root), bg="#E1FFE1",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Opslaan bestelling(en)", command=bestelling_opslaan, bg="#D1FFD1",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.RIGHT)
tk.Button(knoppen_frame, text="TEST", command=test_bestellingen_vullen, bg="yellow",
          font=("Arial", 10), padx=5, pady=2).pack(side=tk.LEFT)
tk.Button(knoppen_frame, text="Koeriers",
          command=lambda: open_koeriers(root),
          bg="#E1FFE1", font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(10, 0))
tk.Button(knoppen_frame, text="Rapportage", command=lambda: open_rapportage(root), bg="#E1E1FF",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Backup/Restore", command=lambda: open_backup_tool(root), bg="#E1E1FF",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Voorraad", command=lambda: open_voorraad(root), bg="#FFF3CD",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))
tk.Button(knoppen_frame, text="Printer Instellingen", command=open_printer_settings, bg="#E1E1FF",
          font=("Arial", 11), padx=10, pady=5).pack(side=tk.LEFT, padx=(0, 10))  # Nieuwe knop

# MAIN LOOP starten
root.mainloop()