from pyscript import document
import csv
import asyncio
from datetime import datetime

AKTUELLES_JAHR = datetime.now().year

daten=["Bilanzposition;Kategorie;Unterkategorie;Betrag_EUR;Seite;Geschaeftsjahr"
"Immaterielle Vermögensgegenstände;Anlagevermögen;Immaterielle Vermögensgegenstände;25000;Aktiva;2025"
 "Grundstücke und Gebäude;Anlagevermögen;Sachanlagen;450000;Aktiva;2025"
 "Technische Anlagen und Maschinen;Anlagevermögen;Sachanlagen;180000;Aktiva;2025"
 "Betriebs- und Geschäftsausstattung;Anlagevermögen;Sachanlagen;75000;Aktiva;2025"
 "Beteiligungen;Finanzanlagen;Beteiligungen;50000;Aktiva;2025"
 "Vorräte;Umlaufvermögen;Vorräte;120000;Aktiva;2025"
 "Forderungen aus Lieferungen und Leistungen;Umlaufvermögen;Forderungen;95000;Aktiva;2025"
 "Sonstige Vermögensgegenstände;Umlaufvermögen;Forderungen;30000;Aktiva;2025"
 "Bankguthaben;Umlaufvermögen;Liquide Mittel;175000;Aktiva;2025"
 "Kassenbestand;Umlaufvermögen;Liquide Mittel;10000;Aktiva;2025"
 "Aktive Rechnungsabgrenzungsposten;Rechnungsabgrenzung;Aktive RAP;15000;Aktiva;2025"   
 "Gezeichnetes Kapital;Eigenkapital;Stammkapital;100000;Passiva;2025"
 "Kapitalrücklage;Eigenkapital;Kapitalrücklage;50000;Passiva;2025"
 "Gewinnrücklagen;Eigenkapital;Gewinnrücklagen;180000;Passiva;2025"
 "Rückstellungen für Pensionen;Rückstellungen;Pensionsrückstellungen;60000;Passiva;2025"
 "Sonstige Rückstellungen;Rückstellungen;Sonstige Rückstellungen;85000;Passiva;2025"
"Verbindlichkeiten gegenüber Kreditinstituten;Verbindlichkeiten;Bankdarlehen;300000;Passiva;2025"
"Verbindlichkeiten aus Lieferungen und Leistungen;Verbindlichkeiten;Lieferantenverbindlichkeiten;95000;Passiva;2025"
"Sonstige Verbindlichkeiten;Verbindlichkeiten;Sonstige Verbindlichkeiten;40000;Passiva;2025"
"Passive Rechnungsabgrenzungsposten;Rechnungsabgrenzung;Passive RAP;10000;Passiva;2025"
]

def parse_csv(text: str) -> list:
    reader = csv.DictReader(text.splitlines(), delimiter=";")
    return list(reader)


def lade_und_filtere(daten: list) -> list:
    return [z for z in daten if z.get("Geschaeftsjahr", z.get("Geschäftsjahr", "")) == str(AKTUELLES_JAHR)]
    


async def analyse_starten(event):
    bilanz_text = document.getElementById("data-bilanz").textContent
    guv_text    = document.getElementById("data-guv").textContent
    output      = document.getElementById("output")

    if not bilanz_text.strip() or not guv_text.strip():
        output.textContent = "Bitte Bilanz und GuV hochladen."
        return

    bilanz = parse_csv(bilanz_text)
    guv    = parse_csv(guv_text)

    output.textContent = "Analysiert Unternehmen..."
    await asyncio.sleep(3)
    output.textContent = "Prüft Liquidität..."
    await asyncio.sleep(2)

    bilanz = lade_und_filtere(bilanz)
    guv    = lade_und_filtere(guv)

    spalten_bilanz = list(bilanz[0].keys()) if bilanz else []
    spalten_guv    = list(guv[0].keys())    if guv    else []

    output.textContent = (
        f"\u2705 Dateien erfolgreich geladen ({AKTUELLES_JAHR})\n"
        f"Bilanz: {len(bilanz)} Zeile(n), Spalten: {', '.join(spalten_bilanz)}\n"
        f"GuV:    {len(guv)} Zeile(n), Spalten: {', '.join(spalten_guv)}\n"
    )


document.getElementById("startButton").addEventListener("click", analyse_starten)