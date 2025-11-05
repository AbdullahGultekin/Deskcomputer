import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import datetime
import database


def open_klant_management(root):
    """Opent het uitgebreide klant management venster"""

    # EMBED in tab i.p.v. Toplevel
    win = root
    for w in win.winfo_children():
        w.destroy()

    # Main PanedWindow (3-koloms layout) direct in de tab
    main_paned = tk.PanedWindow(win, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashpad=4)
    main_paned.pack(fill=tk.BOTH, expand=True)

    # --- LINKS: Klanten zoeken en lijst ---
    left_frame = tk.Frame(main_paned, padx=8, pady=8)
    main_paned.add(left_frame, minsize=400)

    # Zoekbalk
    search_frame = tk.Frame(left_frame)
    search_frame.pack(fill=tk.X, pady=(0, 10))

    tk.Label(search_frame, text="Zoek klant:", font=("Arial", 11, "bold")).pack(anchor="w")

    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var, font=("Arial", 11))
    search_entry.pack(fill=tk.X, pady=(2, 0))
    search_entry.focus()

    # Klanten treeview
    tree_frame = tk.Frame(left_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    columns = ('telefoon', 'naam', 'adres', 'laatste_bestelling', 'totaal_bestellingen')
    klanten_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

    # Column headers en widths
    klanten_tree.heading('telefoon', text='Telefoon')
    klanten_tree.column('telefoon', width=120, anchor='center')
    klanten_tree.heading('naam', text='Naam')
    klanten_tree.column('naam', width=150)
    klanten_tree.heading('adres', text='Adres')
    klanten_tree.column('adres', width=200)
    klanten_tree.heading('laatste_bestelling', text='Laatste Bestelling')
    klanten_tree.column('laatste_bestelling', width=120, anchor='center')
    klanten_tree.heading('totaal_bestellingen', text='# Bestellingen')
    klanten_tree.column('totaal_bestellingen', width=100, anchor='center')

    tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=klanten_tree.yview)
    klanten_tree.configure(yscrollcommand=tree_scrollbar.set)

    klanten_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # --- MIDDEN: Klantdetails ---
    middle_frame = tk.Frame(main_paned, padx=8, pady=8)
    main_paned.add(middle_frame, minsize=500)

    detail_title = tk.Label(middle_frame, text="Klantdetails", font=("Arial", 13, "bold"))
    detail_title.pack(anchor="w")

    # Notebook voor verschillende tabs
    notebook = ttk.Notebook(middle_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    # Tab frames
    info_frame = ttk.Frame(notebook)
    geschiedenis_frame = ttk.Frame(notebook)
    favorieten_frame = ttk.Frame(notebook)
    notities_frame = ttk.Frame(notebook)

    notebook.add(info_frame, text="Info")
    notebook.add(geschiedenis_frame, text="Geschiedenis")
    notebook.add(favorieten_frame, text="Favorieten")
    notebook.add(notities_frame, text="Notities")

    # --- RECHTS: Acties en statistieken ---
    right_frame = tk.Frame(main_paned, padx=8, pady=8)
    main_paned.add(right_frame, minsize=350)

    tk.Label(right_frame, text="Klant Acties", font=("Arial", 13, "bold")).pack(anchor="w")

    # Global variable voor geselecteerde klant
    selected_klant = {'data': None}

    # --- ZOEKFUNCTIONALITEIT ---
    def zoek_klanten(*args):
        """Zoekt klanten op basis van zoekterm"""
        zoekterm = search_var.get().strip()

        # Clear tree
        klanten_tree.delete(*klanten_tree.get_children())

        conn = database.get_db_connection()
        cursor = conn.cursor()

        if zoekterm:
            # Zoek op telefoon, naam, adres
            cursor.execute("""
                           SELECT id,
                                  telefoon,
                                  naam,
                                  straat,
                                  huisnummer,
                                  plaats,
                                  laatste_bestelling,
                                  totaal_bestellingen,
                                  totaal_besteed
                           FROM klanten
                           WHERE telefoon LIKE ?
                              OR naam LIKE ?
                              OR straat LIKE ?
                           ORDER BY totaal_bestellingen DESC, laatste_bestelling DESC
                           """, (f"%{zoekterm}%", f"%{zoekterm}%", f"%{zoekterm}%"))
        else:
            # Toon alle klanten, gesorteerd op activiteit
            cursor.execute("""
                           SELECT id,
                                  telefoon,
                                  naam,
                                  straat,
                                  huisnummer,
                                  plaats,
                                  laatste_bestelling,
                                  totaal_bestellingen,
                                  totaal_besteed
                           FROM klanten
                           ORDER BY totaal_bestellingen DESC, laatste_bestelling DESC LIMIT 100
                           """)

        for klant in cursor.fetchall():
            adres = f"{klant['straat'] or ''} {klant['huisnummer'] or ''}".strip()
            laatste_bestelling = klant['laatste_bestelling'] or 'Nooit'
            if laatste_bestelling != 'Nooit' and ' ' in laatste_bestelling:
                # Format datum
                try:
                    datum_deel = laatste_bestelling.split(' ')[0]
                    laatste_bestelling = datetime.datetime.strptime(datum_deel, '%Y-%m-%d').strftime('%d/%m/%Y')
                except:
                    pass

            klanten_tree.insert("", tk.END, iid=klant['id'], values=(
                klant['telefoon'],
                klant['naam'] or '',
                adres,
                laatste_bestelling,
                klant['totaal_bestellingen'] or 0
            ))

        conn.close()

    def on_klant_select(event):
        """Handler voor klant selectie"""
        selection = klanten_tree.selection()
        if not selection:
            selected_klant['data'] = None
            clear_klant_details()
            return

        klant_id = int(selection[0])
        load_klant_details(klant_id)

    def clear_klant_details():
        """Wist klantdetails"""
        detail_title.config(text="Klantdetails")
        # Clear alle tabs
        for widget in info_frame.winfo_children():
            widget.destroy()
        for widget in geschiedenis_frame.winfo_children():
            widget.destroy()
        for widget in favorieten_frame.winfo_children():
            widget.destroy()
        for widget in notities_frame.winfo_children():
            widget.destroy()

    def load_klant_details(klant_id):
        """Laadt details voor geselecteerde klant"""
        conn = database.get_db_connection()
        cursor = conn.cursor()

        # Haal klantgegevens op
        cursor.execute("SELECT * FROM klanten WHERE id = ?", (klant_id,))
        klant = cursor.fetchone()

        if not klant:
            conn.close()
            return

        selected_klant['data'] = dict(klant)
        detail_title.config(text=f"Klantdetails — {klant['telefoon']}")

        # Clear en vul tabs
        clear_klant_details()
        setup_info_tab(klant)
        setup_geschiedenis_tab(klant_id)
        setup_favorieten_tab(klant_id)
        setup_notities_tab(klant_id)

        conn.close()

    # --- INFO TAB ---
    def setup_info_tab(klant):
        """Setup klantinfo tab"""
        # Klantgegevens frame
        info_main = tk.Frame(info_frame, padx=10, pady=10)
        info_main.pack(fill=tk.BOTH, expand=True)

        # Contact informatie
        contact_frame = tk.LabelFrame(info_main, text="Contact Informatie", padx=10, pady=10)
        contact_frame.pack(fill=tk.X, pady=(0, 10))

        info_data = [
            ("Telefoon:", klant['telefoon']),
            ("Naam:", klant['naam'] or 'Niet opgegeven'),
            ("Adres:", f"{klant['straat'] or ''} {klant['huisnummer'] or ''}".strip()),
            ("Plaats:", klant['plaats'] or ''),
        ]

        for i, (label, value) in enumerate(info_data):
            tk.Label(contact_frame, text=label, font=("Arial", 10, "bold")).grid(row=i, column=0, sticky="w", pady=2)
            tk.Label(contact_frame, text=value, font=("Arial", 10)).grid(row=i, column=1, sticky="w", padx=(10, 0),
                                                                         pady=2)

        # Statistieken
        stats_frame = tk.LabelFrame(info_main, text="Statistieken", padx=10, pady=10)
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        stats_data = [
            ("Totaal bestellingen:", str(klant['totaal_bestellingen'] or 0)),
            ("Totaal besteed:", f"€{klant['totaal_besteed'] or 0:.2f}"),
            ("Laatste bestelling:", klant['laatste_bestelling'] or 'Nooit'),
            ("Gemiddelde bestelling:",
             f"€{(klant['totaal_besteed'] or 0) / max(klant['totaal_bestellingen'] or 1, 1):.2f}"),
        ]

        for i, (label, value) in enumerate(stats_data):
            tk.Label(stats_frame, text=label, font=("Arial", 10, "bold")).grid(row=i, column=0, sticky="w", pady=2)
            tk.Label(stats_frame, text=value, font=("Arial", 10)).grid(row=i, column=1, sticky="w", padx=(10, 0),
                                                                       pady=2)

        # Voorkeuren
        prefs_frame = tk.LabelFrame(info_main, text="Voorkeuren", padx=10, pady=10)
        prefs_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(prefs_frame, text="Levering voorkeur:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w",
                                                                                          pady=2)
        voorkeur_var = tk.StringVar(value=klant['voorkeur_levering'] or 'Geen voorkeur')
        voorkeur_combo = ttk.Combobox(prefs_frame, textvariable=voorkeur_var,
                                      values=['Geen voorkeur', 'Snel leveren', 'Contact bij aankomst', 'Achtertuin',
                                              'Speciale instructies'])
        voorkeur_combo.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=2)

        def update_voorkeur():
            if selected_klant['data']:
                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE klanten SET voorkeur_levering = ? WHERE id = ?",
                               (voorkeur_var.get(), selected_klant['data']['id']))
                conn.commit()
                conn.close()
                selected_klant['data']['voorkeur_levering'] = voorkeur_var.get()

        tk.Button(prefs_frame, text="Opslaan", command=update_voorkeur, bg="#D1FFD1").grid(row=0, column=2, padx=(5, 0))
        prefs_frame.grid_columnconfigure(1, weight=1)

    # --- GESCHIEDENIS TAB ---
    def setup_geschiedenis_tab(klant_id):
        """Setup geschiedenis tab"""
        gesch_main = tk.Frame(geschiedenis_frame, padx=10, pady=10)
        gesch_main.pack(fill=tk.BOTH, expand=True)

        # Bestellingen treeview
        cols = ('datum', 'tijd', 'totaal', 'producten', 'status')
        gesch_tree = ttk.Treeview(gesch_main, columns=cols, show='headings', height=15)

        gesch_tree.heading('datum', text='Datum')
        gesch_tree.column('datum', width=80, anchor='center')
        gesch_tree.heading('tijd', text='Tijd')
        gesch_tree.column('tijd', width=60, anchor='center')
        gesch_tree.heading('totaal', text='Totaal (€)')
        gesch_tree.column('totaal', width=80, anchor='e')
        gesch_tree.heading('producten', text='Producten')
        gesch_tree.column('producten', width=300)
        gesch_tree.heading('status', text='Status')
        gesch_tree.column('status', width=80, anchor='center')

        gesch_scroll = ttk.Scrollbar(gesch_main, orient=tk.VERTICAL, command=gesch_tree.yview)
        gesch_tree.configure(yscrollcommand=gesch_scroll.set)

        gesch_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        gesch_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Laad bestellingen
        conn = database.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT b.id,
                              b.datum,
                              b.tijd,
                              b.totaal,
                              b.opmerking,
                              GROUP_CONCAT(br.aantal || 'x ' || br.product, ', ') as producten
                       FROM bestellingen b
                                LEFT JOIN bestelregels br ON b.id = br.bestelling_id
                       WHERE b.klant_id = ?
                       GROUP BY b.id
                       ORDER BY b.datum DESC, b.tijd DESC
                       """, (klant_id,))

        for bestelling in cursor.fetchall():
            datum_str = datetime.datetime.strptime(bestelling['datum'], '%Y-%m-%d').strftime('%d/%m/%Y')
            producten = bestelling['producten'] or 'Geen producten'
            if len(producten) > 50:
                producten = producten[:47] + '...'

            gesch_tree.insert("", tk.END, values=(
                datum_str,
                bestelling['tijd'],
                f"{bestelling['totaal']:.2f}",
                producten,
                'Voltooid'
            ))

        conn.close()

        # Knop voor toevoegen aan favorieten
        def voeg_toe_aan_favorieten():
            selection = gesch_tree.selection()
            if not selection:
                messagebox.showwarning("Selectie", "Selecteer eerst een bestelling!")
                return

            # Implementatie komt later in deze functie...
            open_favoriet_dialog(klant_id, selection[0])

        btn_frame = tk.Frame(gesch_main)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        tk.Button(btn_frame, text="Voeg toe aan Favorieten", command=voeg_toe_aan_favorieten,
                  bg="#FFE5B4").pack(side=tk.LEFT)

    # --- FAVORIETEN TAB ---
    def setup_favorieten_tab(klant_id):
        """Setup favorieten tab"""
        fav_main = tk.Frame(favorieten_frame, padx=10, pady=10)
        fav_main.pack(fill=tk.BOTH, expand=True)

        # Favorieten treeview
        cols = ('naam', 'totaal', 'producten', 'laatst_gebruikt', 'gebruik_count')
        fav_tree = ttk.Treeview(fav_main, columns=cols, show='headings', height=12)

        fav_tree.heading('naam', text='Naam')
        fav_tree.column('naam', width=120)
        fav_tree.heading('totaal', text='Totaal (€)')
        fav_tree.column('totaal', width=80, anchor='e')
        fav_tree.heading('producten', text='Producten')
        fav_tree.column('producten', width=250)
        fav_tree.heading('laatst_gebruikt', text='Laatst Gebruikt')
        fav_tree.column('laatst_gebruikt', width=100, anchor='center')
        fav_tree.heading('gebruik_count', text='Gebruikt')
        fav_tree.column('gebruik_count', width=70, anchor='center')

        fav_scroll = ttk.Scrollbar(fav_main, orient=tk.VERTICAL, command=fav_tree.yview)
        fav_tree.configure(yscrollcommand=fav_scroll.set)

        fav_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 10))
        fav_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))

        def refresh_favorieten():
            """Vernieuwt de favorieten lijst"""
            fav_tree.delete(*fav_tree.get_children())

            conn = database.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                           SELECT *
                           FROM favoriete_bestellingen
                           WHERE klant_id = ?
                           ORDER BY gebruik_count DESC, laatst_gebruikt DESC
                           """, (klant_id,))

            for favoriet in cursor.fetchall():
                try:
                    bestelregels = json.loads(favoriet['bestelregels_json'])
                    producten_str = ', '.join([f"{regel.get('aantal', 1)}x {regel.get('product', '')}"
                                               for regel in bestelregels[:3]])  # Eerste 3 producten
                    if len(bestelregels) > 3:
                        producten_str += f' (+{len(bestelregels) - 3} meer)'
                except:
                    producten_str = 'Fout bij laden'

                laatst_gebruikt = favoriet['laatst_gebruikt'] or 'Nooit'
                if laatst_gebruikt != 'Nooit':
                    try:
                        laatst_gebruikt = datetime.datetime.strptime(laatst_gebruikt, '%Y-%m-%d').strftime('%d/%m/%Y')
                    except:
                        pass

                fav_tree.insert("", tk.END, iid=favoriet['id'], values=(
                    favoriet['naam'],
                    f"{favoriet['totaal_prijs']:.2f}",
                    producten_str,
                    laatst_gebruikt,
                    favoriet['gebruik_count'] or 0
                ))

            conn.close()

        refresh_favorieten()

        # Knoppen
        btn_frame = tk.Frame(fav_main)
        btn_frame.pack(fill=tk.X)

        def nieuw_favoriet():
            """Maakt een nieuwe favoriet aan"""
            open_favoriet_dialog(klant_id)

        def bewerk_favoriet():
            """Bewerkt geselecteerde favoriet"""
            selection = fav_tree.selection()
            if not selection:
                messagebox.showwarning("Selectie", "Selecteer eerst een favoriet!")
                return
            # Implementatie...
            messagebox.showinfo("Info", "Bewerk functionaliteit komt binnenkort!")

        def verwijder_favoriet():
            """Verwijdert geselecteerde favoriet"""
            selection = fav_tree.selection()
            if not selection:
                messagebox.showwarning("Selectie", "Selecteer eerst een favoriet!")
                return

            if messagebox.askyesno("Bevestigen", "Favoriet verwijderen?"):
                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM favoriete_bestellingen WHERE id = ?", (selection[0],))
                conn.commit()
                conn.close()
                refresh_favorieten()

        def gebruik_favoriet():
            """Gebruikt geselecteerde favoriet voor nieuwe bestelling"""
            selection = fav_tree.selection()
            if not selection:
                messagebox.showwarning("Selectie", "Selecteer eerst een favoriet!")
                return

            # Update gebruik statistieken
            conn = database.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM favoriete_bestellingen WHERE id = ?", (selection[0],))
            favoriet = cursor.fetchone()

            cursor.execute("""
                           UPDATE favoriete_bestellingen
                           SET gebruik_count   = gebruik_count + 1,
                               laatst_gebruikt = ?
                           WHERE id = ?
                           """, (datetime.date.today().strftime('%Y-%m-%d'), selection[0]))
            conn.commit()
            conn.close()

            refresh_favorieten()
            messagebox.showinfo("Succes",
                                f"Favoriet '{favoriet['naam']}' is geactiveerd!\nVoeg de producten toe aan je bestelling.")

        tk.Button(btn_frame, text="Nieuw Favoriet", command=nieuw_favoriet, bg="#D1FFD1").pack(side=tk.LEFT,
                                                                                               padx=(0, 5))
        tk.Button(btn_frame, text="Bewerken", command=bewerk_favoriet, bg="#FFE5B4").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Verwijderen", command=verwijder_favoriet, bg="#FFADAD").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Gebruik", command=gebruik_favoriet, bg="#D1FFE1").pack(side=tk.RIGHT)

    # --- NOTITIES TAB ---
    def setup_notities_tab(klant_id):
        """Setup notities tab"""
        not_main = tk.Frame(notities_frame, padx=10, pady=10)
        not_main.pack(fill=tk.BOTH, expand=True)

        # Huidige notitie (hoofdnotitie van klant)
        current_frame = tk.LabelFrame(not_main, text="Huidige Notitie", padx=5, pady=5)
        current_frame.pack(fill=tk.X, pady=(0, 10))

        notitie_text = tk.Text(current_frame, height=4, width=50, font=("Arial", 10))
        notitie_text.pack(fill=tk.X, pady=2)

        # Laad huidige notitie
        if selected_klant['data']:
            notitie_text.insert('1.0', selected_klant['data']['notities'] or '')

        def save_notitie():
            """Slaat de hoofdnotitie op"""
            if not selected_klant['data']:
                return

            nieuwe_notitie = notitie_text.get('1.0', tk.END).strip()

            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE klanten SET notities = ? WHERE id = ?",
                           (nieuwe_notitie, selected_klant['data']['id']))
            conn.commit()
            conn.close()

            selected_klant['data']['notities'] = nieuwe_notitie
            messagebox.showinfo("Opgeslagen", "Notitie opgeslagen!")

        tk.Button(current_frame, text="Opslaan Notitie", command=save_notitie, bg="#D1FFD1").pack(anchor="e",
                                                                                                  pady=(5, 0))

        # Notitie geschiedenis
        geschiedenis_frame = tk.LabelFrame(not_main, text="Notitie Geschiedenis", padx=5, pady=5)
        geschiedenis_frame.pack(fill=tk.BOTH, expand=True)

        # Notities treeview
        cols = ('datum', 'medewerker', 'notitie')
        not_tree = ttk.Treeview(geschiedenis_frame, columns=cols, show='headings', height=10)

        not_tree.heading('datum', text='Datum')
        not_tree.column('datum', width=100, anchor='center')
        not_tree.heading('medewerker', text='Medewerker')
        not_tree.column('medewerker', width=100)
        not_tree.heading('notitie', text='Notitie')
        not_tree.column('notitie', width=300)

        not_scroll = ttk.Scrollbar(geschiedenis_frame, orient=tk.VERTICAL, command=not_tree.yview)
        not_tree.configure(yscrollcommand=not_scroll.set)

        not_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(5, 10))
        not_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(5, 10))

        def refresh_notities():
            """Vernieuwt de notitie geschiedenis"""
            not_tree.delete(*not_tree.get_children())

            conn = database.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                           SELECT *
                           FROM klant_notities
                           WHERE klant_id = ?
                           ORDER BY aangemaakt_op DESC
                           """, (klant_id,))

            for notitie in cursor.fetchall():
                try:
                    datum = datetime.datetime.strptime(notitie['aangemaakt_op'], '%Y-%m-%d %H:%M:%S').strftime(
                        '%d/%m/%Y %H:%M')
                except:
                    datum = notitie['aangemaakt_op']

                not_tree.insert("", tk.END, values=(
                    datum,
                    notitie['medewerker'] or 'Systeem',
                    notitie['notitie']
                ))

            conn.close()

        refresh_notities()

        def nieuwe_notitie():
            """Voegt een nieuwe notitie toe aan de geschiedenis"""
            notitie = simpledialog.askstring("Nieuwe Notitie", "Voer de notitie in:")
            if notitie and notitie.strip():
                medewerker = simpledialog.askstring("Medewerker", "Uw naam (optioneel):")

                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                               INSERT INTO klant_notities (klant_id, notitie, aangemaakt_op, medewerker)
                               VALUES (?, ?, ?, ?)
                               """, (klant_id, notitie.strip(), datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                     medewerker))
                conn.commit()
                conn.close()

                refresh_notities()

        tk.Button(geschiedenis_frame, text="Nieuwe Notitie", command=nieuwe_notitie, bg="#D1FFE1").pack(anchor="e")

    # --- FAVORIET DIALOG ---
    def open_favoriet_dialog(klant_id, bestelling_id=None):
        """Opent dialog voor het aanmaken van favoriet"""
        dialog = tk.Toplevel(win)
        dialog.title("Nieuw Favoriet")
        dialog.geometry("400x300")
        dialog.transient(win)
        dialog.grab_set()

        tk.Label(dialog, text="Favoriet naam:", font=("Arial", 11, "bold")).pack(pady=(10, 5))
        naam_var = tk.StringVar()
        tk.Entry(dialog, textvariable=naam_var, font=("Arial", 11), width=40).pack(pady=(0, 10))

        tk.Label(dialog, text="Producten:", font=("Arial", 11, "bold")).pack(pady=(10, 5))
        producten_text = tk.Text(dialog, height=8, width=50, font=("Arial", 10))
        producten_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        if bestelling_id:
            # Laad bestaande bestelling
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bestelregels WHERE bestelling_id = ?", (bestelling_id,))
            regels = cursor.fetchall()
            conn.close()

            producten_lijst = []
            for regel in regels:
                producten_lijst.append({
                    'categorie': regel['categorie'],
                    'product': regel['product'],
                    'aantal': regel['aantal'],
                    'prijs': regel['prijs'],
                    'extras': json.loads(regel['extras']) if regel['extras'] else {}
                })

            producten_text.insert('1.0', json.dumps(producten_lijst, indent=2, ensure_ascii=False))

        def save_favoriet():
            """Slaat favoriet op"""
            naam = naam_var.get().strip()
            if not naam:
                messagebox.showerror("Fout", "Voer een naam in!")
                return

            try:
                producten_json = producten_text.get('1.0', tk.END).strip()
                producten = json.loads(producten_json)
                totaal = sum(p.get('prijs', 0) * p.get('aantal', 1) for p in producten)

                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                               INSERT INTO favoriete_bestellingen
                                   (klant_id, naam, bestelregels_json, totaal_prijs, aangemaakt_op)
                               VALUES (?, ?, ?, ?, ?)
                               """, (klant_id, naam, producten_json, totaal,
                                     datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
                conn.close()

                messagebox.showinfo("Succes", f"Favoriet '{naam}' opgeslagen!")
                dialog.destroy()
                # Refresh favorieten tab
                setup_favorieten_tab(klant_id)

            except json.JSONDecodeError:
                messagebox.showerror("Fout", "Ongeldige JSON data!")
            except Exception as e:
                messagebox.showerror("Fout", f"Kon favoriet niet opslaan: {e}")

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Button(btn_frame, text="Opslaan", command=save_favoriet, bg="#D1FFD1").pack(side=tk.LEFT)
        tk.Button(btn_frame, text="Annuleren", command=dialog.destroy, bg="#FFADAD").pack(side=tk.RIGHT)

    # --- KLANT ACTIES (RECHTER PANEEL) ---
    actions_frame = tk.LabelFrame(right_frame, text="Klant Acties", padx=10, pady=10)
    actions_frame.pack(fill=tk.X, pady=(10, 0))

    def nieuwe_klant():
        """Opent dialog voor nieuwe klant"""
        messagebox.showinfo("Info", "Gebruik het hoofdformulier om een nieuwe klant toe te voegen tijdens bestelling.")

    def bewerk_klant():
        """Bewerkt geselecteerde klant"""
        if not selected_klant['data']:
            messagebox.showwarning("Selectie", "Selecteer eerst een klant om te bewerken!")
            return

        klant = selected_klant['data']

        # Maak het bewerkingsvenster
        edit_win = tk.Toplevel(win)
        edit_win.title(f"Klant bewerken: {klant['naam'] or klant['telefoon']}")
        edit_win.geometry("450x250")
        edit_win.transient(win)
        edit_win.grab_set()

        form_frame = tk.Frame(edit_win, padx=15, pady=15)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Velden voor klantgegevens
        fields = {
            "Telefoon:": tk.StringVar(value=klant['telefoon']),
            "Naam:": tk.StringVar(value=klant['naam'] or ""),
            "Straat:": tk.StringVar(value=klant['straat'] or ""),
            "Huisnummer:": tk.StringVar(value=klant['huisnummer'] or ""),
            "Plaats:": tk.StringVar(value=klant['plaats'] or "")
        }

        for i, (label, var) in enumerate(fields.items()):
            tk.Label(form_frame, text=label, font=("Arial", 10, "bold")).grid(row=i, column=0, sticky="w", pady=3)
            entry = tk.Entry(form_frame, textvariable=var, font=("Arial", 10), width=40)
            if label == "Telefoon:":
                entry.config(state='readonly')  # Telefoonnummer is de sleutel en mag niet gewijzigd worden.
            entry.grid(row=i, column=1, sticky="ew", padx=(10, 0))

        form_frame.grid_columnconfigure(1, weight=1)

        def save_changes():
            """Slaat de wijzigingen op in de database."""
            # Valideer input
            new_naam = fields["Naam:"].get().strip()
            if not new_naam:
                messagebox.showerror("Invoerfout", "De naam mag niet leeg zijn.", parent=edit_win)
                return

            try:
                conn = database.get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                               UPDATE klanten
                               SET naam       = ?,
                                   straat     = ?,
                                   huisnummer = ?,
                                   plaats     = ?
                               WHERE id = ?
                               """, (
                                   new_naam,
                                   fields["Straat:"].get().strip(),
                                   fields["Huisnummer:"].get().strip(),
                                   fields["Plaats:"].get().strip(),
                                   klant['id']
                               ))
                conn.commit()
                conn.close()

                messagebox.showinfo("Succes", "Klantgegevens succesvol bijgewerkt.", parent=edit_win)
                edit_win.destroy()

                # Refresh de UI
                zoek_klanten()  # Vernieuw de lijst
                # Selecteer de bewerkte klant opnieuw in de treeview, dit triggert de on_klant_select en laadt de details.
                klanten_tree.selection_set(klant['id'])
                klanten_tree.focus(klant['id'])

            except Exception as e:
                messagebox.showerror("Database Fout", f"Kon de klant niet bijwerken: {e}", parent=edit_win)

        # Knoppen
        button_frame = tk.Frame(edit_win, pady=10)
        button_frame.pack(fill=tk.X)

        tk.Button(button_frame, text="Opslaan", command=save_changes, bg="#D1FFD1", font=("Arial", 10, "bold")).pack(
            side=tk.RIGHT, padx=(0, 15))
        tk.Button(button_frame, text="Annuleren", command=edit_win.destroy, bg="#FFADAD", font=("Arial", 10)).pack(
            side=tk.RIGHT, padx=10)

    def verwijder_klant():
        """Verwijdert geselecteerde klant"""
        if not selected_klant['data']:
            messagebox.showwarning("Selectie", "Selecteer eerst een klant!")
            return

        if messagebox.askyesno("Bevestigen",
                               "Klant en alle gerelateerde data verwijderen?\nDit kan niet ongedaan worden gemaakt!"):
            klant_id = selected_klant['data']['id']

            conn = database.get_db_connection()
            cursor = conn.cursor()

            try:
                # Verwijder gerelateerde data
                cursor.execute("DELETE FROM klant_notities WHERE klant_id = ?", (klant_id,))
                cursor.execute("DELETE FROM favoriete_bestellingen WHERE klant_id = ?", (klant_id,))

                # Verwijder bestelregels van bestellingen
                cursor.execute(
                    "DELETE FROM bestelregels WHERE bestelling_id IN (SELECT id FROM bestellingen WHERE klant_id = ?)",
                    (klant_id,))
                cursor.execute("DELETE FROM bestellingen WHERE klant_id = ?", (klant_id,))

                # Verwijder klant
                cursor.execute("DELETE FROM klanten WHERE id = ?", (klant_id,))

                conn.commit()
                messagebox.showinfo("Succes", "Klant verwijderd!")
                zoek_klanten()
                clear_klant_details()
                selected_klant['data'] = None

            except Exception as e:
                conn.rollback()
                messagebox.showerror("Fout", f"Kon klant niet verwijderen: {e}")
            finally:
                conn.close()

    tk.Button(actions_frame, text="Nieuwe Klant", command=nieuwe_klant, bg="#D1FFD1", width=15).pack(fill=tk.X, pady=2)
    tk.Button(actions_frame, text="Bewerk Klant", command=bewerk_klant, bg="#FFE5B4", width=15).pack(fill=tk.X, pady=2)
    tk.Button(actions_frame, text="Verwijder Klant", command=verwijder_klant, bg="#FFADAD", width=15).pack(fill=tk.X,
                                                                                                           pady=2)

    # Statistieken frame
    stats_frame = tk.LabelFrame(right_frame, text="Database Statistieken", padx=10, pady=10)
    stats_frame.pack(fill=tk.X, pady=(20, 0))

    def update_stats():
        """Update statistieken display"""
        conn = database.get_db_connection()
        cursor = conn.cursor()

        # Haal statistieken op
        cursor.execute("SELECT COUNT(*) as totaal_klanten FROM klanten")
        totaal_klanten = cursor.fetchone()['totaal_klanten']

        cursor.execute("SELECT COUNT(*) as actieve_klanten FROM klanten WHERE totaal_bestellingen > 0")
        actieve_klanten = cursor.fetchone()['actieve_klanten']

        cursor.execute("SELECT COUNT(*) as totaal_favorieten FROM favoriete_bestellingen")
        totaal_favorieten = cursor.fetchone()['totaal_favorieten']

        conn.close()

        # Update labels
        for widget in stats_frame.winfo_children():
            widget.destroy()

        tk.Label(stats_frame, text=f"Totaal klanten: {totaal_klanten}", font=("Arial", 10)).pack(anchor="w")
        tk.Label(stats_frame, text=f"Actieve klanten: {actieve_klanten}", font=("Arial", 10)).pack(anchor="w")
        tk.Label(stats_frame, text=f"Totaal favorieten: {totaal_favorieten}", font=("Arial", 10)).pack(anchor="w")

    # Event bindings
    search_var.trace_add("write", zoek_klanten)
    klanten_tree.bind("<<TreeviewSelect>>", on_klant_select)

    # Initial load
    zoek_klanten()
    update_stats()