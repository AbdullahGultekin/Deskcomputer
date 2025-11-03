import datetime
from decimal import Decimal, ROUND_HALF_UP
import json


def get_pizza_num(naam):
    """
    Haal cijfer voor de eerste punt uit de pizzanaam, bijvoorbeeld:
    "12. Margherita" -> "12"
    """
    if '.' in naam:
        return naam.split('.')[0].strip()
    return naam.strip()





def generate_bon_text(klant, bestelregels, bonnummer, menu_data_for_drinks=None, extras_data=None):
    """
    Genereert bontekst exact zoals de gewenste layout.
    """
    BON_WIDTH = 42

    totaal = sum(Decimal(str(item['prijs'])) * item['aantal'] for item in bestelregels)

    # ============ 1. HEADER ============
    header_lines = [
        "",
        "PITA PIZZA NAPOLI",  # Groot geprint in print functie
        "",
        f"Brugstraat 12 - 9120 Vrasene".center(BON_WIDTH),
        f"TEL: 03 / 775 72 28".center(BON_WIDTH),
        f"FAX: 03 / 755 52 22".center(BON_WIDTH),
        f"BTW: BE 0479.048.950".center(BON_WIDTH),
        "",
        f"Bestel online".center(BON_WIDTH),
        f"www.pitapizzanapoli.be".center(BON_WIDTH),
        f"info@pitapizzanapoli.be".center(BON_WIDTH),
        ""
    ]
    header_str = "\n".join(header_lines)

    # ============ 2. BESTELINFO ============
    nu = datetime.datetime.now()
    bezorgtijd = (nu + datetime.timedelta(minutes=45)).strftime('%H:%M')

    def format_line(label, value_str):
        label_part = f"{label}:"
        value_part = str(value_str)
        filler_space = BON_WIDTH - len(label_part) - len(value_part)
        return f"{label_part}{' ' * filler_space}{value_part}"

    info_lines = [
        format_line("Soort bestelling", "Online"),
        format_line("Bonnummer", bonnummer),
        format_line("Datum", nu.strftime('%d-%m-%Y')),
        format_line("Tijd", nu.strftime('%H:%M')),
        format_line("Betaalmethode", "Cash"),
        "",
        format_line("Bezorgtijd", bezorgtijd),
        ""
    ]
    info_str = "\n".join(info_lines)

    # ============ 3. ADRES (compact, zonder QR hier) ============
    def wrap_text(text, max_width=BON_WIDTH):
        words = text.split(' ')
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if len(test) <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    address_lines = ["Leveringsadres:"]
    address_lines.extend(wrap_text(f"{klant['adres']} {klant['nr']}"))
    address_lines.extend(wrap_text(f"{klant['postcode_gemeente']}"))

    # Telefoon + 1 lege regel erna
    address_lines.extend(wrap_text(str(klant.get('telefoon', ''))))
    address_lines.append("")

    # Aanhef + klantnaam (indien bekend)
    address_lines.append("Dhr. / Mvr.")
    klant_naam = (klant.get("naam") or "").strip()
    if klant_naam:
        address_lines.extend(wrap_text(klant_naam))


    address_lines.append("")  # scheiding naar details



    address_str = "\n".join(address_lines)
    address_for_qr = f"{klant['adres']} {klant['nr']}, {klant['postcode_gemeente']}, Belgium"

    # ============ 4. DETAILS BESTELLING ============
    details_lines = ["Details bestelling"]

    # Groepeer/sorteer regels in gewenste volgorde
    def group_key(item):
        cat = (item.get('categorie') or '').lower()
        if "pizza" in cat:
            return (0, cat)
        if "schotel" in cat:
            return (1, cat)
        if any(x in cat for x in ("brood", "durum", "turks", "kapsalon")):
            return (2, cat)
        if "pasta" in cat or "alforno" in cat:
            return (3, cat)
        return (4, cat)

    bestelregels_sorted = sorted(bestelregels, key=group_key)

    # NIEUW: Groepeer dezelfde producten (zelfs als apart gekozen) samen
    merged_rules = {}
    for item in bestelregels_sorted:
        # Maak een unieke sleutel voor elk product met dezelfde extras
        extras_key = json.dumps(item.get('extras', {}), sort_keys=True)
        product_key = (item['categorie'], item['product'], extras_key, item.get('opmerking', ''))

        if product_key not in merged_rules:
            merged_rules[product_key] = {
                'categorie': item['categorie'],
                'product': item['product'],
                'aantal': 0,
                'prijs': item['prijs'],
                'extras': item.get('extras', {}),
                'opmerking': item.get('opmerking', '')
            }

        # Tel het aantal bij elkaar op
        merged_rules[product_key]['aantal'] += item['aantal']

    # Converteer terug naar lijst met behoud van volgorde
    bestelregels_merged = list(merged_rules.values())

    for item in bestelregels_sorted:
        name_max = BON_WIDTH - 4 - 12
        aantal = item['aantal']
        prijs_per_stuk = Decimal(str(item['prijs']))
        totaal_prijs = prijs_per_stuk * aantal

        product_naam = item['product']
        cat = (item['categorie'] or '').lower()
        prefix = ""

        if "small" in cat: prefix = "Small"
        if "medium" in cat: prefix = "Medium"
        if "large" in cat: prefix = "Large"
        if "grote-broodjes" in cat: prefix = "Groot"
        if "klein-broodjes" in cat: prefix = "Klein"
        if "turks-brood" in cat: prefix = "Turks"
        if "durum" in cat: prefix = "Durum"
        if "pasta" in cat: prefix = "Pasta"
        if "schotel" in cat and "mix schotel" not in cat: prefix = "Schotel"
        if "vegetarisch broodjes" in cat: prefix = "Broodje"

        is_mixschotel = "mix schotel" in cat or "mix-schotel" in cat or "mixschotel" in cat
        extras = item.get('extras', {})
        half_half = extras.get('half_half')
        display_name = ""

        if any(x in cat for x in ("small pizza", "medium pizza", "large pizza", "pizza")):
            if "small" in cat:
                formaat = "Small"
            elif "medium" in cat:
                formaat = "Medium"
            elif "large" in cat:
                formaat = "Large"
            else:
                formaat = "Pizza"

            if half_half and isinstance(half_half, list) and len(half_half) == 2 and menu_data_for_drinks:
                gekozen_cat = [k for k in (menu_data_for_drinks or {}).keys()
                               if k.lower() == (item['categorie'] or "").lower()]
                all_pizzas = (menu_data_for_drinks or {}).get(gekozen_cat[0], []) if gekozen_cat else []
                nummers = []
                for pizza_naam in half_half:
                    nummer = ""
                    for p in all_pizzas:
                        menu_nummer = get_pizza_num(p['naam'])
                        if menu_nummer == str(pizza_naam).strip():
                            nummer = menu_nummer
                            break
                    nummers.append(nummer if nummer else '?')
                display_name = f"{formaat} {nummers[0]}/{nummers[1]}"
            else:
                nummer = get_pizza_num(product_naam)
                display_name = f"{formaat} {nummer}"
        else:
            if is_mixschotel:
                display_name = product_naam.strip()
            elif any(x in cat for x in ('schotel', 'grote-broodjes', 'klein-broodjes',
                                        'durum', 'turks-brood', 'vegetarisch broodjes', 'kapsalon')):
                display_name = f"{prefix} {product_naam}".strip()
            else:
                display_name = product_naam.strip()

        if not display_name:
            display_name = product_naam.strip()

        if len(display_name) > name_max:
            display_name = display_name[:name_max - 3] + "..."

        qty = f"{aantal}x"
        price = f"€ {totaal_prijs:.2f}".replace('.', ',') + " C"
        price = price.replace('\u20ac', '€').replace('\xe2\x82\xac', '€').replace('?', '€', 1)

        line = f"{qty:3s} {display_name:<{name_max}s}{price:>12s}"
        line = line.replace('\u20ac', '€').replace('\xe2\x82\xac', '€').replace('?', '€', 1)
        details_lines.append(line)

        # Extra's in bullets
        if item.get('extras'):
            extras = item['extras']
            flat_extras = []
            for key in ['vlees', 'bijgerecht', 'saus', 'sauzen', 'garnering']:
                if key in extras and extras[key]:
                    val = extras[key]
                    if isinstance(val, list):
                        flat_extras.extend(val)
                    else:
                        flat_extras.append(val)
            for extra in flat_extras:
                details_lines.append(f"> {extra}")
            if 'pasta_extras' in extras:
                for extra in extras['pasta_extras']:
                    details_lines.append(f"> {extra.upper()}")

        if item.get('opmerking'):
            details_lines.append(f"> {item['opmerking']}")

    details_lines.append('-' * BON_WIDTH)
    details_lines.append(f"Totaal{'':<{BON_WIDTH - 18}}€ {totaal:.2f}".replace('.', ',').replace('?', '€'))
    details_str = "\n".join(details_lines)

    # ============ 5. TARIEF TABEL (als kolommen) ============
    if not isinstance(totaal, Decimal):
        totaal = Decimal(str(totaal))

    basis = (totaal / Decimal('1.06')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    btw = totaal - basis

    # Maak een tabel met kolommen: Tarief | Basis | BTW | Totaal
    tarief_lines = [
        "",
        "-" * BON_WIDTH,
        f"{'':1s}{'Tarief':<10s}{'Basis':>10s}{'BTW':>10s}{'Totaal':>10s}",
        f"{'C':1s}{'6%':<10s}{f'€ {basis:.2f}'.replace('.', ','):>10s}{f'€ {btw:.2f}'.replace('.', ','):>10s}{f'€ {totaal:.2f}'.replace('.', ','):>10s}",
        f"{'':1s}{'':10s}{f'€ {basis:.2f}'.replace('.', ','):>10s}{f'€ {btw:.2f}'.replace('.', ','):>10s}{f'€ {totaal:.2f}'.replace('.', ','):>10s}",
        ""
    ]

    tarief_str = "\n".join(tarief_lines)

    # ============ 6. TOTAAL (vet en groot) ============
    totaal_label = "Totaal"  # Wordt groot/vet in print functie
    totaal_waarde = f"€ {totaal:.2f}".replace('.', ',')

    # ============ 7. TE BETALEN ============
    betaald_str = "TE BETALEN!"  # Wordt vet in print functie

    # Extra lege regel vóór de footer
    footer_prefix_blank = "\n"

    # ============ 8. FOOTER ============
    footer_lines = [
        footer_prefix_blank,
        "Eet smakelijk!".center(BON_WIDTH),
        "Dank u en tot weerziens!".center(BON_WIDTH),
        "Dins- tot Zon 17.00-20.30".center(BON_WIDTH),
        ""
    ]
    footer_str = "\n".join(footer_lines)

    return (
        header_str,
        info_str,
        address_str,
        details_str,
        tarief_str,
        totaal_label,
        totaal_waarde,
        betaald_str,
        footer_str,
        address_for_qr,
        BON_WIDTH
    )
