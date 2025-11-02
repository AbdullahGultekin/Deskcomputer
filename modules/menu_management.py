import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os


def open_menu_management(root):
    """Opent het menu management venster"""

    def load_menu_data():
        """Laadt de menu data uit menu.json"""
        try:
            with open("menu.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Fout", "menu.json niet gevonden!")
            return {}
        except json.JSONDecodeError:
            messagebox.showerror("Fout", "menu.json is geen geldige JSON!")
            return {}

    def save_menu_data(menu_data):
        """Slaat de menu data op naar menu.json"""
        try:
            with open("menu.json", "w", encoding="utf-8") as f:
                json.dump(menu_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            messagebox.showerror("Fout", f"Kon menu niet opslaan: {e}")
            return False

    def get_next_id(menu_data, category):
        if category not in menu_data or not menu_data[category]:
            return 1
        existing_ids = [item.get('id') for item in menu_data[category] if 'id' in item]
        return (max(existing_ids) + 1) if existing_ids else 1

    # Embed in tab
    win = root
    for w in win.winfo_children():
        w.destroy()

    # Menu data laden
    menu_data = load_menu_data()
    if not menu_data:
        return

    # Main PanedWindow (verticaal gesplitst)
    main_paned = tk.PanedWindow(win, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashpad=4)
    main_paned.pack(fill=tk.BOTH, expand=True)

    # --- LINKS: Categorieën ---
    left_frame = tk.Frame(main_paned, padx=8, pady=8)
    main_paned.add(left_frame, minsize=250)

    tk.Label(left_frame, text="Categorieën", font=("Arial", 13, "bold")).pack(anchor="w")

    # Categorieën listbox
    cat_frame = tk.Frame(left_frame)
    cat_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

    cat_listbox = tk.Listbox(cat_frame, font=("Arial", 11), exportselection=False)
    cat_scrollbar = tk.Scrollbar(cat_frame, orient=tk.VERTICAL, command=cat_listbox.yview)
    cat_listbox.configure(yscrollcommand=cat_scrollbar.set)

    cat_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    cat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Categorie knoppen
    cat_buttons_frame = tk.Frame(left_frame)
    cat_buttons_frame.pack(fill=tk.X)

    def refresh_categories():
        """Vernieuwt de categorieën lijst"""
        cat_listbox.delete(0, tk.END)
        for category in menu_data.keys():
            cat_listbox.insert(tk.END, category)

    def add_category():
        """Voegt een nieuwe categorie toe"""
        new_cat = simpledialog.askstring("Nieuwe Categorie", "Naam van de nieuwe categorie:")
        if new_cat and new_cat.strip():
            new_cat = new_cat.strip()
            if new_cat in menu_data:
                messagebox.showwarning("Fout", "Deze categorie bestaat al!")
                return

            menu_data[new_cat] = []
            if save_menu_data(menu_data):
                refresh_categories()
                messagebox.showinfo("Succes", f"Categorie '{new_cat}' toegevoegd!")

    def rename_category():
        """Hernoemt een categorie"""
        selection = cat_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
            return

        old_name = list(menu_data.keys())[selection[0]]
        new_name = simpledialog.askstring("Categorie Hernoemen",
                                          f"Nieuwe naam voor '{old_name}':",
                                          initialvalue=old_name)

        if new_name and new_name.strip() and new_name.strip() != old_name:
            new_name = new_name.strip()
            if new_name in menu_data:
                messagebox.showwarning("Fout", "Deze categorie bestaat al!")
                return

            # Hernoem de categorie
            menu_data[new_name] = menu_data.pop(old_name)
            if save_menu_data(menu_data):
                refresh_categories()
                refresh_products()
                messagebox.showinfo("Succes", f"Categorie hernoemd naar '{new_name}'!")

    def delete_category():
        """Verwijdert een categorie"""
        selection = cat_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
            return

        cat_name = list(menu_data.keys())[selection[0]]
        product_count = len(menu_data[cat_name])

        if product_count > 0:
            if not messagebox.askyesno("Bevestigen",
                                       f"Categorie '{cat_name}' bevat {product_count} product(en).\n"
                                       f"Weet u zeker dat u deze wilt verwijderen?"):
                return

        del menu_data[cat_name]
        if save_menu_data(menu_data):
            refresh_categories()
            refresh_products()
            messagebox.showinfo("Succes", f"Categorie '{cat_name}' verwijderd!")

    tk.Button(cat_buttons_frame, text="Toevoegen", command=add_category,
              bg="#D1FFD1", width=12).pack(side=tk.LEFT, padx=(0, 5))
    tk.Button(cat_buttons_frame, text="Hernoemen", command=rename_category,
              bg="#FFE5B4", width=12).pack(side=tk.LEFT, padx=5)
    tk.Button(cat_buttons_frame, text="Verwijderen", command=delete_category,
              bg="#FFADAD", width=12).pack(side=tk.LEFT, padx=(5, 0))

    # --- MIDDEN: Producten ---
    middle_frame = tk.Frame(main_paned, padx=8, pady=8)
    main_paned.add(middle_frame, minsize=500)

    products_title = tk.Label(middle_frame, text="Producten", font=("Arial", 13, "bold"))
    products_title.pack(anchor="w")

    # Producten treeview
    tree_frame = tk.Frame(middle_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

    columns = ('id', 'naam', 'prijs', 'desc')
    product_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

    # Column headers en widths
    product_tree.heading('id', text='ID')
    product_tree.column('id', width=60, anchor='center')
    product_tree.heading('naam', text='Naam')
    product_tree.column('naam', width=200)
    product_tree.heading('prijs', text='Prijs (€)')
    product_tree.column('prijs', width=80, anchor='e')
    product_tree.heading('desc', text='Beschrijving')
    product_tree.column('desc', width=300)

    tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=product_tree.yview)
    product_tree.configure(yscrollcommand=tree_scrollbar.set)

    product_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Product knoppen
    product_buttons_frame = tk.Frame(middle_frame)
    product_buttons_frame.pack(fill=tk.X)

    def get_selected_category():
        """Geeft de geselecteerde categorie terug"""
        selection = cat_listbox.curselection()
        if not selection:
            return None
        return list(menu_data.keys())[selection[0]]

    def refresh_products():
        """Vernieuwt de productlijst"""
        product_tree.delete(*product_tree.get_children())

        category = get_selected_category()
        if not category or category not in menu_data:
            products_title.config(text="Producten")
            return

        products_title.config(text=f"Producten — {category}")

        for product in menu_data[category]:
            product_tree.insert('', tk.END, values=(
                product.get('id', ''),
                product.get('naam', ''),
                f"{product.get('prijs', 0):.2f}",
                product.get('desc', '')
            ))

    def add_product():
        """Voegt een nieuw product toe"""
        category = get_selected_category()
        if not category:
            messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
            return

        open_product_dialog(category, None, "Nieuw Product")

    def edit_product():
        """Bewerkt het geselecteerde product"""
        category = get_selected_category()
        if not category:
            messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
            return

        selection = product_tree.selection()
        if not selection:
            messagebox.showwarning("Selectie", "Selecteer eerst een product!")
            return

        # Vind het product op basis van de geselecteerde rij
        item = product_tree.item(selection[0])
        values = item['values']
        product_id = values[0]

        # Zoek het product in de data
        product = None
        product_index = None
        for i, p in enumerate(menu_data[category]):
            if str(p.get('id', '')) == str(product_id):
                product = p
                product_index = i
                break

        if product is None:
            messagebox.showerror("Fout", "Product niet gevonden!")
            return

        open_product_dialog(category, (product, product_index), "Product Bewerken")

    def delete_product():
        """Verwijdert het geselecteerde product"""
        category = get_selected_category()
        if not category:
            messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
            return

        selection = product_tree.selection()
        if not selection:
            messagebox.showwarning("Selectie", "Selecteer eerst een product!")
            return

        item = product_tree.item(selection[0])
        values = item['values']
        product_id = values[0]
        product_name = values[1]

        if not messagebox.askyesno("Bevestigen", f"Weet u zeker dat u '{product_name}' wilt verwijderen?"):
            return

        # Verwijder het product
        menu_data[category] = [p for p in menu_data[category] if str(p.get('id', '')) != str(product_id)]

        if save_menu_data(menu_data):
            refresh_products()
            messagebox.showinfo("Succes", f"Product '{product_name}' verwijderd!")

    def open_product_dialog(category, product_data, title):
        """Opent een dialog voor product bewerking/toevoeging"""
        dialog = tk.Toplevel(win)
        dialog.title(title)
        dialog.geometry("400x300")
        dialog.transient(win)
        dialog.grab_set()

        # Center the dialog
        dialog.geometry("400x300+{}+{}".format(
            win.winfo_x() + 400, win.winfo_y() + 200
        ))

        # Variables
        naam_var = tk.StringVar()
        prijs_var = tk.StringVar()
        desc_var = tk.StringVar()
        id_var = tk.StringVar()

        if product_data:  # Bewerken
            product, product_index = product_data
            naam_var.set(product.get('naam', ''))
            prijs_var.set(str(product.get('prijs', '')))
            desc_var.set(product.get('desc', ''))
            id_var.set(str(product.get('id', '')))
        else:  # Nieuw
            id_var.set(str(get_next_id(menu_data, category)))

        # Form
        tk.Label(dialog, text="ID:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        id_entry = tk.Entry(dialog, textvariable=id_var, font=("Arial", 10), width=30)
        id_entry.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        tk.Label(dialog, text="Naam:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        naam_entry = tk.Entry(dialog, textvariable=naam_var, font=("Arial", 10), width=30)
        naam_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        tk.Label(dialog, text="Prijs (€):", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w", padx=10,
                                                                             pady=5)
        prijs_entry = tk.Entry(dialog, textvariable=prijs_var, font=("Arial", 10), width=30)
        prijs_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        tk.Label(dialog, text="Beschrijving:", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky="nw", padx=10,
                                                                                pady=5)
        desc_text = tk.Text(dialog, width=30, height=8, font=("Arial", 10))
        desc_text.grid(row=3, column=1, padx=10, pady=5, sticky="ew")
        desc_text.insert('1.0', desc_var.get())

        dialog.grid_columnconfigure(1, weight=1)

        # Buttons
        button_frame = tk.Frame(dialog)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        def save_product():
            """Slaat het product op"""
            # Validatie
            if not naam_var.get().strip():
                messagebox.showwarning("Validatie", "Productnaam is verplicht!")
                return

            try:
                prijs = float(prijs_var.get().replace(',', '.'))
            except ValueError:
                messagebox.showwarning("Validatie", "Voer een geldige prijs in!")
                return

            try:
                product_id = int(id_var.get())
            except ValueError:
                messagebox.showwarning("Validatie", "Voer een geldig ID in!")
                return

            # Check for duplicate ID (alleen bij nieuwe producten of als ID is veranderd)
            if not product_data or str(product_data[0].get('id', '')) != str(product_id):
                for p in menu_data[category]:
                    if p.get('id') == product_id:
                        messagebox.showwarning("Validatie", "Dit ID bestaat already!")
                        return

            # Maak of update product
            new_product = {
                'id': product_id,
                'naam': naam_var.get().strip(),
                'prijs': prijs,
                'desc': desc_text.get('1.0', tk.END).strip()
            }

            if product_data:  # Bewerken
                menu_data[category][product_data[1]] = new_product
                action = "bewerkt"
            else:  # Nieuw
                menu_data[category].append(new_product)
                # Sort by ID
                menu_data[category].sort(key=lambda x: x.get('id', 0))
                action = "toegevoegd"

            if save_menu_data(menu_data):
                refresh_products()
                messagebox.showinfo("Succes", f"Product '{new_product['naam']}' {action}!")
                dialog.destroy()

        def cancel():
            dialog.destroy()

        tk.Button(button_frame, text="Opslaan", command=save_product,
                  bg="#D1FFD1", width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Annuleren", command=cancel,
                  bg="#FFADAD", width=12).pack(side=tk.LEFT, padx=5)

        # Focus op naam veld
        naam_entry.focus()

    tk.Button(product_buttons_frame, text="Toevoegen", command=add_product,
              bg="#D1FFD1", width=12).pack(side=tk.LEFT, padx=(0, 5))
    tk.Button(product_buttons_frame, text="Bewerken", command=edit_product,
              bg="#FFE5B4", width=12).pack(side=tk.LEFT, padx=5)
    tk.Button(product_buttons_frame, text="Verwijderen", command=delete_product,
              bg="#FFADAD", width=12).pack(side=tk.LEFT, padx=(5, 0))

    # --- RECHTS: Bulk operaties en informatie ---
    right_frame = tk.Frame(main_paned, padx=8, pady=8)
    main_paned.add(right_frame, minsize=300)

    tk.Label(right_frame, text="Bulk Operaties", font=("Arial", 13, "bold")).pack(anchor="w")

    bulk_frame = tk.LabelFrame(right_frame, text="Prijsaanpassingen", padx=10, pady=10)
    bulk_frame.pack(fill=tk.X, pady=(10, 0))

    def bulk_price_adjustment():
        """Bulk prijsaanpassing voor de geselecteerde categorie"""
        category = get_selected_category()
        if not category:
            messagebox.showwarning("Selectie", "Selecteer eerst een categorie!")
            return

        # Dialog voor prijsaanpassing
        adjustment_dialog = tk.Toplevel(win)
        adjustment_dialog.title("Bulk Prijsaanpassing")
        adjustment_dialog.geometry("350x200")
        adjustment_dialog.transient(win)
        adjustment_dialog.grab_set()

        tk.Label(adjustment_dialog, text=f"Prijsaanpassing voor categorie: {category}",
                 font=("Arial", 11, "bold")).pack(pady=10)

        # Options frame
        options_frame = tk.Frame(adjustment_dialog)
        options_frame.pack(pady=10)

        adjustment_type = tk.StringVar(value="percentage")
        tk.Radiobutton(options_frame, text="Percentage", variable=adjustment_type,
                       value="percentage").grid(row=0, column=0, sticky="w")
        tk.Radiobutton(options_frame, text="Vast bedrag", variable=adjustment_type,
                       value="amount").grid(row=1, column=0, sticky="w")

        tk.Label(options_frame, text="Waarde:").grid(row=0, column=1, padx=(20, 5), sticky="w")
        value_var = tk.StringVar()
        tk.Entry(options_frame, textvariable=value_var, width=10).grid(row=0, column=2, sticky="w")

        tk.Label(options_frame, text="(+ voor verhogen, - voor verlagen)").grid(row=2, column=0, columnspan=3, pady=5)

        def apply_adjustment():
            try:
                value = float(value_var.get().replace(',', '.'))
            except ValueError:
                messagebox.showwarning("Fout", "Voer een geldige waarde in!")
                return

            if not messagebox.askyesno("Bevestigen",
                                       f"Alle prijzen in '{category}' aanpassen?\n"
                                       f"Type: {adjustment_type.get()}\n"
                                       f"Waarde: {value}"):
                return

            # Apply adjustment
            count = 0
            for product in menu_data[category]:
                old_price = product.get('prijs', 0)
                if adjustment_type.get() == "percentage":
                    new_price = old_price * (1 + value / 100)
                else:  # amount
                    new_price = old_price + value

                # Round to 2 decimals and ensure non-negative
                new_price = max(0, round(new_price, 2))
                product['prijs'] = new_price
                count += 1

            if save_menu_data(menu_data):
                refresh_products()
                messagebox.showinfo("Succes", f"{count} prijzen aangepast!")
                adjustment_dialog.destroy()

        button_frame = tk.Frame(adjustment_dialog)
        button_frame.pack(pady=20)
        tk.Button(button_frame, text="Toepassen", command=apply_adjustment,
                  bg="#D1FFD1", width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Annuleren", command=adjustment_dialog.destroy,
                  bg="#FFADAD", width=12).pack(side=tk.LEFT, padx=5)

    tk.Button(bulk_frame, text="Prijzen Aanpassen", command=bulk_price_adjustment,
              bg="#FFE5B4", width=20).pack(fill=tk.X, pady=2)

    # Informatie sectie
    info_frame = tk.LabelFrame(right_frame, text="Informatie", padx=10, pady=10)
    info_frame.pack(fill=tk.X, pady=(20, 0))

    info_text = tk.Text(info_frame, height=12, width=30, font=("Arial", 10), wrap=tk.WORD, state=tk.DISABLED)
    info_text.pack(fill=tk.BOTH, expand=True)

    def update_info():
        """Update de informatie panel"""
        category = get_selected_category()

        info_text.config(state=tk.NORMAL)
        info_text.delete(1.0, tk.END)

        if category and category in menu_data:
            products = menu_data[category]
            count = len(products)
            if count > 0:
                prices = [p.get('prijs', 0) for p in products]
                min_price = min(prices)
                max_price = max(prices)
                avg_price = sum(prices) / count

                info_text.insert(tk.END, f"Categorie: {category}\n\n")
                info_text.insert(tk.END, f"Aantal producten: {count}\n\n")
                info_text.insert(tk.END, f"Prijs bereik:\n")
                info_text.insert(tk.END, f"  Min: €{min_price:.2f}\n")
                info_text.insert(tk.END, f"  Max: €{max_price:.2f}\n")
                info_text.insert(tk.END, f"  Gemiddeld: €{avg_price:.2f}\n")
            else:
                info_text.insert(tk.END, f"Categorie: {category}\n\n")
                info_text.insert(tk.END, "Geen producten\n")
        else:
            total_categories = len(menu_data)
            total_products = sum(len(products) for products in menu_data.values())

            info_text.insert(tk.END, f"Totaal overzicht:\n\n")
            info_text.insert(tk.END, f"Categorieën: {total_categories}\n")
            info_text.insert(tk.END, f"Producten: {total_products}\n\n")

            for cat_name, products in menu_data.items():
                info_text.insert(tk.END, f"{cat_name}: {len(products)}\n")

        info_text.config(state=tk.DISABLED)

    # Event handlers
    def on_category_select(event=None):
        refresh_products()
        update_info()

    cat_listbox.bind("<<ListboxSelect>>", on_category_select)

    # Initial load
    refresh_categories()
    update_info()