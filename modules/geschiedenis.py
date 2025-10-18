import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import json
import database  # Gebruik de nieuwe database module


def open_geschiedenis(root):
    win = tk.Toplevel(root)
    win.title("Bestelgeschiedenis van Vandaag")
    win.geometry("1100x600")

    tree_frame = tk.Frame(win)
    tree_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

    cols = ('tijd', 'adres', 'nr', 'gemeente', 'tel', 'prijs', 'bestelling')
    tree = ttk.Treeview(tree_frame, columns=cols, show='headings')

    tree.heading('tijd', text='Tijd')
    tree.column('tijd', width=60, anchor='center')
    tree.heading('adres', text='Adres')
    tree.column('adres', width=200)
    tree.heading('nr', text='Nr')
    tree.column('nr', width=40, anchor='center')
    tree.heading('gemeente', text='Gemeente')
    tree.column('gemeente', width=120)
    tree.heading('tel', text='Telefoon')
    tree.column('tel', width=100)
    tree.heading('prijs', text='Prijs (€)')
    tree.column('prijs', width=60, anchor='e')
    tree.heading('bestelling', text='Details Bestelling')
    tree.column('bestelling', width=400)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def laad_geschiedenis():
        for i in tree.get_children():
            tree.delete(i)

        vandaag_str = datetime.date.today().strftime('%Y-%m-%d')
        conn = database.get_db_connection()
        cursor = conn.cursor()

        # JOIN query om klantgegevens en bestelregels op te halen
        cursor.execute("""
                       SELECT b.id, b.tijd, b.totaal, k.telefoon, k.straat, k.huisnummer, k.plaats
                       FROM bestellingen b
                                JOIN klanten k ON b.klant_id = k.id
                       WHERE b.datum = ?
                       ORDER BY b.tijd DESC
                       """, (vandaag_str,))

        bestellingen_vandaag = cursor.fetchall()

        for bestelling in bestellingen_vandaag:
            # Haal bestelregels op voor een beknopte weergave
            cursor.execute("SELECT aantal, product FROM bestelregels WHERE bestelling_id = ?", (bestelling['id'],))
            regels = cursor.fetchall()
            details_list = [f"{r['aantal']}x {r['product']}" for r in regels]
            bestel_details_str = ", ".join(details_list)

            gemeente = ' '.join(bestelling['plaats'].split()[1:]) if ' ' in bestelling['plaats'] else ''

            tree.insert("", "end", iid=bestelling['id'], values=(
                bestelling['tijd'],
                bestelling['straat'],
                bestelling['huisnummer'],
                gemeente,
                bestelling['telefoon'],
                f"{bestelling['totaal']:.2f}",
                bestel_details_str
            ))
        conn.close()

    def wis_vandaag_geschiedenis():
        if messagebox.askyesno("Bevestig",
                               "Weet u zeker dat u ALLE bestellingen van vandaag wilt verwijderen? Dit kan niet ongedaan worden gemaakt."):
            vandaag_str = datetime.date.today().strftime('%Y-%m-%d')
            conn = database.get_db_connection()
            cursor = conn.cursor()

            # Haal alle bestelling ID's van vandaag op
            cursor.execute("SELECT id FROM bestellingen WHERE datum = ?", (vandaag_str,))
            bestelling_ids = [row[0] for row in cursor.fetchall()]

            if bestelling_ids:
                # Verwijder eerst de afhankelijke bestelregels
                cursor.executemany("DELETE FROM bestelregels WHERE bestelling_id = ?",
                                   [(bid,) for bid in bestelling_ids])
                # Verwijder daarna de hoofdbestellingen
                cursor.execute("DELETE FROM bestellingen WHERE datum = ?", (vandaag_str,))
                conn.commit()

            conn.close()
            laad_geschiedenis()

    def verwijder_geselecteerde_rij():
        selected_items = tree.selection()
        if not selected_items:
            messagebox.showwarning("Selectie", "Selecteer eerst een bestelling om te verwijderen.")
            return

        if messagebox.askyesno("Bevestig", "Weet u zeker dat u de geselecteerde bestelling(en) wilt verwijderen?"):
            conn = database.get_db_connection()
            cursor = conn.cursor()

            bestelling_ids_to_delete = [(int(iid),) for iid in selected_items]

            # Verwijder eerst de bestelregels, dan de bestellingen zelf
            cursor.executemany("DELETE FROM bestelregels WHERE bestelling_id = ?", bestelling_ids_to_delete)
            cursor.executemany("DELETE FROM bestellingen WHERE id = ?", bestelling_ids_to_delete)

            conn.commit()
            conn.close()
            laad_geschiedenis()

    button_frame = tk.Frame(win, padx=10, pady=10)
    button_frame.pack(fill=tk.X)

    tk.Button(button_frame, text="Herladen", command=laad_geschiedenis, bg="#E1E1FF").pack(side=tk.LEFT)
    tk.Button(button_frame, text="Verwijder Selectie", command=verwijder_geselecteerde_rij, bg="#FFADAD").pack(
        side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="Wis Alle Bestellingen van Vandaag", command=wis_vandaag_geschiedenis,
              bg="#FF5555").pack(side=tk.RIGHT)

    laad_geschiedenis()