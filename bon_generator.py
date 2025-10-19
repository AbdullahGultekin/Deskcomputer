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

    # Helpt met uitlijnen van label: waarde
    def format_info_line(label, value_str, label_width=10):
        remaining_width = BON_WIDTH - label_width
        return f"{label:<{label_width}}{str(value_str).rjust(remaining_width)}"

    info_lines = [
        "",
        format_info_line("Type:", "Tel"),
        format_info_line("Bon nr:", bonnummer),
        format_info_line("Datum:", nu.strftime('%d-%m-%Y')),
        format_info_line("Tijd:", nu.strftime('%H:%M')),
        format_info_line("Betaling:", "Cash"),
        format_info_line("Bezorging:", bezorgtijd),
        ""
    ]
    info_str = "\n".join(info_lines)

    # --- 3. ADRES ---
    address_lines = [
        "Leveradres:",
    ]

    # Implementeer een functie voor het wrappen van adreslijnen
    def wrap_address_text(text_to_wrap, indent_len=0):
        wrapped = []
        current_chunk = ""
        words = text_to_wrap.split(' ')
        for word in words:
            # Check if adding the next word (plus a space) exceeds available width
            if current_chunk and len(current_chunk) + len(word) + 1 > (BON_WIDTH - indent_len):
                wrapped.append((" " * indent_len) + current_chunk.strip().ljust(BON_WIDTH - indent_len))
                current_chunk = word + " "
            else:
                current_chunk += word + " "
        if current_chunk.strip():  # Add any remaining content
            wrapped.append((" " * indent_len) + current_chunk.strip().ljust(BON_WIDTH - indent_len))
        return wrapped

    # Voeg de gewrapte adresinformatie toe
    address_lines.extend(wrap_address_text(f"{klant['adres']} {klant['nr']}"))
    address_lines.extend(wrap_address_text(f"{klant['postcode_gemeente']}"))
    address_lines.extend(wrap_address_text(f"{klant['telefoon']}"))
    if klant.get("naam"):
        address_lines.extend(wrap_address_text(klant["naam"]))
    address_str = "\n".join(address_lines)

    # --- 4. QR Adres string (voor QR-generatie) ---
    address_for_qr = f"{klant['adres']} {klant['nr']}, {klant['postcode_gemeente']}, Belgium"

    # --- 5. DETAILS BESTELLING (inclusief extra's en opmerkingen) ---
    details_output_lines = []
    details_output_lines.append("Details bestelling".center(BON_WIDTH))
    details_output_lines.append("-" * BON_WIDTH)

    # Kolombreedtes voor item details:
    ITEM_QTY_COL_WIDTH = 4  # bv. "2x "
    ITEM_PRICE_COL_WIDTH = 8  # bv. "€ 12,50"
    ITEM_NAME_COL_WIDTH_FIRST_LINE = BON_WIDTH - ITEM_QTY_COL_WIDTH - ITEM_PRICE_COL_WIDTH  # 42 - 4 - 8 = 30

    # Inspringing voor gewrapte productregels of extra info
    ITEM_INDENT_WIDTH = 2  # bv. "  "
    ITEM_NAME_COL_WIDTH_SUBSEQUENT_LINES = BON_WIDTH - ITEM_INDENT_WIDTH  # 42 - 2 = 40

    for item in bestelregels:
        aantal = item['aantal']
        product_prijs_per_stuk = Decimal(str(item['prijs']))
        product_totaal_prijs = product_prijs_per_stuk * aantal

        original_product_name = item['product']
        cat_lower = item['categorie'].lower()

        # Bouw display_product_name met afkortingen
        display_product_name = original_product_name

        category_abbreviations_with_name_part = {
            "schotels": "SCH", "grote-broodjes": "GR", "klein-broodjes": "KL",
            "turks-brood": "T", "durum": "D", "kapsalons": "KAP", "pasta's": "PAS",
            "mix schotels": "MIX", "visgerechten": "VIS", "vegetarisch broodjes": "VEG"
        }
        pizza_category_abbreviations = {
            "small pizza's": "S", "medium pizza's": "M", "large pizza's": "L",
        }

        if cat_lower in category_abbreviations_with_name_part:
            prefix = category_abbreviations_with_name_part[cat_lower]
            if original_product_name and '.' in original_product_name and original_product_name.split('.')[
                0].strip().isdigit():
                product_name_part = " ".join(original_product_name.split(".")[1:]).strip()
                display_product_name = f"{prefix} ({product_name_part})"
            else:
                display_product_name = f"{prefix} ({original_product_name})"
        elif cat_lower in pizza_category_abbreviations:
            prefix = pizza_category_abbreviations[cat_lower]
            if original_product_name and '.' in original_product_name:
                nummer_str = original_product_name.split('.')[0].strip()
                if nummer_str.isdigit():
                    display_product_name = f"{prefix} {nummer_str}"
                else:
                    display_product_name = f"{prefix} {original_product_name}"
            else:
                display_product_name = f"{prefix} {original_product_name}"

        # Formatteer de hoofdproductregel (aantal, productnaam, totaalprijs voor product)
        qty_part = f"{aantal}x ".ljust(ITEM_QTY_COL_WIDTH)
        price_part = f"€ {product_totaal_prijs:.2f}".replace('.', ',').rjust(ITEM_PRICE_COL_WIDTH)

        product_name_lines = []
        remaining_name = display_product_name

        while remaining_name:
            current_max_width = ITEM_NAME_COL_WIDTH_FIRST_LINE if not product_name_lines else ITEM_NAME_COL_WIDTH_SUBSEQUENT_LINES

            if len(remaining_name) <= current_max_width:
                product_name_lines.append(remaining_name)
                remaining_name = ""
            else:
                split_point = current_max_width
                temp_chunk = remaining_name[:split_point]
                last_space_idx = temp_chunk.rfind(' ')

                if last_space_idx != -1 and last_space_idx > 0:
                    product_name_lines.append(remaining_name[:last_space_idx])
                    remaining_name = remaining_name[last_space_idx + 1:].strip()
                else:  # Geen spatie gevonden, hard afbreken
                    product_name_lines.append(remaining_name[:split_point])
                    remaining_name = remaining_name[split_point:].strip()

        # Output de geformatteerde regels voor het hoofdproduct
        if product_name_lines:
            # Eerste regel: Aantal + Naam + Prijs
            first_name_part = product_name_lines[0].ljust(ITEM_NAME_COL_WIDTH_FIRST_LINE)
            details_output_lines.append(f"{qty_part}{first_name_part}{price_part}")

            # Volgende regels van de productnaam, ingesprongen
            for i in range(1, len(product_name_lines)):
                indented_name_part = (" " * ITEM_INDENT_WIDTH) + product_name_lines[i].ljust(
                    ITEM_NAME_COL_WIDTH_SUBSEQUENT_LINES)
                details_output_lines.append(indented_name_part)
        else:
            # Fallback als productnaam leeg is
            details_output_lines.append(f"{qty_part}{''.ljust(ITEM_NAME_COL_WIDTH_FIRST_LINE)}{price_part}")

        # LOGICA VOOR HALF-HALF PIZZA'S
        if 'half_half' in item.get('extras', {}) and isinstance(item['extras']['half_half'], list) and len(
                item['extras']['half_half']) == 2:
            pizza1_full = item['extras']['half_half'][0]
            pizza2_full = item['extras']['half_half'][1]

            pizza1_display = pizza1_full.split('.')[0].strip() if '.' in pizza1_full and pizza1_full.split('.')[
                0].strip().isdigit() else pizza1_full
            pizza2_display = pizza2_full.split('.')[0].strip() if '.' in pizza2_full and pizza2_full.split('.')[
                0].strip().isdigit() else pizza2_full

            details_output_lines.append(f"{' ' * ITEM_INDENT_WIDTH}> {pizza1_display}".ljust(BON_WIDTH))
            details_output_lines.append(f"{' ' * ITEM_INDENT_WIDTH}> {pizza2_display}".ljust(BON_WIDTH))

        # LOGICA VOOR EXTRAS WEERGAVE MET '>'
        if item.get('extras'):
            extras = item['extras']
            garnering_prijzen_per_cat = extras_data.get(cat_lower, {}).get('garnering', {}) if extras_data else {}

            def add_extra_display_line(extra_type_label, extra_value, is_garnering=False):
                if isinstance(extra_value, list):
                    for val in extra_value:
                        add_extra_display_line(extra_type_label, val, is_garnering)
                elif extra_value:
                    extra_line_text_base = f"{extra_type_label}: {str(extra_value)}"
                    extra_line_price_str = ""

                    if is_garnering:
                        garnering_basis_prijs = Decimal(str(garnering_prijzen_per_cat.get(str(extra_value), 0)))
                        if garnering_basis_prijs > 0:
                            extra_line_price_str = f"€ {garnering_basis_prijs * aantal:.2f}".replace('.', ',')

                    line_prefix = " " * ITEM_INDENT_WIDTH + "> "
                    effective_max_text_width = BON_WIDTH - len(line_prefix) - len(extra_line_price_str)

                    # Wrap extra_line_text_base
                    current_extra_text_lines = []
                    remaining_extra_text = extra_line_text_base
                    while remaining_extra_text:
                        if len(remaining_extra_text) <= effective_max_text_width:
                            current_extra_text_lines.append(remaining_extra_text)
                            remaining_extra_text = ""
                        else:
                            split_point = effective_max_text_width
                            temp_chunk = remaining_extra_text[:split_point]
                            last_space_idx = temp_chunk.rfind(' ')

                            if last_space_idx != -1 and last_space_idx > 0:
                                current_extra_text_lines.append(remaining_extra_text[:last_space_idx])
                                remaining_extra_text = remaining_extra_text[last_space_idx + 1:].strip()
                            else:  # Geen spatie, hard afbreken
                                current_extra_text_lines.append(remaining_extra_text[:split_point])
                                remaining_extra_text = remaining_extra_text[split_point:].strip()

                    if current_extra_text_lines:
                        # Eerste regel van extra met prijs (indien aanwezig)
                        first_extra_line_text_formatted = current_extra_text_lines[0].ljust(effective_max_text_width)
                        details_output_lines.append(
                            f"{line_prefix}{first_extra_line_text_formatted}{extra_line_price_str}")

                        # Volgende regels van gewrapte extra tekst (ingesprongen)
                        for i in range(1, len(current_extra_text_lines)):
                            indented_extra_line = current_extra_text_lines[i].ljust(BON_WIDTH - len(line_prefix))
                            details_output_lines.append(f"{' ' * len(line_prefix)}{indented_extra_line}")

            # Algemene extra's (vlees, bijgerecht, sauzen, garnering)
            for extra_type_key in ['vlees', 'bijgerecht']:
                if extra_type_key in extras and extras[extra_type_key]:
                    add_extra_display_line(extra_type_key.capitalize(), extras[extra_type_key])

            saus_key = 'sauzen' if 'sauzen' in extras else 'saus'
            if saus_key in extras and extras[saus_key]:
                add_extra_display_line(saus_key.capitalize(), extras[saus_key])

            if 'garnering' in extras and extras['garnering']:
                add_extra_display_line("Garnering", extras['garnering'], is_garnering=True)

        # OPMERKINGEN
        if item.get('opmerking'):
            opm_prefix = " " * ITEM_INDENT_WIDTH + "> Opm: "
            max_opm_content_width = BON_WIDTH - len(opm_prefix)

            opmerking_lines = []
            remaining_opm = item['opmerking']
            while remaining_opm:
                if len(remaining_opm) <= max_opm_content_width:
                    opmerking_lines.append(remaining_opm)
                    remaining_opm = ""
                else:
                    split_point = max_opm_content_width
                    temp_chunk = remaining_opm[:split_point]
                    last_space_idx = temp_chunk.rfind(' ')

                    if last_space_idx != -1 and last_space_idx > 0:
                        opmerking_lines.append(remaining_opm[:last_space_idx])
                        remaining_opm = remaining_opm[last_space_idx + 1:].strip()
                    else:  # Geen spatie, hard afbreken
                        opmerking_lines.append(remaining_opm[:split_point])
                        remaining_opm = remaining_opm[split_point:].strip()

            if opmerking_lines:
                # Eerste regel van opmerking
                details_output_lines.append(f"{opm_prefix}{opmerking_lines[0].ljust(max_opm_content_width)}")
                # Volgende regels van gewrapte opmerking (ingesprongen)
                for i in range(1, len(opmerking_lines)):
                    details_output_lines.append(
                        f"{' ' * len(opm_prefix)}{opmerking_lines[i].ljust(max_opm_content_width)}")

        details_output_lines.append("-" * BON_WIDTH)  # Scheidingsteken na elk item voor betere leesbaarheid

    # Verwijder het laatste scheidingsteken als het aanwezig is en niet nodig
    if details_output_lines and details_output_lines[-1] == "-" * BON_WIDTH:
        details_output_lines.pop()

    details_str = "\n".join(details_output_lines)

    # --- 6. PRIJSTABEL (headers en waardes) ---
    # Controleer of totaal een Decimal is, zo niet, converteer
    if not isinstance(totaal, Decimal):
        totaal = Decimal(str(totaal))

    # Rond af op 2 decimalen na de deling
    basis = (totaal / Decimal('1.06')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    btw = totaal - basis

    # Gebruik f-strings met vaste breedtes voor nette uitlijning
    # Totaal BON_WIDTH = 42 karakters
    total_header = f"{'Tarief':<6}{'Basis':>11}{'BTW':>11}{'Totaal':>14}"
    total_row = f"{'6%':<6}{f'€ {basis:.2f}'.replace('.', ','):>11}{f'€ {btw:.2f}'.replace('.', ','):>11}{f'€ {totaal:.2f}'.replace('.', ','):>14}"

    # --- 7. Te Betalen string ---
    te_betalen_str = "TE BETALEN!".center(BON_WIDTH)

    # --- 8. Totaalbedrag string ---
    totaal_bedrag_label = "Totaal: "  # Inclusief spatie
    totaal_bedrag_value = f"€ {totaal:.2f}".replace('.', ',')
    remaining_width = BON_WIDTH - len(totaal_bedrag_label) - len(totaal_bedrag_value)
    totaal_bedrag_str = f"{totaal_bedrag_label}{' ' * remaining_width}{totaal_bedrag_value}"

    # --- 9. Footer (rest) ---
    footer_lines = [
        "Eet smakelijk! Tot ziens!".center(BON_WIDTH),
        "Di-Zo 17:00-20:30".center(BON_WIDTH)
    ]
    footer_str = "\n".join(footer_lines)

    # De volgorde van de return-waarden moet overeenkomen met wat bon_viewer.py verwacht (10 items)
    return (
        header_str,
        info_str,
        address_str,
        details_str,
        total_header,
        total_row,
        te_betalen_str,
        totaal_bedrag_str,
        footer_str,
        address_for_qr
    )
