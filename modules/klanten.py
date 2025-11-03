import tkinter as tk
from tkinter import ttk
import database


def open_klanten_zoeken(root, tel_entry, naam_entry, adres_entry, nr_entry, postcode_var, postcodes_lijst):
    """Open klant-zoekvenster in een apart Toplevel (hoofdschema blijft intact)."""
    top = tk.Toplevel(root)
    top.title("Klant zoeken")
    top.transient(root)
    top.grab_set()

    tk.Label(top, text="Zoek op Telefoonnummer:", font=("Arial", 11)).pack(pady=(10, 2), padx=10, anchor="w")

    zoek_var = tk.StringVar()
    zoek_entry = tk.Entry(top, textvariable=zoek_var, font=("Arial", 11))
    zoek_entry.pack(fill=tk.X, padx=10)
    zoek_entry.focus()

    result_frame = tk.Frame(top)
    result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    cols = ('telefoon', 'naam', 'adres')
    tree = ttk.Treeview(result_frame, columns=cols, show='headings', height=12)
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

    def update_zoekresultaten(*_):
        term = zoek_var.get().strip()
        tree.delete(*tree.get_children())
        if not term:
            return
        conn = database.get_db_connection()
        cur = conn.execute(
            "SELECT id, telefoon, naam, straat, huisnummer FROM klanten WHERE telefoon LIKE ?",
            (f"%{term}%",)
        )
        for r in cur.fetchall():
            adres = f"{r['straat'] or ''} {r['huisnummer'] or ''}".strip()
            tree.insert("", "end", iid=str(r['id']), values=(r['telefoon'], r['naam'] or "", adres))
        conn.close()

    def selecteer_klant_en_sluit():
        sel = tree.selection()
        if not sel:
            return
        klant_id = int(sel[0])
        conn = database.get_db_connection()
        k = conn.execute("SELECT * FROM klanten WHERE id = ?", (klant_id,)).fetchone()
        conn.close()
        if not k:
            return
        try:
            tel_entry.delete(0, tk.END);
            tel_entry.insert(0, k['telefoon'] or "")
            naam_entry.delete(0, tk.END);
            naam_entry.insert(0, k['naam'] or "")
            adres_entry.delete(0, tk.END);
            adres_entry.insert(0, k['straat'] or "")
            nr_entry.delete(0, tk.END);
            nr_entry.insert(0, k['huisnummer'] or "")
            plaats = k['plaats'] or ""
            match = next((p for p in postcodes_lijst if plaats in p), "")
            postcode_var.set(match if match else postcodes_lijst[0])
        except tk.TclError:
            pass
        top.destroy()

    zoek_var.trace_add("write", update_zoekresultaten)
    tree.bind("<Double-1>", lambda e: selecteer_klant_en_sluit())

    btns = tk.Frame(top, padx=10)
    btns.pack(fill=tk.X, pady=(0, 10))
    tk.Button(btns, text="Selecteer Klant", command=selecteer_klant_en_sluit, bg="#D1FFD1").pack(side=tk.LEFT)
    tk.Button(btns, text="Sluiten", command=top.destroy).pack(side=tk.RIGHT)