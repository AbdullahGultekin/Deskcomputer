import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import database
import json
from collections import defaultdict


def open_rapportage(root):
    # root is tab-frame
    win = root

    for w in win.winfo_children():
        w.destroy()

    paned = tk.PanedWindow(win, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashpad=4)
    paned.pack(fill=tk.BOTH, expand=True)

    # --- Linkerzijde: filters ---
    left = tk.Frame(paned, padx=10, pady=10)
    paned.add(left, minsize=260)

    tk.Label(left, text="Filters", font=("Arial", 13, "bold")).pack(anchor="w")

    periode_frame = tk.LabelFrame(left, text="Periode", padx=8, pady=8)
    periode_frame.pack(fill=tk.X, pady=(6, 10))

    periode_var = tk.StringVar(value="vandaag")
    opties = [("Vandaag", "vandaag"), ("Deze week", "week"), ("Deze maand", "maand"), ("Custom", "custom")]
    for text, val in opties:
        ttk.Radiobutton(periode_frame, text=text, value=val, variable=periode_var).pack(anchor="w")

    custom_frame = tk.Frame(periode_frame)
    custom_frame.pack(fill=tk.X, pady=(6, 0))
    tk.Label(custom_frame, text="Van (YYYY-MM-DD):").grid(row=0, column=0, sticky="w")
    from_var = tk.StringVar()
    tk.Entry(custom_frame, textvariable=from_var, width=12).grid(row=0, column=1, padx=(6, 0))
    tk.Label(custom_frame, text="Tot (YYYY-MM-DD):").grid(row=1, column=0, sticky="w", pady=(4, 0))
    to_var = tk.StringVar()
    tk.Entry(custom_frame, textvariable=to_var, width=12).grid(row=1, column=1, padx=(6, 0), pady=(4, 0))

    def get_date_range():
        today = datetime.date.today()
        if periode_var.get() == "vandaag":
            d1 = d2 = today
        elif periode_var.get() == "week":
            d1 = today - datetime.timedelta(days=today.weekday())
            d2 = today
        elif periode_var.get() == "maand":
            d1 = today.replace(day=1)
            d2 = today
        else:
            try:
                d1 = datetime.datetime.strptime(from_var.get(), "%Y-%m-%d").date()
                d2 = datetime.datetime.strptime(to_var.get(), "%Y-%m-%d").date()
            except Exception:
                messagebox.showwarning("Periode", "Voer geldige datums in (YYYY-MM-DD).")
                return None, None
        return d1, d2

    def refresh_all():
        d1, d2 = get_date_range()
        if not d1 or not d2:
            return
        load_omzet(d1, d2)
        load_populair(d1, d2)
        load_koeriers(d1, d2)

    ttk.Button(left, text="Toepassen", command=refresh_all).pack(anchor="w", pady=(4, 10))

    export_frame = tk.LabelFrame(left, text="Export", padx=8, pady=8)
    export_frame.pack(fill=tk.X)

    def export_excel(rows, headers, filename):
        try:
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.append(headers)
            for r in rows:
                ws.append(list(r))
            wb.save(filename)
            messagebox.showinfo("Export", f"Excel geëxporteerd naar {filename}")
        except ImportError:
            messagebox.showwarning("Export", "openpyxl niet gevonden. Valt terug op CSV.")
            export_csv(rows, headers, filename.replace(".xlsx", ".csv"))
        except Exception as e:
            messagebox.showerror("Export", f"Mislukt: {e}")

    export_data = {
        "omzet": ([], []),
        "populair": ([], []),
        "koeriers": ([], [])
    }

    ttk.Button(export_frame, text="Excel Omzet (.xlsx)",
               command=lambda: export_excel(*export_data["omzet"], "omzet.xlsx")).pack(fill=tk.X, pady=2)
    ttk.Button(export_frame, text="Excel Populair (.xlsx)",
               command=lambda: export_excel(*export_data["populair"], "populaire_producten.xlsx")).pack(fill=tk.X,
                                                                                                        pady=2)
    ttk.Button(export_frame, text="Excel Koeriers (.xlsx)",
               command=lambda: export_excel(*export_data["koeriers"], "koeriers.xlsx")).pack(fill=tk.X, pady=2)

    # --- Rechterzijde: tabs met rapporten ---
    right = tk.Frame(paned, padx=10, pady=10)
    paned.add(right, minsize=700)

    tabs = ttk.Notebook(right)
    tabs.pack(fill=tk.BOTH, expand=True)

    # Omzet tab
    omzet_tab = ttk.Frame(tabs)
    tabs.add(omzet_tab, text="Omzet")

    omzet_tree = ttk.Treeview(omzet_tab, columns=("periode", "orders", "omzet", "gemiddeld"), show="headings",
                              height=10)
    for col, text, w, anchor in [
        ("periode", "Periode", 160, "w"),
        ("orders", "Aantal orders", 120, "center"),
        ("omzet", "Omzet (€)", 120, "e"),
        ("gemiddeld", "Gem. per order (€)", 160, "e"),
    ]:
        omzet_tree.heading(col, text=text)
        omzet_tree.column(col, width=w, anchor=anchor)
    omzet_tree.pack(fill=tk.BOTH, expand=True)

    omzet_summary = tk.Label(omzet_tab, text="", font=("Arial", 11, "bold"))
    omzet_summary.pack(anchor="w", pady=(6, 0))

    # Populaire producten tab
    pop_tab = ttk.Frame(tabs)
    tabs.add(pop_tab, text="Populaire producten")

    pop_tree = ttk.Treeview(pop_tab, columns=("product", "categorie", "aantal", "omzet"), show="headings", height=14)
    for col, text, w, anchor in [
        ("product", "Product", 260, "w"),
        ("categorie", "Categorie", 160, "w"),
        ("aantal", "Aantal", 100, "center"),
        ("omzet", "Omzet (€)", 120, "e"),
    ]:
        pop_tree.heading(col, text=text)
        pop_tree.column(col, width=w, anchor=anchor)
    pop_tree.pack(fill=tk.BOTH, expand=True)

    # Koeriers tab
    koerier_tab = ttk.Frame(tabs)
    tabs.add(koerier_tab, text="Koeriers")

    koerier_tree = ttk.Treeview(koerier_tab, columns=("koerier", "orders", "omzet", "gem"), show="headings", height=14)
    for col, text, w, anchor in [
        ("koerier", "Koerier", 200, "w"),
        ("orders", "Aantal orders", 120, "center"),
        ("omzet", "Omzet (€)", 120, "e"),
        ("gem", "Gem. per order (€)", 160, "e"),
    ]:
        koerier_tree.heading(col, text=text)
        koerier_tree.column(col, width=w, anchor=anchor)
    koerier_tree.pack(fill=tk.BOTH, expand=True)

    def load_omzet(d1: datetime.date, d2: datetime.date):
        omzet_tree.delete(*omzet_tree.get_children())
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
                    SELECT datum, COUNT(*) AS orders, COALESCE(SUM(totaal), 0) AS omzet
                    FROM bestellingen
                    WHERE datum BETWEEN ? AND ?
                    GROUP BY datum
                    ORDER BY datum
                    """, (d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d")))
        rows = cur.fetchall()

        total_orders = 0
        total_omzet = 0.0
        for r in rows:
            orders = r["orders"]
            omzet = float(r["omzet"])
            total_orders += orders
            total_omzet += omzet
            gem = (omzet / orders) if orders else 0.0
            periode_str = datetime.datetime.strptime(r["datum"], "%Y-%m-%d").strftime("%d/%m/%Y")
            omzet_tree.insert("", tk.END, values=(periode_str, orders, f"{omzet:.2f}", f"{gem:.2f}"))

        cur.execute("""
                    SELECT strftime('%Y-%W', datum) AS week, COUNT(*) AS orders, COALESCE(SUM(totaal), 0) AS omzet
                    FROM bestellingen
                    WHERE datum BETWEEN ? AND ?
                    GROUP BY week
                    ORDER BY week
                    """, (d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d")))
        week_rows = cur.fetchall()
        cur.execute("""
                    SELECT strftime('%Y-%m', datum) AS maand, COUNT(*) AS orders, COALESCE(SUM(totaal), 0) AS omzet
                    FROM bestellingen
                    WHERE datum BETWEEN ? AND ?
                    GROUP BY maand
                    ORDER BY maand
                    """, (d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d")))
        maand_rows = cur.fetchall()
        conn.close()

        omzet_tree.insert("", tk.END, values=("", "", "", ""))
        omzet_tree.insert("", tk.END, values=("Per week", "", "", ""))
        for r in week_rows:
            gem = (float(r["omzet"]) / r["orders"]) if r["orders"] else 0.0
            omzet_tree.insert("", tk.END,
                              values=(f"Week {r['week']}", r["orders"], f"{float(r['omzet']):.2f}", f"{gem:.2f}"))
        omzet_tree.insert("", tk.END, values=("", "", "", ""))
        omzet_tree.insert("", tk.END, values=("Per maand", "", "", ""))
        for r in maand_rows:
            gem = (float(r["omzet"]) / r["orders"]) if r["orders"] else 0.0
            omzet_tree.insert("", tk.END,
                              values=(f"Maand {r['maand']}", r["orders"], f"{float(r['omzet']):.2f}", f"{gem:.2f}"))

        omzet_summary.config(
            text=f"Totaal orders: {total_orders}   |   Totale omzet: €{total_omzet:.2f}   |   Gemiddeld per order: €{(total_omzet / total_orders if total_orders else 0):.2f}")
        export_data["omzet"] = ([(omzet_tree.set(i, "periode"), omzet_tree.set(i, "orders"), omzet_tree.set(i, "omzet"),
                                  omzet_tree.set(i, "gemiddeld")) for i in omzet_tree.get_children("")],
                                ["Periode", "Aantal orders", "Omzet (€)", "Gem. per order (€)"])

    def load_populair(d1: datetime.date, d2: datetime.date):
        pop_tree.delete(*pop_tree.get_children())
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
                    SELECT br.product,
                           br.categorie,
                           SUM(br.aantal)                         AS aantal,
                           COALESCE(SUM(br.aantal * br.prijs), 0) AS omzet
                    FROM bestelregels br
                             JOIN bestellingen b ON b.id = br.bestelling_id
                    WHERE b.datum BETWEEN ? AND ?
                    GROUP BY br.product, br.categorie
                    ORDER BY aantal DESC, omzet DESC LIMIT 200
                    """, (d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d")))
        rows = cur.fetchall()
        conn.close()

        data = []
        for r in rows:
            pop_tree.insert("", tk.END, values=(r["product"], r["categorie"], r["aantal"], f"{float(r['omzet']):.2f}"))
            data.append((r["product"], r["categorie"], r["aantal"], f"{float(r['omzet']):.2f}"))

        export_data["populair"] = (data, ["Product", "Categorie", "Aantal", "Omzet (€)"])

    def load_koeriers(d1: datetime.date, d2: datetime.date):
        koerier_tree.delete(*koerier_tree.get_children())
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
                    SELECT COALESCE(ko.naam, 'Niet toegewezen') AS koerier,
                           COUNT(*)                             AS orders,
                           COALESCE(SUM(b.totaal), 0)           AS omzet
                    FROM bestellingen b
                             LEFT JOIN koeriers ko ON ko.id = b.koerier_id
                    WHERE b.datum BETWEEN ? AND ?
                    GROUP BY koerier
                    ORDER BY omzet DESC
                    """, (d1.strftime("%Y-%m-%d"), d2.strftime("%Y-%m-%d")))
        rows = cur.fetchall()
        conn.close()

        data = []
        for r in rows:
            orders = r["orders"]
            omzet = float(r["omzet"])
            gem = (omzet / orders) if orders else 0.0
            koerier_tree.insert("", tk.END, values=(r["koerier"], orders, f"{omzet:.2f}", f"{gem:.2f}"))
            data.append((r["koerier"], orders, f"{omzet:.2f}", f"{gem:.2f}"))

        export_data["koeriers"] = (data, ["Koerier", "Aantal orders", "Omzet (€)", "Gem. per order (€)"])

    # Init: vandaag
    periode_var.set("vandaag")
    refresh_all()