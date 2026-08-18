from pyscript import document
from pyodide.ffi import create_proxy
import csv
from datetime import datetime

AKTUELLES_JAHR = datetime.now().year

daten=[
    "Bilanzposition;Kategorie;Unterkategorie;Betrag_EUR;Seite;Geschaeftsjahr",
    "Immaterielle Vermögensgegenstände;Anlagevermögen;Immaterielle Vermögensgegenstände;25000;Aktiva;2026",
    "Grundstücke und Gebäude;Anlagevermögen;Sachanlagen;450000;Aktiva;2026",
    "Technische Anlagen und Maschinen;Anlagevermögen;Sachanlagen;180000;Aktiva;2026",
    "Betriebs- und Geschäftsausstattung;Anlagevermögen;Sachanlagen;75000;Aktiva;2026",
    "Beteiligungen;Finanzanlagen;Beteiligungen;50000;Aktiva;2026",
    "Vorräte;Umlaufvermögen;Vorräte;120000;Aktiva;2025",
    "Forderungen aus Lieferungen und Leistungen;Umlaufvermögen;Forderungen;95000;Aktiva;2025",
    "Sonstige Vermögensgegenstände;Umlaufvermögen;Forderungen;30000;Aktiva;2025",
    "Bankguthaben;Umlaufvermögen;Liquide Mittel;175000;Aktiva;2025",
    "Kassenbestand;Umlaufvermögen;Liquide Mittel;10000;Aktiva;2025",
    "Aktive Rechnungsabgrenzungsposten;Rechnungsabgrenzung;Aktive RAP;15000;Aktiva;2025",
    "Gezeichnetes Kapital;Eigenkapital;Stammkapital;100000;Passiva;2025",
    "Kapitalrücklage;Eigenkapital;Kapitalrücklage;50000;Passiva;2025",
    "Gewinnrücklagen;Eigenkapital;Gewinnrücklagen;180000;Passiva;2025",
    "Rückstellungen für Pensionen;Rückstellungen;Pensionsrückstellungen;60000;Passiva;2025",
    "Sonstige Rückstellungen;Rückstellungen;Sonstige Rückstellungen;85000;Passiva;2025",
    "Verbindlichkeiten gegenüber Kreditinstituten;Verbindlichkeiten;Bankdarlehen;300000;Passiva;2025",
    "Verbindlichkeiten aus Lieferungen und Leistungen;Verbindlichkeiten;Lieferantenverbindlichkeiten;95000;Passiva;2025",
    "Sonstige Verbindlichkeiten;Verbindlichkeiten;Sonstige Verbindlichkeiten;40000;Passiva;2025",
    "Passive Rechnungsabgrenzungsposten;Rechnungsabgrenzung;Passive RAP;10000;Passiva;2025",
]


from pyscript import document
import csv
from datetime import datetime

AKTUELLES_JAHR = datetime.now().year


def parse_csv(text):
    # CSV lesen (Semikolon)
    clean_text = (text or "").strip().lstrip("\ufeff")
    if not clean_text:
        return []
    reader = csv.DictReader(clean_text.splitlines(), delimiter=";")
    return list(reader)


def lade_und_filtere(daten, jahr):
    # Nach Jahr filtern; wenn kein Treffer -> alle Daten zurück
    gefiltert = [
        z for z in daten
        if z.get("Geschaeftsjahr", z.get("Geschäftsjahr", "")).strip() == str(jahr)
    ]
    return gefiltert if gefiltert else daten


def zeige_loader(sichtbar):
    loader = document.getElementById("loader")
    if loader:
        loader.style.display = "block" if sichtbar else "none"


def Finanzanalyse_starten(event=None):
    output = document.getElementById("output")
    bilanz_el = document.getElementById("data-bilanz")
    guv_el = document.getElementById("data-guv")

    if not output or not bilanz_el or not guv_el:
        print("FEHLER: HTML-Elemente nicht gefunden.")
        return

    bilanz_text = bilanz_el.textContent or ""
    guv_text = guv_el.textContent or ""

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
        guv = parse_csv(guv_text)

        if not bilanz:
            output.textContent = "⚠️ Bilanz-Datei ist leer oder ungültig."
            return
        if not guv:
            output.textContent = "⚠️ GuV-Datei ist leer oder ungültig."
            return

        bilanz = lade_und_filtere(bilanz, AKTUELLES_JAHR)
        guv = lade_und_filtere(guv, AKTUELLES_JAHR)

        spalten_bilanz = list(bilanz[0].keys()) if bilanz else []
        spalten_guv = list(guv[0].keys()) if guv else []

        output.textContent = (
            "✅ Dateien erfolgreich geladen\n"
            f"Bilanz: {len(bilanz)} Zeile(n), Spalten: {', '.join(spalten_bilanz)}\n"
            f"GuV:    {len(guv)} Zeile(n), Spalten: {', '.join(spalten_guv)}"
        )
    except Exception as e:
        output.textContent = f"❌ Fehler bei der Analyse: {e}"
    finally:
        zeige_loader(False)



def Test():
    try:
        
