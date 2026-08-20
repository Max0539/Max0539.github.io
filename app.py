from pyscript import document, when, window
import csv
import json
from datetime import datetime

AKTUELLES_JAHR = datetime.now().year


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


def hole_guv_seite(zeile):
    """Liest haben/soll aus der GuV-Zeile, mit einfachem Fallback."""
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
        "Freumdkapital": fremdkapital,
        "Cash": cash,
    }


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

        ergebnisse.append(
            {
                "gj": jahr,
                "msg": eq_msg,
                "ek": eigenkapital,
                "bs": bilanzsumme_aktiva,
                "overview": overview,
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
        encoded = window.encodeURIComponent(ergebnisse_json)
        window.location.href = f"index2.html?results={encoded}"

    except Exception as e:
        output.textContent = f"❌ Fehler: {e}"
    finally:
        zeige_loader(False)


def Finanzanalyse_starten(event=None):
    """Kompatibilität für bestehendes py-click im HTML."""
    finanzanalyse_starten(event)


def Format_Prüfung_Bilanz(bilanz):
    """Kompatibler Wrapper für alte Aufrufe."""
    return pruefe_pflicht_spalten(
        bilanz,
        ["Bilanzposition", "Kategorie", "Unterkategorie", "Betrag_EUR", "Seite"],
        "Bilanz",
    )


def Format_Prüfung_GuV(guv):
    """Kompatibler Wrapper für alte Aufrufe."""
    return pruefe_pflicht_spalten(
        guv,
        ["position", "Kategorie", "Betrag_EUR"],
        "GuV",
    )
