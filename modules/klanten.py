import tkinter as tk
from tkinter import ttk
import database  # Gebruik de nieuwe database module


def open_klanten_zoeken(root, tel_entry, naam_entry,  adres_entry, nr_entry, postcode_var, postcodes_lijst):
    """Opent een venster om een klant te zoeken op telefoonnummer en de velden in te vullen."""
    win = tk.Toplevel(root)
    win.title("Zoek Klant")
    win.geometry("650x400")

    tk.Label(win, text="Zoek op Telefoonnummer:", font=("Arial", 11)).pack(pady=(10, 2), padx=10, anchor="w")

    zoek_var = tk.StringVar()
    zoek_entry = tk.Entry(win, textvariable=zoek_var, font=("Arial", 11))
    zoek_entry.pack(fill=tk.X, padx=10)
    zoek_entry.focus()

    result_frame = tk.Frame(win)
    result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    cols = ('telefoon', 'naam', 'adres')
    tree = ttk.Treeview(result_frame, columns=cols, show='headings')
    tree.heading('telefoon', text='Telefoonnummer')
    tree.heading('naam', text='Naam')
    tree.heading('adres', text='Adres')
    tree.column('telefoon', width=120)
    tree.column('naam', width=150)
    tree.column('adres', width=250)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_zoekresultaten(*args):
        zoekterm = zoek_var.get().strip()
        tree.delete(*tree.get_children())

        if not zoekterm:
            return

        conn = database.get_db_connection()
        # Gebruik LIKE voor een flexibele zoekopdracht
        cursor = conn.execute("SELECT id, telefoon, naam, straat, huisnummer FROM klanten WHERE telefoon LIKE ?",
                              (f"%{zoekterm}%",))

        for klant in cursor.fetchall():
            adres = f"{klant['straat']} {klant['huisnummer']}"
            tree.insert("", "end", values=(klant['telefoon'], klant['naam'], adres), iid=klant['id'])

        conn.close()

    def selecteer_klant_en_sluit():
        selected_item = tree.selection()
        if not selected_item:
            return

        klant_id = selected_item[0]
        conn = database.get_db_connection()
        geselecteerde_klant = conn.execute("SELECT * FROM klanten WHERE id = ?", (klant_id,)).fetchone()
        conn.close()

        if geselecteerde_klant:
            tel_entry.delete(0, tk.END)
            tel_entry.insert(0, geselecteerde_klant['telefoon'])

            naam_entry.delete(0, tk.END)
            naam_entry.insert(0, geselecteerde_klant['naam'] or "")

            adres_entry.delete(0, tk.END)
            adres_entry.insert(0, geselecteerde_klant['straat'])

            nr_entry.delete(0, tk.END)
            nr_entry.insert(0, geselecteerde_klant['huisnummer'])

            postcode_plaats_db = geselecteerde_klant['plaats']

            gevonden_postcode = ""
            for p in postcodes_lijst:
                if postcode_plaats_db in p:
                    gevonden_postcode = p
                    break

            postcode_var.set(gevonden_postcode if gevonden_postcode else postcodes_lijst[0])

            win.destroy()

    zoek_var.trace_add("write", update_zoekresultaten)
    tree.bind("<Double-1>", lambda event: selecteer_klant_en_sluit())

    button_frame = tk.Frame(win, padx=10)
    button_frame.pack(fill=tk.X, pady=(0, 10))
    tk.Button(button_frame, text="Selecteer Klant", command=selecteer_klant_en_sluit, bg="#D1FFD1").pack(side=tk.LEFT)
    tk.Button(button_frame, text="Sluiten", command=win.destroy).pack(side=tk.RIGHT)


def voeg_klant_toe_indien_nodig(telefoon, adres, nr, postcode_plaats, naam_of_opmerking):
    """Voegt een klant toe aan de database als deze nog niet bestaat op basis van telefoonnummer."""
    if not telefoon:
        return

    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Controleer of klant bestaat
    cursor.execute("SELECT id FROM klanten WHERE telefoon = ?", (telefoon,))
    bestaande_klant = cursor.fetchone()

    if bestaande_klant is None:
        # Klant bestaat niet, voeg toe
        cursor.execute('''
                       INSERT INTO klanten (telefoon, straat, huisnummer, plaats, naam)
                       VALUES (?, ?, ?, ?, ?)
                       ''', (telefoon, adres, nr, postcode_plaats, naam_of_opmerking))
        conn.commit()
        print(f"Nieuwe klant ({telefoon}) toegevoegd aan de database.")

    conn.close()