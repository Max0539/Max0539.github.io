from pyscript import document, when, window
import csv
import json
from datetime import datetime

AKTUELLES_JAHR = datetime.now().year
# Bei jeder neuen Version erhöhen (auch in index.html), damit Browser keine alten Dateien aus dem Cache laden
VERSION = "45"


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


def ist_zusatzangabe(zeile):
    """Zeilen mit Kategorie "Zusatzangaben" gehören nicht zur GuV-Rechnung
    (z. B. Tilgung, Entnahmen, Investitionen für die Kapitaldienstfähigkeit)."""
    return "zusatz" in normalisiere_text(zeile.get("Kategorie", ""))


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


def zeige_loader(sichtbar):
    loader = document.getElementById("loader")
    if loader:
        loader.style.display = "block" if sichtbar else "none"


def eigenkapitalquote(bilanz_jahr):
    eigenkapital = 0.0
    bilanzsumme_aktiva = 0.0

    for zeile in bilanz_jahr:
        betrag = parse_betrag(zeile.get("Betrag_EUR", "0"))
        kategorie = text_klein(zeile, "Kategorie")
        seite = text_klein(zeile, "Seite")

        if kategorie == "eigenkapital":
            eigenkapital += betrag
        if seite == "aktiva":
            bilanzsumme_aktiva += betrag

    if bilanzsumme_aktiva == 0:
        return "Eigenkapitalquote: Keine Aktiva-Bilanzsumme gefunden.", 0.0, 0.0

    quote = (eigenkapital / bilanzsumme_aktiva) * 100
    return f"Die Eigenkapitalquote beträgt {quote:.2f}%", eigenkapital, bilanzsumme_aktiva


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


def baue_financel_overview(bilanz_jahr, guv_jahr, bilanzsumme_aktiva, eigenkapital):
    umsatz = 0.0
    haben = 0.0
    soll = 0.0

    for zeile in guv_jahr:
        betrag = parse_betrag(zeile.get("Betrag_EUR", "0"))
        seite = hole_guv_seite(zeile)

        if seite == "haben":
            umsatz += betrag
            haben += betrag
        elif seite == "soll":
            soll += betrag

    jahresergebnis = haben - soll
    if jahresergebnis >= 0:
        jahresueberschuss_text = f"Gewinn[{jahresergebnis:.2f}]"
    else:
        jahresueberschuss_text = f"Verlust[{abs(jahresergebnis):.2f}]"

    passiva_summe = 0.0
    cash = 0.0

    for zeile in bilanz_jahr:
        betrag = parse_betrag(zeile.get("Betrag_EUR", "0"))
        seite = text_klein(zeile, "Seite")
        unterkategorie = normalisiere_text(zeile.get("Unterkategorie", ""))

        if seite == "passiva":
            passiva_summe += betrag
        if "liquide mittel" in unterkategorie:
            cash += betrag

    fremdkapital = passiva_summe - eigenkapital
    if fremdkapital < 0:
        fremdkapital = 0.0

    return {
        "Gesamtumsatz": umsatz,
        "EBITA": 0.0,
        "Jahresüberschuss": jahresueberschuss_text,
        "Bilanzsumme": bilanzsumme_aktiva,
        "Eigenkapital": eigenkapital,
        "Fremdkapital": fremdkapital,
        "Cash": cash,
    }


def ist_lul(text):
    """Erkennt Positionen aus Lieferungen und Leistungen."""
    return "lul" in text or "l+l" in text or "lieferungen und leistungen" in text


def sammle_bilanz_posten(bilanz_jahr):
    """Summiert die für die Kennzahlen benötigten Bilanzposten eines Jahres.

    Langfristiges Fremdkapital: Wenn eine Spalte "Fristigkeit" (kurz/lang) vorhanden ist,
    wird sie verwendet. Sonst gelten Darlehen/Bankverbindlichkeiten und
    Pensionsrückstellungen als langfristig, alles andere als kurzfristig.
    """
    p = {
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
        betrag = parse_betrag(zeile.get("Betrag_EUR", "0"))
        seite = text_klein(zeile, "Seite")
        kategorie = normalisiere_text(zeile.get("Kategorie", ""))
        unterkategorie = normalisiere_text(zeile.get("Unterkategorie", ""))
        position = normalisiere_text(zeile.get("Bilanzposition", ""))
        fristigkeit = normalisiere_text(zeile.get("Fristigkeit", "") or "")

        if seite == "aktiva":
            p["bilanzsumme"] += betrag
            if "anlageverm" in kategorie or "finanzanlage" in kategorie:
                p["anlagevermoegen"] += betrag
            elif "umlaufverm" in kategorie:
                p["umlaufvermoegen"] += betrag
                if "liquide mittel" in unterkategorie:
                    p["liquide_mittel"] += betrag
                if "vorraete" in unterkategorie or "vorraete" in position:
                    p["vorraete"] += betrag
                if "forderung" in unterkategorie:
                    p["forderungen"] += betrag
                    if ist_lul(position):
                        p["forderungen_lul"] += betrag

        elif seite == "passiva":
            if kategorie == "eigenkapital":
                p["eigenkapital"] += betrag
                continue

            p["fremdkapital"] += betrag
            ist_langfristig = False

            if "rueckstellung" in kategorie:
                p["rueckstellungen"] += betrag
                if "pension" in unterkategorie or "pension" in position:
                    ist_langfristig = True

            if "verbindlichkeit" in kategorie:
                p["verbindlichkeiten"] += betrag
                ist_bank = "bank" in unterkategorie or "bank" in position or "kreditinstitut" in position
                ist_darlehen = "darlehen" in unterkategorie or "darlehen" in position or "anleihe" in position
                if ist_bank:
                    p["bankverbindlichkeiten"] += betrag
                if ist_bank or ist_darlehen:
                    p["finanzverbindlichkeiten"] += betrag
                    ist_langfristig = True
                if "lieferant" in unterkategorie or ist_lul(position):
                    p["verbindlichkeiten_lul"] += betrag

            if fristigkeit:
                ist_langfristig = "lang" in fristigkeit
            if ist_langfristig:
                p["langfr_fk"] += betrag

    # Ohne LuL-Kennzeichnung alle Forderungen für das Debitorenziel verwenden
    if p["forderungen_lul"] == 0:
        p["forderungen_lul"] = p["forderungen"]

    p["kurzfr_fk"] = p["fremdkapital"] - p["langfr_fk"]
    return p


def sammle_guv_posten(guv_jahr):
    """Summiert die für die Kennzahlen benötigten GuV-Posten eines Jahres."""
    p = {
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
        # Zusatzangaben: None = nicht angegeben
        "tilgung": None,
        "entnahmen": None,
        "investitionen": None,
    }

    for zeile in guv_jahr:
        betrag = parse_betrag(zeile.get("Betrag_EUR", "0"))
        seite = hole_guv_seite(zeile)
        position = normalisiere_text(zeile.get("position", "") or zeile.get("Position", ""))

        if ist_zusatzangabe(zeile):
            if "tilgung" in position:
                schluessel = "tilgung"
            elif "entnahme" in position or "ausschuettung" in position:
                schluessel = "entnahmen"
            elif "investition" in position:
                schluessel = "investitionen"
            else:
                continue
            p[schluessel] = (p[schluessel] or 0.0) + betrag
            continue

        if seite == "haben":
            p["ertraege"] += betrag
            if "umsatz" in position:
                p["umsatz"] += betrag
            if "bestandsver" in position:
                p["bestandsveraenderung"] += betrag
            if "eigenleistung" in position:
                p["eigenleistungen"] += betrag
        elif seite == "soll":
            p["aufwendungen"] += betrag
            if "bestandsver" in position:
                p["bestandsveraenderung"] -= betrag
            elif "material" in position:
                p["materialaufwand"] += betrag
            elif "personal" in position:
                p["personalaufwand"] += betrag
            elif "abschreibung" in position:
                p["abschreibungen"] += betrag
            elif "zins" in position:
                p["zinsaufwand"] += betrag
            elif "steuer" in position and "sonstige steuer" not in position:
                p["steuern"] += betrag

    if p["umsatz"] == 0:
        p["umsatz"] = p["ertraege"]

    p["jahresueberschuss"] = p["ertraege"] - p["aufwendungen"]
    p["ebt"] = p["jahresueberschuss"] + p["steuern"]
    p["ebit"] = p["ebt"] + p["zinsaufwand"]
    p["ebitda"] = p["ebit"] + p["abschreibungen"]
    p["gesamtleistung"] = p["umsatz"] + p["bestandsveraenderung"] + p["eigenleistungen"]
    return p


def teile(zaehler, nenner):
    if zaehler is None or nenner is None or nenner == 0:
        return None
    return zaehler / nenner


def durchschnitt(aktuell, vorjahr):
    """Durchschnittsbestand, wenn ein Vorjahr vorhanden ist, sonst Stichtagswert."""
    if vorjahr is None:
        return aktuell
    return (aktuell + vorjahr) / 2


def berechne_kennzahlen(b, g, vb=None, vg=None):
    """Berechnet alle Kennzahlen aus Bilanz (b) und GuV (g), optional mit Vorjahr (vb, vg).

    Rückgabe: {ID: {"w": Wert oder None, "h": Hinweis, "a": erzwungene Ampel}}
    Prozentwerte werden als Anteil (0.25 = 25 %) geliefert.
    """
    k = {}

    def setze(kid, wert, hinweis="", ampel=""):
        eintrag = {"w": None if wert is None else round(wert, 6)}
        if hinweis:
            eintrag["h"] = hinweis
        if ampel:
            eintrag["a"] = ampel
        k[kid] = eintrag

    ek = b["eigenkapital"]
    bs = b["bilanzsumme"]
    fk = b["fremdkapital"]
    av = b["anlagevermoegen"]
    kfk = b["kurzfr_fk"]
    umsatz = g["umsatz"]
    gl = g["gesamtleistung"]

    # Kapitalstruktur
    setze("K01", teile(ek, bs))
    setze("K02", teile(fk, bs))
    if ek > 0:
        setze("K03", teile(fk, ek))
    else:
        setze("K03", None, "Eigenkapital ≤ 0", "rot")
    setze("K04", teile(av, bs))
    setze("K05", teile(ek, av))
    setze("K06", teile(ek + b["langfr_fk"], av))
    setze("K07", teile(b["bankverbindlichkeiten"], bs))
    setze("K08", teile(b["finanzverbindlichkeiten"] - b["liquide_mittel"], bs))

    # Rentabilität
    setze("R01", teile(g["ebt"], gl))
    setze("R02", teile(g["ebt"] + g["zinsaufwand"], bs))
    if ek > 0:
        setze("R03", teile(g["ebt"], ek))
    else:
        setze("R03", None, "Eigenkapital ≤ 0", "rot")
    setze("R04", teile(g["ebitda"], umsatz))
    setze("R05", teile(g["personalaufwand"], gl))
    setze("R06", teile(g["materialaufwand"], gl))
    if vg and vg["umsatz"] > 0:
        setze("R07", umsatz / vg["umsatz"] - 1)
    else:
        setze("R07", None, "Vorjahr fehlt")

    # Cashflow & Kapitaldienst
    cashflow = g["jahresueberschuss"] + g["abschreibungen"]
    cf_hinweis = ""
    if vb is not None:
        cashflow += b["rueckstellungen"] - vb["rueckstellungen"]
    else:
        cf_hinweis = "Vereinfacht ohne Vorjahr (ohne Veränderung der Rückstellungen)"
    setze("C01", cashflow, cf_hinweis)
    setze("C02", teile(cashflow, umsatz), cf_hinweis)
    if cashflow > 0:
        netto_schulden = max(b["verbindlichkeiten"] - b["liquide_mittel"], 0.0)
        setze("C03", netto_schulden / cashflow, cf_hinweis)
    else:
        setze("C03", None, "Cashflow ≤ 0", "rot")
    if g["zinsaufwand"] > 0:
        setze("C04", teile(g["ebit"], g["zinsaufwand"]))
    else:
        setze("C04", None, "Kein Zinsaufwand")

    # Kapitaldienstfähigkeit (braucht Zusatzangaben in der GuV-Datei)
    zins = g["zinsaufwand"]
    tilgung = g["tilgung"]
    if g["entnahmen"] is None or g["investitionen"] is None:
        kdg = None
        setze("C05", None, "Zusatzangaben Entnahmen/Ausschüttungen und Investitionen fehlen")
    else:
        erweiterter_cashflow = cashflow + zins - g["entnahmen"]
        kdg = erweiterter_cashflow - g["investitionen"]
        setze("C05", kdg, cf_hinweis, "rot" if kdg <= 0 else "")

    if kdg is None or tilgung is None:
        setze("C06", None, "Zusatzangaben Tilgung, Entnahmen oder Investitionen fehlen")
    elif kdg <= 0:
        setze("C06", None, "Kapitaldienstgrenze ≤ 0", "rot")
    else:
        setze("C06", (zins + tilgung) / kdg, cf_hinweis)

    if tilgung is None:
        setze("C07", None, "Zusatzangabe Tilgung fehlt")
    else:
        setze("C07", teile(cashflow + zins, zins + tilgung), cf_hinweis)

    # Liquidität & Working Capital
    setze("L01", teile(b["liquide_mittel"], kfk))
    setze("L02", teile(b["liquide_mittel"] + b["forderungen"], kfk))
    setze("L03", teile(b["umlaufvermoegen"], kfk))
    setze("L04", teile(b["umlaufvermoegen"] - kfk, umsatz))

    tage_hinweis = "Durchschnittsbestand mit Vorjahr" if vb is not None else "Stichtagswert (kein Vorjahr)"
    vor = vb or {}
    dso = teile(durchschnitt(b["forderungen_lul"], vor.get("forderungen_lul")) * 360, umsatz)
    dio = teile(durchschnitt(b["vorraete"], vor.get("vorraete")) * 360, g["materialaufwand"])
    dpo = teile(durchschnitt(b["verbindlichkeiten_lul"], vor.get("verbindlichkeiten_lul")) * 360, g["materialaufwand"])
    setze("L05", dso, tage_hinweis)
    setze("L06", dio, tage_hinweis)
    setze("L07", dpo, tage_hinweis)
    if dso is not None and dio is not None and dpo is not None:
        setze("L08", dso + dio - dpo, tage_hinweis)
    else:
        setze("L08", None, "DSO, DIO oder DPO nicht berechenbar")

    return k


def vorjahr_von(jahr):
    try:
        return str(int(jahr) - 1)
    except ValueError:
        return ""


def analysiere_alle_jahre(bilanz, guv):
    bilanz_jahre = hole_gj_liste(bilanz)
    guv_jahre = hole_gj_liste(guv)

    gemeinsame_jahre = []
    for jahr in bilanz_jahre:
        if jahr in guv_jahre:
            gemeinsame_jahre.append(jahr)

    if not gemeinsame_jahre:
        return None, "⚠️ Keine gemeinsamen GJ-Daten in Bilanz und GuV gefunden.", []

    ergebnisse = []
    bilanz_posten = {}
    guv_posten = {}
    for jahr in gemeinsame_jahre:
        bilanz_posten[jahr] = sammle_bilanz_posten(lade_und_filtere_nach_jahr(bilanz, jahr))
        guv_posten[jahr] = sammle_guv_posten(lade_und_filtere_nach_jahr(guv, jahr))

    for jahr in gemeinsame_jahre:
        bilanz_jahr = lade_und_filtere_nach_jahr(bilanz, jahr)
        guv_jahr = lade_und_filtere_nach_jahr(guv, jahr)

        if not bilanz_jahr or not guv_jahr:
            continue

        if not pruefe_bilanzsumme_fuer_jahr(bilanz_jahr):
            return None, "bilanzsummen stimmen nicht überein", gemeinsame_jahre

        eq_msg, eigenkapital, bilanzsumme_aktiva = eigenkapitalquote(bilanz_jahr)
        overview = baue_financel_overview(
            bilanz_jahr,
            guv_jahr,
            bilanzsumme_aktiva,
            eigenkapital,
        )

        vorjahr = vorjahr_von(jahr)
        kennzahlen = berechne_kennzahlen(
            bilanz_posten[jahr],
            guv_posten[jahr],
            bilanz_posten.get(vorjahr),
            guv_posten.get(vorjahr),
        )

        ergebnisse.append(
            {
                "gj": jahr,
                "msg": eq_msg,
                "ek": eigenkapital,
                "bs": bilanzsumme_aktiva,
                "overview": overview,
                "kennzahlen": kennzahlen,
            }
        )

    if not ergebnisse:
        return None, "⚠️ Keine auswertbaren Daten nach GJ-Filterung gefunden.", gemeinsame_jahre

    return ergebnisse, None, gemeinsame_jahre


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

def Finanzanalyse_starten(event=None):
    finanzanalyse_starten(event)

def Format_Prüfung_Bilanz(bilanz):
    return pruefe_pflicht_spalten(
        bilanz,
        ["Bilanzposition", "Kategorie", "Unterkategorie", "Betrag_EUR", "Seite"],
        "Bilanz",
    )

def Format_Prüfung_GuV(guv):
    return pruefe_pflicht_spalten(
        guv,
        ["position", "Kategorie", "Betrag_EUR"],
        "GuV",
    )
