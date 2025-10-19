import datetime
from decimal import Decimal, ROUND_HALF_UP


def generate_bon_text(klant, bestelregels, bonnummer, menu_data_for_drinks=None, extras_data=None):
    """
    Genereert de volledige bontekst in onderdelen voor GUI-opmaak, geoptimaliseerd voor thermische printer.
    """
    BON_WIDTH = 42  # Aangepast naar 42 karakters voor 80mm printer

    # Bereken de totaalprijs correct aan het begin
    totaal = sum(Decimal(str(item['prijs'])) * item['aantal'] for item in bestelregels)

    # --- 1. HEADER ---
    header_lines = [
        "PITA PIZZA NAPOLI".center(BON_WIDTH),
        "Brugstraat 12 - 9120 Vrasene".center(BON_WIDTH),
        "TEL: 03/775 72 28".center(BON_WIDTH),
        "BTW: BE 0479.048.950".center(BON_WIDTH),
        "www.pitapizzanapoli.be".center(BON_WIDTH)
    ]
    header_str = "\n".join(header_lines)

    # --- 2. BESTELINFO ---
    nu = datetime.datetime.now()
    bezorgtijd = (nu + datetime.timedelta(minutes=45)).strftime('%H:%M')
    info_lines = [
        "",
        f"{'Type:':<15}{'Tel':>{BON_WIDTH - 15}}",
        f"{'Bon nr:':<15}{bonnummer:>{BON_WIDTH - 15}}",
        f"{'Datum:':<15}{nu.strftime('%d-%m-%Y'):>{BON_WIDTH - 15}}",
        f"{'Tijd:':<15}{nu.strftime('%H:%M'):>{BON_WIDTH - 15}}",
        f"{'Betaling:':<15}{'Cash':>{BON_WIDTH - 15}}",
        f"{'Bezorging:':<15}{bezorgtijd:>{BON_WIDTH - 15}}",
        ""
    ]
    info_str = "\n".join(info_lines)

    # --- 3. ADRES ---
    address_lines = [
        "Leveradres:",
        f"{klant['adres']} {klant['nr']}",
        f"{klant['postcode_gemeente']}",
        f"{klant['telefoon']}"
    ]
    if klant.get("naam"):
        address_lines.append(klant["naam"])  # Klantnaam toevoegen als deze bestaat
    address_str = "\n".join(address_lines)

    # --- 4. QR Adres string (voor QR-generatie) ---
    address_for_qr = f"{klant['adres']} {klant['nr']}, {klant['postcode_gemeente']}, Belgium"

    # --- 5. DETAILS BESTELLING (inclusief extra's en opmerkingen) ---
    details_output_lines = []  # Lijst om alle details-regels te verzamelen
    details_output_lines.append("Details bestelling".center(BON_WIDTH))
    details_output_lines.append("-" * BON_WIDTH)

    for item in bestelregels:
        aantal = item['aantal']
        product_prijs_per_stuk = Decimal(str(item['prijs']))
        product_totaal_prijs = product_prijs_per_stuk * aantal

        original_product_name = item['product']
        current_display_name = original_product_name  # Start met de originele naam, pas aan indien nodig

        cat_lower = item['categorie'].lower()

        # Afkortingen voor categorieën die het "ABBR (Naam)" formaat gebruiken
        category_abbreviations_with_name_part = {
            "schotels": "SCH",
            "grote-broodjes": "GR",
            "klein-broodjes": "KL",
            "turks-brood": "T",
            "durum": "D",
            "kapsalons": "KAP",  # Toegevoegd voor consistentie met eerdere codeblokken
            "pasta's": "PAS",  # Toegevoegd voor consistentie met eerdere codeblokken
        }

        # Afkortingen voor pizza categorieën die het "ABBR Nummer" formaat gebruiken
        pizza_category_abbreviations = {
            "small pizza's": "S",
            "medium pizza's": "M",
            "large pizza's": "L",
        }

        # Pas formaat toe voor categorieën die moeten worden weergegeven als "ABBR (Product Naam Deel)"
        if cat_lower in category_abbreviations_with_name_part:
            prefix = category_abbreviations_with_name_part[cat_lower]
            if original_product_name and '.' in original_product_name and original_product_name.split('.')[
                0].strip().isdigit():
                # Haal het naamgedeelte na het nummer op (bijv. "101. Natuur" -> "Natuur")
                product_name_part = " ".join(original_product_name.split(".")[1:]).strip()
                current_display_name = f"{prefix} ({product_name_part})"
            else:
                # Als niet genummerd, gebruik de originele productnaam met prefix (bijv. "SCH (Natuur)")
                current_display_name = f"{prefix} ({original_product_name})"

        # Pas formaat toe voor pizza categorieën die moeten worden weergegeven als "ABBR ProductNummer"
        elif cat_lower in pizza_category_abbreviations:
            prefix = pizza_category_abbreviations[cat_lower]
            if original_product_name and '.' in original_product_name:
                nummer_str = original_product_name.split('.')[0].strip()
                if nummer_str.isdigit():
                    current_display_name = f"{prefix} {nummer_str}"
                else:
                    # Terugval als pizzanaam geen nummer heeft maar wel in een pizzacategorie zit
                    current_display_name = f"{prefix} {original_product_name}"  # Bijv. "S Margherita"
            else:
                # Terugval als pizzanaam geen nummer of punt heeft
                current_display_name = f"{prefix} {original_product_name}"  # Bijv. "S Margherita"

        # Voor alle andere categorieën blijft current_display_name de original_product_name.
        display_product_name = current_display_name

        # Hoofdregel van het product op de bon
        main_line_text = f"{aantal}x {display_product_name}"
        main_line_price = f"€ {product_totaal_prijs:.2f}"
        details_output_lines.append(f"{main_line_text:<{BON_WIDTH - 9}}{main_line_price:>{8}}")

        # LOGICA VOOR HALF-HALF PIZZA'S (specifiek hier behandeld voor de bon weergave)
        if 'half_half' in item.get('extras', {}) and isinstance(item['extras']['half_half'], list) and len(
                item['extras']['half_half']) == 2:
            pizza1_full = item['extras']['half_half'][0]
            pizza2_full = item['extras']['half_half'][1]

            # Haal de nummers op voor weergave van Half-Half (bijv. "6. Salame" -> "6")
            pizza1_display = pizza1_full.split('.')[0].strip() if '.' in pizza1_full and pizza1_full.split('.')[
                0].strip().isdigit() else pizza1_full
            pizza2_display = pizza2_full.split('.')[0].strip() if '.' in pizza2_full and pizza2_full.split('.')[
                0].strip().isdigit() else pizza2_full

            details_output_lines.append(f"> {pizza1_display}")
            details_output_lines.append(f"> {pizza2_display}")

        # LOGICA VOOR EXTRAS WEERGAVE MET '>' (deze sectie begint hier)
        if item.get('extras'):
            extras = item['extras']
            garnering_prijzen_per_cat = extras_data.get(cat_lower, {}).get('garnering', {}) if extras_data else {}

            def add_extra_display_line(extra_value, is_garnering=False):
                if isinstance(extra_value, list):
                    for val in extra_value:
                        add_extra_display_line(val, is_garnering)
                elif extra_value:
                    line_prefix = "> "
                    extra_line_text = str(extra_value)  # Zorg dat het een string is
                    extra_line_price_str = ""

                    if is_garnering:
                        garnering_basis_prijs = Decimal(str(garnering_prijzen_per_cat.get(extra_line_text, 0)))
                        if garnering_basis_prijs > 0:
                            extra_line_price_str = f"€ {garnering_basis_prijs * aantal:.2f}"

                    max_text_width = BON_WIDTH - len(line_prefix) - len(extra_line_price_str) - 1
                    if len(extra_line_text) > max_text_width:
                        extra_line_text = extra_line_text[:max_text_width - 3] + "..."

                    full_line_output = f"{line_prefix}{extra_line_text}"
                    details_output_lines.append(
                        f"{full_line_output:<{BON_WIDTH - len(extra_line_price_str)}}{extra_line_price_str:>{len(extra_line_price_str)}}")

            # Algemene extra's (vlees, bijgerecht, sauzen, garnering)
            for extra_type in ['vlees', 'bijgerecht']:
                if extra_type in extras and extras[extra_type]:
                    add_extra_display_line(extras[extra_type])

            saus_key = 'sauzen' if 'sauzen' in extras else 'saus'
            if saus_key in extras and extras[saus_key]:
                add_extra_display_line(extras[saus_key])

            if 'garnering' in extras and extras['garnering']:
                add_extra_display_line(extras['garnering'], is_garnering=True)

        # OPMERKINGEN
        if item.get('opmerking'):
            opm = item['opmerking']
            opm_prefix = "> Opm: "
            max_opm_width = BON_WIDTH - len(opm_prefix)
            if len(opm) > max_opm_width:
                opm = opm[:max_opm_width - 3] + "..."
            details_output_lines.append(f"{opm_prefix}{opm}")

    details_str = "\n".join(details_output_lines)  # Bouw de details_str hier

    # --- 6. PRIJSTABEL (headers en waardes) ---
    basis = (totaal / Decimal('1.06')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    btw = totaal - basis

    # Gebruik f-strings met vaste breedtes voor nette uitlijning
    # Totaal BON_WIDTH = 42 karakters
    # Kolombreedtes: Tarief (6), Basis (11), BTW (11), Totaal (14) = 42
    total_header = f"{'Tarief':<6}{'Basis':>11}{'BTW':>11}{'Totaal':>14}"
    total_row = f"{'6%':<6}{f'€ {basis:.2f}':>11}{f'€ {btw:.2f}':>11}{f'€ {totaal:.2f}':>14}"

    # --- 7. Te Betalen string ---
    te_betalen_str = "TE BETALEN!"

    # --- 8. Totaalbedrag string ---
    totaal_bedrag_str = f"Totaal: € {totaal:.2f}"

    # --- 9. Footer (rest) ---
    footer_lines = [
        "Eet smakelijk! Tot ziens!".center(BON_WIDTH),
        "Di-Zo 17:00-20:30".center(BON_WIDTH)
    ]
    footer_str = "\n".join(footer_lines)

    # De volgorde van de return-waarden moet overeenkomen met wat main.py verwacht (10 items)
    return (
        header_str,  # 1
        info_str,  # 2
        address_str,  # 3
        details_str,  # 4 (Samengevoegde string van alle details)
        total_header,  # 5
        total_row,  # 6
        te_betalen_str,  # 7
        totaal_bedrag_str,  # 8
        footer_str,  # 9
        address_for_qr  # 10 (qr string voor QR-generatie)
    )