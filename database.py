import sqlite3
import csv
import os
import json
import datetime

DB_FILE = "pizzeria.db"


def get_db_connection():
    """Maakt een databaseconnectie aan en retourneert deze."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    """Maakt de databasetabellen aan als ze nog niet bestaan en voegt ontbrekende kolommen toe."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Klanten tabel (uitgebreid voor CRM)
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS klanten
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       telefoon
                       TEXT
                       UNIQUE
                       NOT
                       NULL,
                       straat
                       TEXT,
                       huisnummer
                       TEXT,
                       plaats
                       TEXT,
                       naam
                       TEXT,
                       notities
                       TEXT,
                       voorkeur_levering
                       TEXT,
                       laatste_bestelling
                       TEXT,
                       totaal_bestellingen
                       INTEGER
                       DEFAULT
                       0,
                       totaal_besteed
                       REAL
                       DEFAULT
                       0.0
                   )
                   ''')

    # Zorg dat nieuwe kolommen bestaan in bestaande DB's
    cursor.execute("PRAGMA table_info(klanten)")
    kcols = [row[1] for row in cursor.fetchall()]
    if 'notities' not in kcols:
        cursor.execute("ALTER TABLE klanten ADD COLUMN notities TEXT")
    if 'voorkeur_levering' not in kcols:
        cursor.execute("ALTER TABLE klanten ADD COLUMN voorkeur_levering TEXT")
    if 'laatste_bestelling' not in kcols:
        cursor.execute("ALTER TABLE klanten ADD COLUMN laatste_bestelling TEXT")
    if 'totaal_bestellingen' not in kcols:
        cursor.execute("ALTER TABLE klanten ADD COLUMN totaal_bestellingen INTEGER DEFAULT 0")
    if 'totaal_besteed' not in kcols:
        cursor.execute("ALTER TABLE klanten ADD COLUMN totaal_besteed REAL DEFAULT 0.0")

    # Koeriers tabel
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS koeriers
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       naam
                       TEXT
                       UNIQUE
                       NOT
                       NULL
                   )
                   ''')

    # Bestellingen tabel
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS bestellingen
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       klant_id
                       INTEGER,
                       koerier_id
                       INTEGER,
                       datum
                       TEXT
                       NOT
                       NULL,
                       tijd
                       TEXT
                       NOT
                       NULL,
                       totaal
                       REAL
                       NOT
                       NULL,
                       opmerking
                       TEXT,
                       bonnummer
                       TEXT,
                       FOREIGN
                       KEY
                   (
                       klant_id
                   ) REFERENCES klanten
                   (
                       id
                   ),
                       FOREIGN KEY
                   (
                       koerier_id
                   ) REFERENCES koeriers
                   (
                       id
                   )
                       )
                   ''')
    # Backwards compat kolommen
    cursor.execute("PRAGMA table_info(bestellingen)")
    bcols = [row[1] for row in cursor.fetchall()]
    if 'koerier_id' not in bcols:
        cursor.execute("ALTER TABLE bestellingen ADD COLUMN koerier_id INTEGER REFERENCES koeriers(id)")
    if 'bonnummer' not in bcols:
        cursor.execute("ALTER TABLE bestellingen ADD COLUMN bonnummer TEXT")

    # Bestelregels tabel
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS bestelregels
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       bestelling_id
                       INTEGER
                       NOT
                       NULL,
                       categorie
                       TEXT,
                       product
                       TEXT,
                       aantal
                       INTEGER,
                       prijs
                       REAL,
                       extras
                       TEXT,
                       FOREIGN
                       KEY
                   (
                       bestelling_id
                   ) REFERENCES bestellingen
                   (
                       id
                   )
                       )
                   ''')

    # Controleer het schema van bon_teller en herstel het indien nodig.
    # Dit is nodig voor oudere databases waar de 'dag' kolom nog niet bestond.
    cursor.execute("PRAGMA table_info(bon_teller)")
    bon_teller_cols = [row[1] for row in cursor.fetchall()]
    if bon_teller_cols and 'dag' not in bon_teller_cols:
        print("Verouderde 'bon_teller' tabel gedetecteerd. Tabel wordt opnieuw aangemaakt om het schema te corrigeren.")
        cursor.execute("DROP TABLE IF EXISTS bon_teller")

    # Bon-teller tabel
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS bon_teller
                   (
                       jaar
                       INTEGER
                       NOT
                       NULL,
                       dag
                       INTEGER
                       NOT
                       NULL,
                       laatste_nummer
                       INTEGER
                       NOT
                       NULL,
                       PRIMARY
                       KEY
                   (
                       jaar,
                       dag
                   )
                       )
                   ''')

    # Favoriete bestellingen (per klant)
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS favoriete_bestellingen
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       klant_id
                       INTEGER
                       NOT
                       NULL,
                       naam
                       TEXT
                       NOT
                       NULL,
                       bestelregels_json
                       TEXT
                       NOT
                       NULL,
                       totaal_prijs
                       REAL,
                       aangemaakt_op
                       TEXT
                       NOT
                       NULL,
                       laatst_gebruikt
                       TEXT,
                       gebruik_count
                       INTEGER
                       DEFAULT
                       0,
                       FOREIGN
                       KEY
                   (
                       klant_id
                   ) REFERENCES klanten
                   (
                       id
                   )
                       )
                   ''')

    # Klant notities (geschiedenis)
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS klant_notities
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       klant_id
                       INTEGER
                       NOT
                       NULL,
                       notitie
                       TEXT
                       NOT
                       NULL,
                       aangemaakt_op
                       TEXT
                       NOT
                       NULL,
                       medewerker
                       TEXT,
                       FOREIGN
                       KEY
                   (
                       klant_id
                   ) REFERENCES klanten
                   (
                       id
                   )
                       )
                   ''')

    # Voorraad tabellen
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS ingredienten
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       naam
                       TEXT
                       UNIQUE
                       NOT
                       NULL,
                       eenheid
                       TEXT
                       NOT
                       NULL, -- bv. 'kg','st','l'
                       minimum
                       REAL
                       DEFAULT
                       0,    -- drempel voor waarschuwing
                       huidige_voorraad
                       REAL
                       DEFAULT
                       0
                   )
                   ''')
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS recepturen
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       categorie
                       TEXT
                       NOT
                       NULL,
                       product
                       TEXT
                       NOT
                       NULL,
                       ingredient_id
                       INTEGER
                       NOT
                       NULL,
                       hoeveelheid_per_stuk
                       REAL
                       NOT
                       NULL,
                       UNIQUE
                   (
                       categorie,
                       product,
                       ingredient_id
                   ),
                       FOREIGN KEY
                   (
                       ingredient_id
                   ) REFERENCES ingredienten
                   (
                       id
                   )
                       )
                   ''')
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS voorraad_mutaties
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       ingredient_id
                       INTEGER
                       NOT
                       NULL,
                       mutatie
                       REAL
                       NOT
                       NULL, -- + of - waarde
                       reden
                       TEXT,
                       datumtijd
                       TEXT
                       NOT
                       NULL, -- ISO timestamp
                       FOREIGN
                       KEY
                   (
                       ingredient_id
                   ) REFERENCES ingredienten
                   (
                       id
                   )
                       )
                   ''')

    conn.commit()
    conn.close()
    print("Tabellen zijn aangemaakt/bijgewerkt (indien nodig).")


def migrate_klanten_from_csv():
    """Migreert klantgegevens van klanten.csv naar de SQLite database, indien nodig."""
    if not os.path.exists("klanten.csv"):
        print("klanten.csv niet gevonden. Migratie overgeslagen.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM klanten")
    if cursor.fetchone()[0] > 0:
        conn.close()
        print("Klantendatabase is niet leeg. Migratie overgeslagen.")
        return

    print("Start migratie van klanten uit klanten.csv...")
    try:
        with open("klanten.csv", 'r', encoding='latin-1', newline='') as f:
            reader = csv.DictReader(f, delimiter=';')
            klanten_to_insert = []
            for row in reader:
                telefoon = row.get('Telefoonnummer', '').strip()
                if telefoon:
                    klanten_to_insert.append((
                        telefoon,
                        row.get('Straat', '').strip(),
                        row.get('Huisnummer', '').strip(),
                        row.get('Plaats', '').strip(),
                        row.get('Naam', '').strip()
                    ))
            cursor.executemany(
                "INSERT OR IGNORE INTO klanten (telefoon, straat, huisnummer, plaats, naam) VALUES (?, ?, ?, ?, ?)",
                klanten_to_insert
            )
            conn.commit()
            print(f"{cursor.rowcount} unieke klanten gemigreerd.")
    except Exception as e:
        print(f"Fout tijdens migratie van klanten: {e}")
    finally:
        conn.close()


def migrate_bestellingen_from_csv():
    """Migreert de bestelgeschiedenis van bestellingen.csv naar de database."""
    if not os.path.exists("bestellingen.csv"):
        print("bestellingen.csv niet gevonden. Migratie overgeslagen.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM bestellingen")
    if cursor.fetchone()[0] > 0:
        conn.close()
        print("Database 'bestellingen' is niet leeg. Migratie overgeslagen.")
        return

    print("Start migratie van bestellingen uit bestellingen.csv...")
    try:
        with open("bestellingen.csv", 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f, delimiter=';')
            for row in reader:
                if len(row) < 8:
                    continue  # Onvolledige rij

                order_datum, order_tijd, tel, straat, nr, plaats, totaal_str, bestelregels_json, *rest = row
                opmerking = rest[0] if rest else ""

                cursor.execute("SELECT id FROM klanten WHERE telefoon = ?", (tel.strip(),))
                klant_row = cursor.fetchone()
                klant_id = klant_row[0] if klant_row else None

                if not klant_id:
                    continue  # Klant bestaat niet in database

                cursor.execute(
                    "INSERT INTO bestellingen (klant_id, datum, tijd, totaal, opmerking) VALUES (?, ?, ?, ?, ?)",
                    (klant_id, order_datum, order_tijd, float(totaal_str), opmerking)
                )
                bestelling_id = cursor.lastrowid

                try:
                    bestelregels_data = json.loads(bestelregels_json)
                except Exception:
                    bestelregels_data = []

                for regel in bestelregels_data:
                    cursor.execute(
                        "INSERT INTO bestelregels (bestelling_id, categorie, product, aantal, prijs, extras) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            bestelling_id,
                            regel.get('categorie', ''),
                            regel.get('product', ''),
                            int(regel.get('aantal', 1)),
                            float(regel.get('prijs', 0)),
                            json.dumps(regel.get('extras', {}))
                        )
                    )
        conn.commit()
        print("Migratie van bestellingen voltooid.")
        os.rename("bestellingen.csv", "bestellingen.csv.migrated")
        print("bestellingen.csv is hernoemd naar bestellingen.csv.migrated.")
    except Exception as e:
        print(f"Fout tijdens migratie van bestellingen: {e}")
        conn.rollback()
    finally:
        conn.close()


def populate_koeriers_if_empty():
    """Voegt standaardkoeriers toe aan de database als de tabel leeg is."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM koeriers")
    if cursor.fetchone()[0] == 0:
        print("Koeriers-tabel is leeg, standaardkoeriers worden toegevoegd.")
        koeriers = [("Koerier 1",), ("Koerier 2",), ("Koerier 3",)]
        cursor.executemany("INSERT INTO koeriers (naam) VALUES (?)", koeriers)
        conn.commit()
    conn.close()


def update_klant_statistieken(klant_id):
    """Werk klantstatistieken (totaal bestellingen, besteed, laatste) bij."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT COUNT(*)                  AS aantal_bestellingen,
                              COALESCE(SUM(totaal), 0)  AS totaal_besteed,
                              MAX(datum || ' ' || tijd) AS laatste_bestelling
                       FROM bestellingen
                       WHERE klant_id = ?
                       """, (klant_id,))
        stats = cursor.fetchone()
        cursor.execute("""
                       UPDATE klanten
                       SET totaal_bestellingen = ?,
                           totaal_besteed      = ?,
                           laatste_bestelling  = ?
                       WHERE id = ?
                       """,
                       (stats['aantal_bestellingen'], stats['totaal_besteed'], stats['laatste_bestelling'], klant_id))
        conn.commit()
    finally:
        conn.close()


def boek_voorraad_verbruik(bestelling_id: int):
    """Boekt voorraadverbruik voor alle bestelregels via recepturen."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Haal regels op
        cur.execute("""
                    SELECT categorie, product, aantal
                    FROM bestelregels
                    WHERE bestelling_id = ?
                    """, (bestelling_id,))
        regels = cur.fetchall()

        verbruik = {}  # ingredient_id -> totale verbruik

        for r in regels:
            categorie = (r["categorie"] or "").strip()
            product = (r["product"] or "").strip()
            aantal = int(r["aantal"] or 0)

            if aantal <= 0:
                continue

            # Receptuurregels ophalen
            cur.execute("""
                        SELECT ingredient_id, hoeveelheid_per_stuk
                        FROM recepturen
                        WHERE LOWER(categorie) = LOWER(?)
                          AND product = ?
                        """, (categorie, product))
            recs = cur.fetchall()
            for rec in recs:
                ingredient_id = rec["ingredient_id"]
                qty = float(rec["hoeveelheid_per_stuk"]) * aantal
                verbruik[ingredient_id] = verbruik.get(ingredient_id, 0.0) + qty

        # Boek verbruik
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for ingr_id, qty in verbruik.items():
            # Mutatie opslaan
            cur.execute("""
                        INSERT INTO voorraad_mutaties (ingredient_id, mutatie, reden, datumtijd)
                        VALUES (?, ?, ?, ?)
                        """, (ingr_id, -qty, f"Bestelling #{bestelling_id}", now_str))
            # Voorraad updaten
            cur.execute("""
                        UPDATE ingredienten
                        SET huidige_voorraad = COALESCE(huidige_voorraad, 0) - ?
                        WHERE id = ?
                        """, (qty, ingr_id))
        conn.commit()
    finally:
        conn.close()


def get_next_bonnummer(peek_only=False):
    import datetime
    now = datetime.datetime.now()
    jaar = now.year
    dag_in_jaar = now.timetuple().tm_yday  # dagnummer in jaar (1-366)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO bon_teller (jaar, dag, laatste_nummer) VALUES (?, ?, 0)",
            (jaar, dag_in_jaar)
        )
        conn.commit()
        cursor.execute(
            "SELECT laatste_nummer FROM bon_teller WHERE jaar = ? AND dag = ?",
            (jaar, dag_in_jaar)
        )
        result = cursor.fetchone()
        current_last_number = result['laatste_nummer'] if result else 0
        next_number = current_last_number + 1

        if not peek_only:
            cursor.execute(
                "UPDATE bon_teller SET laatste_nummer = ? WHERE jaar = ? AND dag = ?",
                (next_number, jaar, dag_in_jaar)
            )
            conn.commit()

        # Bonnummer structuur: YYYYNNNN (dag telt alleen voor reset, niet zichtbaar in bonnummer)
        return f"{jaar}{next_number:04d}"
    finally:
        conn.close()


def initialize_database():
    """Initialiseert de database: maakt tabellen aan en migreert data."""
    create_tables()
    populate_koeriers_if_empty()
    migrate_klanten_from_csv()
    migrate_bestellingen_from_csv()

# Aanroepen indien gewenst:
# initialize_database()