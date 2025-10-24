import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os


def open_extras_management(root):
    """Opent het extras management venster"""

    def load_extras_data():
        """Laadt de extras data uit extras.json"""
        try:
            with open("extras.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Fout", "extras.json niet gevonden!")
            return {}
        except json.JSONDecodeError:
            messagebox.showerror("Fout", "extras.json is geen geldige JSON!")
            return {}

    def save_extras_data(extras_data):
        """Slaat de extras data op naar extras.json"""
        try:
            with open("extras.json", "w", encoding="utf-8") as f:
                json.dump(extras_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            messagebox.showerror("Fout", f"Kon extras niet opslaan: {e}")
            return False

    def load_menu_categories():
        """Laadt beschikbare categorieën uit menu.json"""
        try:
            with open("menu.json", "r", encoding="utf-8") as f:
                menu_data = json.load(f)
                return list(menu_data.keys())
        except:
            return []

    # Main window
    win = tk.Toplevel(root)
    win.title("Extras Management")
    win.geometry("1400x900")
    win.minsize(1200, 700)

    # Data laden
    extras_data = load_extras_data()
    menu_categories = load_menu_categories()

    if not extras_data:
        win.destroy()
        return

    # Main PanedWindow (3-koloms layout)
    main_paned = tk.PanedWindow(win, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashpad=4)
    main_paned.pack(fill=tk.BOTH, expand=True)

    # --- LINKS: Categorieën ---
    left_frame = tk.Frame(main_paned, padx=8, pady=8)
    main_paned.add(left_frame, minsize=280)

    tk.Label(left_frame, text="Categorieën", font=("Arial", 13, "bold")).pack(anchor="w")

    # Categorieën listbox
    cat_frame = tk.Frame(left_frame)
    cat_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

    cat_listbox = tk.Listbox(cat_frame, font=("Arial", 11), exportselection=False)
    cat_scrollbar = tk.Scrollbar(cat_frame, orient=tk.VERTICAL, command=cat_listbox.yview)
    cat_listbox.configure(yscrollcommand=cat_scrollbar.set)

    cat_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    cat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Categorie info
    info_frame = tk.LabelFrame(left_frame, text="Categorie Info", padx=5, pady=5)
    info_frame.pack(fill=tk.X, pady=(10, 0))

    info_text = tk.Text(info_frame, height=8, font=("Arial", 9), wrap=tk.WORD, state=tk.DISABLED)
    info_text.pack(fill=tk.BOTH, expand=True)

    def refresh_categories():
        """Vernieuwt de categorieën lijst"""
        cat_listbox.delete(0, tk.END)
        for category in extras_data.keys():
            extra_count = count_extras_in_category(category)
            cat_listbox.insert(tk.END, f"{category} ({extra_count})")

    def count_extras_in_category(category):
        """Telt het aantal extra's in een categorie"""
        if category not in extras_data:
            return 0

        count = 0
        cat_data = extras_data[category]

        if isinstance(cat_data, dict):
            for key, value in cat_data.items():
                if key in ['vlees', 'bijgerecht', 'saus', 'sauzen']:
                    count += len(value) if isinstance(value, list) else 0
                elif key == 'garnering' and isinstance(value, dict):
                    count += len(value)
                elif isinstance(value, dict) and 'garnering' in value:
                    count += len(value['garnering'])

        return count

    def update_category_info():
        """Update categorie informatie"""
        selection = cat_listbox.curselection()
        if not selection:
            info_text.config(state=tk.NORMAL)
            info_text.delete(1.0, tk.END)
            info_text.config(state=tk.DISABLED)
            return

        category_display = cat_listbox.get(selection[0])
        category = category_display.split(" (")[0]  # Remove count from display

        info_text.config(state=tk.NORMAL)
        info_text.delete(1.0, tk.END)

        if category in extras_data:
            cat_data = extras_data[category]
            info_text.insert(tk.END, f"Categorie: {category}\n\n")

            # Toon overzicht van extras types
            if isinstance(cat_data, dict):
                for key, value in cat_data.items():
                    if key == 'vlees' and isinstance(value, list):
                        info_text.insert(tk.END, f"Vlees opties: {len(value)}\n")
                    elif key == 'bijgerecht' and isinstance(value, list):
                        info_text.insert(tk.END, f"Bijgerechten: {len(value)}\n")
                    elif key in ['saus', 'sauzen'] and isinstance(value, list):
                        info_text.insert(tk.END, f"Sauzen: {len(value)}\n")
                    elif key == 'garnering' and isinstance(value, dict):
                        info_text.insert(tk.END, f"Garneringen: {len(value)}\n")
                    elif key.endswith('_aantal'):
                        info_text.insert(tk.END, f"{key}: {value}\n")
                    elif isinstance(value, dict):
                        # Product-specifieke configuratie
                        info_text.insert(tk.END, f"\nProduct '{key}':\n")
                        for subkey, subvalue in value.items():
                            if isinstance(subvalue, list):
                                info_text.insert(tk.END, f"  {subkey}: {len(subvalue)} opties\n")
                            elif isinstance(subvalue, dict):
                                info_text.insert(tk.END, f"  {subkey}: {len(subvalue)} items\n")
                            else:
                                info_text.insert(tk.END, f"  {subkey}: {subvalue}\n")

        info_text.config(state=tk.DISABLED)

    # --- MIDDEN: Extras configuratie ---
    middle_frame = tk.Frame(main_paned, padx=8, pady=8)
    main_paned.add(middle_frame, minsize=600)

    config_title = tk.Label(middle_frame, text="Extras Configuratie", font=("Arial", 13, "bold"))
    config_title.pack(anchor="w")

    # Notebook voor verschillende types extras
    notebook = ttk.Notebook(middle_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    # Tabs
    vlees_frame = ttk.Frame(notebook)
    bijgerecht_frame = ttk.Frame(notebook)
    sauzen_frame = ttk.Frame(notebook)
    garnering_frame = ttk.Frame(notebook)

    notebook.add(vlees_frame, text="Vlees")
    notebook.add(bijgerecht_frame, text="Bijgerechten")
    notebook.add(sauzen_frame, text="Sauzen")
    notebook.add(garnering_frame, text="Garneringen")

    # --- RECHTS: Quick Actions ---
    right_frame = tk.Frame(main_paned, padx=8, pady=8)
    main_paned.add(right_frame, minsize=350)

    tk.Label(right_frame, text="Quick Actions", font=("Arial", 13, "bold")).pack(anchor="w")

    # Categorie toevoegen/verwijderen
    cat_actions_frame = tk.LabelFrame(right_frame, text="Categorie Beheer", padx=10, pady=10)
    cat_actions_frame.pack(fill=tk.X, pady=(10, 0))

    def add_category_to_extras():
        """Voegt een categorie toe aan extras"""
        available = [cat for cat in menu_categories if cat not in extras_data]
        if not available:
            messagebox.showinfo("Info", "Alle menu categorieën hebben al extra configuraties!")
            return

        # Dialog om categorie te selecteren
        dialog = tk.Toplevel(win)
        dialog.title("Categorie Toevoegen")
        dialog.geometry("300x400")
        dialog.transient(win)
        dialog.grab_set()

        tk.Label(dialog, text="Selecteer categorie om toe te voegen:", font=("Arial", 11, "bold")).pack(pady=10)

        listbox = tk.Listbox(dialog, font=("Arial", 10))
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        for cat in available:
            listbox.insert(tk.END, cat)

        def add_selected():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("Selectie", "Selecteer een categorie!")
                return

            category = available[selection[0]]
            extras_data[category] = {}

            if save_extras_data(extras_data):
                refresh_categories()
                refresh_current_config()
                messagebox.showinfo("Succes", f"Categorie '{category}' toegevoegd!")
                dialog.destroy()

        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Toevoegen", command=add_selected, bg="#D1FFD1").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Annuleren", command=dialog.destroy, bg="#FFADAD").pack(side=tk.LEFT, padx=5)

    def remove_category_from_extras():
        """Verwijdert een categorie uit extras"""
        selection = cat_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
            return

        category_display = cat_listbox.get(selection[0])
        category = category_display.split(" (")[0]

        if not messagebox.askyesno("Bevestigen", f"Categorie '{category}' verwijderen uit extras configuratie?"):
            return

        del extras_data[category]
        if save_extras_data(extras_data):
            refresh_categories()
            refresh_current_config()
            messagebox.showinfo("Succes", f"Categorie '{category}' verwijderd!")

    tk.Button(cat_actions_frame, text="Categorie Toevoegen", command=add_category_to_extras,
              bg="#D1FFD1", width=20).pack(fill=tk.X, pady=2)
    tk.Button(cat_actions_frame, text="Categorie Verwijderen", command=remove_category_from_extras,
              bg="#FFADAD", width=20).pack(fill=tk.X, pady=2)

    # Template acties
    template_frame = tk.LabelFrame(right_frame, text="Templates", padx=10, pady=10)
    template_frame.pack(fill=tk.X, pady=(20, 0))

    def apply_pizza_template():
        """Past pizza template toe op huidige categorie"""
        category = get_selected_category()
        if not category:
            messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
            return

        if not messagebox.askyesno("Bevestigen", f"Pizza template toepassen op '{category}'?"):
            return

        pizza_template = {
            "garnering": {
                "Ananas": 2.0,
                "Champignons": 2.0,
                "Ham": 3.0,
                "Salami": 3.0,
                "Paprika": 2.0,
                "Ui": 2.0,
                "Verse tomaat": 2.0,
                "Mozzarella": 3.0,
                "Feta": 3.0
            }
        }

        extras_data[category].update(pizza_template)
        if save_extras_data(extras_data):
            refresh_current_config()
            messagebox.showinfo("Succes", "Pizza template toegepast!")

    def apply_schotel_template():
        """Past schotel template toe op huidige categorie"""
        category = get_selected_category()
        if not category:
            messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
            return

        if not messagebox.askyesno("Bevestigen", f"Schotel template toepassen op '{category}'?"):
            return

        schotel_template = {
            "vlees": ["Pita", "Kip", "Lams", "Kalkoen"],
            "bijgerecht": ["Frieten", "Brood", "Kroketten", "Aardappelen"],
            "sauzen": ["Looksaus", "Samurai", "Cocktail", "Currysaus", "Andalouse", "Ketchup", "Mayonaise"],
            "sauzen_aantal": 2,
            "garnering": {
                "Extra vlees": 3.0,
                "Extra saus": 1.0,
                "Kaas": 2.0
            }
        }

        extras_data[category].update(schotel_template)
        if save_extras_data(extras_data):
            refresh_current_config()
            messagebox.showinfo("Succes", "Schotel template toegepast!")

    tk.Button(template_frame, text="Pizza Template", command=apply_pizza_template,
              bg="#FFE5B4", width=20).pack(fill=tk.X, pady=2)
    tk.Button(template_frame, text="Schotel Template", command=apply_schotel_template,
              bg="#FFE5B4", width=20).pack(fill=tk.X, pady=2)

    # Bulk prijsaanpassingen
    bulk_frame = tk.LabelFrame(right_frame, text="Bulk Prijsaanpassingen", padx=10, pady=10)
    bulk_frame.pack(fill=tk.X, pady=(20, 0))

    def bulk_garnering_price_adjustment():
        """Bulk prijsaanpassing voor garneringen"""
        category = get_selected_category()
        if not category or 'garnering' not in extras_data.get(category, {}):
            messagebox.showwarning("Fout", "Selecteer een categorie met garneringen!")
            return

        # Simple dialog voor prijsaanpassing
        adjustment = simpledialog.askfloat(
            "Prijsaanpassing",
            f"Hoeveel euro toevoegen/aftrekken van alle garnering prijzen in '{category}'?\n(gebruik - voor verlagen)",
            minvalue=-50.0,
            maxvalue=50.0
        )

        if adjustment is None:
            return

        if not messagebox.askyesno("Bevestigen",
                                   f"Alle garnering prijzen in '{category}' met €{adjustment:.2f} aanpassen?"):
            return

        garnering = extras_data[category]['garnering']
        count = 0
        for item, price in garnering.items():
            new_price = max(0, price + adjustment)  # Zorg dat prijs niet negatief wordt
            garnering[item] = round(new_price, 2)
            count += 1

        if save_extras_data(extras_data):
            refresh_current_config()
            messagebox.showinfo("Succes", f"{count} garnering prijzen aangepast!")

    tk.Button(bulk_frame, text="Garnering Prijzen", command=bulk_garnering_price_adjustment,
              bg="#E1E1FF", width=20).pack(fill=tk.X, pady=2)

    # Helper functions
    def get_selected_category():
        """Geeft de geselecteerde categorie terug"""
        selection = cat_listbox.curselection()
        if not selection:
            return None
        category_display = cat_listbox.get(selection[0])
        return category_display.split(" (")[0]

    def refresh_current_config():
        """Vernieuwt de huidige configuratie weergave"""
        category = get_selected_category()
        if category:
            load_category_config(category)
            update_category_info()
        refresh_categories()

    # Tab content functions
    def setup_vlees_tab():
        """Setup vlees tab"""
        tk.Label(vlees_frame, text="Vlees Opties", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))

        vlees_listbox = tk.Listbox(vlees_frame, font=("Arial", 10))
        vlees_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        vlees_buttons = tk.Frame(vlees_frame)
        vlees_buttons.pack(fill=tk.X, padx=10, pady=5)

        def add_vlees():
            category = get_selected_category()
            if not category:
                messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
                return

            vlees_naam = simpledialog.askstring("Nieuwe Vlees Optie", "Naam van de vlees optie:")
            if vlees_naam and vlees_naam.strip():
                if category not in extras_data:
                    extras_data[category] = {}
                if 'vlees' not in extras_data[category]:
                    extras_data[category]['vlees'] = []

                if vlees_naam.strip() not in extras_data[category]['vlees']:
                    extras_data[category]['vlees'].append(vlees_naam.strip())
                    if save_extras_data(extras_data):
                        load_category_config(category)
                        messagebox.showinfo("Succes", f"Vlees optie '{vlees_naam}' toegevoegd!")
                else:
                    messagebox.showwarning("Bestaat al", "Deze vlees optie bestaat al!")

        def remove_vlees():
            selection = vlees_listbox.curselection()
            if not selection:
                messagebox.showwarning("Selectie", "Selecteer eerst een vlees optie!")
                return

            category = get_selected_category()
            if not category:
                return

            vlees_naam = vlees_listbox.get(selection[0])
            if messagebox.askyesno("Bevestigen", f"Vlees optie '{vlees_naam}' verwijderen?"):
                extras_data[category]['vlees'].remove(vlees_naam)
                if save_extras_data(extras_data):
                    load_category_config(category)
                    messagebox.showinfo("Succes", f"Vlees optie '{vlees_naam}' verwijderd!")

        tk.Button(vlees_buttons, text="Toevoegen", command=add_vlees, bg="#D1FFD1", width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(vlees_buttons, text="Verwijderen", command=remove_vlees, bg="#FFADAD", width=12).pack(side=tk.LEFT,
                                                                                                        padx=5)

        return vlees_listbox

    def setup_bijgerecht_tab():
        """Setup bijgerecht tab"""
        tk.Label(bijgerecht_frame, text="Bijgerecht Opties", font=("Arial", 12, "bold")).pack(anchor="w", padx=10,
                                                                                              pady=(10, 5))

        bijgerecht_listbox = tk.Listbox(bijgerecht_frame, font=("Arial", 10))
        bijgerecht_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Aantal frame
        aantal_frame = tk.Frame(bijgerecht_frame)
        aantal_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(aantal_frame, text="Aantal bijgerechten:").pack(side=tk.LEFT)
        bijgerecht_aantal_var = tk.IntVar(value=1)
        tk.Spinbox(aantal_frame, from_=1, to=10, textvariable=bijgerecht_aantal_var, width=5).pack(side=tk.LEFT,
                                                                                                   padx=(5, 0))

        def update_bijgerecht_aantal():
            category = get_selected_category()
            if category and category in extras_data:
                extras_data[category]['bijgerecht_aantal'] = bijgerecht_aantal_var.get()
                save_extras_data(extras_data)

        tk.Button(aantal_frame, text="Update", command=update_bijgerecht_aantal, bg="#E1E1FF").pack(side=tk.LEFT,
                                                                                                    padx=(10, 0))

        bijgerecht_buttons = tk.Frame(bijgerecht_frame)
        bijgerecht_buttons.pack(fill=tk.X, padx=10, pady=5)

        def add_bijgerecht():
            category = get_selected_category()
            if not category:
                messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
                return

            bijgerecht_naam = simpledialog.askstring("Nieuwe Bijgerecht Optie", "Naam van het bijgerecht:")
            if bijgerecht_naam and bijgerecht_naam.strip():
                if category not in extras_data:
                    extras_data[category] = {}
                if 'bijgerecht' not in extras_data[category]:
                    extras_data[category]['bijgerecht'] = []

                if bijgerecht_naam.strip() not in extras_data[category]['bijgerecht']:
                    extras_data[category]['bijgerecht'].append(bijgerecht_naam.strip())
                    if save_extras_data(extras_data):
                        load_category_config(category)
                        messagebox.showinfo("Succes", f"Bijgerecht '{bijgerecht_naam}' toegevoegd!")
                else:
                    messagebox.showwarning("Bestaat al", "Dit bijgerecht bestaat al!")

        def remove_bijgerecht():
            selection = bijgerecht_listbox.curselection()
            if not selection:
                messagebox.showwarning("Selectie", "Selecteer eerst een bijgerecht!")
                return

            category = get_selected_category()
            if not category:
                return

            bijgerecht_naam = bijgerecht_listbox.get(selection[0])
            if messagebox.askyesno("Bevestigen", f"Bijgerecht '{bijgerecht_naam}' verwijderen?"):
                extras_data[category]['bijgerecht'].remove(bijgerecht_naam)
                if save_extras_data(extras_data):
                    load_category_config(category)
                    messagebox.showinfo("Succes", f"Bijgerecht '{bijgerecht_naam}' verwijderd!")

        tk.Button(bijgerecht_buttons, text="Toevoegen", command=add_bijgerecht, bg="#D1FFD1", width=12).pack(
            side=tk.LEFT, padx=5)
        tk.Button(bijgerecht_buttons, text="Verwijderen", command=remove_bijgerecht, bg="#FFADAD", width=12).pack(
            side=tk.LEFT, padx=5)

        return bijgerecht_listbox, bijgerecht_aantal_var

    def setup_sauzen_tab():
        """Setup sauzen tab"""
        tk.Label(sauzen_frame, text="Sauzen Opties", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 5))

        sauzen_listbox = tk.Listbox(sauzen_frame, font=("Arial", 10))
        sauzen_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Aantal frame
        sauzen_aantal_frame = tk.Frame(sauzen_frame)
        sauzen_aantal_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(sauzen_aantal_frame, text="Aantal sauzen:").pack(side=tk.LEFT)
        sauzen_aantal_var = tk.IntVar(value=1)
        tk.Spinbox(sauzen_aantal_frame, from_=1, to=10, textvariable=sauzen_aantal_var, width=5).pack(side=tk.LEFT,
                                                                                                      padx=(5, 0))

        def update_sauzen_aantal():
            category = get_selected_category()
            if category and category in extras_data:
                extras_data[category]['sauzen_aantal'] = sauzen_aantal_var.get()
                save_extras_data(extras_data)

        tk.Button(sauzen_aantal_frame, text="Update", command=update_sauzen_aantal, bg="#E1E1FF").pack(side=tk.LEFT,
                                                                                                       padx=(10, 0))

        sauzen_buttons = tk.Frame(sauzen_frame)
        sauzen_buttons.pack(fill=tk.X, padx=10, pady=5)

        def add_saus():
            category = get_selected_category()
            if not category:
                messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
                return

            saus_naam = simpledialog.askstring("Nieuwe Saus", "Naam van de saus:")
            if saus_naam and saus_naam.strip():
                if category not in extras_data:
                    extras_data[category] = {}

                # Bepaal de juiste sleutel (saus of sauzen)
                saus_key = 'sauzen' if 'sauzen' in extras_data[category] else 'saus'
                if saus_key not in extras_data[category]:
                    extras_data[category][saus_key] = []

                if saus_naam.strip() not in extras_data[category][saus_key]:
                    extras_data[category][saus_key].append(saus_naam.strip())
                    if save_extras_data(extras_data):
                        load_category_config(category)
                        messagebox.showinfo("Succes", f"Saus '{saus_naam}' toegevoegd!")
                else:
                    messagebox.showwarning("Bestaat al", "Deze saus bestaat al!")

        def remove_saus():
            selection = sauzen_listbox.curselection()
            if not selection:
                messagebox.showwarning("Selectie", "Selecteer eerst een saus!")
                return

            category = get_selected_category()
            if not category:
                return

            saus_naam = sauzen_listbox.get(selection[0])
            saus_key = 'sauzen' if 'sauzen' in extras_data[category] else 'saus'

            if messagebox.askyesno("Bevestigen", f"Saus '{saus_naam}' verwijderen?"):
                extras_data[category][saus_key].remove(saus_naam)
                if save_extras_data(extras_data):
                    load_category_config(category)
                    messagebox.showinfo("Succes", f"Saus '{saus_naam}' verwijderd!")

        tk.Button(sauzen_buttons, text="Toevoegen", command=add_saus, bg="#D1FFD1", width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(sauzen_buttons, text="Verwijderen", command=remove_saus, bg="#FFADAD", width=12).pack(side=tk.LEFT,
                                                                                                        padx=5)

        return sauzen_listbox, sauzen_aantal_var

    def setup_garnering_tab():
        """Setup garnering tab"""
        tk.Label(garnering_frame, text="Garneringen (met prijzen)", font=("Arial", 12, "bold")).pack(anchor="w",
                                                                                                     padx=10,
                                                                                                     pady=(10, 5))

        # Treeview voor naam + prijs
        tree_frame = tk.Frame(garnering_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        garnering_tree = ttk.Treeview(tree_frame, columns=('prijs',), show='tree headings', height=15)
        garnering_tree.heading('#0', text='Garnering')
        garnering_tree.heading('prijs', text='Prijs (€)')
        garnering_tree.column('#0', width=200)
        garnering_tree.column('prijs', width=100, anchor='e')

        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=garnering_tree.yview)
        garnering_tree.configure(yscrollcommand=tree_scrollbar.set)

        garnering_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        garnering_buttons = tk.Frame(garnering_frame)
        garnering_buttons.pack(fill=tk.X, padx=10, pady=5)

        def add_garnering():
            category = get_selected_category()
            if not category:
                messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
                return

            # Dialog voor garnering + prijs
            dialog = tk.Toplevel(win)
            dialog.title("Nieuwe Garnering")
            dialog.geometry("300x150")
            dialog.transient(win)
            dialog.grab_set()

            tk.Label(dialog, text="Naam:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
            naam_var = tk.StringVar()
            tk.Entry(dialog, textvariable=naam_var, width=20).grid(row=0, column=1, padx=10, pady=5)

            tk.Label(dialog, text="Prijs (€):").grid(row=1, column=0, sticky="w", padx=10, pady=5)
            prijs_var = tk.StringVar()
            tk.Entry(dialog, textvariable=prijs_var, width=20).grid(row=1, column=1, padx=10, pady=5)

            def save_garnering():
                naam = naam_var.get().strip()
                try:
                    prijs = float(prijs_var.get().replace(',', '.'))
                except ValueError:
                    messagebox.showerror("Fout", "Voer een geldige prijs in!")
                    return

                if not naam:
                    messagebox.showerror("Fout", "Voer een naam in!")
                    return

                if category not in extras_data:
                    extras_data[category] = {}
                if 'garnering' not in extras_data[category]:
                    extras_data[category]['garnering'] = {}

                extras_data[category]['garnering'][naam] = prijs
                if save_extras_data(extras_data):
                    load_category_config(category)
                    messagebox.showinfo("Succes", f"Garnering '{naam}' toegevoegd!")
                    dialog.destroy()

            button_frame = tk.Frame(dialog)
            button_frame.grid(row=2, column=0, columnspan=2, pady=20)
            tk.Button(button_frame, text="Opslaan", command=save_garnering, bg="#D1FFD1").pack(side=tk.LEFT, padx=5)
            tk.Button(button_frame, text="Annuleren", command=dialog.destroy, bg="#FFADAD").pack(side=tk.LEFT, padx=5)

        def edit_garnering():
            selection = garnering_tree.selection()
            if not selection:
                messagebox.showwarning("Selectie", "Selecteer eerst een garnering!")
                return

            category = get_selected_category()
            if not category:
                return

            item = garnering_tree.item(selection[0])
            naam = item['text']
            huidige_prijs = extras_data[category]['garnering'][naam]

            # Edit dialog
            dialog = tk.Toplevel(win)
            dialog.title("Garnering Bewerken")
            dialog.geometry("300x150")
            dialog.transient(win)
            dialog.grab_set()

            tk.Label(dialog, text="Naam:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
            naam_var = tk.StringVar(value=naam)
            tk.Entry(dialog, textvariable=naam_var, width=20).grid(row=0, column=1, padx=10, pady=5)

            tk.Label(dialog, text="Prijs (€):").grid(row=1, column=0, sticky="w", padx=10, pady=5)
            prijs_var = tk.StringVar(value=str(huidige_prijs))
            tk.Entry(dialog, textvariable=prijs_var, width=20).grid(row=1, column=1, padx=10, pady=5)

            def save_changes():
                nieuwe_naam = naam_var.get().strip()
                try:
                    nieuwe_prijs = float(prijs_var.get().replace(',', '.'))
                except ValueError:
                    messagebox.showerror("Fout", "Voer een geldige prijs in!")
                    return

                if not nieuwe_naam:
                    messagebox.showerror("Fout", "Voer een naam in!")
                    return

                # Verwijder oude entry als naam veranderd
                if nieuwe_naam != naam:
                    del extras_data[category]['garnering'][naam]

                extras_data[category]['garnering'][nieuwe_naam] = nieuwe_prijs
                if save_extras_data(extras_data):
                    load_category_config(category)
                    messagebox.showinfo("Succes", f"Garnering '{nieuwe_naam}' bijgewerkt!")
                    dialog.destroy()

            button_frame = tk.Frame(dialog)
            button_frame.grid(row=2, column=0, columnspan=2, pady=20)
            tk.Button(button_frame, text="Opslaan", command=save_changes, bg="#D1FFD1").pack(side=tk.LEFT, padx=5)
            tk.Button(button_frame, text="Annuleren", command=dialog.destroy, bg="#FFADAD").pack(side=tk.LEFT, padx=5)

        def remove_garnering():
            selection = garnering_tree.selection()
            if not selection:
                messagebox.showwarning("Selectie", "Selecteer eerst een garnering!")
                return

            category = get_selected_category()
            if not category:
                return

            item = garnering_tree.item(selection[0])
            naam = item['text']

            if messagebox.askyesno("Bevestigen", f"Garnering '{naam}' verwijderen?"):
                del extras_data[category]['garnering'][naam]
                if save_extras_data(extras_data):
                    load_category_config(category)
                    messagebox.showinfo("Succes", f"Garnering '{naam}' verwijderd!")

        tk.Button(garnering_buttons, text="Toevoegen", command=add_garnering, bg="#D1FFD1", width=12).pack(side=tk.LEFT,
                                                                                                           padx=5)
        tk.Button(garnering_buttons, text="Bewerken", command=edit_garnering, bg="#FFE5B4", width=12).pack(side=tk.LEFT,
                                                                                                           padx=5)
        tk.Button(garnering_buttons, text="Verwijderen", command=remove_garnering, bg="#FFADAD", width=12).pack(
            side=tk.LEFT, padx=5)

        return garnering_tree

    # Setup alle tabs
    vlees_listbox = setup_vlees_tab()
    bijgerecht_listbox, bijgerecht_aantal_var = setup_bijgerecht_tab()
    sauzen_listbox, sauzen_aantal_var = setup_sauzen_tab()
    garnering_tree = setup_garnering_tab()

    def load_category_config(category):
        """Laadt configuratie voor een categorie"""
        if category not in extras_data:
            return

        cat_data = extras_data[category]

        # Clear all
        vlees_listbox.delete(0, tk.END)
        bijgerecht_listbox.delete(0, tk.END)
        sauzen_listbox.delete(0, tk.END)
        garnering_tree.delete(*garnering_tree.get_children())

        # Load vlees
        if 'vlees' in cat_data and isinstance(cat_data['vlees'], list):
            for vlees in cat_data['vlees']:
                vlees_listbox.insert(tk.END, vlees)

        # Load bijgerecht
        if 'bijgerecht' in cat_data and isinstance(cat_data['bijgerecht'], list):
            for bijgerecht in cat_data['bijgerecht']:
                bijgerecht_listbox.insert(tk.END, bijgerecht)

        bijgerecht_aantal_var.set(cat_data.get('bijgerecht_aantal', 1))

        # Load sauzen
        saus_key = 'sauzen' if 'sauzen' in cat_data else 'saus'
        if saus_key in cat_data and isinstance(cat_data[saus_key], list):
            for saus in cat_data[saus_key]:
                sauzen_listbox.insert(tk.END, saus)

        sauzen_aantal_var.set(cat_data.get('sauzen_aantal', 1))

        # Load garnering
        if 'garnering' in cat_data and isinstance(cat_data['garnering'], dict):
            for naam, prijs in cat_data['garnering'].items():
                garnering_tree.insert('', tk.END, text=naam, values=[f"{prijs:.2f}"])

        config_title.config(text=f"Extras Configuratie — {category}")

    # Event handlers
    def on_category_select(event=None):
        category = get_selected_category()
        if category:
            load_category_config(category)
            update_category_info()

    cat_listbox.bind("<<ListboxSelect>>", on_category_select)

    # Initial load
    refresh_categories()
    if extras_data:
        cat_listbox.selection_set(0)
        on_category_select()