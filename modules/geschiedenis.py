import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import json
import database
from modules.bon_viewer import open_bon_viewer  # <-- BELANGRIJK: Importeer de bon_viewer


def open_geschiedenis(root, menu_data_global, extras_data_global, app_settings_global):  # <-- Let op de parameters
    win = tk.Toplevel(root)
    win.title("Bestelgeschiedenis van Vandaag")
    win.geometry("1100x600")

    tree_frame = tk.Frame(win)
    tree_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

    cols = ('tijd', 'adres', 'nr', 'gemeente', 'tel', 'prijs', 'bonnummer', 'bestelling')  # <-- Bonnummer toegevoegd
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
    tree.heading('bonnummer', text='Bon Nr.')  # <-- Nieuwe kolom header
    tree.column('bonnummer', width=70, anchor='center')  # <-- Nieuwe kolom breedte
    tree.heading('bestelling', text='Details Bestelling')
    tree.column('bestelling', width=350)  # Breedte aangepast i.v.m. nieuwe kolom

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
                       SELECT b.id,
                              b.tijd,
                              b.totaal,
                              b.bonnummer,
                              k.telefoon,
                              k.straat,
                              k.huisnummer,
                              k.plaats
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
                bestelling['bonnummer'],  # <-- Bonnummer toegevoegd
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

    def herdruk_bon():  # <-- NIEUW: Functie om de bon te herdrukken
        selected_item_id = tree.focus()  # Krijg de ID van het geselecteerde item
        if not selected_item_id:
            messagebox.showwarning("Selectie Fout", "Selecteer alstublieft een bestelling om te herdrukken.")
            return

        bestelling_id = int(selected_item_id)

        conn = database.get_db_connection()
        cursor = conn.cursor()

        try:
            # 1. Haal bestelling details op
            cursor.execute("""
                           SELECT b.id,
                                  b.bonnummer,
                                  b.opmerking,
                                  b.klant_id,
                                  b.totaal,
                                  b.datum,
                                  b.tijd,
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
                messagebox.showerror("Fout", "Bestelling niet gevonden in de database.")
                return

            # Bouw klant_data dict voor bon_generator
            klant_data = {
                "telefoon": bestelling['telefoon'],
                "adres": bestelling['straat'],
                "nr": bestelling['huisnummer'],
                "postcode_gemeente": bestelling['plaats'],
                "opmerking": bestelling['opmerking'] if bestelling['opmerking'] else "",
                "naam": bestelling['naam'] if bestelling['naam'] else ""
            }

            # 2. Haal bestelregels op voor deze bestelling
            cursor.execute("SELECT categorie, product, aantal, prijs, extras FROM bestelregels WHERE bestelling_id = ?",
                           (bestelling_id,))
            bestelregels_db = cursor.fetchall()

            # Transformeer bestelregels naar het verwachte formaat van bon_generator
            formatted_bestelregels = []
            for regel in bestelregels_db:
                formatted_bestelregels.append({
                    'categorie': regel['categorie'],
                    'product': regel['product'],
                    'aantal': regel['aantal'],
                    'prijs': regel['prijs'],
                    'extras': json.loads(regel['extras']) if regel['extras'] else {}  # Extras zijn JSON strings
                })

            # 3. Roep de bon viewer aan
            open_bon_viewer(
                win,  # Gebruik het geschiedenis venster als ouder
                klant_data,
                formatted_bestelregels,
                bestelling['bonnummer'],
                menu_data_global,
                extras_data_global,
                app_settings_global
            )

        except Exception as e:
            messagebox.showerror("Fout bij herdrukken",
                                 f"Er is een fout opgetreden bij het ophalen van de bestelling: {e}")
        finally:
            conn.close()

    button_frame = tk.Frame(win, padx=10, pady=10)
    button_frame.pack(fill=tk.X)

    tk.Button(button_frame, text="Herladen", command=laad_geschiedenis, bg="#E1E1FF").pack(side=tk.LEFT)
    tk.Button(button_frame, text="Bon Herdrukken", command=herdruk_bon, bg="#FFF59D").pack(side=tk.LEFT,
                                                                                           padx=10)  # <-- NIEUW: Herdruk knop
    tk.Button(button_frame, text="Verwijder Selectie", command=verwijder_geselecteerde_rij, bg="#FFADAD").pack(
        side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="Wis Alle Bestellingen van Vandaag", command=wis_vandaag_geschiedenis,
              bg="#FF5555").pack(side=tk.RIGHT)

    laad_geschiedenis()