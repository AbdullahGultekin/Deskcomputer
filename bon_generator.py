import datetime
from decimal import Decimal, ROUND_HALF_UP


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
    address_lines.extend(wrap_text(klant['telefoon']))
    address_lines.append("")  # Lege regel voor Dhr./Mvr.

    # Dhr./Mvr. en naam
    if klant.get("naam"):
        address_lines.append("Dhr. / Mvr.")
        address_lines.extend(wrap_text(klant["naam"]))

    address_lines.append("")  # Lege regel voor details

    address_str = "\n".join(address_lines)
    address_for_qr = f"{klant['adres']} {klant['nr']}, {klant['postcode_gemeente']}, Belgium"

    # ============ 4. DETAILS BESTELLING ============
    details_lines = ["Details bestelling"]
    for item in bestelregels:
        aantal = item['aantal']
        prijs_per_stuk = Decimal(str(item['prijs']))
        totaal_prijs = prijs_per_stuk * aantal

        product_naam = item['product']
        cat = item['categorie'].lower()
        prefix = ""

        if "small" in cat:
            prefix = "Small"
        if "medium" in cat:
            prefix = "Medium"
        if "large" in cat:
            prefix = "Large"
        if "grote-broodjes" in cat:
            prefix = "Groot Brood"
        if "klein-broodjes" in cat:
            prefix = "Klein Brood"
        if "turks-brood" in cat:
            prefix = "Turks Brood"
        if "durum" in cat:
            prefix = "Durum"
        if "pasta" in cat:
            prefix = "Pasta"
        if "schotel" in cat and "mix schotel" not in cat:
            prefix = "Schotel"
        if "kapsalon" in cat:
            prefix = "Kapsalon"

        # Bepaal of het een mix schotel is
        is_mixschotel = "mix schotel" in cat or "mix-schotel" in cat or "mixschotel" in cat

        # ENKEL hier display_name toewijzen:
        if is_mixschotel:
            display_name = product_naam.strip()
        elif any(x in cat for x in (
                'schotel', 'grote-broodjes', 'klein-broodjes',
                'durum', 'turks-brood', 'pizza'
        )):
            display_name = f"{prefix} {product_naam}".strip()
        else:
            display_name = product_naam.strip()

        qty = f"{aantal}x"
        price = f"€ {totaal_prijs:.2f}".replace('.', ',') + " C"
        # Fix alle euro-gerelateerde tekens of vraagtekens in de prijs
        price = price.replace('\u20ac', '€').replace('\xe2\x82\xac', '€').replace('?', '€', 1)

        name_max = BON_WIDTH - 4 - 12
        if len(display_name) > name_max:
            display_name = display_name[:name_max - 3] + "..."

        line = f"{qty:3s} {display_name:<{name_max}s}{price:>12s}"
        # Forceer ook hier in elk geval echte euro (voor de zekerheid)
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

        # Opmerking
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

    # ============ 8. FOOTER ============
    footer_lines = [
        "",
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
