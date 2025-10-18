import datetime
import json
import urllib.parse
from decimal import Decimal, ROUND_HALF_UP


def generate_bon_text(klant, bestelregels, bonnummer, menu_data_for_drinks=None, extras_data=None):
    """
    Genereert de volledige bontekst in onderdelen voor GUI-opmaak.
    """
    BON_WIDTH = 42

    # Bereken de totaalprijs correct aan het begin
    totaal = sum(Decimal(str(item['prijs'])) * item['aantal'] for item in bestelregels)

    # --- Header ---
    header_content = [
        "PITA PIZZA NAPOLI", "Brugstraat 12 - 9120 Vrasene", "TEL: 03 / 775 72 28",
        "FAX: 03 / 755 52 22", "BTW: BE 0479.048.950", "", "Bestel online",
        "www.pitapizzanapoli.be", "info@pitapizzanapoli.be"
    ]
    header_lines = [line.center(BON_WIDTH) for line in header_content]

    # --- Bestelinfo (rechts uitgelijnd) ---
    nu = datetime.datetime.now()
    bezorgtijd = (nu + datetime.timedelta(minutes=45)).strftime('%H:%M')
    info_content = {
        "Soort bestelling:": "Tel",
        "Bonnummer:": bonnummer,
        "Datum:": nu.strftime('%d-%m-%Y'),
        "Tijd:": nu.strftime('%H:%M'),
        "Betaalmethode:": "Cash",
        "Bezorgtijd:": bezorgtijd
    }
    info_lines = [""]
    for label, value in info_content.items():
        info_lines.append(f"{label:<20}{str(value):>{BON_WIDTH - 20}}")
    info_lines.append("")

    # --- Adres & QR Code prep ---
    postcode_gemeente = klant["postcode_gemeente"].split()
    postcode = postcode_gemeente[0] if len(postcode_gemeente) > 0 else ""
    gemeente = ' '.join(postcode_gemeente[1:]) if len(postcode_gemeente) > 1 else ""
    address_lines = [
        "Leveringsadres:",
        f"{klant['adres']} {klant['nr']}",
        f"{postcode} {gemeente}",
        f"{klant['telefoon']}"
    ]
    full_address_for_qr = f"{klant['adres']} {klant['nr']}, {postcode} {gemeente}, Belgium"

    # --- Details Bestelling ---
    details_lines = ["Details bestelling".center(BON_WIDTH), ("-" * BON_WIDTH)]

    for item in bestelregels:
        aantal = item['aantal']
        base_price = Decimal(str(item.get('base_price', item['prijs'])))

        display_product_name = item['product']
        if 'pizza' in item['categorie'].lower() and "." in display_product_name:
            display_product_name = " ".join(display_product_name.split(".")[1:]).strip()

        main_line_text = f"{aantal}x {display_product_name}"
        main_line_price = f"€ {base_price * aantal:.2f}"
        details_lines.append(f"{main_line_text:<{BON_WIDTH - 10}}{main_line_price:>{9}}")

        if item.get('extras'):
            extras = item['extras']
            cat_lower = item['categorie'].lower()
            garnering_prices = extras_data.get(cat_lower, {}).get('garnering', {}) if extras_data else {}

            def add_extra_line(value):
                if isinstance(value, list):
                    for sub_val in value:
                        add_extra_line(sub_val)
                else:
                    price = Decimal('0.00')
                    is_garnering = isinstance(garnering_prices, dict) and value in garnering_prices
                    if is_garnering:
                        price = Decimal(str(garnering_prices.get(value, 0)))

                    extra_line_price = price * aantal
                    price_str = f"€ {extra_line_price:.2f}" if price > 0 else ""
                    details_lines.append(f"   + {value:<{BON_WIDTH - 15}}{price_str:>{9}}")

            for key, value in extras.items():
                if value:
                    if key == 'half_half':
                        details_lines.append(f"   > Pizza {value[0]} & {value[1]}")
                    else:
                        add_extra_line(value)

        if item.get('opmerking'):
            details_lines.append(f"   > Opmerking: {item['opmerking']}")

    details_lines.append("-" * BON_WIDTH)

    # --- Totaal ---
    basis = (totaal / Decimal('1.06')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    btw = totaal - basis
    total_lines = [
        "",
        "Tarief     Basis    BTW    Totaal",
        f"6%   € {basis:<7.2f}  € {btw:<4.2f}  € {totaal:<7.2f}",
        ""
    ]

    # --- Footer ---
    footer_text = f"Totaal: € {totaal:.2f}"
    footer_lines = [
        footer_text.rjust(BON_WIDTH),
        "Eet smakelijk!".center(BON_WIDTH),
        "Dank u en tot ziens!".center(BON_WIDTH),
        "Dins- tot Zon 17.00-20.30".center(BON_WIDTH)
    ]

    # --- Te Betalen ---
    te_betalen_str = "TE BETALEN!"

    return (
        "\n".join(header_lines),  # header_str
        "\n".join(info_lines),  # info_str
        "\n".join(address_lines),  # address_str
        "\n".join(details_lines),  # details_str
        total_lines[1],  # kolomkop (header)
        total_lines[2],  # kolomwaarden (row)
        te_betalen_str,  # te_betalen_str
        footer_lines[0],  # alleen "Totaal: ..." (voor vetgedrukt)
        "\n".join(footer_lines[1:]),  # overig footer
        full_address_for_qr  # qr string
    )
