import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import datetime
import database


def open_voorraad(root):
    # root is tab-frame; embed i.p.v. Toplevel
    win = root

    for w in win.winfo_children():
        w.destroy()

    paned = tk.PanedWindow(win, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashpad=4)
    paned.pack(fill=tk.BOTH, expand=True)

    # Links: ingrediëntenlijst + acties
    left = tk.Frame(paned, padx=10, pady=10)
    paned.add(left, minsize=420)

    tk.Label(left, text="Ingrediënten", font=("Arial", 13, "bold")).pack(anchor="w")

    cols = ("naam", "eenheid", "voorraad", "minimum", "status")
    tree = ttk.Treeview(left, columns=cols, show="headings", height=20)
    settings = {
        "naam": ("Naam", 200, "w"),
        "eenheid": ("Eenheid", 80, "center"),
        "voorraad": ("Huidige", 100, "e"),
        "minimum": ("Minimum", 100, "e"),
        "status": ("Status", 110, "w")
    }
    for c in cols:
        text, w, a = settings[c]
        tree.heading(c, text=text)
        tree.column(c, width=w, anchor=a)
    tree.pack(fill=tk.BOTH, expand=True)

    btns = tk.Frame(left)
    btns.pack(fill=tk.X, pady=(8, 0))
    ttk.Button(btns, text="Nieuw ingrediënt", command=lambda: nieuw_ingredient()).pack(side=tk.LEFT)
    ttk.Button(btns, text="Voorraad +", command=lambda: wijzig_voorraad(+1)).pack(side=tk.LEFT, padx=6)
    ttk.Button(btns, text="Voorraad -", command=lambda: wijzig_voorraad(-1)).pack(side=tk.LEFT)
    ttk.Button(btns, text="Minimum instellen", command=lambda: stel_minimum_in()).pack(side=tk.LEFT, padx=6)
    ttk.Button(btns, text="Herlaad", command=lambda: laad_ingredienten()).pack(side=tk.RIGHT)

    # Rechts: tabs Recepturen en Mutaties
    right = tk.Frame(paned, padx=10, pady=10)
    paned.add(right, minsize=520)

    tabs = ttk.Notebook(right)
    tabs.pack(fill=tk.BOTH, expand=True)

    # Recepturen tab
    rec_tab = ttk.Frame(tabs)
    tabs.add(rec_tab, text="Recepturen (per product)")

    rec_cols = ("categorie", "product", "ingredient", "hoeveelheid", "eenheid")
    rec_tree = ttk.Treeview(rec_tab, columns=rec_cols, show="headings", height=16)
    for c, t, w, a in [
        ("categorie", "Categorie", 180, "w"),
        ("product", "Product", 220, "w"),
        ("ingredient", "Ingrediënt", 200, "w"),
        ("hoeveelheid", "Per stuk", 100, "e"),
        ("eenheid", "Eenheid", 80, "center"),
    ]:
        rec_tree.heading(c, text=t)
        rec_tree.column(c, width=w, anchor=a)
    rec_tree.pack(fill=tk.BOTH, expand=True)

    rec_btns = tk.Frame(rec_tab)
    rec_btns.pack(fill=tk.X, pady=(8, 0))
    ttk.Button(rec_btns, text="Koppeling toevoegen", command=lambda: nieuwe_receptregel()).pack(side=tk.LEFT)
    ttk.Button(rec_btns, text="Koppeling verwijderen", command=lambda: verwijder_receptregel()).pack(side=tk.LEFT,
                                                                                                     padx=6)
    ttk.Button(rec_btns, text="Herlaad", command=lambda: laad_recepturen()).pack(side=tk.RIGHT)

    # Mutaties tab
    mut_tab = ttk.Frame(tabs)
    tabs.add(mut_tab, text="Voorraadmutaties")

    mut_cols = ("tijd", "ingredient", "mutatie", "reden")
    mut_tree = ttk.Treeview(mut_tab, columns=mut_cols, show="headings", height=16)
    for c, t, w, a in [
        ("tijd", "Datum/Tijd", 150, "center"),
        ("ingredient", "Ingrediënt", 220, "w"),
        ("mutatie", "Mutatie", 100, "e"),
        ("reden", "Reden", 260, "w"),
    ]:
        mut_tree.heading(c, text=t)
        mut_tree.column(c, width=w, anchor=a)
    mut_tree.pack(fill=tk.BOTH, expand=True)

    ttk.Button(mut_tab, text="Herlaad", command=lambda: laad_mutaties()).pack(anchor="e", pady=(8, 0))

    # Loaders
    def laad_ingredienten():
        tree.delete(*tree.get_children())
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, naam, eenheid, huidige_voorraad, minimum FROM ingredienten ORDER BY naam")
        for r in cur.fetchall():
            status = ""
            if r["huidige_voorraad"] is not None and r["minimum"] is not None and r["huidige_voorraad"] <= r["minimum"]:
                status = "Onder minimum"
            tree.insert("", tk.END, iid=r["id"], values=(
                r["naam"], r["eenheid"], f"{(r['huidige_voorraad'] or 0):.3f}", f"{(r['minimum'] or 0):.3f}", status
            ))
        conn.close()

    def nieuw_ingredient():
        naam = simpledialog.askstring("Nieuw ingrediënt", "Naam:")
        if not naam: return
        eenheid = simpledialog.askstring("Nieuw ingrediënt", "Eenheid (bv. kg, st, l):")
        if not eenheid: return
        try:
            conn = database.get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO ingredienten (naam, eenheid, minimum, huidige_voorraad) VALUES (?, ?, 0, 0)",
                        (naam.strip(), eenheid.strip()))
            conn.commit()
            conn.close()
            laad_ingredienten()
        except Exception as e:
            messagebox.showerror("Fout", f"Invoegen mislukt: {e}")

    def wijzig_voorraad(sign):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Selectie", "Selecteer een ingrediënt.")
            return
        try:
            delta = float(simpledialog.askstring("Voorraad aanpassen", "Hoeveelheid (+/-):").replace(",", "."))
        except Exception:
            return
        ingr_id = int(sel[0])
        conn = database.get_db_connection()
        cur = conn.cursor()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mut = delta * sign
        try:
            cur.execute("INSERT INTO voorraad_mutaties (ingredient_id, mutatie, reden, datumtijd) VALUES (?, ?, ?, ?)",
                        (ingr_id, mut, "Handmatige aanpassing", now_str))
            cur.execute("UPDATE ingredienten SET huidige_voorraad = COALESCE(huidige_voorraad,0) + ? WHERE id = ?",
                        (mut, ingr_id))
            conn.commit()
        finally:
            conn.close()
        laad_ingredienten()
        laad_mutaties()

    def stel_minimum_in():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Selectie", "Selecteer een ingrediënt.")
            return
        try:
            val = float(simpledialog.askstring("Minimum drempel", "Minimum:", initialvalue="0").replace(",", "."))
        except Exception:
            return
        ingr_id = int(sel[0])
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE ingredienten SET minimum = ? WHERE id = ?", (val, ingr_id))
        conn.commit()
        conn.close()
        laad_ingredienten()

    def laad_recepturen():
        rec_tree.delete(*rec_tree.get_children())
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
                    SELECT r.id, r.categorie, r.product, i.naam AS ingredient, r.hoeveelheid_per_stuk, i.eenheid
                    FROM recepturen r
                             JOIN ingredienten i ON i.id = r.ingredient_id
                    ORDER BY r.categorie, r.product, i.naam
                    """)
        for r in cur.fetchall():
            rec_tree.insert("", tk.END, iid=r["id"], values=(
                r["categorie"], r["product"], r["ingredient"], f"{r['hoeveelheid_per_stuk']:.3f}", r["eenheid"]
            ))
        conn.close()

    # Add this function in your voorraad.py file, likely near other recipe-related functions

    def nieuwe_receptregel():
        """Voegt een nieuwe receptregel/koppeling toe"""
        # This function should open a dialog or add a row to link ingredients to menu items
        # Example implementation:
        try:
            # Add your logic here to create a new recipe ingredient link
            # For example, opening a dialog to select product and ingredient
            messagebox.showinfo("Info", "Koppeling toevoegen functionaliteit nog te implementeren")
        except Exception as e:
            messagebox.showerror("Fout", f"Kon receptregel niet toevoegen: {e}")

    def verwijder_receptregel():
        sel = rec_tree.selection()
        if not sel:
            messagebox.showinfo("Selectie", "Selecteer een receptuurregel.")
            return
        rec_id = int(sel[0])
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM recepturen WHERE id = ?", (rec_id,))
        conn.commit()
        conn.close()
        laad_recepturen()

    def laad_mutaties():
        mut_tree.delete(*mut_tree.get_children())
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
                    SELECT m.id, m.datumtijd, i.naam AS ingredient, m.mutatie, m.reden
                    FROM voorraad_mutaties m
                             JOIN ingredienten i ON i.id = m.ingredient_id
                    ORDER BY m.datumtijd DESC LIMIT 500
                    """)
        for r in cur.fetchall():
            mut_tree.insert("", tk.END, iid=r["id"],
                            values=(r["datumtijd"], r["ingredient"], f"{r['mutatie']:.3f}", r["reden"] or ""))
        conn.close()

    # eerste load
    laad_ingredienten()
    laad_recepturen()
    laad_mutaties()