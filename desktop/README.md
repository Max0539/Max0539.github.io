# Keitmann Dashboard – Desktop-Programm

Verpackt das Dashboard aus `../dashboard` mit [Electron](https://www.electronjs.org/)
als eigenständiges Programm. Es läuft komplett offline, Dateien werden über
den normalen „Speichern unter“-Dialog gespeichert.

## Herunterladen

Die fertigen `.exe`-Dateien baut GitHub automatisch (Reiter **Actions** →
„Desktop-App bauen“ → unten bei *Artifacts*, oder unter **Releases**):

- `Keitmann-Dashboard-Setup-x.y.z.exe` – Installation mit Startmenü- und Desktop-Verknüpfung
- `Keitmann-Dashboard-x.y.z-portable.exe` – ohne Installation, z. B. für einen USB-Stick

Da das Programm nicht signiert ist, warnt Windows beim ersten Start
(„Der Computer wurde durch Windows geschützt“) → **Weitere Informationen** → **Trotzdem ausführen**.

## Selbst bauen (auf einem Windows-PC)

```
cd desktop
npm install
npm start          # zum Ausprobieren
npm run build:win  # erzeugt die .exe-Dateien in desktop/dist
```

Für ein neues Release: Version in `package.json` erhöhen, dann einen Tag
pushen, z. B. `git tag v1.1.0 && git push origin v1.1.0`.
