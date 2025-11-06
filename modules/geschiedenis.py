# modules/geschiedenis.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import database


def open_geschiedenis(root, menu_data_global, extras_data_global, app_settings_global, laad_bestelling_callback):
    """
    Opent de geschiedenistab met de mogelijkheid om bestellingen te bekijken,
    te filteren en opnieuw te laden voor bewerking.
    """
    for widget in root.winfo_children():
        widget.destroy()

    # --- Frames ---
    top_frame = tk.Frame(root)
    top_frame.pack(fill=tk.X, padx=10, pady=10)
    tree_frame = tk.Frame(root)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=10)
    bottom_frame = tk.Frame(root)
    bottom_frame.pack(fill=tk.X, padx=10, pady=10)

    # --- Filters ---
    tk.Label(top_frame, text="Zoek op naam/telefoon/adres:").pack(side=tk.LEFT, padx=(0, 5))
    search_var = tk.StringVar()
    search_entry = tk.Entry(top_frame, textvariable=search_var, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)

    tk.Label(top_frame, text="Datum (YYYY-MM-DD):").pack(side=tk.LEFT, padx=(15, 5))
    date_var = tk.StringVar()
    date_entry = tk.Entry(top_frame, textvariable=date_var, width=12)
    date_entry.pack(side=tk.LEFT, padx=5)

    tk.Button(top_frame, text="Vernieuwen", command=lambda: refresh_data(), bg="#E1E1FF").pack(side=tk.LEFT, padx=10)

    # --- Treeview ---
    columns = ('datum', 'tijd', 'bon', 'naam', 'telefoon', 'adres', 'totaal')
    tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
    tree.heading('datum', text='Datum')
    tree.heading('tijd', text='Tijd')
    tree.heading('bon', text='Bonnummer')
    tree.heading('naam', text='Naam')
    tree.heading('telefoon', text='Telefoon')
    tree.heading('adres', text='Adres')
    tree.heading('totaal', text='Totaal')

    for col in columns:
        tree.column(col, width=120)
    tree.column('adres', width=250)
    tree.column('naam', width=150)

    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    vsb.pack(side='right', fill='y')
    tree.pack(side='left', fill='both', expand=True)

    # --- Data verversen ---
    def refresh_data(*_):
        """Haalt data op en vult de treeview."""
        for i in tree.get_children():
            tree.delete(i)

        conn = database.get_db_connection()
        cursor = conn.cursor()

        query = """
                SELECT b.id,
                       b.datum,
                       b.tijd,
                       b.totaal,
                       b.bonnummer,
                       k.naam,
                       k.telefoon,
                       k.straat,
                       k.huisnummer
                FROM bestellingen b
                         JOIN klanten k ON b.klant_id = k.id \
                """
        params = []
        conditions = []

        search_term = (search_var.get() or "").strip()
        if search_term:
            conditions.append("(k.naam LIKE ? OR k.telefoon LIKE ? OR k.straat LIKE ?)")
            params.extend([f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"])

        date_term = (date_var.get() or "").strip()
        if date_term:
            conditions.append("b.datum = ?")
            params.append(date_term)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY b.datum DESC, b.tijd DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            adres = f"{row['straat'] or ''} {row['huisnummer'] or ''}".strip()
            tree.insert(
                "",
                "end",
                iid=row['id'],
                values=(row['datum'], row['tijd'], row['bonnummer'], row['naam'], row['telefoon'], adres,
                        f"€ {row['totaal']:.2f}")
            )

    search_var.trace_add("write", refresh_data)
    date_var.trace_add("write", refresh_data)

    # --- Acties ---
    def bewerk_en_herdruk_bon():
        """Laadt een oude bestelling in het hoofdscherm om te bewerken."""
        selected_item_id = tree.focus()
        if not selected_item_id:
            messagebox.showwarning("Selectie Fout", "Selecteer alstublieft een bestelling om te bewerken.", parent=root)
            return

        bestelling_id = int(selected_item_id)

        if not messagebox.askyesno(
                "Bevestigen",
                "Weet u zeker dat u deze bestelling wilt laden om te bewerken?\n\n"
                "De originele bestelling wordt hierbij verwijderd en vervangen door de nieuwe versie na het opslaan.",
                icon='warning',
                parent=root
        ):
            return

        conn = database.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                           SELECT b.id,
                                  b.bonnummer,
                                  b.opmerking,
                                  b.klant_id,
                                  k.telefoon,
                                  k.straat,
                                  k.huisnummer,
                                  k.plaats,
                                  k.naam
                           FROM bestellingen b
                                    JOIN klanten k ON b.klant_id = k.id
                           WHERE b.id = ?
                           """, (bestelling_id,))
            bestelling = cursor.fetchone()
            if not bestelling:
                messagebox.showerror("Fout", "Bestelling niet gevonden in de database.", parent=root)
                return

            klant_data = {
                "klant_id": bestelling['klant_id'],
                "telefoon": bestelling['telefoon'],
                "adres": bestelling['straat'],
                "nr": bestelling['huisnummer'],
                "postcode_gemeente": bestelling['plaats'],
                "opmerking": bestelling['opmerking'] or "",
                "naam": bestelling['naam'] or ""
            }

            cursor.execute(
                "SELECT categorie, product, aantal, prijs, extras FROM bestelregels WHERE bestelling_id = ?",
                (bestelling_id,)
            )
            bestelregels_db = cursor.fetchall()

            formatted_bestelregels = []
            for regel in bestelregels_db:
                formatted_bestelregels.append({
                    'categorie': regel['categorie'],
                    'product': regel['product'],
                    'aantal': regel['aantal'],
                    'prijs': regel['prijs'],
                    'extras': json.loads(regel['extras']) if regel['extras'] else {}
                })

            # Laad in hoofdscherm + verwijder oude bestelling
            laad_bestelling_callback(klant_data, formatted_bestelregels, bestelling_id)

            # Vernieuw lijst
            refresh_data()

        except Exception as e:
            messagebox.showerror("Fout", f"Er is een fout opgetreden bij het laden van de bestelling: {e}", parent=root)
        finally:
            if conn:
                conn.close()

    def verwijder_bestelling():
        """Verwijdert de geselecteerde bestelling volledig."""
        selected_item_id = tree.focus()
        if not selected_item_id:
            messagebox.showwarning("Selectie Fout", "Selecteer een bestelling om te verwijderen.", parent=root)
            return

        if not messagebox.askyesno(
                "Zeker weten?",
                "Weet u zeker dat u deze bestelling definitief wilt verwijderen? Dit kan niet ongedaan worden gemaakt.",
                icon='warning',
                parent=root
        ):
            return

        bestelling_id = int(selected_item_id)
        conn = database.get_db_connection()
        try:
            row = conn.execute("SELECT klant_id FROM bestellingen WHERE id = ?", (bestelling_id,)).fetchone()
            klant_id = row['klant_id'] if row else None

            conn.execute("DELETE FROM bestelregels WHERE bestelling_id = ?", (bestelling_id,))
            conn.execute("DELETE FROM bestellingen WHERE id = ?", (bestelling_id,))
            conn.commit()

            if klant_id:
                database.update_klant_statistieken(klant_id)

            messagebox.showinfo("Succes", "Bestelling succesvol verwijderd.", parent=root)
            refresh_data()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Fout", f"Kon bestelling niet verwijderen: {e}", parent=root)
        finally:
            conn.close()

    def verwijder_alles():
        """Verwijder alle bestellingen (incl. bestelregels) na bevestiging."""
        if not messagebox.askyesno(
                "Alles verwijderen?",
                "Weet u zeker dat u ALLE bestellingen permanent wilt verwijderen?\nDit kan niet ongedaan worden gemaakt.",
                icon='warning',
                parent=root
        ):
            return

        confirm = simpledialog.askstring(
            "Bevestig",
            "Typ VERWIJDER ALLES om te bevestigen:",
            parent=root
        )
        if (confirm or "").strip().upper() != "VERWIJDER ALLES":
            messagebox.showinfo("Geannuleerd", "Verwijderen geannuleerd.", parent=root)
            return

        conn = database.get_db_connection()
        try:
            klant_ids = [row['klant_id'] for row in conn.execute("SELECT klant_id FROM bestellingen").fetchall()]

            conn.execute("DELETE FROM bestelregels")
            conn.execute("DELETE FROM bestellingen")
            conn.commit()

            for kid in set(klant_ids):
                if kid:
                    database.update_klant_statistieken(kid)

            messagebox.showinfo("Gereed", "Alle bestellingen zijn verwijderd.", parent=root)
            refresh_data()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Fout", f"Kon alle bestellingen niet verwijderen: {e}", parent=root)
        finally:
            conn.close()

    # --- Knoppen (zorg dat dit NIET in een functie staat) ---
    try:
        bewerk_icon = tk.PhotoImage(file="icons/edit.png")
        verwijder_icon = tk.PhotoImage(file="icons/delete.png")
        verwijder_alles_icon = tk.PhotoImage(file="icons/delete_all.png")
        bottom_frame._icons = (bewerk_icon, verwijder_icon, verwijder_alles_icon)
    except Exception:
        bewerk_icon = verwijder_icon = verwijder_alles_icon = None

    tk.Button(
        bottom_frame,
        text="Bewerk & Herdruk",
        image=bewerk_icon, compound="left",
        command=bewerk_en_herdruk_bon, bg="#D1FFD1"
    ).pack(side=tk.LEFT, padx=10, pady=5)

    tk.Button(
        bottom_frame,
        text="Verwijder Bestelling",
        image=verwijder_icon, compound="left",
        command=verwijder_bestelling, bg="#FFADAD"
    ).pack(side=tk.RIGHT, padx=10, pady=5)

    tk.Button(
        bottom_frame,
        text="Verwijder Alles",
        image=verwijder_alles_icon, compound="left",
        command=verwijder_alles, bg="#FF6B6B"
    ).pack(side=tk.RIGHT, padx=10, pady=5)

    # --- Start ---
    refresh_data()