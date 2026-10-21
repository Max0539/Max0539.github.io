from pyscript import document, when, window
import csv
import json


VERSION = "52"

JAHR_SPALTEN = ["GJ", "Geschaeftsjahr", "Geschäftsjahr"]
SEITE_SPALTEN = ["Seite", "seite", "SollHaben", "Soll/Haben"]
BILANZ_PFLICHT = ["Bilanzposition", "Kategorie", "Unterkategorie", "Betrag_EUR", "Seite"]
GUV_PFLICHT = ["position", "Kategorie", "Betrag_EUR"]


def parse_csv(text):
    inhalt = (text or "").strip().lstrip("﻿")
    if inhalt == "":
        return []

    reader = csv.DictReader(inhalt.splitlines(), delimiter=";")
    if reader.fieldnames:
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
    return list(reader)


def parse_betrag(wert):
    text = (wert or "").strip()
    text = text.replace(" ", "")
    text = text.replace("'", "")

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "")
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return 0.0


def normalisiere(text):
    text = (text or "").strip().lower()
    text = text.replace("ä", "ae")
    text = text.replace("ö", "oe")
    text = text.replace("ü", "ue")
    text = text.replace("ß", "ss")
    return text


def feld(zeile, spalte):
    return normalisiere(zeile.get(spalte, ""))


def enthaelt(text, woerter):
    for wort in woerter:
        if wort in text:
            return True
    return False


def hole_jahr(zeile):
    for spalte in JAHR_SPALTEN:
        wert = (zeile.get(spalte) or "").strip()
        if wert != "":
            return wert
    return ""


def hat_jahr_spalte(daten):
    for spalte in JAHR_SPALTEN:
        if spalte in daten[0]:
            return True
    return False


def zeilen_fuer_jahr(daten, jahr):
    ergebnis = []
    for zeile in daten:
        if hole_jahr(zeile) == jahr:
            ergebnis.append(zeile)
    return ergebnis


def alle_jahre(daten):
    jahre = []
    for zeile in daten:
        jahr = hole_jahr(zeile)
        if jahr != "" and jahr not in jahre:
            jahre.append(jahr)
    jahre.sort(reverse=True)
    return jahre


def vorjahr_von(jahr):
    if not jahr.isdigit():
        return ""
    return str(int(jahr) - 1)


def pruefe_eingaben(bilanz_text, guv_text):
    hat_bilanz = (bilanz_text or "").strip() != ""
    hat_guv = (guv_text or "").strip() != ""

    if not hat_bilanz and not hat_guv:
        return "⚠️ Bitte Bilanz- und GuV-Datei hochladen."
    if not hat_bilanz:
        return "⚠️ Bitte die Bilanz-Datei hochladen."
    if not hat_guv:
        return "⚠️ Bitte die GuV-Datei hochladen."
    return None


def fehlende_spalten(daten, pflicht_spalten):
    fehlende = []
    for spalte in pflicht_spalten:
        if spalte not in daten[0]:
            fehlende.append(spalte)
    return fehlende


def bilanz_geht_auf(bilanz_jahr):
    aktiva = 0.0
    passiva = 0.0
    for zeile in bilanz_jahr:
        betrag = parse_betrag(zeile.get("Betrag_EUR"))
        if feld(zeile, "Seite") == "aktiva":
            aktiva += betrag
        elif feld(zeile, "Seite") == "passiva":
            passiva += betrag
    return abs(aktiva - passiva) <= 0.01


def ist_lul(text):
    return enthaelt(text, ["lul", "l+l", "lieferungen und leistungen"])


def sammle_bilanz_posten(bilanz_jahr):
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
        betrag = parse_betrag(zeile.get("Betrag_EUR"))
        seite = feld(zeile, "Seite")
        kategorie = feld(zeile, "Kategorie")
        unterkategorie = feld(zeile, "Unterkategorie")
        position = feld(zeile, "Bilanzposition")
        fristigkeit = feld(zeile, "Fristigkeit")

        if seite == "aktiva":
            p["bilanzsumme"] += betrag

            if enthaelt(kategorie, ["anlageverm", "finanzanlage"]):
                p["anlagevermoegen"] += betrag
            elif "umlaufverm" in kategorie:
                p["umlaufvermoegen"] += betrag
                if "liquide" in unterkategorie or enthaelt(position, ["kasse", "bankguthaben", "guthaben bei kreditinstituten"]):
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
            langfristig = False

            if "rueckstellung" in kategorie:
                p["rueckstellungen"] += betrag
                if "pension" in unterkategorie or "pension" in position:
                    langfristig = True

            if "verbindlichkeit" in kategorie:
                p["verbindlichkeiten"] += betrag
                ist_bank = "bank" in unterkategorie or enthaelt(position, ["bank", "kreditinstitut"])
                ist_darlehen = "darlehen" in unterkategorie or enthaelt(position, ["darlehen", "anleihe"])

                if ist_bank:
                    p["bankverbindlichkeiten"] += betrag
                if ist_bank or ist_darlehen:
                    p["finanzverbindlichkeiten"] += betrag
                    langfristig = True
                if "lieferant" in unterkategorie or ist_lul(position):
                    p["verbindlichkeiten_lul"] += betrag

            if fristigkeit != "":
                langfristig = "lang" in fristigkeit
            if langfristig:
                p["langfr_fk"] += betrag

    if p["forderungen_lul"] == 0:
        p["forderungen_lul"] = p["forderungen"]

    p["kurzfr_fk"] = p["fremdkapital"] - p["langfr_fk"]
    return p


def ist_zusatzangabe(zeile):
    return "zusatz" in feld(zeile, "Kategorie")


def guv_seite(zeile):
    if ist_zusatzangabe(zeile):
        return ""

    seite = ""
    for spalte in SEITE_SPALTEN:
        if seite == "":
            seite = feld(zeile, spalte)

    if seite in ["haben", "habenseite", "h"]:
        return "haben"
    if seite in ["soll", "sollseite", "s"]:
        return "soll"

    kategorie = feld(zeile, "Kategorie")
    if enthaelt(kategorie, ["ertr", "erloes"]) or "umsatz" in guv_position(zeile):
        return "haben"
    if enthaelt(kategorie, ["aufw", "kosten"]):
        return "soll"
    return ""


def guv_position(zeile):
    position = feld(zeile, "position")
    if position == "":
        position = feld(zeile, "Position")
    return position


def ist_ertragsteuer(position):
    if position == "steuern":
        return True
    if "steuer" not in position:
        return False
    return enthaelt(position, ["einkommen", "ertrag", "koerperschaft", "gewerbesteuer"])


def sammle_guv_posten(guv_jahr):
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
        "tilgung": None,
        "entnahmen": None,
        "investitionen": None,
    }

    for zeile in guv_jahr:
        betrag = parse_betrag(zeile.get("Betrag_EUR"))
        position = guv_position(zeile)
        seite = guv_seite(zeile)

        if ist_zusatzangabe(zeile):
            schluessel = ""
            if "tilgung" in position:
                schluessel = "tilgung"
            elif enthaelt(position, ["entnahme", "ausschuettung"]):
                schluessel = "entnahmen"
            elif "investition" in position:
                schluessel = "investitionen"

            if schluessel != "":
                if p[schluessel] is None:
                    p[schluessel] = 0.0
                p[schluessel] += betrag

        elif seite == "haben":
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
            elif enthaelt(position, ["material", "roh-", "hilfs- und betriebsstoffe", "bezogene waren", "bezogene leistungen", "wareneinsatz"]):
                p["materialaufwand"] += betrag
            elif enthaelt(position, ["personal", "loehne", "gehaelter", "soziale abgaben", "altersversorgung"]):
                p["personalaufwand"] += betrag
            elif "abschreibung" in position:
                p["abschreibungen"] += betrag
            elif "zins" in position:
                p["zinsaufwand"] += betrag
            elif ist_ertragsteuer(position):
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
    if vorjahr is None:
        return aktuell
    return (aktuell + vorjahr) / 2


def kennzahl(wert, hinweis="", ampel=""):
    eintrag = {"wert": None}
    if wert is not None:
        eintrag["wert"] = round(wert, 6)
    if hinweis != "":
        eintrag["hinweis"] = hinweis
    if ampel != "":
        eintrag["ampel"] = ampel
    return eintrag


def berechne_cashflow(b, g, b_vorjahr):
    cashflow = g["jahresueberschuss"] + g["abschreibungen"]
    if b_vorjahr is None:
        return cashflow, "Vereinfacht ohne Vorjahr (ohne Veränderung der Rückstellungen)"
    cashflow = cashflow + b["rueckstellungen"] - b_vorjahr["rueckstellungen"]
    return cashflow, ""


def kennzahlen_kapitalstruktur(b, k):
    ek = b["eigenkapital"]
    bs = b["bilanzsumme"]
    fk = b["fremdkapital"]
    av = b["anlagevermoegen"]

    k["K01"] = kennzahl(teile(ek, bs))
    k["K02"] = kennzahl(teile(fk, bs))
    if ek > 0:
        k["K03"] = kennzahl(teile(fk, ek))
    else:
        k["K03"] = kennzahl(None, "Eigenkapital ≤ 0", "rot")
    k["K04"] = kennzahl(teile(av, bs))
    k["K05"] = kennzahl(teile(ek, av))
    k["K06"] = kennzahl(teile(ek + b["langfr_fk"], av))
    k["K07"] = kennzahl(teile(b["bankverbindlichkeiten"], bs))
    k["K08"] = kennzahl(teile(b["finanzverbindlichkeiten"] - b["liquide_mittel"], bs))


def kennzahlen_rentabilitaet(b, g, g_vorjahr, k):
    ek = b["eigenkapital"]
    gesamtleistung = g["gesamtleistung"]

    k["R01"] = kennzahl(teile(g["ebt"], gesamtleistung))
    k["R02"] = kennzahl(teile(g["ebt"] + g["zinsaufwand"], b["bilanzsumme"]))
    if ek > 0:
        k["R03"] = kennzahl(teile(g["ebt"], ek))
    else:
        k["R03"] = kennzahl(None, "Eigenkapital ≤ 0", "rot")
    k["R04"] = kennzahl(teile(g["ebitda"], g["umsatz"]))
    k["R05"] = kennzahl(teile(g["personalaufwand"], gesamtleistung))
    k["R06"] = kennzahl(teile(g["materialaufwand"], gesamtleistung))

    if g_vorjahr is not None and g_vorjahr["umsatz"] > 0:
        k["R07"] = kennzahl(g["umsatz"] / g_vorjahr["umsatz"] - 1)
    else:
        k["R07"] = kennzahl(None, "Vorjahr fehlt")


def kennzahlen_cashflow(b, g, cashflow, hinweis, k):
    zins = g["zinsaufwand"]
    tilgung = g["tilgung"]

    k["C01"] = kennzahl(cashflow, hinweis)
    k["C02"] = kennzahl(teile(cashflow, g["umsatz"]), hinweis)

    if cashflow > 0:
        netto_schulden = max(b["verbindlichkeiten"] - b["liquide_mittel"], 0.0)
        k["C03"] = kennzahl(netto_schulden / cashflow, hinweis)
    else:
        k["C03"] = kennzahl(None, "Cashflow ≤ 0", "rot")

    if zins > 0:
        k["C04"] = kennzahl(g["ebit"] / zins)
    else:
        k["C04"] = kennzahl(None, "Kein Zinsaufwand")

    kapitaldienstgrenze = None
    if g["entnahmen"] is None or g["investitionen"] is None:
        k["C05"] = kennzahl(None, "Zusatzangaben Entnahmen/Ausschüttungen und Investitionen fehlen")
    else:
        kapitaldienstgrenze = cashflow + zins - g["entnahmen"] - g["investitionen"]
        if kapitaldienstgrenze <= 0:
            k["C05"] = kennzahl(kapitaldienstgrenze, hinweis, "rot")
        else:
            k["C05"] = kennzahl(kapitaldienstgrenze, hinweis)

    if kapitaldienstgrenze is None or tilgung is None:
        k["C06"] = kennzahl(None, "Zusatzangaben Tilgung, Entnahmen oder Investitionen fehlen")
    elif kapitaldienstgrenze <= 0:
        k["C06"] = kennzahl(None, "Kapitaldienstgrenze ≤ 0", "rot")
    else:
        k["C06"] = kennzahl((zins + tilgung) / kapitaldienstgrenze, hinweis)

    if tilgung is None:
        k["C07"] = kennzahl(None, "Zusatzangabe Tilgung fehlt")
    else:
        k["C07"] = kennzahl(teile(cashflow + zins, zins + tilgung), hinweis)


def kennzahlen_liquiditaet(b, g, b_vorjahr, k):
    kurzfr_fk = b["kurzfr_fk"]
    umsatz = g["umsatz"]

    k["L01"] = kennzahl(teile(b["liquide_mittel"], kurzfr_fk))
    k["L02"] = kennzahl(teile(b["liquide_mittel"] + b["forderungen"], kurzfr_fk))
    k["L03"] = kennzahl(teile(b["umlaufvermoegen"], kurzfr_fk))
    k["L04"] = kennzahl(teile(b["umlaufvermoegen"] - kurzfr_fk, umsatz))

    if b_vorjahr is None:
        hinweis = "Stichtagswert (kein Vorjahr)"
        forderungen = b["forderungen_lul"]
        vorraete = b["vorraete"]
        verb_lul = b["verbindlichkeiten_lul"]
    else:
        hinweis = "Durchschnittsbestand mit Vorjahr"
        forderungen = durchschnitt(b["forderungen_lul"], b_vorjahr["forderungen_lul"])
        vorraete = durchschnitt(b["vorraete"], b_vorjahr["vorraete"])
        verb_lul = durchschnitt(b["verbindlichkeiten_lul"], b_vorjahr["verbindlichkeiten_lul"])

    dso = teile(forderungen * 360, umsatz)
    dio = teile(vorraete * 360, g["materialaufwand"])
    dpo = teile(verb_lul * 360, g["materialaufwand"])

    k["L05"] = kennzahl(dso, hinweis)
    k["L06"] = kennzahl(dio, hinweis)
    k["L07"] = kennzahl(dpo, hinweis)
    if dso is None or dio is None or dpo is None:
        k["L08"] = kennzahl(None, "DSO, DIO oder DPO nicht berechenbar")
    else:
        k["L08"] = kennzahl(dso + dio - dpo, hinweis)


def berechne_kennzahlen(b, g, b_vorjahr=None, g_vorjahr=None):
    k = {}
    cashflow, hinweis = berechne_cashflow(b, g, b_vorjahr)

    kennzahlen_kapitalstruktur(b, k)
    kennzahlen_rentabilitaet(b, g, g_vorjahr, k)
    kennzahlen_cashflow(b, g, cashflow, hinweis, k)
    kennzahlen_liquiditaet(b, g, b_vorjahr, k)
    return k


def uebersicht_werte(b, g, k):
    kapitaldienst = None
    if g["tilgung"] is not None:
        kapitaldienst = g["zinsaufwand"] + g["tilgung"]

    return {
        "umsatz": g["umsatz"],
        "ebitda": g["ebitda"],
        "jahresueberschuss": g["jahresueberschuss"],
        "cashflow": k["C01"]["wert"],
        "bilanzsumme": b["bilanzsumme"],
        "eigenkapital": b["eigenkapital"],
        "fremdkapital": b["fremdkapital"],
        "langfr_fk": b["langfr_fk"],
        "kurzfr_fk": b["kurzfr_fk"],
        "liquide_mittel": b["liquide_mittel"],
        "kapitaldienstgrenze": k["C05"]["wert"],
        "kapitaldienst": kapitaldienst,
    }


def analysiere_alle_jahre(bilanz, guv):
    guv_jahre = alle_jahre(guv)
    jahre = []
    for jahr in alle_jahre(bilanz):
        if jahr in guv_jahre:
            jahre.append(jahr)

    if len(jahre) == 0:
        return None, "⚠️ Keine gemeinsamen GJ-Daten in Bilanz und GuV gefunden.", []

    for jahr in jahre:
        if not bilanz_geht_auf(zeilen_fuer_jahr(bilanz, jahr)):
            return None, "⚠️ Bilanzsummen stimmen nicht überein (GJ " + jahr + ": Aktiva ≠ Passiva)", jahre

    bilanz_posten = {}
    guv_posten = {}
    for jahr in jahre:
        bilanz_posten[jahr] = sammle_bilanz_posten(zeilen_fuer_jahr(bilanz, jahr))
        guv_posten[jahr] = sammle_guv_posten(zeilen_fuer_jahr(guv, jahr))

    ergebnisse = []
    for jahr in jahre:
        vorjahr = vorjahr_von(jahr)
        b_vorjahr = bilanz_posten.get(vorjahr)
        g_vorjahr = guv_posten.get(vorjahr)

        kennzahlen = berechne_kennzahlen(bilanz_posten[jahr], guv_posten[jahr], b_vorjahr, g_vorjahr)
        ergebnisse.append({
            "gj": jahr,
            "werte": uebersicht_werte(bilanz_posten[jahr], guv_posten[jahr], kennzahlen),
            "kennzahlen": kennzahlen,
        })

    return ergebnisse, None, jahre


def zeige_loader(sichtbar):
    loader = document.getElementById("loader")
    if sichtbar:
        loader.style.display = "block"
    else:
        loader.style.display = "none"


@when("click", "#startButton")
def finanzanalyse_starten(event=None):
    ausgabe = document.getElementById("output")
    bilanz_text = document.getElementById("data-bilanz").textContent or ""
    guv_text = document.getElementById("data-guv").textContent or ""
    branche = document.getElementById("branche").value or ""

    fehler = pruefe_eingaben(bilanz_text, guv_text)
    if fehler:
        ausgabe.textContent = fehler
        return

    zeige_loader(True)
    ausgabe.textContent = "⏳ Analyse läuft..."

    try:
        bilanz = parse_csv(bilanz_text)
        guv = parse_csv(guv_text)

        if len(bilanz) == 0:
            ausgabe.textContent = "⚠️ Bilanz-Datei ist leer oder ungültig."
            return
        if len(guv) == 0:
            ausgabe.textContent = "⚠️ GuV-Datei ist leer oder ungültig."
            return

        fehlt_bilanz = fehlende_spalten(bilanz, BILANZ_PFLICHT)
        fehlt_guv = fehlende_spalten(guv, GUV_PFLICHT)
        if len(fehlt_bilanz) > 0 or len(fehlt_guv) > 0:
            text = ""
            if len(fehlt_bilanz) > 0:
                text += "Bilanz FEHLER: Spalten fehlen: " + ", ".join(fehlt_bilanz) + "\n"
            if len(fehlt_guv) > 0:
                text += "GuV FEHLER: Spalten fehlen: " + ", ".join(fehlt_guv)
            ausgabe.textContent = text
            return

        if not hat_jahr_spalte(bilanz):
            ausgabe.textContent = "Bilanz FEHLER: Spalte GJ/Geschaeftsjahr/Geschäftsjahr fehlt"
            return
        if not hat_jahr_spalte(guv):
            ausgabe.textContent = "GuV FEHLER: Spalte GJ/Geschaeftsjahr/Geschäftsjahr fehlt"
            return

        ergebnisse, fehler, jahre = analysiere_alle_jahre(bilanz, guv)
        if fehler:
            ausgabe.textContent = fehler
            return

        ausgabe.textContent = "✅ Dateien erfolgreich geladen\nGJ gefunden: " + ", ".join(jahre)

        adresse = "index2.html?v=" + VERSION
        adresse += "&results=" + window.encodeURIComponent(json.dumps(ergebnisse))
        adresse += "&branche=" + window.encodeURIComponent(branche)
        window.location.href = adresse

    except Exception as e:
        ausgabe.textContent = "❌ Fehler: " + str(e)
    finally:
        zeige_loader(False)
