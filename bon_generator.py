import datetime
import json
import urllib.parse
from decimal import Decimal, ROUND_HALF_UP


def generate_bon_text(klant, bestelregels, bonnummer, menu_data_for_drinks=None, extras_data=None):
    """
    Genereert de volledige bontekst in onderdelen voor GUI-opmaak, geoptimaliseerd voor thermische printer.
    """
    BON_WIDTH = 42  # Aangepast naar 42 karakters voor 80mm printer

    # Bereken de totaalprijs correct aan het begin
    totaal = sum(Decimal(str(item['prijs'])) * item['aantal'] for item in bestelregels)

    # --- Header ---
    # Condenseer de header om minder regels in te nemen
    header_content = [
        "PITA PIZZA NAPOLI",
        "Brugstraat 12 - 9120 Vrasene",
        "TEL: 03/775 72 28",
        "BTW: BE 0479.048.950",
        "",  # Extra witregel
        "www.pitapizzanapoli.be"
    ]
    header_lines = [line.center(BON_WIDTH) for line in header_content]

    # --- Bestelinfo (rechts uitgelijnd) ---
    nu = datetime.datetime.now()
    bezorgtijd = (nu + datetime.timedelta(minutes=45)).strftime('%H:%M')
    # Verkort labels
    info_content = {
        "Type:": "Tel",
        "Bon nr:": bonnummer,
        "Datum:": nu.strftime('%d-%m-%Y'),
        "Tijd:": nu.strftime('%H:%M'),
        "Betaling:": "Cash",
        "Bezorging:": bezorgtijd
    }
    info_lines = [""]
    for label, value in info_content.items():
        info_lines.append(f"{label:<15}{str(value):>{BON_WIDTH - 15}}")
    info_lines.append("")

    # --- Adres & QR Code prep ---
    postcode_gemeente = klant["postcode_gemeente"].split()
    postcode = postcode_gemeente[0] if len(postcode_gemeente) > 0 else ""
    gemeente = ' '.join(postcode_gemeente[1:]) if len(postcode_gemeente) > 1 else ""
    address_lines = [
        "Leveradres:",
        f"{klant['adres']} {klant['nr']}",
        f"{postcode} {gemeente}",
        f"{klant['telefoon']}"
    ]
    full_address_for_qr = f"{klant['adres']} {klant['nr']}, {postcode} {gemeente}, Belgium"

    # --- Details Bestelling ---
    details_lines = ["Details bestelling".center(BON_WIDTH), ("-" * BON_WIDTH)]

    for item in bestelregels:
        aantal = item['aantal']
        # base_price wordt nu niet direct op de bonregel getoond, alleen de totale prijs van het product
        product_totaal_prijs = Decimal(str(item['prijs'])) * aantal

        display_product_name = item['product']
        cat_lower = item['categorie'].lower()

        # Vereenvoudig pizzanamen naar alleen het nummer
        if 'pizza' in cat_lower and display_product_name and '.' in display_product_name:
            try:
                # Extra check om te zorgen dat het nummer echt een nummer is en geen deel van de naam
                nummer_str = display_product_name.split('.')[0].strip()
                if nummer_str.isdigit():
                    display_product_name = nummer_str
                else:
                    display_product_name = " ".join(display_product_name.split(".")[1:]).strip()
            except:
                pass  # Blijf bij originele naam als parsen mislukt

        # Vereenvoudig weergave van schotels, broodjes, durums, turks-brood
        elif cat_lower in ["schotels", "grote-broodjes", "klein-broodjes", "turks-brood", "durum", "kapsalons",
                           "pasta's"]:
            # Indien productnaam een nummer-prefix heeft, verwijder die (bv. "1. Margherita")
            if display_product_name and '.' in display_product_name:
                try:
                    # Extra check om te zorgen dat het nummer echt een nummer is en geen deel van de naam
                    nummer_str = display_product_name.split('.')[0].strip()
                    if nummer_str.isdigit():
                        display_product_name = " ".join(display_product_name.split(".")[1:]).strip()
                    else:
                        pass  # Blijf bij originele naam
                except:
                    pass  # Blijf bij originele naam

        # Hoofdlijn product: Aantal x Naam Product (Prijs)
        main_line_text = f"{aantal}x {display_product_name}"
        main_line_price = f"€ {product_totaal_prijs:.2f}"
        # Aangepaste padding voor smallere bon
        details_lines.append(f"{main_line_text:<{BON_WIDTH - 9}}{main_line_price:>{8}}")

        # Extras onder product, elke extra op nieuwe regel met '>' prefix
        if item.get('extras'):
            extras = item['extras']
            garnering_prices = extras_data.get(cat_lower, {}).get('garnering', {}) if extras_data else {}

            # Functie om extra's netjes uit te lijnen onder elkaar
            def add_extra_display_line(extra_label, extra_value, is_garnering=False):
                if isinstance(extra_value, list):
                    for val in extra_value:
                        add_extra_display_line(extra_label, val, is_garnering)
                elif extra_value:
                    display_text = f"> {extra_value}"
                    extra_price_str = ""
                    if is_garnering:
                        price = Decimal(str(garnering_prices.get(extra_value, 0)))
                        if price > 0:
                            extra_price_str = f"€ {price * aantal:.2f}"  # Prijs per eenheid * aantal van product

                    # Zorg dat de display_text niet langer is dan BON_WIDTH-2 om ruimte voor '>' te houden
                    if len(display_text) > BON_WIDTH - 2 - len(extra_price_str.strip()):
                        display_text = display_text[:BON_WIDTH - 2 - len(
                            extra_price_str.strip()) - 3] + "..."  # afkorten indien te lang

                    details_lines.append(
                        f"{display_text:<{BON_WIDTH - len(extra_price_str)}}{extra_price_str:>{len(extra_price_str)}}")

            # HALF-HALF PIZZA's
            if 'half_half' in extras and isinstance(extras['half_half'], list) and len(extras['half_half']) == 2:
                # Voor half-half pizza, toon de nummers (of namen als geen nummer)
                pizza1 = extras['half_half'][0]
                pizza2 = extras['half_half'][1]
                # Als het nummers zijn (bv. "1"), toon dan alleen het nummer
                if pizza1.split('.')[0].strip().isdigit(): pizza1 = pizza1.split('.')[0].strip()
                if pizza2.split('.')[0].strip().isdigit(): pizza2 = pizza2.split('.')[0].strip()

                details_lines.append(f"> Half: {pizza1} & {pizza2}")

            # VLEES
            if 'vlees' in extras and extras['vlees']:
                add_extra_display_line("Vlees", extras['vlees'])

            # BIJGERECHT
            if 'bijgerecht' in extras and extras['bijgerecht']:
                add_extra_display_line("Bijgerecht", extras['bijgerecht'])

            # SAUZEN (check voor 'saus' en 'sauzen')
            saus_key = 'sauzen' if 'sauzen' in extras else 'saus'
            if saus_key in extras and extras[saus_key]:
                add_extra_display_line("Saus", extras[saus_key])

            # GARNERING
            if 'garnering' in extras and extras['garnering']:
                add_extra_display_line("Garnering", extras['garnering'], is_garnering=True)

        # OPMERKING
        if item.get('opmerking'):
            opm = item['opmerking']
            # Als opmerking te lang is, snijd af met '...'
            if len(opm) > BON_WIDTH - 5:  # -5 om ruimte te laten voor "> Opm: "
                opm = opm[:BON_WIDTH - 8] + "..."
            details_lines.append(f"> Opm: {opm}")

    details_lines.append("-" * BON_WIDTH)

    # --- Totaal ---
    basis = (totaal / Decimal('1.06')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    btw = totaal - basis
    total_lines = [
        "",
        "Tarief\tBasis\tBTW\tTotaal",
        f"6%\t€ {basis:.2f}\t€ {btw:.2f}\t€ {totaal:.2f}",
        ""
    ]

    # --- Te Betalen ---
    te_betalen_str = "TE BETALEN!"

    # --- Footer ---
    footer_text = f"Totaal: € {totaal:.2f}"
    footer_lines = [
        footer_text.rjust(BON_WIDTH),
        "Eet smakelijk! Tot ziens!".center(BON_WIDTH),
        "Di-Zo 17:00-20:30".center(BON_WIDTH)
    ]

    return (
        "\n".join(header_lines),
        "\n".join(info_lines),
        "\n".join(address_lines),
        "\n".join(details_lines),
        total_lines[1],  # kolomkop (header)
        total_lines[2],  # kolomwaarden (row)
        te_betalen_str,  # te_betalen_str
        footer_lines[0],  # alleen "Totaal: ..." (voor vetgedrukt)
        "\n".join(footer_lines[1:]),  # overig footer
        full_address_for_qr  # qr string
    )