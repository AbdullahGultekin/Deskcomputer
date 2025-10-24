import datetime
from decimal import Decimal, ROUND_HALF_UP


def generate_bon_text(klant, bestelregels, bonnummer, menu_data_for_drinks=None, extras_data=None):
    """
    Genereert de volledige bontekst in onderdelen voor GUI-opmaak, geoptimaliseerd voor thermische printer.
    """
    BON_WIDTH = 42  # Aangepast naar 42 karakters voor 80mm bonprinters

    # Bereken de totaalprijs correct aan het begin
    totaal = sum(Decimal(str(item['prijs'])) * item['aantal'] for item in bestelregels)

    # --- 1. HEADER ---
    header_lines = [
        "PITA PIZZA NAPOLI".center(BON_WIDTH),
        f"Brugstraat 12".center(BON_WIDTH),
        f"9120 Vrasene".center(BON_WIDTH),
        "TEL: 03/775 72 28".center(BON_WIDTH),
        "BTW: BE 0479.048.950".center(BON_WIDTH),
        "www.pitapizzanapoli.be".center(BON_WIDTH)
    ]
    header_str = "\n".join(header_lines)

    # --- 2. BESTELINFO ---
    nu = datetime.datetime.now()
    bezorgtijd = (nu + datetime.timedelta(minutes=45)).strftime('%H:%M')

    # Helpt met uitlijnen van label: waarde
    def format_line(label, value_str, separator=':', space_between=1):
        label_part = f"{label}{separator}"
        value_part = str(value_str)

        # Bereken de maximale lengte voor de labelpart, zodat de value part altijd past.
        # Minimaliseer de label_part als de value_part te lang is.
        available_width_for_value = BON_WIDTH - len(label_part) - space_between
        if len(value_part) > available_width_for_value:
            value_part = value_part[:available_width_for_value]  # Truncate value if too long

        # Nu kunnen we de label_part de rest van de ruimte geven, min de value_part en space
        filler_space = BON_WIDTH - len(label_part) - len(value_part)
        return f"{label_part}{' ' * filler_space}{value_part}"

    info_lines = [
        "",
        format_line("Type", "Tel", separator=":", space_between=1),
        format_line("Bon nr", bonnummer),
        format_line("Datum", nu.strftime('%d-%m-%Y')),
        format_line("Tijd", nu.strftime('%H:%M')),
        format_line("Betaling", "Cash"),
        format_line("Bezorging", bezorgtijd),
        ""
    ]
    info_str = "\n".join(info_lines)

    # --- 3. ADRES ---
    address_lines = [
        "Leveradres:".ljust(BON_WIDTH),
    ]

    # Implementeer een functie voor het wrappen van adreslijnen
    def wrap_text_for_bon(text_to_wrap, indent_len=0, total_width=BON_WIDTH):
        wrapped = []
        current_chunk = ""
        words = text_to_wrap.split(' ')

        for word in words:
            # Als we al iets in current_chunk hebben, tel dan de spatie mee.
            # Anders, gewoon de lengte van het woord.
            test_len = len(current_chunk) + len(word) + (1 if current_chunk else 0)

            if test_len > (total_width - indent_len):
                # De huidige chunk is vol, voeg toe en start een nieuwe
                wrapped.append((" " * indent_len) + current_chunk.strip().ljust(total_width - indent_len))
                current_chunk = word + " "
            else:
                current_chunk += word + " "

        if current_chunk.strip():  # Voeg de resterende inhoud toe
            wrapped.append((" " * indent_len) + current_chunk.strip().ljust(total_width - indent_len))
        return wrapped

    # Voeg de gewrapte adresinformatie toe
    address_lines.extend(wrap_text_for_bon(f"{klant['adres']} {klant['nr']}", indent_len=0))
    address_lines.extend(wrap_text_for_bon(f"{klant['postcode_gemeente']}", indent_len=0))
    address_lines.extend(wrap_text_for_bon(f"{klant['telefoon']}", indent_len=0))
    if klant.get("naam"):
        address_lines.extend(wrap_text_for_bon(klant["naam"],
                                               indent_len=0))  # <<-- CORRECTIE: wrap_text_for_for_bon naar wrap_text_for_bon
    address_str = "\n".join(address_lines)

    # --- 4. QR Adres string (voor QR-generatie) ---
    address_for_qr = f"{klant['adres']} {klant['nr']}, {klant['postcode_gemeente']}, Belgium"

    # --- 5. DETAILS BESTELLING (inclusief extra's en opmerkingen) ---
    details_output_lines = []
    details_output_lines.append("Details bestelling".center(BON_WIDTH))
    details_output_lines.append("-" * BON_WIDTH)

    # Kolombreedtes voor item details:
    ITEM_QTY_COL_WIDTH = 4  # bv. "2x "
    ITEM_PRICE_COL_WIDTH = 8  # bv. "€ 12,50" (incl. "€ ")
    ITEM_NAME_COL_WIDTH_FIRST_LINE = BON_WIDTH - ITEM_QTY_COL_WIDTH - ITEM_PRICE_COL_WIDTH  # 42 - 4 - 8 = 30

    # Inspringing voor gewrapte productregels of extra info
    ITEM_INDENT_WIDTH = 2  # bv. "  "
    # Breedte voor opvolgende regels (geen qty/prijs, alleen ingesprongen naam)
    ITEM_NAME_COL_WIDTH_SUBSEQUENT_LINES = BON_WIDTH - ITEM_INDENT_WIDTH

    for item in bestelregels:
        aantal = item['aantal']
        product_prijs_per_stuk = Decimal(str(item['prijs']))
        product_totaal_prijs = product_prijs_per_stuk * aantal

        original_product_name = item['product']
        cat_lower = item['categorie'].lower()

        display_product_name = original_product_name  # Default

        category_abbreviations_with_name_part = {
            "schotels": "SCH", "grote-broodjes": "GR", "klein-broodjes": "KL",
            "turks-brood": "T", "durum": "D", "kapsalons": "KAP", "pasta's": "PAS",
            "mix schotels": "MIX", "visgerechten": "VIS", "vegetarisch broodjes": "VEG",
            "lookbrood": "LB", "sauzen": "SZ", "extra's": "EXT", "dranken": "DR",
            "salades": "SAL", "desserten": "DES"
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
        qty_prefix = f"{aantal}x "
        price_text = f"€ {product_totaal_prijs:.2f}".replace('.', ',')

        # Deel de productnaam op als deze te lang is
        current_product_lines = wrap_text_for_bon(display_product_name, indent_len=0,
                                                  total_width=ITEM_NAME_COL_WIDTH_FIRST_LINE)

        if current_product_lines:
            # Eerste regel: Aantal + Naam + Prijs
            first_product_line = current_product_lines[0].ljust(ITEM_NAME_COL_WIDTH_FIRST_LINE)
            line_to_add = f"{qty_prefix:<{ITEM_QTY_COL_WIDTH}}{first_product_line}{price_text:>{ITEM_PRICE_COL_WIDTH}}"
            details_output_lines.append(line_to_add)

            # Volgende regels van de productnaam, ingesprongen
            for i in range(1, len(current_product_lines)):
                indented_name_part = (" " * ITEM_INDENT_WIDTH) + current_product_lines[i].ljust(
                    ITEM_NAME_COL_WIDTH_SUBSEQUENT_LINES - ITEM_INDENT_WIDTH)
                details_output_lines.append(f"{indented_name_part}")
        else:  # Fallback voor lege productnaam
            details_output_lines.append(
                f"{qty_prefix:<{ITEM_QTY_COL_WIDTH}}{''.ljust(ITEM_NAME_COL_WIDTH_FIRST_LINE)}{price_text:>{ITEM_PRICE_COL_WIDTH}}")

        # LOGICA VOOR HALF-HALF PIZZA'S
        if 'half_half' in item.get('extras', {}) and isinstance(item['extras']['half_half'], list) and len(
                item['extras']['half_half']) == 2:
            pizza1_full = item['extras']['half_half'][0]
            pizza2_full = item['extras']['half_half'][1]

            pizza1_display = pizza1_full.split('.')[0].strip() if '.' in pizza1_full and pizza1_full.split('.')[
                0].strip().isdigit() else pizza1_full
            pizza2_display = pizza2_full.split('.')[0].strip() if '.' in pizza2_full and pizza2_full.split('.')[
                0].strip().isdigit() else pizza2_full

            details_output_lines.append(f"{' ' * ITEM_INDENT_WIDTH}> Pizza 1: {pizza1_display}".ljust(BON_WIDTH))
            details_output_lines.append(f"{' ' * ITEM_INDENT_WIDTH}> Pizza 2: {pizza2_display}".ljust(BON_WIDTH))

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

                    current_extra_text_lines = wrap_text_for_bon(extra_line_text_base, indent_len=0,
                                                                 total_width=effective_max_text_width)

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

            opmerking_lines = wrap_text_for_bon(item['opmerking'], indent_len=0, total_width=max_opm_content_width)

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
    basis_excl_btw = (totaal / Decimal('1.06')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    btw_amount = totaal - basis_excl_btw

    # Nieuwe lay-out voor BTW-specificatie, meer als de Excel bon
    total_section_lines = []
    total_section_lines.append("-" * BON_WIDTH)

    # Tarief  Basis (gebaseerd op het voorbeeld)
    total_section_lines.append(f"{'Tarief':<10}{'Basis':>{BON_WIDTH - 10}}")
    # 6%    €  4,72
    total_section_lines.append(f"{'6%':<10}{f'€ {basis_excl_btw:.2f}'.replace('.', ','):>{BON_WIDTH - 10}}")
    # BTW   €  0,28
    total_section_lines.append(f"{'BTW':<10}{f'€ {btw_amount:.2f}'.replace('.', ','):>{BON_WIDTH - 10}}")
    total_section_lines.append("-" * BON_WIDTH)

    total_header = ""  # De headers worden nu in de total_section_lines opgenomen
    total_row = ""  # De totalen worden nu in de total_section_lines opgenomen

    details_str += "\n" + "\n".join(total_section_lines)  # Voeg de totalen toe aan details_str

    # --- 7. Te Betalen string ---
    te_betalen_str = "TE BETALEN!".center(BON_WIDTH)

    # --- 8. Totaalbedrag string ---
    # Deze moet nu alleen de "Totaal: € 5,00" zijn, gescheiden van de BTW-details
    totaal_bedrag_label = "Totaal: "
    totaal_bedrag_value = f"€ {totaal:.2f}".replace('.', ',')
    # Bereken opvulling voor correcte uitlijning (label links, waarde rechts)
    padding = BON_WIDTH - len(totaal_bedrag_label) - len(totaal_bedrag_value)
    totaal_bedrag_str = f"{totaal_bedrag_label}{' ' * padding}{totaal_bedrag_value}"

    # --- 9. Footer (rest) ---
    footer_lines = [
        "",  # Lege regel voor wat ruimte
        "Eet smakelijk! Tot ziens!".center(BON_WIDTH),
        "Di-Zo 17:00-20:30".center(BON_WIDTH),
        ""  # Lege regel voor wat ruimte onderaan
    ]
    footer_str = "\n".join(footer_lines)

    # De volgorde van de return-waarden moet overeenkomen met wat bon_viewer.py verwacht (11 items nu)
    return (
        header_str,
        info_str,
        address_str,
        details_str,
        total_header,  # Leeg
        total_row,  # Leeg
        te_betalen_str,
        totaal_bedrag_str,
        footer_str,
        address_for_qr,
        BON_WIDTH
    )
