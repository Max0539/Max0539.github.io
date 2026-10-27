// Keitmann Dashboard als Desktop-Programm (Electron)
// Zeigt die Dateien aus dem Ordner "dashboard" in einem eigenen Fenster an.

const { app, BrowserWindow, Menu, protocol, net, shell } = require("electron");
const path = require("path");
const { pathToFileURL } = require("url");

// Im fertigen Programm liegt "dashboard" neben main.js, beim Entwickeln eine Ebene höher
const ORDNER = require("fs").existsSync(path.join(__dirname, "dashboard"))
  ? path.join(__dirname, "dashboard")
  : path.join(__dirname, "..", "dashboard");

const STARTSEITE = "kd://app/index.html";

// Eigene Adresse kd://app/ statt file:// – damit funktionieren Speicher und PDF-Worker zuverlässig
protocol.registerSchemesAsPrivileged([
  { scheme: "kd", privileges: { standard: true, secure: true, supportFetchAPI: true } }
]);

function liefereDatei(anfrage) {
  const pfad = decodeURIComponent(new URL(anfrage.url).pathname);
  const datei = path.normalize(path.join(ORDNER, pfad === "/" ? "index.html" : pfad));
  if (!datei.startsWith(ORDNER + path.sep)) {
    return new Response("Nicht erlaubt", { status: 403 });
  }
  return net.fetch(pathToFileURL(datei).toString());
}

function oeffneFenster() {
  const fenster = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 380,
    minHeight: 500,
    title: "Keitmann Dashboard",
    icon: path.join(ORDNER, "icons", "icon-512.png"),
    backgroundColor: "#071A2F",
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  fenster.once("ready-to-show", function () {
    fenster.show();
  });

  // Nicht wegnavigieren (z. B. wenn eine Datei neben die Ablagezone gezogen wird)
  fenster.webContents.on("will-navigate", function (e, url) {
    if (!url.startsWith("kd://app/")) {
      e.preventDefault();
    }
  });

  // Externe Links im normalen Browser öffnen
  fenster.webContents.setWindowOpenHandler(function (details) {
    if (/^https?:/.test(details.url)) {
      shell.openExternal(details.url);
    }
    return { action: "deny" };
  });

  // Beim Speichern den "Speichern unter"-Dialog im Downloads-Ordner öffnen
  fenster.webContents.session.on("will-download", function (e, eintrag) {
    eintrag.setSaveDialogOptions({
      title: "Datei speichern",
      defaultPath: path.join(app.getPath("downloads"), eintrag.getFilename())
    });
  });

  fenster.loadURL(STARTSEITE);
  return fenster;
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", function () {
    const fenster = BrowserWindow.getAllWindows()[0];
    if (fenster) {
      if (fenster.isMinimized()) {
        fenster.restore();
      }
      fenster.focus();
    }
  });

  app.whenReady().then(function () {
    Menu.setApplicationMenu(null);
    protocol.handle("kd", liefereDatei);
    oeffneFenster();

    app.on("activate", function () {
      if (BrowserWindow.getAllWindows().length === 0) {
        oeffneFenster();
      }
    });
  });

  app.on("window-all-closed", function () {
    if (process.platform !== "darwin") {
      app.quit();
    }
  });
}
