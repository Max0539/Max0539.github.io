from pyscript import document, when, window
import csv
from datetime import datetime

AKTUELLES_JAHR = datetime.now().year


def parse_csv(text):
    """Liest CSV-Text (Semikolon-getrennt) und gibt eine Liste von Dictionaries zurück."""
    clean = (text or "").strip().lstrip("\ufeff")
    if not clean:
        return []
    reader = csv.DictReader(clean.splitlines(), delimiter=";")
    # Spaltennamen trimmen damit Leerzeichen im CSV keinen Fehler auslösen
    reader.fieldnames = [f.strip() for f in reader.fieldnames] if reader.fieldnames else []
    return list(reader)


def lade_und_filtere(daten, jahr):
    """Filtert nach Geschäftsjahr. Gibt alle zurück wenn kein Treffer."""
    gefiltert = [
        z for z in daten
        if z.get("Geschaeftsjahr", z.get("Geschäftsjahr", "")).strip() == str(jahr)
    ]
    return gefiltert if gefiltert else daten


def zeige_loader(sichtbar):
    """Zeigt oder versteckt das Ladesymbol."""
    loader = document.getElementById("loader")
    if loader:
        loader.style.display = "block" if sichtbar else "none"


@when("click", "#startButton")
def Finanzanalyse_starten(event=None):
    """Wird beim Klick auf den Start-Button aufgerufen."""
    output    = document.getElementById("output")
    bilanz_el = document.getElementById("data-bilanz")
    guv_el    = document.getElementById("data-guv")

    if not output or not bilanz_el or not guv_el:
        print("FEHLER: HTML-Elemente nicht gefunden.")
        return

    bilanz_text = bilanz_el.textContent or ""
    guv_text    = guv_el.textContent or ""

    if not bilanz_text.strip() and not guv_text.strip():
        output.textContent = "⚠️ Bitte Bilanz- und GuV-Datei hochladen."
        return
    if not bilanz_text.strip():
        output.textContent = "⚠️ Bitte die Bilanz-Datei hochladen."
        return
    if not guv_text.strip():
        output.textContent = "⚠️ Bitte die GuV-Datei hochladen."
        return

    zeige_loader(True)
    output.textContent = "⏳ Analyse läuft..."

    try:
        bilanz = parse_csv(bilanz_text)
        guv    = parse_csv(guv_text)

        if not bilanz:
            output.textContent = "⚠️ Bilanz-Datei ist leer oder ungültig."
            return
        if not guv:
            output.textContent = "⚠️ GuV-Datei ist leer oder ungültig."
            return

        bilanz = lade_und_filtere(bilanz, AKTUELLES_JAHR)
        guv    = lade_und_filtere(guv, AKTUELLES_JAHR)

        ok_bilanz, msg_bilanz = Format_Prüfung_Bilanz(bilanz)
        ok_guv,    msg_guv    = Format_Prüfung_GuV(guv)

        if not ok_bilanz or not ok_guv:
            output.textContent = f"{msg_bilanz}\n{msg_guv}"
            return

        spalten_bilanz = list(bilanz[0].keys()) if bilanz else []
        spalten_guv    = list(guv[0].keys())    if guv    else []

        output.textContent = (
            "✅ Dateien erfolgreich geladen\n"
            f"Bilanz: {len(bilanz)} Zeile(n), Spalten: {', '.join(spalten_bilanz)}\n"
            f"GuV:    {len(guv)} Zeile(n), Spalten: {', '.join(spalten_guv)}"
        )

        eq_msg, ek, vb = eigenkapitalquote(bilanz)
        encoded_msg = window.encodeURIComponent(eq_msg)
        window.location.href = f"index2.html?eq_msg={encoded_msg}&ek={ek}&vb={vb}"

    except Exception as e:
        output.textContent = f"❌ Fehler: {e}"
    finally:
        zeige_loader(False)

def parse_betrag(wert):
    """Wandelt deutsches Zahlenformat (1.234,56) in float um."""
    s = (wert or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0

def eigenkapitalquote(bilanz):
    ek = sum(parse_betrag(z["Betrag_EUR"]) for z in bilanz if z.get("Kategorie", "").strip() == "Eigenkapital")
    vb = sum(parse_betrag(z["Betrag_EUR"]) for z in bilanz if z.get("Kategorie", "").strip() == "Verbindlichkeiten")
    if vb == 0:
        return "Eigenkapitalquote: Keine Verbindlichkeiten gefunden.", 0, 0
    quote = ek / vb
    return f"Die Eigenkapitalquote betr\u00e4gt {quote:.2f}", ek, vb

def Format_Prüfung_Bilanz(bilanz):
    """Prüft ob die Bilanz die richtigen Spalten hat."""
    pflicht_spalten = ["Bilanzposition", "Kategorie", "Unterkategorie", "Betrag_EUR", "Seite", "GJ"]
    vorhandene_spalten = list(bilanz[0].keys()) if bilanz else []

    fehlende = [s for s in pflicht_spalten if s not in vorhandene_spalten]

    if fehlende:
        return False, f"Bilanz FEHLER: Spalten fehlen: {', '.join(fehlende)}"
    return True, "Bilanz OK"

def Format_Prüfung_GuV(guv):
    """Prüft ob die GuV die richtigen Spalten hat."""
    pflicht_spalten = ["position", "Kategorie", "Betrag_EUR", "GJ"]
    vorhandene_spalten = list(guv[0].keys()) if guv else []

    fehlende = [s for s in pflicht_spalten if s not in vorhandene_spalten]

    if fehlende:
        return False, f"GuV FEHLER: Spalten fehlen: {', '.join(fehlende)}"
    return True, "GuV OK"
