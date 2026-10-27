// Keitmann Dashboard – Grundgerüst
// Jedes Werkzeug meldet sich mit KD.registriere({...}) an (siehe tools/pdf.js).
// Alle Dateien werden nur im Browser verarbeitet, nichts wird hochgeladen.

const KD = (function () {
  const ANZAHL_STELLPLAETZE = 8;

  const werkzeuge = [];

  const SYMBOLE = {
    start: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
    pdf: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/></svg>',
    frei: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>'
  };

  function registriere(werkzeug) {
    werkzeuge.push(werkzeug);
  }

  function symbol(name) {
    return SYMBOLE[name] || name || SYMBOLE.frei;
  }

  // ---------- kleine Helfer für alle Werkzeuge ----------

  function element(tag, klasse, text) {
    const el = document.createElement(tag);
    if (klasse) {
      el.className = klasse;
    }
    if (text !== undefined) {
      el.textContent = text;
    }
    return el;
  }

  function meldung(text, istFehler) {
    const box = element("div", istFehler ? "meldung fehler" : "meldung", text);
    document.getElementById("meldungen").appendChild(box);
    setTimeout(function () {
      box.remove();
    }, istFehler ? 7000 : 4000);
  }

  function herunterladen(daten, dateiname, typ) {
    const blob = daten instanceof Blob ? daten : new Blob([daten], { type: typ || "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = dateiname;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 10000);
  }

  function dateigroesse(bytes) {
    if (bytes < 1024) {
      return bytes + " B";
    }
    if (bytes < 1024 * 1024) {
      return (bytes / 1024).toFixed(0) + " KB";
    }
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  }

  function ohneEndung(dateiname) {
    return dateiname.replace(/\.[^.]+$/, "");
  }

  // Ablagezone: Dateien per Klick oder Drag & Drop auswählen
  function ablagezone(optionen) {
    const zone = element("div", "ablagezone");
    zone.innerHTML = "<div><strong>Dateien hierher ziehen</strong> oder klicken zum Auswählen</div>";
    zone.appendChild(element("div", "leise", optionen.hinweis || ""));

    const eingabe = document.createElement("input");
    eingabe.type = "file";
    eingabe.accept = optionen.accept || "";
    eingabe.multiple = optionen.mehrere !== false;
    eingabe.hidden = true;
    zone.appendChild(eingabe);

    zone.addEventListener("click", function () {
      eingabe.click();
    });
    eingabe.addEventListener("change", function () {
      if (eingabe.files.length > 0) {
        optionen.beiDateien(Array.from(eingabe.files));
      }
      eingabe.value = "";
    });
    zone.addEventListener("dragover", function (e) {
      e.preventDefault();
      zone.classList.add("drueber");
    });
    zone.addEventListener("dragleave", function () {
      zone.classList.remove("drueber");
    });
    zone.addEventListener("drop", function (e) {
      e.preventDefault();
      zone.classList.remove("drueber");
      let dateien = Array.from(e.dataTransfer.files);
      if (optionen.passt) {
        dateien = dateien.filter(optionen.passt);
      }
      if (dateien.length === 0) {
        meldung("Dieser Dateityp passt hier nicht.", true);
        return;
      }
      if (optionen.mehrere === false) {
        dateien = dateien.slice(0, 1);
      }
      optionen.beiDateien(dateien);
    });
    return zone;
  }

  // ---------- Navigation und Seiten ----------

  function stellplaetze() {
    const liste = werkzeuge.slice();
    for (let i = liste.length; i < ANZAHL_STELLPLAETZE; i++) {
      liste.push(null);
    }
    return liste;
  }

  function baueNavigation(aktiveId) {
    const nav = document.getElementById("navigation");
    nav.innerHTML = "";

    nav.appendChild(navLink("#/", "Übersicht", SYMBOLE.start, aktiveId === ""));
    nav.appendChild(element("div", "nav-gruppe", "Werkzeuge"));

    stellplaetze().forEach(function (werkzeug, index) {
      if (werkzeug) {
        nav.appendChild(navLink("#/" + werkzeug.id, werkzeug.name, symbol(werkzeug.symbol), aktiveId === werkzeug.id));
      } else {
        const link = navLink("#/", "Stellplatz " + (index + 1) + " – frei", SYMBOLE.frei, false);
        link.classList.add("frei");
        nav.appendChild(link);
      }
    });
  }

  function navLink(href, text, svg, aktiv) {
    const link = element("a", aktiv ? "nav-link aktiv" : "nav-link");
    link.href = href;
    link.innerHTML = svg;
    link.appendChild(element("span", "", text));
    return link;
  }

  function zeigeUebersicht(inhalt) {
    const stunde = new Date().getHours();
    let gruss = "Guten Abend";
    if (stunde < 11) {
      gruss = "Guten Morgen";
    } else if (stunde < 18) {
      gruss = "Guten Tag";
    }
    inhalt.appendChild(element("p", "begruessung", gruss + "! Wähle ein Werkzeug aus."));

    const raster = element("div", "kachel-raster");
    stellplaetze().forEach(function (werkzeug, index) {
      let kachel;
      if (werkzeug) {
        kachel = element("a", "kachel");
        kachel.href = "#/" + werkzeug.id;
        kachel.innerHTML = '<div class="kachel-symbol">' + symbol(werkzeug.symbol) + "</div>";
        kachel.appendChild(element("h3", "", werkzeug.name));
        kachel.appendChild(element("p", "", werkzeug.beschreibung));
      } else {
        kachel = element("div", "kachel frei");
        kachel.innerHTML = '<div class="kachel-symbol">' + SYMBOLE.frei + "</div>";
        kachel.appendChild(element("h3", "", "Stellplatz " + (index + 1)));
        kachel.appendChild(element("p", "", "Frei für ein weiteres Werkzeug."));
      }
      raster.appendChild(kachel);
    });
    inhalt.appendChild(raster);

    const hinweis = element("div", "hinweis-box");
    hinweis.textContent = "Privat: Alle Dateien werden nur hier im Browser verarbeitet und nirgendwo hochgeladen. " +
      "Nach dem ersten Laden funktioniert das Dashboard auch offline.";
    inhalt.appendChild(hinweis);
  }

  function zeigeSeite() {
    const id = location.hash.replace(/^#\/?/, "").split("/")[0];
    const werkzeug = werkzeuge.find(function (w) {
      return w.id === id;
    });

    const inhalt = document.getElementById("inhalt");
    inhalt.innerHTML = "";
    document.getElementById("seitenleiste").classList.remove("offen");

    if (werkzeug) {
      document.getElementById("seitentitel").textContent = werkzeug.name;
      document.title = werkzeug.name + " – Keitmann Dashboard";
      baueNavigation(werkzeug.id);
      werkzeug.anzeigen(inhalt);
    } else {
      document.getElementById("seitentitel").textContent = "Übersicht";
      document.title = "Keitmann Dashboard";
      baueNavigation("");
      zeigeUebersicht(inhalt);
    }
    window.scrollTo(0, 0);
  }

  // ---------- Uhr, Thema, Menü, Installation ----------

  function starteUhr() {
    const uhr = document.getElementById("uhr");
    function aktualisieren() {
      const jetzt = new Date();
      uhr.innerHTML = "<strong>" + jetzt.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) + "</strong><br>" +
        jetzt.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    }
    aktualisieren();
    setInterval(aktualisieren, 15000);
  }

  function leseEinstellung(name) {
    try {
      return localStorage.getItem("kd-" + name);
    } catch (e) {
      return null;
    }
  }

  function speichereEinstellung(name, wert) {
    try {
      localStorage.setItem("kd-" + name, wert);
    } catch (e) {
      // Private Fenster erlauben manchmal keinen Speicher – dann eben ohne
    }
  }

  function setzeThema(thema) {
    document.documentElement.setAttribute("data-thema", thema);
    document.querySelector('meta[name="theme-color"]').content = thema === "hell" ? "#F2F5F9" : "#071A2F";
  }

  function starte() {
    let thema = leseEinstellung("thema");
    if (!thema) {
      thema = window.matchMedia("(prefers-color-scheme: light)").matches ? "hell" : "dunkel";
    }
    setzeThema(thema);

    document.getElementById("thema-knopf").addEventListener("click", function () {
      thema = thema === "hell" ? "dunkel" : "hell";
      setzeThema(thema);
      speichereEinstellung("thema", thema);
    });

    document.getElementById("menue-knopf").addEventListener("click", function () {
      document.getElementById("seitenleiste").classList.toggle("offen");
    });

    let installAnfrage = null;
    const installKnopf = document.getElementById("installieren-knopf");
    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      installAnfrage = e;
      installKnopf.classList.remove("versteckt");
    });
    installKnopf.addEventListener("click", function () {
      if (installAnfrage) {
        installAnfrage.prompt();
        installAnfrage = null;
        installKnopf.classList.add("versteckt");
      }
    });

    if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
      navigator.serviceWorker.register("sw.js").catch(function () {});
    }

    starteUhr();
    window.addEventListener("hashchange", zeigeSeite);
    zeigeSeite();
  }

  document.addEventListener("DOMContentLoaded", starte);

  return {
    registriere: registriere,
    element: element,
    meldung: meldung,
    herunterladen: herunterladen,
    dateigroesse: dateigroesse,
    ohneEndung: ohneEndung,
    ablagezone: ablagezone,
    leseEinstellung: leseEinstellung,
    speichereEinstellung: speichereEinstellung
  };
})();
