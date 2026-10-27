# Keitmann Dashboard

Privates „Schweizer Taschenmesser“ für den PC. Läuft komplett im Browser –
Dateien werden **nicht** hochgeladen, sondern nur lokal verarbeitet.

Adresse: https://max0539.github.io/dashboard/

## Werkzeuge

| Stellplatz | Werkzeug | Funktionen |
|---|---|---|
| 1 | PDF-Konverter | Bilder → PDF, PDFs zusammenfügen, Seiten auswählen/drehen/entfernen/einzeln speichern, PDF → Bilder (PNG/JPG), Text → PDF |
| 2–8 | frei | – |

## Als Programm für den PC

Im Ordner `../desktop` wird das Dashboard als Windows-Programm (.exe) verpackt –
siehe `desktop/README.md`.

Alternativ ohne Download: In Chrome oder Edge die Seite öffnen und auf **„Als App installieren“** unten
links klicken (oder das Installieren-Symbol in der Adressleiste). Danach
startet das Dashboard wie ein normales Programm und funktioniert auch offline.

## Neues Werkzeug hinzufügen

1. `tools/_vorlage.js` kopieren und anpassen.
2. Die neue Datei in `index.html` als `<script>` eintragen.
3. In `sw.js` die Datei in `DATEIEN` aufnehmen und `VERSION` erhöhen.

Die Anzahl der Stellplätze steht in `app.js` (`ANZAHL_STELLPLAETZE`).

## Verwendete Bibliotheken (in `vendor/`)

- [pdf-lib](https://pdf-lib.js.org/) 1.17.1 – PDFs erstellen und bearbeiten
- [PDF.js](https://mozilla.github.io/pdf.js/) 3.11.174 – PDF-Seiten anzeigen und als Bild rendern
- [JSZip](https://stuk.github.io/jszip/) 3.10.1 – ZIP-Dateien packen
