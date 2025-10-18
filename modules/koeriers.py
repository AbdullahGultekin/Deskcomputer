import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import database
import sqlite3


def open_koeriers(root):
    # Config
    STARTGELD = 31.0

    win = tk.Toplevel(root)
    win.title("Koeriers")
    win.geometry("1000x600")
    win.minsize(900, 500)

    paned = tk.PanedWindow(win, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashpad=4)
    paned.pack(fill=tk.BOTH, expand=True)

    # --- Data ophalen ---
    conn = database.get_db_connection()
    koeriers_data = {row['naam']: row['id'] for row in
                     conn.execute("SELECT id, naam FROM koeriers ORDER BY naam").fetchall()}
    conn.close()
    koeriers = list(koeriers_data.keys())

    # --- Linker zijde: tabel ---
    left = tk.Frame(paned, padx=8, pady=8)
    paned.add(left, minsize=600)

    cols = ("adres", "nr", "gemeente", "tel", "totaal", "koerier")
    tree = ttk.Treeview(left, columns=cols, show="headings", height=16)

    headers = {"adres": "Adres", "nr": "Huisnr", "gemeente": "Gemeente", "tel": "Tel", "totaal": "Totaal (€)",
               "koerier": "Koerier"}
    widths = {"adres": 220, "nr": 50, "gemeente": 140, "tel": 110, "totaal": 80, "koerier": 120}
    for c in cols:
        tree.heading(c, text=headers[c])
        tree.column(c, width=widths[c], anchor="w" if c != "totaal" else "e")

    scroll_y = ttk.Scrollbar(left, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scroll_y.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll_y.grid(row=0, column=1, sticky="ns")
    left.grid_rowconfigure(0, weight=1)
    left.grid_columnconfigure(0, weight=1)

    # --- Hulpfuncties ---
    def laad_bestellingen():
        """Laadt alle bestellingen van vandaag uit de database."""
        for i in tree.get_children():
            tree.delete(i)

        vandaag_str = datetime.date.today().strftime('%Y-%m-%d')
        conn = database.get_db_connection()
        cursor = conn.cursor()

        query = """
                SELECT b.id, b.totaal, k.straat, k.huisnummer, k.plaats, k.telefoon, ko.naam as koerier_naam
                FROM bestellingen b
                         JOIN klanten k ON b.klant_id = k.id
                         LEFT JOIN koeriers ko ON b.koerier_id = ko.id
                WHERE b.datum = ?
                ORDER BY b.tijd \
                """
        cursor.execute(query, (vandaag_str,))

        for bestelling in cursor.fetchall():
            gemeente = ' '.join(bestelling['plaats'].split()[1:]) if ' ' in bestelling['plaats'] else ''
            tree.insert("", tk.END, iid=bestelling['id'], values=(
                bestelling['straat'],
                bestelling['huisnummer'],
                gemeente,
                bestelling['telefoon'],
                f"{bestelling['totaal']:.2f}",
                bestelling['koerier_naam'] or ""
            ))
        conn.close()
        herbereken_koeriers()

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
        laad_bestellingen()

    # Knoppen onder de tabel
    btns = tk.Frame(left)
    btns.grid(row=1, column=0, columnspan=2, sticky="we", pady=(8, 0))
    tk.Button(btns, text="Herlaad bestellingen", command=laad_bestellingen, bg="#E1E1FF").pack(side=tk.LEFT)
    tk.Button(btns, text="Toewijzing verwijderen", command=verwijder_toewijzing, bg="#FFD1D1").pack(side=tk.LEFT,
                                                                                                    padx=8)

    # --- Rechter zijde: koeriers + totalen ---
    right = tk.Frame(paned, padx=8, pady=8)
    paned.add(right, minsize=300)
    tk.Label(right, text="Koeriers", font=("Arial", 13, "bold")).pack(anchor="w")

    koerier_list_frame = tk.Frame(right)
    koerier_list_frame.pack(fill=tk.X, pady=(4, 10))

    totals_var = {k: tk.DoubleVar(value=0.0) for k in koeriers}
    eind_totals_var = {k: tk.DoubleVar(value=0.0) for k in koeriers}

    def herbereken_koeriers():
        for k in koeriers:
            totals_var[k].set(0.0)

        for iid in tree.get_children(""):
            vals = tree.item(iid, "values")
            try:
                totaal = float(vals[4])
                koerier_naam = vals[5]
                if koerier_naam in totals_var:
                    totals_var[koerier_naam].set(totals_var[koerier_naam].get() + totaal)
            except (ValueError, IndexError):
                continue

        for k in koeriers:
            eind_totals_var[k].set(totals_var[k].get() + STARTGELD)

    def wijs_koerier_toe(naam):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Selectie", "Selecteer eerst een rij in de tabel.")
            return

        koerier_id = koeriers_data.get(naam)
        if koerier_id is None: return

        conn = database.get_db_connection()
        cursor = conn.cursor()
        for iid in sel:
            cursor.execute("UPDATE bestellingen SET koerier_id = ? WHERE id = ?", (koerier_id, iid))
        conn.commit()
        conn.close()
        laad_bestellingen()

    def voeg_koerier_toe():
        """Voegt een nieuwe koerier toe aan de database en herlaadt het venster."""
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
            win.destroy()
            open_koeriers(root)
        except sqlite3.IntegrityError:
            messagebox.showwarning("Fout", f"Koerier '{naam}' bestaat al.")
        except Exception as e:
            messagebox.showerror("Database Fout", f"Kon koerier niet toevoegen: {e}")
        finally:
            if conn:
                conn.close()

    def verwijder_koerier(naam):
        """Controleert of een koerier in gebruik is en verwijdert deze indien mogelijk."""
        if not messagebox.askyesno("Bevestigen", f"Weet u zeker dat u '{naam}' wilt verwijderen?"):
            return

        koerier_id = koeriers_data.get(naam)
        if koerier_id is None:
            messagebox.showerror("Fout", "Koerier niet gevonden in de data.")
            return

        conn = database.get_db_connection()
        cursor = conn.cursor()
        try:
            # Controleer of de koerier nog is toegewezen aan bestellingen
            cursor.execute("SELECT COUNT(*) FROM bestellingen WHERE koerier_id = ?", (koerier_id,))
            count = cursor.fetchone()[0]
            if count > 0:
                messagebox.showerror("Fout",
                                     f"Kan '{naam}' niet verwijderen. De koerier is nog aan {count} bestelling(en) toegewezen.")
                return

            # Verwijder de koerier
            cursor.execute("DELETE FROM koeriers WHERE id = ?", (koerier_id,))
            conn.commit()
            messagebox.showinfo("Succes", f"Koerier '{naam}' is verwijderd.")

            # Herlaad het venster om de wijzigingen te tonen
            win.destroy()
            open_koeriers(root)

        except Exception as e:
            messagebox.showerror("Database Fout", f"Kon koerier niet verwijderen: {e}")
        finally:
            conn.close()

    # Knoppen voor koeriers
    for i, naam in enumerate(koeriers):
        r, c = divmod(i, 2)
        tk.Button(koerier_list_frame, text=naam, width=14, command=lambda n=naam: wijs_koerier_toe(n),
                  bg="#FFF59D").grid(row=r, column=c, padx=4, pady=2, sticky="w")

    # Frame voor toevoegen van nieuwe koerier
    add_koerier_frame = tk.LabelFrame(right, text="Nieuwe koerier toevoegen", padx=6, pady=6)
    add_koerier_frame.pack(fill=tk.X, pady=(0, 10))
    new_koerier_entry = tk.Entry(add_koerier_frame, font=("Arial", 10))
    new_koerier_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    tk.Button(add_koerier_frame, text="Toevoegen", command=voeg_koerier_toe, bg="#D1FFD1").pack(side=tk.LEFT)

    # Totalen tabel
    totals_frame = tk.LabelFrame(right, text="Afrekening per koerier", padx=6, pady=6)
    totals_frame.pack(fill=tk.X, pady=(6, 0))

    # Header
    headers_afrekening = ["Koerier", "Subtotaal (€)", f"+ Startgeld (€{STARTGELD:.2f})", "Eindtotaal (€)", "Acties"]
    for i, header_text in enumerate(headers_afrekening):
        tk.Label(totals_frame, text=header_text, font=("Arial", 10, "bold"), anchor="w").grid(row=0, column=i,
                                                                                              sticky="w", padx=5)

    for i, naam in enumerate(koeriers, start=1):
        tk.Label(totals_frame, text=naam, anchor="w").grid(row=i, column=0, sticky="w", padx=5)
        tk.Label(totals_frame, textvariable=totals_var[naam], anchor="e").grid(row=i, column=1, sticky="e", padx=5)
        tk.Label(totals_frame, text=f"{STARTGELD:.2f}", anchor="e").grid(row=i, column=2, sticky="e", padx=5)
        tk.Label(totals_frame, textvariable=eind_totals_var[naam], font=("Arial", 10, "bold"), anchor="e").grid(row=i,
                                                                                                                column=3,
                                                                                                                sticky="e",
                                                                                                                padx=5)
        tk.Button(totals_frame, text="Verwijder", command=lambda n=naam: verwijder_koerier(n),
                  bg="#FFADAD").grid(row=i, column=4, padx=5)

    for i in range(5):
        totals_frame.grid_columnconfigure(i, weight=1)

    laad_bestellingen()