import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import database
import sqlite3

def open_koeriers(root):
    STARTGELD = 31.0
    KM_TARIEF = 0.25
    UUR_TARIEF = 10.0

    # EMBED in tab i.p.v. Toplevel
    win = root
    for w in win.winfo_children():
        w.destroy()

    paned = tk.PanedWindow(win, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashpad=4)
    paned.pack(fill=tk.BOTH, expand=True)

    # --- Data ophalen ---
    conn = database.get_db_connection()
    koeriers_data = {row['naam']: row['id'] for row in
                     conn.execute("SELECT id, naam FROM koeriers ORDER BY naam").fetchall()}
    conn.close()
    koeriers = list(koeriers_data.keys())

    # ===================== LINKERZIJDE: BESTELLINGEN =====================
    left = tk.Frame(paned, padx=10, pady=10)
    paned.add(left, minsize=350)

    # Filterbalk
    filter_frame = tk.Frame(left)
    filter_frame.pack(fill=tk.X, pady=(0, 6))
    tk.Label(filter_frame, text="Zoek:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
    search_var = tk.StringVar()
    search_entry = tk.Entry(filter_frame, textvariable=search_var, width=12)
    search_entry.pack(side=tk.LEFT, padx=(6, 12))
    tk.Label(filter_frame, text="Koerier:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
    filter_koerier_var = tk.StringVar(value="Alle")
    koerier_opt = ttk.Combobox(filter_frame, state="readonly",
                               values=["Alle"] + koeriers, textvariable=filter_koerier_var, width=12)
    koerier_opt.pack(side=tk.LEFT, padx=(6, 12))
    tk.Label(filter_frame, text="Datum:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
    datum_var = tk.StringVar(value=datetime.date.today().strftime('%Y-%m-%d'))
    datum_entry = tk.Entry(filter_frame, textvariable=datum_var, width=12)
    datum_entry.pack(side=tk.LEFT, padx=(6, 12))
    tk.Button(filter_frame, text="Herlaad", command=lambda: laad_bestellingen(True), bg="#E1E1FF").pack(side=tk.LEFT)

    # Tabel met zebra-styling en duidelijke kolommen
    cols = ("tijd", "adres", "nr", "gemeente", "tel", "totaal", "koerier")
    headers = {
        "tijd": "Tijd",
        "adres": "Adres",
        "nr": "Nr",
        "gemeente": "Gemeente",
        "tel": "Tel",
        "totaal": "Totaal (€)",
        "koerier": "Koerier"
    }
    widths = {"tijd": 70, "adres": 240, "nr": 50, "gemeente": 150, "tel": 120, "totaal": 90, "koerier": 140}
    tree = ttk.Treeview(left, columns=cols, show="headings", height=18)
    for c in cols:
        tree.heading(c, text=headers[c])
        tree.column(c, width=widths[c],
                    anchor="w" if c not in ("totaal", "tijd") else ("center" if c == "tijd" else "e"))
    scroll_y = ttk.Scrollbar(left, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scroll_y.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll_y.pack(side=tk.LEFT, fill=tk.Y)

    # Style: zebra en kleurcode als geen koerier toegewezen
    style = ttk.Style(tree)
    style.map("Treeview")
    tree.tag_configure("row_a", background="#FAFAFA")
    tree.tag_configure("row_b", background="#F0F4FF")
    tree.tag_configure("unassigned", background="#FFF3CD")  # geel highlight

    # Nieuw: kleur per koerier in de lijst (matcht rechter kaarten)
    KOERIER_ROW_COLORS = {
        # vul dynamisch in na het ophalen van koeriers
    }

    # Actiebalk onder tabel
    btns = tk.Frame(left)
    btns.pack(fill=tk.X, pady=(8, 0))
    tk.Button(btns, text="Toewijzing verwijderen", command=lambda: verwijder_toewijzing(), bg="#FFD1D1").pack(
        side=tk.LEFT)
    tk.Button(btns, text="Selectie -> Koerier", command=lambda: open_toewijs_popup(), bg="#D1FFD1").pack(side=tk.LEFT,
                                                                                                         padx=8)
    geselecteerd_lbl = tk.Label(btns, text="Geen selectie", fg="#666")
    geselecteerd_lbl.pack(side=tk.RIGHT)

    def update_geselecteerd_lbl(*_):
        n = len(tree.selection())
        geselecteerd_lbl.config(text=f"{n} geselecteerd" if n else "Geen selectie")

    tree.bind("<<TreeviewSelect>>", update_geselecteerd_lbl)

    # ===================== RECHTERZIJDE: KOERIERS + AFREKENING =====================
    right = tk.Frame(paned, padx=10, pady=10)
    paned.add(right, minsize=1000)

    tk.Label(right, text="Koeriers", font=("Arial", 13, "bold")).pack(anchor="w")

    # Palet met vaste, onderscheidende kleuren
    CARD_COLORS = [
        ("#FFF3CD", "#7A5E00"),  # licht geel / donker tekst
        ("#E3F2FD", "#0D47A1"),  # licht blauw
        ("#E8F5E9", "#1B5E20"),  # licht groen
        ("#F3E5F5", "#4A148C"),  # licht paars
        ("#FFEDE7", "#BF360C"),  # licht oranje
        ("#EDE7F6", "#283593"),  # indigo
        ("#E0F7FA", "#006064"),  # cyaan
        ("#FFF8E1", "#8D6E63"),  # crème/bruin
    ]

    # Koerier-kaarten
    koerier_cards = tk.Frame(right)
    koerier_cards.pack(fill=tk.X)

    totals_var = {k: tk.DoubleVar(value=0.0) for k in koeriers}

    # Koppel koerier -> rijkleur (zacht tintje)
    KOERIER_ROW_COLORS.clear()
    for i, naam in enumerate(koeriers):
        KOERIER_ROW_COLORS[naam] = CARD_COLORS[i % len(CARD_COLORS)][0]

    def initials(name: str) -> str:
        parts = [p for p in name.split() if p.strip()]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def render_koerier_cards():
        for w in koerier_cards.winfo_children():
            w.destroy()
        for i, naam in enumerate(koeriers):
            bg, fg = CARD_COLORS[i % len(CARD_COLORS)]
            card = tk.Frame(koerier_cards, bd=1, relief="groove", padx=10, pady=8, bg=bg, highlightthickness=0)
            card.grid(row=i // 2, column=i % 2, padx=6, pady=6, sticky="ew")
            card.grid_columnconfigure(1, weight=1)

            # “Avatar” met initialen
            avatar = tk.Canvas(card, width=34, height=34, bg=bg, highlightthickness=0)
            avatar.grid(row=0, column=0, rowspan=2, padx=(0, 8))
            avatar.create_oval(2, 2, 32, 32, fill=fg, outline=fg)
            avatar.create_text(17, 17, text=initials(naam), fill=bg, font=("Arial", 10, "bold"))

            name_lbl = tk.Label(card, text=naam, font=("Arial", 11, "bold"), bg=bg, fg=fg, anchor="w", wraplength=180)
            name_lbl.grid(row=0, column=1, sticky="w")

            tk.Label(
                card, textvariable=totals_var[naam], font=("Arial", 10, "bold"),
                fg=fg, bg=bg
            ).grid(row=1, column=1, sticky="w")

            btn = tk.Button(
                card, text="Wijs selectie toe", command=lambda n=naam: wijs_koerier_toe(n),
                bg="#FFFFFF", fg=fg, font=("Arial", 10, "bold"), relief="raised", bd=1, activebackground="#FFF"
            )
            btn.grid(row=0, column=2, rowspan=2, padx=(8, 0))

            # Hover/active effect voor betere affordance
            def on_enter(e, b=btn):
                b.configure(bg="#F5F5F5")

            def on_leave(e, b=btn):
                b.configure(bg="#FFFFFF")

            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

    render_koerier_cards()

    # Nieuwe koerier toevoegen/verwijderen (compact)
    manage_frame = tk.LabelFrame(right, text="Koeriers beheren", padx=8, pady=8)
    manage_frame.pack(fill=tk.X, pady=(8, 8))
    new_koerier_entry = tk.Entry(manage_frame, font=("Arial", 10))
    new_koerier_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # Definieer helpers die door knoppen gebruikt worden
    def voeg_koerier_toe():
        nonlocal koeriers, koeriers_data
        naam = new_koerier_entry.get().strip()
        if not naam:
            messagebox.showwarning("Invoerfout", "Voer een naam in voor de nieuwe koerier.")
            return
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO koeriers (naam) VALUES (?)", (naam,))
            conn.commit()
            messagebox.showinfo("Succes", f"Koerier '{naam}' is succesvol toegevoegd.")
            # herlaad UI-data
            conn2 = database.get_db_connection()
            koeriers_data = {row['naam']: row['id'] for row in
                             conn2.execute("SELECT id, naam FROM koeriers ORDER BY naam").fetchall()}
            conn2.close()
            koeriers = sorted(list(koeriers_data.keys()), key=str.lower)
            render_koerier_cards()
            del_combo['values'] = koeriers
            if koeriers:
                del_combo.set(koeriers[0])
            totals_var[naam] = tk.DoubleVar(value=0)
            eind_totals_var[naam] = tk.DoubleVar(value=0)
            extra_km_var[naam] = tk.DoubleVar(value=0)
            extra_uur_var[naam] = tk.DoubleVar(value=0)
            extra_bedrag_var[naam] = tk.DoubleVar(value=0)
            afrekening_var[naam] = tk.DoubleVar(value=0)
            laad_bestellingen(True)
        except sqlite3.IntegrityError:
            messagebox.showwarning("Fout", f"Koerier '{naam}' bestaat al.")
        except Exception as e:
            messagebox.showerror("Database Fout", f"Kon koerier niet toevoegen: {e}")
        finally:
            try:
                conn.close()
            except:
                pass

    def verwijder_koerier(naam):
        nonlocal koeriers, koeriers_data  # verplaatst naar boven, slechts één keer
        if not naam:
            messagebox.showwarning("Selectie", "Kies eerst een koerier om te verwijderen.")
            return
        if not messagebox.askyesno("Bevestigen", f"Weet u zeker dat u '{naam}' wilt verwijderen?"):
            return
        koerier_id = koeriers_data.get(naam)
        if koerier_id is None:
            messagebox.showerror("Fout", "Koerier niet gevonden in de data.")
            return
        conn = database.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM bestellingen WHERE koerier_id = ?", (koerier_id,))
            count = cursor.fetchone()[0]
            if count > 0:
                messagebox.showerror("Fout",
                                     f"Kan '{naam}' niet verwijderen. De koerier is nog aan {count} bestelling(en) toegewezen.")
                return
            cursor.execute("DELETE FROM koeriers WHERE id = ?", (koerier_id,))
            conn.commit()
            messagebox.showinfo("Succes", f"Koerier '{naam}' is verwijderd.")
            # verwijder uit lokale structuren en refresh UI
            del koeriers_data[naam]
            koeriers = sorted(list(koeriers_data.keys()), key=str.lower)
            del_combo['values'] = koeriers
            if koeriers:
                del_combo.set(koeriers[0])
            for d in (totals_var, eind_totals_var, extra_km_var, extra_uur_var, extra_bedrag_var, afrekening_var):
                d.pop(naam, None)
            render_koerier_cards()
            laad_bestellingen(True)
        except Exception as e:
            messagebox.showerror("Database Fout", f"Kon koerier niet verwijderen: {e}")
        finally:
            conn.close()

    tk.Button(manage_frame, text="Toevoegen", command=lambda: voeg_koerier_toe(), bg="#D1FFD1").pack(side=tk.LEFT,
                                                                                                     padx=6)
    del_name_var = tk.StringVar(value=koeriers[0] if koeriers else "")
    del_combo = ttk.Combobox(manage_frame, values=koeriers, textvariable=del_name_var, width=12, state="readonly")
    del_combo.pack(side=tk.LEFT, padx=6)
    tk.Button(manage_frame, text="Verwijderen", command=lambda: verwijder_koerier(del_name_var.get()),
              bg="#FFD1D1").pack(side=tk.LEFT)

    # Afrekening
    totals_frame = tk.LabelFrame(right, text="Afrekening per koerier", padx=8, pady=8, bg="#F3F6FC")
    totals_frame.pack(fill=tk.X)

    headers_afrekening = [
        "Koerier", "Subtotaal (€)", f"+ Startgeld (€{STARTGELD:.2f})", "Eindtotaal (€)",
        "Km", "Uur", "Extra €", "Definitief (€)"
    ]
    for col, header_text in enumerate(headers_afrekening):
        tk.Label(totals_frame, text=header_text, font=("Arial", 10, "bold"), anchor="w", bg="#D2F2FF"
                 ).grid(row=0, column=col, sticky="we", padx=5, pady=2)

    eind_totals_var = {k: tk.DoubleVar(value= 0) for k in koeriers}
    extra_km_var = {k: tk.DoubleVar(value=0) for k in koeriers}
    extra_uur_var = {k: tk.DoubleVar(value=0) for k in koeriers}
    extra_bedrag_var = {k: tk.DoubleVar(value=0) for k in koeriers}
    afrekening_var = {k: tk.DoubleVar(value=0) for k in koeriers}
    subtotaal_totaal_var = tk.DoubleVar(value=0)
    totaal_betaald_var = tk.DoubleVar(value=0)

    # Rij-achtergrond per koerier in zelfde kleurfamilie
    for i, naam in enumerate(koeriers, start=1):
        bg_light, fg_dark = CARD_COLORS[(i - 1) % len(CARD_COLORS)]
        tk.Label(totals_frame, text=naam, anchor="w", bg=bg_light, fg=fg_dark, font=("Arial", 10, "bold")
                 ).grid(row=i, column=0, sticky="we", padx=5)
        tk.Label(totals_frame, textvariable=totals_var[naam], anchor="e", bg=bg_light, fg=fg_dark, font=("Arial", 10)
                 ).grid(row=i, column=1, sticky="e", padx=5)
        tk.Label(totals_frame, text=f"{STARTGELD:.2f}", anchor="e", bg=bg_light, fg=fg_dark, font=("Arial", 10)
                 ).grid(row=i, column=2, sticky="e", padx=5)
        tk.Label(totals_frame, textvariable=eind_totals_var[naam], font=("Arial", 10, "bold"),
                 anchor="e", bg=bg_light, fg=fg_dark
                 ).grid(row=i, column=3, sticky="e", padx=5)
        entry_bg = "#FFFFFF"
        tk.Entry(totals_frame, textvariable=extra_km_var[naam], font=("Arial", 10, "bold"), width=7, justify="right",
                 bg=entry_bg, relief="groove", borderwidth=2).grid(row=i, column=4, padx=2)
        tk.Entry(totals_frame, textvariable=extra_uur_var[naam], font=("Arial", 10, "bold"), width=5, justify="right",
                 bg=entry_bg, relief="groove", borderwidth=2).grid(row=i, column=5, padx=2)
        tk.Entry(totals_frame, textvariable=extra_bedrag_var[naam], font=("Arial", 10, "bold"), width=6,
                 justify="right",
                 bg=entry_bg, relief="groove", borderwidth=2).grid(row=i, column=6, padx=2)
        tk.Label(totals_frame, textvariable=afrekening_var[naam], font=("Arial", 11, "bold"), fg=fg_dark, bg=bg_light
                 ).grid(row=i, column=7, padx=4, sticky="e")

        def herbereken_afrekening(naam_in):
            try:
                km = extra_km_var[naam_in].get()
                uur = extra_uur_var[naam_in].get()
                extra = extra_bedrag_var[naam_in].get()
                totaal = (km * KM_TARIEF) + (uur * UUR_TARIEF) + extra
                afrekening_var[naam_in].set(round(totaal, 2))
            except Exception:
                afrekening_var[naam_in].set(0.0)

        for var in (extra_km_var[naam], extra_uur_var[naam], extra_bedrag_var[naam], totals_var[naam],
                    eind_totals_var[naam]):
            var.trace_add("write", lambda *_, n=naam: (herbereken_afrekening(n), herbereken_totaal_betaald()))

    # Subtotalen en totaal
    subtotal_row_idx = len(koeriers) + 1
    tk.Label(totals_frame, text="Totaal Bestellingen", font=("Arial", 11, "bold"), anchor="e", bg="#D2F2FF"
             ).grid(row=subtotal_row_idx, column=0, sticky="ew", padx=5, pady=(8, 4))
    tk.Label(totals_frame, textvariable=subtotaal_totaal_var, font=("Arial", 11, "bold"), anchor="e", bg="#D2F2FF"
             ).grid(row=subtotal_row_idx, column=1, sticky="ew", padx=5, pady=(8, 4))
    total_row = len(koeriers) + 2
    tk.Label(totals_frame, text="Totaal uitbetaling aan koeriers (€):",
             font=("Arial", 12, "bold"), fg="#225722", bg="#EAFCD5", relief="ridge"
             ).grid(row=total_row, column=0, columnspan=6, sticky="e", padx=8, pady=(10, 4))
    tk.Label(totals_frame, textvariable=totaal_betaald_var,
             font=("Arial", 14, "bold"), fg="#268244", bg="#EAFCD5", relief="ridge"
             ).grid(row=total_row, column=6, columnspan=2, sticky="e", padx=8, pady=(10, 4))

    for colindex in range(8):
        totals_frame.grid_columnconfigure(colindex, weight=1)

    # ======= Logica =======
    def herbereken_koeriers():
        for k in koeriers:
            totals_var[k].set(0.0)
        totaal_bestellingen_geld = 0.0
        for iid in tree.get_children(""):
            vals = tree.item(iid, "values")
            try:
                bedrag = float(vals[5])
                koerier_naam = vals[6]
                totaal_bestellingen_geld += bedrag
                if koerier_naam in totals_var:
                    totals_var[koerier_naam].set(totals_var[koerier_naam].get() + bedrag)
            except (ValueError, IndexError):
                continue
        subtotaal_totaal_var.set(round(totaal_bestellingen_geld, 2))
        for k in koeriers:
            eind_totals_var[k].set(round(totals_var[k].get() + STARTGELD, 2))

    def herbereken_totaal_betaald(*_):
        totaal = sum(afrekening_var[naam].get() for naam in koeriers)
        totaal_betaald_var.set(round(totaal, 2))

    def apply_filters(row):
        # Tekstfilter: tijd/adres/gemeente/tel
        tekst = search_var.get().lower().strip()
        if tekst:
            if not any(tekst in str(v).lower() for v in (row['tijd'], row['straat'], row['plaats'], row['telefoon'])):
                return False
        # Koerier filter
        f = filter_koerier_var.get()
        if f and f != "Alle":
            if (row.get('koerier_naam') or "") != f:
                return False
        return True

    def laad_bestellingen(force=False):
        for i in tree.get_children():
            tree.delete(i)
        datum = (datum_var.get() or datetime.date.today().strftime('%Y-%m-%d'))
        conn = database.get_db_connection()
        cursor = conn.cursor()
        query = """
                SELECT b.id, \
                       b.totaal, \
                       b.tijd, \
                       k.straat, \
                       k.huisnummer, \
                       k.plaats, \
                       k.telefoon, \
                       ko.naam as koerier_naam
                FROM bestellingen b
                         JOIN klanten k ON b.klant_id = k.id
                         LEFT JOIN koeriers ko ON b.koerier_id = ko.id
                WHERE b.datum = ?
                ORDER BY b.tijd \
                """
        cursor.execute(query, (datum,))
        rows = cursor.fetchall()
        conn.close()

        # Headereffect (kleine caps) – visueel
        for c in cols:
            tree.heading(c, text=headers[c].upper())

        # Voeg rijen toe met tags (zebra, unassigned en koerierkleur)
        for idx, bestelling in enumerate(rows):
            if not apply_filters(bestelling) and not force:
                continue
            gemeente = ' '.join(bestelling['plaats'].split()[1:]) if ' ' in bestelling['plaats'] else bestelling[
                'plaats']

            koerier_naam = bestelling['koerier_naam'] or ""
            if koerier_naam:
                kg = f"koerier_{koerier_naam.replace(' ', '_')}"
                if not style.lookup(kg, "background"):
                    tree.tag_configure(kg, background=KOERIER_ROW_COLORS.get(koerier_naam, "#FFFFFF"),
                                       foreground="#000000")
                tags = (kg,)
            else:
                # Alleen zebra kleur als geen koerier
                base_tag = "row_a" if idx % 2 == 0 else "row_b"
                tags = ("unassigned", base_tag)

            koerier_cell = koerier_naam if koerier_naam else "(geen)"

            tree.insert(
                "", tk.END, iid=bestelling['id'],
                values=(
                    bestelling['tijd'],
                    bestelling['straat'],
                    bestelling['huisnummer'],
                    gemeente,
                    bestelling['telefoon'],
                    f"{bestelling['totaal']:.2f}",
                    koerier_cell
                ),
                tags=tags
            )

        # Hover/selection highlight
        style.configure("Treeview", rowheight=24)
        style.map("Treeview", background=[('selected', '#B3E5FC')], foreground=[('selected', '#0D47A1')])

        herbereken_koeriers()
        herbereken_totaal_betaald()


    def verwijder_toewijzing():
        sel = tree.selection()
        if not sel:
            return
        conn = database.get_db_connection()
        cursor = conn.cursor()
        for iid in sel:
            cursor.execute("UPDATE bestellingen SET koerier_id = NULL WHERE id = ?", (iid,))
        conn.commit()
        conn.close()
        laad_bestellingen(True)

    def wijs_koerier_toe(naam):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Selectie", "Selecteer eerst één of meer rijen.")
            return
        koerier_id = koeriers_data.get(naam)
        if koerier_id is None:
            return
        conn = database.get_db_connection()
        cursor = conn.cursor()
        for iid in sel:
            cursor.execute("UPDATE bestellingen SET koerier_id = ? WHERE id = ?", (koerier_id, iid))
        conn.commit()
        conn.close()
        laad_bestellingen(True)

    def open_toewijs_popup():
        if not tree.selection():
            messagebox.showinfo("Selectie", "Selecteer eerst één of meer rijen.")
            return
        top = tk.Toplevel(win)
        top.title("Wijs koerier toe")
        tk.Label(top, text="Kies koerier:", font=("Arial", 10, "bold")).pack(padx=10, pady=(10, 4))
        combo_var = tk.StringVar(value=koeriers[0] if koeriers else "")
        ttk.Combobox(top, values=koeriers, textvariable=combo_var, state="readonly", width=24).pack(padx=10, pady=4)

        def ok():
            if combo_var.get():
                wijs_koerier_toe(combo_var.get())
            top.destroy()

        tk.Button(top, text="OK", command=ok, bg="#D1FFD1").pack(padx=10, pady=(8, 10))

    # Live filters
    search_var.trace_add("write", lambda *_: laad_bestellingen())
    filter_koerier_var.trace_add("write", lambda *_: laad_bestellingen())
    datum_var.trace_add("write", lambda *_: laad_bestellingen())

    laad_bestellingen(True)