from pyscript import document, when, window
import csv
import json
from datetime import datetime

AKTUELLES_JAHR = datetime.now().year


def parse_csv(text):
    """Liest CSV-Text (Semikolon-getrennt) und gibt eine Liste von Dictionaries zurück."""
    csv_text = (text or "").strip().lstrip("\ufeff")
    if not csv_text:
        return []

    reader = csv.DictReader(csv_text.splitlines(), delimiter=";")
    if reader.fieldnames:
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
    return list(reader)


def parse_betrag(wert):
    """Wandelt deutsches Zahlenformat (1.234,56) in float um."""
    text = (wert or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def lade_und_filtere_nach_jahr(daten, jahr):
    """Filtert strikt nach GJ und gibt nur passende Zeilen zurück."""
    gefiltert = []
    for zeile in daten:
        gj = zeile.get("GJ", "").strip()
        if gj == str(jahr):
            gefiltert.append(zeile)
    return gefiltert


def hole_gj_liste(daten):
    """Liefert alle vorhandenen GJ-Werte ohne Duplikate, absteigend sortiert."""
    jahre = []
    for zeile in daten:
        gj = zeile.get("GJ", "").strip()
        if gj and gj not in jahre:
            jahre.append(gj)
    jahre.sort(reverse=True)
    return jahre


def zeige_loader(sichtbar):
    """Zeigt oder versteckt das Ladesymbol."""
    loader = document.getElementById("loader")
    if loader:
        loader.style.display = "block" if sichtbar else "none"


def pruefe_pflicht_spalten(daten, pflicht_spalten, name):
    """Prüft, ob alle Pflichtspalten vorhanden sind."""
    vorhandene_spalten = list(daten[0].keys()) if daten else []
    fehlende = [spalte for spalte in pflicht_spalten if spalte not in vorhandene_spalten]

    if fehlende:
        return False, f"{name} FEHLER: Spalten fehlen: {', '.join(fehlende)}"
    return True, f"{name} OK"


def pruefe_eingaben(bilanz_text, guv_text):
    """Validiert, ob Bilanz- und GuV-Text vorhanden sind."""
    hat_bilanz = bool((bilanz_text or "").strip())
    hat_guv = bool((guv_text or "").strip())

    if not hat_bilanz and not hat_guv:
        return "⚠️ Bitte Bilanz- und GuV-Datei hochladen."
    if not hat_bilanz:
        return "⚠️ Bitte die Bilanz-Datei hochladen."
    if not hat_guv:
        return "⚠️ Bitte die GuV-Datei hochladen."
    return None


def eigenkapitalquote(bilanz):
    eigenkapital = 0.0
    bilanzsumme_aktiva = 0.0

    for zeile in bilanz:
        betrag = parse_betrag(zeile.get("Betrag_EUR", "0"))

        if zeile.get("Kategorie", "").strip() == "Eigenkapital":
            eigenkapital += betrag

        if zeile.get("Seite", "").strip().lower() == "aktiva":
            bilanzsumme_aktiva += betrag

    if bilanzsumme_aktiva == 0:
        return "Eigenkapitalquote: Keine Aktiva-Bilanzsumme gefunden.", 0, 0

    quote = (eigenkapital / bilanzsumme_aktiva) * 100
    return f"Die Eigenkapitalquote beträgt {quote:.2f}%", eigenkapital, bilanzsumme_aktiva


def pruefe_bilanzsummen(bilanz, toleranz=0.01):
    """Prüft, ob die Summe von Aktiva und Passiva übereinstimmt."""
    summe_aktiva = 0.0
    summe_passiva = 0.0

    for zeile in bilanz:
        betrag = parse_betrag(zeile.get("Betrag_EUR", "0"))
        seite = zeile.get("Seite", "").strip().lower()

        if seite == "aktiva":
            summe_aktiva += betrag
        elif seite == "passiva":
            summe_passiva += betrag

    stimmt = abs(summe_aktiva - summe_passiva) <= toleranz
    return stimmt, summe_aktiva, summe_passiva


@when("click", "#startButton")
def finanzanalyse_starten(event=None):
    """Startet die Analyse nach Klick auf den Button."""
    output = document.getElementById("output")
    bilanz_el = document.getElementById("data-bilanz")
    guv_el = document.getElementById("data-guv")

    if not output or not bilanz_el or not guv_el:
        print("FEHLER: HTML-Elemente nicht gefunden.")
        return

    bilanz_text = bilanz_el.textContent or ""
    guv_text = guv_el.textContent or ""

    eingabe_fehler = pruefe_eingaben(bilanz_text, guv_text)
    if eingabe_fehler:
        output.textContent = eingabe_fehler
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
            ["Bilanzposition", "Kategorie", "Unterkategorie", "Betrag_EUR", "Seite", "GJ"],
            "Bilanz",
        )
        ok_guv, msg_guv = pruefe_pflicht_spalten(
            guv,
            ["position", "Kategorie", "Betrag_EUR", "GJ"],
            "GuV",
        )

        if not ok_bilanz or not ok_guv:
            output.textContent = f"{msg_bilanz}\n{msg_guv}"
            return

        bilanz_jahre = hole_gj_liste(bilanz)
        guv_jahre = hole_gj_liste(guv)
        gemeinsame_jahre = [jahr for jahr in bilanz_jahre if jahr in guv_jahre]

        if not gemeinsame_jahre:
            output.textContent = "⚠️ Keine gemeinsamen GJ-Daten in Bilanz und GuV gefunden."
            return

        ergebnisse = []

        for jahr in gemeinsame_jahre:
            bilanz_jahr = lade_und_filtere_nach_jahr(bilanz, jahr)
            guv_jahr = lade_und_filtere_nach_jahr(guv, jahr)

            if not bilanz_jahr or not guv_jahr:
                continue

            summen_ok, _, _ = pruefe_bilanzsummen(bilanz_jahr)
            if not summen_ok:
                output.textContent = "bilanzsummen stimmen nicht überein"
                return

            eq_msg, ek, bs = eigenkapitalquote(bilanz_jahr)
            ergebnisse.append({
                "gj": jahr,
                "msg": eq_msg,
                "ek": ek,
                "bs": bs,
            })

        if not ergebnisse:
            output.textContent = "⚠️ Keine auswertbaren Daten nach GJ-Filterung gefunden."
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
        encoded_ergebnisse = window.encodeURIComponent(ergebnisse_json)
        window.location.href = f"index2.html?results={encoded_ergebnisse}"

    except Exception as fehler:
        output.textContent = f"❌ Fehler: {fehler}"
    finally:
        zeige_loader(False)


def Format_Prüfung_Bilanz(bilanz):
    """Kompatible Wrapper-Funktion für Bilanzprüfung."""
    return pruefe_pflicht_spalten(
        bilanz,
        ["Bilanzposition", "Kategorie", "Unterkategorie", "Betrag_EUR", "Seite", "GJ"],
        "Bilanz",
    )


def Format_Prüfung_GuV(guv):
    """Kompatible Wrapper-Funktion für GuV-Prüfung."""
    return pruefe_pflicht_spalten(
        guv,
        ["position", "Kategorie", "Betrag_EUR", "GJ"],
        "GuV",
    )
