"""
Finanzanalyse – Berechnung (läuft mit PyScript im Browser)

Ablauf, wenn man auf "Finanzanalyse starten" klickt:
  1. Die hochgeladenen CSV-Dateien (Bilanz und GuV) werden eingelesen.
  2. Es wird geprüft, ob alle nötigen Spalten da sind und die Bilanz aufgeht.
  3. Für jedes Geschäftsjahr werden die wichtigen Posten zusammengezählt.
  4. Daraus werden die Kennzahlen berechnet (mit Vorjahr, wenn vorhanden).
  5. Die Ergebnisse werden an die Ergebnisseite (index2.html) geschickt.
    Dort werden Ampelfarben, Score und Diagramme angezeigt.

Abschnitte in dieser Datei:
  1. Einstellungen
  2. CSV einlesen und Text vorbereiten
  3. Geschäftsjahre
  4. Prüfungen
  5. Posten sammeln (Bilanz und GuV)
  6. Kennzahlen berechnen
  7. Alle Jahre analysieren
  8. Button "Finanzanalyse starten"
"""

from pyscript import document, when, window
import csv
import json


# ============================================================
# 1. Einstellungen
# ============================================================

# Bei jeder neuen Version erhöhen (auch in index.html), damit Browser keine alten Dateien aus dem Cache laden
VERSION = "47"


# ============================================================
# 2. CSV einlesen und Text vorbereiten
# ============================================================

def parse_csv(text):
    """Liest CSV-Text (Semikolon-getrennt) und gibt eine Liste von Zeilen zurück."""
    inhalt = (text or "").strip().lstrip("\ufeff")
    if not inhalt:
        return []

    reader = csv.DictReader(inhalt.splitlines(), delimiter=";")
    if reader.fieldnames:
        reader.fieldnames = [name.strip() for name in reader.fieldnames]

    return list(reader)


def parse_betrag(wert):
    """Wandelt verschiedene Zahlenformate in float um."""
    text = (wert or "").strip()
    text = text.replace(" ", "")
    text = text.replace("'", "")

    if "," in text and "." in text:
        letztes_komma = text.rfind(",")
        letzter_punkt = text.rfind(".")

        if letztes_komma > letzter_punkt:
            # Deutsch: 1.234,56
            text = text.replace(".", "")
            text = text.replace(",", ".")
        else:
            # Englisch: 1,234.56
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return 0.0


def text_klein(zeile, feld):
    return (zeile.get(feld, "") or "").strip().lower()


def normalisiere_text(text):
    """Macht Text robust für Vergleiche (z. B. Umlaute)."""
    t = (text or "").strip().lower()
    t = t.replace("ä", "ae")
    t = t.replace("ö", "oe")
    t = t.replace("ü", "ue")
    t = t.replace("ß", "ss")
    return t


# ============================================================
# 3. Geschäftsjahre
# ============================================================
# Die Spalte heißt "GJ", "Geschaeftsjahr" oder "Geschäftsjahr".

def hole_gj_wert(zeile):
    """Liest das Geschäftsjahr aus verschiedenen Spaltennamen."""
    gj = (zeile.get("GJ", "") or "").strip()
    if gj:
        return gj

    gj = (zeile.get("Geschaeftsjahr", "") or "").strip()
    if gj:
        return gj

    gj = (zeile.get("Geschäftsjahr", "") or "").strip()
    return gj


def hat_jahr_spalte(daten):
    if not daten:
        return False

    spalten = list(daten[0].keys())
    if "GJ" in spalten:
        return True
    if "Geschaeftsjahr" in spalten:
        return True
    if "Geschäftsjahr" in spalten:
        return True
    return False


def lade_und_filtere_nach_jahr(daten, jahr):
    gefiltert = []
    for zeile in daten:
        if hole_gj_wert(zeile) == str(jahr):
            gefiltert.append(zeile)
    return gefiltert


def hole_gj_liste(daten):
    jahre = []
    for zeile in daten:
        gj = hole_gj_wert(zeile)
        if gj and gj not in jahre:
            jahre.append(gj)
    jahre.sort(reverse=True)
    return jahre


def vorjahr_von(jahr):
    """Gibt das Vorjahr als Text zurück, z. B. "2025" -> "2024"."""
    if not jahr.isdigit():
        return ""
    return str(int(jahr) - 1)


# ============================================================
# 4. Prüfungen
# ============================================================

def pruefe_eingaben(bilanz_text, guv_text):
    hat_bilanz = bool((bilanz_text or "").strip())
    hat_guv = bool((guv_text or "").strip())

    if not hat_bilanz and not hat_guv:
        return "⚠️ Bitte Bilanz- und GuV-Datei hochladen."
    if not hat_bilanz:
        return "⚠️ Bitte die Bilanz-Datei hochladen."
    if not hat_guv:
        return "⚠️ Bitte die GuV-Datei hochladen."
    return None


def pruefe_pflicht_spalten(daten, pflicht_spalten, name):
    spalten = list(daten[0].keys()) if daten else []
    fehlende = []

    for spalte in pflicht_spalten:
        if spalte not in spalten:
            fehlende.append(spalte)

    if fehlende:
        return False, f"{name} FEHLER: Spalten fehlen: {', '.join(fehlende)}"
    return True, f"{name} OK"


def pruefe_bilanzsumme_fuer_jahr(bilanz_jahr, toleranz=0.01):
    aktiva = 0.0
    passiva = 0.0

    for zeile in bilanz_jahr:
        betrag = parse_betrag(zeile.get("Betrag_EUR", "0"))
        seite = text_klein(zeile, "Seite")

        if seite == "aktiva":
            aktiva += betrag
        elif seite == "passiva":
            passiva += betrag

    if abs(aktiva - passiva) > toleranz:
        return False
    return True


# ============================================================
# 5. Posten sammeln (Bilanz und GuV)
# ============================================================
# Hier werden die Zeilen der CSV-Dateien zu Summen zusammengezählt,
# z. B. alle Zeilen mit Kategorie "Eigenkapital" -> eigenkapital.

def ist_lul(text):
    """Prüft, ob eine Position zu "Lieferungen und Leistungen" gehört."""
    if "lul" in text:
        return True
    if "l+l" in text:
        return True
    if "lieferungen und leistungen" in text:
        return True
    return False


def sammle_bilanz_posten(bilanz_jahr):
    """Zählt die Bilanzposten eines Jahres zusammen, die für die Kennzahlen gebraucht werden.

    Langfristiges Fremdkapital:
    - Wenn die Spalte "Fristigkeit" ausgefüllt ist (kurz/lang), wird sie verwendet.
    - Sonst gelten Darlehen, Bankschulden und Pensionsrückstellungen als langfristig.
    """
    # Alle Summen starten bei 0
    posten = {
        "bilanzsumme": 0.0,
        "eigenkapital": 0.0,
        "fremdkapital": 0.0,
        "langfr_fk": 0.0,
        "anlagevermoegen": 0.0,
        "umlaufvermoegen": 0.0,
        "liquide_mittel": 0.0,
        "vorraete": 0.0,
        "forderungen": 0.0,
        "forderungen_lul": 0.0,
        "verbindlichkeiten": 0.0,
        "bankverbindlichkeiten": 0.0,
        "finanzverbindlichkeiten": 0.0,
        "verbindlichkeiten_lul": 0.0,
        "rueckstellungen": 0.0,
    }

    for zeile in bilanz_jahr:
        # Werte aus der Zeile lesen (Text klein und ohne Umlaute, damit der Vergleich klappt)
        betrag = parse_betrag(zeile.get("Betrag_EUR", "0"))
        seite = text_klein(zeile, "Seite")
        kategorie = normalisiere_text(zeile.get("Kategorie", ""))
        unterkategorie = normalisiere_text(zeile.get("Unterkategorie", ""))
        position = normalisiere_text(zeile.get("Bilanzposition", ""))
        fristigkeit = normalisiere_text(zeile.get("Fristigkeit", "") or "")

        # ---------- Aktiva ----------
        if seite == "aktiva":
            posten["bilanzsumme"] += betrag

            if "anlageverm" in kategorie or "finanzanlage" in kategorie:
                posten["anlagevermoegen"] += betrag

            elif "umlaufverm" in kategorie:
                posten["umlaufvermoegen"] += betrag

                if "liquide mittel" in unterkategorie:
                    posten["liquide_mittel"] += betrag
                if "vorraete" in unterkategorie or "vorraete" in position:
                    posten["vorraete"] += betrag
                if "forderung" in unterkategorie:
                    posten["forderungen"] += betrag
                    if ist_lul(position):
                        posten["forderungen_lul"] += betrag

        # ---------- Passiva ----------
        elif seite == "passiva":
            if kategorie == "eigenkapital":
                posten["eigenkapital"] += betrag
                continue  # Eigenkapital ist kein Fremdkapital -> nächste Zeile

            # Alles andere auf der Passivseite ist Fremdkapital
            posten["fremdkapital"] += betrag
            ist_langfristig = False

            if "rueckstellung" in kategorie:
                posten["rueckstellungen"] += betrag
                if "pension" in unterkategorie or "pension" in position:
                    ist_langfristig = True

            if "verbindlichkeit" in kategorie:
                posten["verbindlichkeiten"] += betrag

                ist_bank = False
                if "bank" in unterkategorie or "bank" in position or "kreditinstitut" in position:
                    ist_bank = True

                ist_darlehen = False
                if "darlehen" in unterkategorie or "darlehen" in position or "anleihe" in position:
                    ist_darlehen = True

                if ist_bank:
                    posten["bankverbindlichkeiten"] += betrag
                if ist_bank or ist_darlehen:
                    posten["finanzverbindlichkeiten"] += betrag
                    ist_langfristig = True
                if "lieferant" in unterkategorie or ist_lul(position):
                    posten["verbindlichkeiten_lul"] += betrag

            # Wenn die Spalte "Fristigkeit" ausgefüllt ist, gilt sie
            if fristigkeit != "":
                ist_langfristig = "lang" in fristigkeit

            if ist_langfristig:
                posten["langfr_fk"] += betrag

    # Wenn keine Forderung als "LuL" erkennbar war, alle Forderungen nehmen
    if posten["forderungen_lul"] == 0:
        posten["forderungen_lul"] = posten["forderungen"]

    # Kurzfristiges Fremdkapital = Fremdkapital - langfristiges Fremdkapital
    posten["kurzfr_fk"] = posten["fremdkapital"] - posten["langfr_fk"]
    return posten


def ist_zusatzangabe(zeile):
    """Prüft, ob eine GuV-Zeile eine Zusatzangabe ist (Kategorie "Zusatzangaben").

    Zusatzangaben sind z. B. Tilgung, Entnahmen und Investitionen. Sie werden für den
    Kapitaldienst gebraucht, gehören aber nicht zum Jahresergebnis.
    """
    kategorie = normalisiere_text(zeile.get("Kategorie", ""))
    return "zusatz" in kategorie


def hole_guv_seite(zeile):
    """Liest haben/soll aus der GuV-Zeile, mit einfachem Fallback."""
    if ist_zusatzangabe(zeile):
        return ""

    seite = normalisiere_text(zeile.get("Seite", "") or "")
    if not seite:
        seite = normalisiere_text(zeile.get("seite", "") or "")
    if not seite:
        seite = normalisiere_text(zeile.get("SollHaben", "") or "")
    if not seite:
        seite = normalisiere_text(zeile.get("Soll/Haben", "") or "")

    if seite in ["haben", "habenseite", "h"]:
        return "haben"
    if seite in ["soll", "sollseite", "s"]:
        return "soll"

    kategorie = normalisiere_text(zeile.get("Kategorie", ""))
    position = normalisiere_text(zeile.get("position", "") or zeile.get("Position", ""))

    if "ertrag" in kategorie or "erloes" in kategorie or "umsatz" in position:
        return "haben"
    if "aufwand" in kategorie or "kosten" in kategorie:
        return "soll"

    return ""


def sammle_guv_posten(guv_jahr):
    """Zählt die GuV-Posten eines Jahres zusammen, die für die Kennzahlen gebraucht werden."""
    posten = {
        "ertraege": 0.0,
        "aufwendungen": 0.0,
        "umsatz": 0.0,
        "bestandsveraenderung": 0.0,
        "eigenleistungen": 0.0,
        "materialaufwand": 0.0,
        "personalaufwand": 0.0,
        "abschreibungen": 0.0,
        "zinsaufwand": 0.0,
        "steuern": 0.0,
    }

    # Zusatzangaben (stehen nicht in der GuV, sind aber für den Kapitaldienst nötig).
    # None bedeutet: In der Datei nicht angegeben.
    tilgung = None
    entnahmen = None
    investitionen = None

    for zeile in guv_jahr:
        betrag = parse_betrag(zeile.get("Betrag_EUR", "0"))
        seite = hole_guv_seite(zeile)
        position = normalisiere_text(zeile.get("position", "") or zeile.get("Position", ""))

        # ---------- Zusatzangaben ----------
        if ist_zusatzangabe(zeile):
            if "tilgung" in position:
                if tilgung is None:
                    tilgung = 0.0
                tilgung += betrag
            elif "entnahme" in position or "ausschuettung" in position:
                if entnahmen is None:
                    entnahmen = 0.0
                entnahmen += betrag
            elif "investition" in position:
                if investitionen is None:
                    investitionen = 0.0
                investitionen += betrag
            continue  # Zusatzangaben gehören nicht zum Jahresergebnis

        # ---------- Erträge (Haben) ----------
        if seite == "haben":
            posten["ertraege"] += betrag
            if "umsatz" in position:
                posten["umsatz"] += betrag
            if "bestandsver" in position:
                posten["bestandsveraenderung"] += betrag
            if "eigenleistung" in position:
                posten["eigenleistungen"] += betrag

        # ---------- Aufwendungen (Soll) ----------
        elif seite == "soll":
            posten["aufwendungen"] += betrag
            if "bestandsver" in position:
                posten["bestandsveraenderung"] -= betrag
            elif "material" in position:
                posten["materialaufwand"] += betrag
            elif "personal" in position:
                posten["personalaufwand"] += betrag
            elif "abschreibung" in position:
                posten["abschreibungen"] += betrag
            elif "zins" in position:
                posten["zinsaufwand"] += betrag
            elif "steuer" in position and "sonstige steuer" not in position:
                posten["steuern"] += betrag

    # Wenn keine Zeile "Umsatz" heißt, alle Erträge als Umsatz nehmen
    if posten["umsatz"] == 0:
        posten["umsatz"] = posten["ertraege"]

    posten["tilgung"] = tilgung
    posten["entnahmen"] = entnahmen
    posten["investitionen"] = investitionen

    # Ergebnisgrößen ausrechnen
    posten["jahresueberschuss"] = posten["ertraege"] - posten["aufwendungen"]
    posten["ebt"] = posten["jahresueberschuss"] + posten["steuern"]       # Ergebnis vor Steuern
    posten["ebit"] = posten["ebt"] + posten["zinsaufwand"]                # Ergebnis vor Zinsen und Steuern
    posten["ebitda"] = posten["ebit"] + posten["abschreibungen"]          # ... und vor Abschreibungen
    posten["gesamtleistung"] = (
        posten["umsatz"] + posten["bestandsveraenderung"] + posten["eigenleistungen"]
    )
    return posten


# ============================================================
# 6. Kennzahlen berechnen
# ============================================================
#
# Jede Kennzahl wird so gespeichert:
#   {"wert": 0.25, "hinweis": "...", "ampel": "rot"}
#   - wert:    die Zahl (Prozent als Anteil, also 0.25 = 25 %) oder None, wenn nicht berechenbar
#   - hinweis: Erklärung, z. B. "Vorjahr fehlt" (optional)
#   - ampel:   nur bei Sonderfällen, z. B. "rot" bei negativem Eigenkapital (optional)
# Die Ampelfarben selbst werden auf der Ergebnisseite (index2.html) bestimmt.

def teile(zaehler, nenner):
    """Teilt zwei Zahlen. Gibt None zurück, wenn man nicht teilen kann (z. B. durch 0)."""
    if zaehler is None or nenner is None:
        return None
    if nenner == 0:
        return None
    return zaehler / nenner


def durchschnitt(aktuell, vorjahr):
    """Mittelwert aus aktuellem Jahr und Vorjahr. Ohne Vorjahr: nur der aktuelle Wert."""
    if vorjahr is None:
        return aktuell
    return (aktuell + vorjahr) / 2


def kennzahl(wert, hinweis="", ampel=""):
    """Baut den Eintrag für eine Kennzahl: {"wert": ..., "hinweis": ..., "ampel": ...}"""
    eintrag = {}
    if wert is None:
        eintrag["wert"] = None
    else:
        eintrag["wert"] = round(wert, 6)
    if hinweis != "":
        eintrag["hinweis"] = hinweis
    if ampel != "":
        eintrag["ampel"] = ampel
    return eintrag


def berechne_kennzahlen(bilanz, guv, bilanz_vorjahr=None, guv_vorjahr=None):
    """Berechnet alle Kennzahlen eines Jahres.

    bilanz, guv: Posten des aktuellen Jahres (von sammle_bilanz_posten / sammle_guv_posten)
    bilanz_vorjahr, guv_vorjahr: Posten des Vorjahres oder None, wenn es kein Vorjahr gibt
    """
    k = {}

    # Häufig gebrauchte Werte in kurze Variablen schreiben
    ek = bilanz["eigenkapital"]
    bs = bilanz["bilanzsumme"]
    fk = bilanz["fremdkapital"]
    av = bilanz["anlagevermoegen"]
    kurzfr_fk = bilanz["kurzfr_fk"]
    liquide = bilanz["liquide_mittel"]
    umsatz = guv["umsatz"]
    gesamtleistung = guv["gesamtleistung"]
    zins = guv["zinsaufwand"]
    hat_vorjahr = bilanz_vorjahr is not None

    # ---------- Kapitalstruktur (K01-K08) ----------
    k["K01"] = kennzahl(teile(ek, bs))                       # Eigenkapitalquote
    k["K02"] = kennzahl(teile(fk, bs))                       # Fremdkapitalquote
    if ek > 0:
        k["K03"] = kennzahl(teile(fk, ek))                   # Verschuldungsgrad
    else:
        k["K03"] = kennzahl(None, "Eigenkapital ≤ 0", "rot")
    k["K04"] = kennzahl(teile(av, bs))                       # Anlagenintensität
    k["K05"] = kennzahl(teile(ek, av))                       # Anlagendeckung I
    k["K06"] = kennzahl(teile(ek + bilanz["langfr_fk"], av))  # Anlagendeckung II
    k["K07"] = kennzahl(teile(bilanz["bankverbindlichkeiten"], bs))
    k["K08"] = kennzahl(teile(bilanz["finanzverbindlichkeiten"] - liquide, bs))

    # ---------- Rentabilität (R01-R07) ----------
    k["R01"] = kennzahl(teile(guv["ebt"], gesamtleistung))   # Umsatzrentabilität
    k["R02"] = kennzahl(teile(guv["ebt"] + zins, bs))        # Gesamtkapitalrentabilität
    if ek > 0:
        k["R03"] = kennzahl(teile(guv["ebt"], ek))           # Eigenkapitalrentabilität
    else:
        k["R03"] = kennzahl(None, "Eigenkapital ≤ 0", "rot")
    k["R04"] = kennzahl(teile(guv["ebitda"], umsatz))        # EBITDA-Marge
    k["R05"] = kennzahl(teile(guv["personalaufwand"], gesamtleistung))
    k["R06"] = kennzahl(teile(guv["materialaufwand"], gesamtleistung))
    if guv_vorjahr is not None and guv_vorjahr["umsatz"] > 0:
        k["R07"] = kennzahl(umsatz / guv_vorjahr["umsatz"] - 1)  # Umsatzwachstum
    else:
        k["R07"] = kennzahl(None, "Vorjahr fehlt")

    # ---------- Cashflow & Kapitaldienst (C01-C07) ----------
    # Cashflow = Jahresüberschuss + Abschreibungen + Veränderung der Rückstellungen
    cashflow = guv["jahresueberschuss"] + guv["abschreibungen"]
    if hat_vorjahr:
        cashflow = cashflow + bilanz["rueckstellungen"] - bilanz_vorjahr["rueckstellungen"]
        cf_hinweis = ""
    else:
        cf_hinweis = "Vereinfacht ohne Vorjahr (ohne Veränderung der Rückstellungen)"

    k["C01"] = kennzahl(cashflow, cf_hinweis)                     # Cashflow
    k["C02"] = kennzahl(teile(cashflow, umsatz), cf_hinweis)      # Cashflow-Rate

    if cashflow > 0:                                              # Schuldentilgungsdauer
        netto_schulden = bilanz["verbindlichkeiten"] - liquide
        if netto_schulden < 0:
            netto_schulden = 0.0
        k["C03"] = kennzahl(netto_schulden / cashflow, cf_hinweis)
    else:
        k["C03"] = kennzahl(None, "Cashflow ≤ 0", "rot")

    if zins > 0:                                                  # Zinsdeckung
        k["C04"] = kennzahl(guv["ebit"] / zins)
    else:
        k["C04"] = kennzahl(None, "Kein Zinsaufwand")

    # Kapitaldienst: braucht die Zusatzangaben aus der GuV-Datei
    tilgung = guv["tilgung"]
    entnahmen = guv["entnahmen"]
    investitionen = guv["investitionen"]

    # C05 Kapitaldienstgrenze = erweiterter Cashflow - betriebsnotwendige Investitionen
    kapitaldienstgrenze = None
    if entnahmen is None or investitionen is None:
        k["C05"] = kennzahl(None, "Zusatzangaben Entnahmen/Ausschüttungen und Investitionen fehlen")
    else:
        erweiterter_cashflow = cashflow + zins - entnahmen
        kapitaldienstgrenze = erweiterter_cashflow - investitionen
        if kapitaldienstgrenze <= 0:
            k["C05"] = kennzahl(kapitaldienstgrenze, cf_hinweis, "rot")
        else:
            k["C05"] = kennzahl(kapitaldienstgrenze, cf_hinweis)

    # C06 Auslastung = Kapitaldienst (Zins + Tilgung) / Kapitaldienstgrenze
    if kapitaldienstgrenze is None or tilgung is None:
        k["C06"] = kennzahl(None, "Zusatzangaben Tilgung, Entnahmen oder Investitionen fehlen")
    elif kapitaldienstgrenze <= 0:
        k["C06"] = kennzahl(None, "Kapitaldienstgrenze ≤ 0", "rot")
    else:
        k["C06"] = kennzahl((zins + tilgung) / kapitaldienstgrenze, cf_hinweis)

    # C07 DSCR = (Cashflow + Zins) / (Zins + Tilgung)
    if tilgung is None:
        k["C07"] = kennzahl(None, "Zusatzangabe Tilgung fehlt")
    else:
        k["C07"] = kennzahl(teile(cashflow + zins, zins + tilgung), cf_hinweis)

    # ---------- Liquidität & Working Capital (L01-L08) ----------
    k["L01"] = kennzahl(teile(liquide, kurzfr_fk))                            # Liquidität 1. Grades
    k["L02"] = kennzahl(teile(liquide + bilanz["forderungen"], kurzfr_fk))    # Liquidität 2. Grades
    k["L03"] = kennzahl(teile(bilanz["umlaufvermoegen"], kurzfr_fk))          # Liquidität 3. Grades
    k["L04"] = kennzahl(teile(bilanz["umlaufvermoegen"] - kurzfr_fk, umsatz))  # Working Capital

    # Für die Tage-Kennzahlen mit Vorjahr den Durchschnittsbestand nehmen
    if hat_vorjahr:
        tage_hinweis = "Durchschnittsbestand mit Vorjahr"
        forderungen = durchschnitt(bilanz["forderungen_lul"], bilanz_vorjahr["forderungen_lul"])
        vorraete = durchschnitt(bilanz["vorraete"], bilanz_vorjahr["vorraete"])
        verb_lul = durchschnitt(bilanz["verbindlichkeiten_lul"], bilanz_vorjahr["verbindlichkeiten_lul"])
    else:
        tage_hinweis = "Stichtagswert (kein Vorjahr)"
        forderungen = bilanz["forderungen_lul"]
        vorraete = bilanz["vorraete"]
        verb_lul = bilanz["verbindlichkeiten_lul"]

    dso = teile(forderungen * 360, umsatz)                       # Debitorenziel
    dio = teile(vorraete * 360, guv["materialaufwand"])          # Lagerdauer
    dpo = teile(verb_lul * 360, guv["materialaufwand"])          # Kreditorenziel
    k["L05"] = kennzahl(dso, tage_hinweis)
    k["L06"] = kennzahl(dio, tage_hinweis)
    k["L07"] = kennzahl(dpo, tage_hinweis)
    if dso is None or dio is None or dpo is None:
        k["L08"] = kennzahl(None, "DSO, DIO oder DPO nicht berechenbar")
    else:
        k["L08"] = kennzahl(dso + dio - dpo, tage_hinweis)        # Cash Conversion Cycle

    return k


def uebersicht_werte(bilanz, guv, kennzahlen):
    """Wichtige Beträge in Euro für die Finanzübersicht und die Diagramme auf der Ergebnisseite."""
    # Kapitaldienst = Zinsen + Tilgung (nur wenn die Tilgung angegeben ist)
    kapitaldienst = None
    if guv["tilgung"] is not None:
        kapitaldienst = guv["zinsaufwand"] + guv["tilgung"]

    return {
        "umsatz": guv["umsatz"],
        "ebitda": guv["ebitda"],
        "jahresueberschuss": guv["jahresueberschuss"],
        "cashflow": kennzahlen["C01"]["wert"],
        "bilanzsumme": bilanz["bilanzsumme"],
        "eigenkapital": bilanz["eigenkapital"],
        "fremdkapital": bilanz["fremdkapital"],
        "langfr_fk": bilanz["langfr_fk"],
        "kurzfr_fk": bilanz["kurzfr_fk"],
        "liquide_mittel": bilanz["liquide_mittel"],
        "kapitaldienstgrenze": kennzahlen["C05"]["wert"],
        "kapitaldienst": kapitaldienst,
    }


# ============================================================
# 7. Alle Jahre analysieren
# ============================================================

def analysiere_alle_jahre(bilanz, guv):
    """Berechnet für jedes Geschäftsjahr die Kennzahlen.

    Rückgabe: (ergebnisse, fehlertext, gemeinsame_jahre)
    - ergebnisse: Liste mit einem Eintrag pro Jahr: {"gj": ..., "werte": ..., "kennzahlen": ...}
    - fehlertext: None, wenn alles geklappt hat
    """
    # Nur Jahre nehmen, die in Bilanz UND GuV vorkommen
    bilanz_jahre = hole_gj_liste(bilanz)
    guv_jahre = hole_gj_liste(guv)

    gemeinsame_jahre = []
    for jahr in bilanz_jahre:
        if jahr in guv_jahre:
            gemeinsame_jahre.append(jahr)

    if not gemeinsame_jahre:
        return None, "⚠️ Keine gemeinsamen GJ-Daten in Bilanz und GuV gefunden.", []

    # Schritt 1: Bilanz jedes Jahres prüfen (Aktiva = Passiva)
    for jahr in gemeinsame_jahre:
        bilanz_jahr = lade_und_filtere_nach_jahr(bilanz, jahr)
        if not pruefe_bilanzsumme_fuer_jahr(bilanz_jahr):
            return None, "⚠️ Bilanzsummen stimmen nicht überein (GJ " + jahr + ": Aktiva ≠ Passiva)", gemeinsame_jahre

    # Schritt 2: Für jedes Jahr die Posten sammeln (vorher, damit wir aufs Vorjahr zugreifen können)
    bilanz_posten = {}
    guv_posten = {}
    for jahr in gemeinsame_jahre:
        bilanz_posten[jahr] = sammle_bilanz_posten(lade_und_filtere_nach_jahr(bilanz, jahr))
        guv_posten[jahr] = sammle_guv_posten(lade_und_filtere_nach_jahr(guv, jahr))

    # Schritt 3: Kennzahlen für jedes Jahr berechnen
    ergebnisse = []
    for jahr in gemeinsame_jahre:
        # Vorjahr suchen (gibt es nicht, wenn es das älteste Jahr ist)
        vorjahr = vorjahr_von(jahr)
        bilanz_vorjahr = None
        guv_vorjahr = None
        if vorjahr in bilanz_posten:
            bilanz_vorjahr = bilanz_posten[vorjahr]
            guv_vorjahr = guv_posten[vorjahr]

        kennzahlen = berechne_kennzahlen(bilanz_posten[jahr], guv_posten[jahr], bilanz_vorjahr, guv_vorjahr)
        werte = uebersicht_werte(bilanz_posten[jahr], guv_posten[jahr], kennzahlen)

        ergebnisse.append({
            "gj": jahr,
            "werte": werte,
            "kennzahlen": kennzahlen,
        })

    return ergebnisse, None, gemeinsame_jahre


# ============================================================
# 8. Button "Finanzanalyse starten"
# ============================================================

def zeige_loader(sichtbar):
    loader = document.getElementById("loader")
    if loader:
        loader.style.display = "block" if sichtbar else "none"


@when("click", "#startButton")
def finanzanalyse_starten(event=None):
    output = document.getElementById("output")
    bilanz_el = document.getElementById("data-bilanz")
    guv_el = document.getElementById("data-guv")
    branche_el = document.getElementById("branche")

    if not output or not bilanz_el or not guv_el:
        print("FEHLER: HTML-Elemente nicht gefunden.")
        return

    bilanz_text = bilanz_el.textContent or ""
    guv_text = guv_el.textContent or ""

    fehler = pruefe_eingaben(bilanz_text, guv_text)
    if fehler:
        output.textContent = fehler
        return

    zeige_loader(True)
    output.textContent = "⏳ Analyse läuft..."

    try:
        bilanz = parse_csv(bilanz_text)
        guv = parse_csv(guv_text)

        if not bilanz:
            output.textContent = "⚠️ Bilanz-Datei ist leer oder ungültig."
            return
        if not guv:
            output.textContent = "⚠️ GuV-Datei ist leer oder ungültig."
            return

        ok_bilanz, msg_bilanz = pruefe_pflicht_spalten(
            bilanz,
            ["Bilanzposition", "Kategorie", "Unterkategorie", "Betrag_EUR", "Seite"],
            "Bilanz",
        )
        ok_guv, msg_guv = pruefe_pflicht_spalten(
            guv,
            ["position", "Kategorie", "Betrag_EUR"],
            "GuV",
        )

        if not ok_bilanz or not ok_guv:
            output.textContent = f"{msg_bilanz}\n{msg_guv}"
            return

        if not hat_jahr_spalte(bilanz):
            output.textContent = "Bilanz FEHLER: Spalte GJ/Geschaeftsjahr/Geschäftsjahr fehlt"
            return
        if not hat_jahr_spalte(guv):
            output.textContent = "GuV FEHLER: Spalte GJ/Geschaeftsjahr/Geschäftsjahr fehlt"
            return

        ergebnisse, analyse_fehler, gemeinsame_jahre = analysiere_alle_jahre(bilanz, guv)
        if analyse_fehler:
            output.textContent = analyse_fehler
            return

        spalten_bilanz = list(bilanz[0].keys())
        spalten_guv = list(guv[0].keys())
        output.textContent = (
            "✅ Dateien erfolgreich geladen\n"
            f"Bilanz: {len(bilanz)} Zeile(n), Spalten: {', '.join(spalten_bilanz)}\n"
            f"GuV:    {len(guv)} Zeile(n), Spalten: {', '.join(spalten_guv)}\n"
            f"GJ gefunden: {', '.join(gemeinsame_jahre)}"
        )

        ergebnisse_json = json.dumps(ergebnisse)
        encoded_results = window.encodeURIComponent(ergebnisse_json)
        branche = ""
        if branche_el:
            branche = branche_el.value or ""
        encoded_branche = window.encodeURIComponent(branche)
        window.location.href = f"index2.html?v={VERSION}&results={encoded_results}&branche={encoded_branche}"

    except Exception as e:
        output.textContent = f"❌ Fehler: {e}"
    finally:
        zeige_loader(False)
