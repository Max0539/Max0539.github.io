// Werkzeug: PDF-Konverter
// Bilder -> PDF, PDFs zusammenfügen, Seiten bearbeiten, PDF -> Bilder, Text -> PDF

(function () {
  const el = KD.element;

  pdfjsLib.GlobalWorkerOptions.workerSrc = "vendor/pdf.worker.min.js";

  const A4 = [595.28, 841.89];
  const MM = 72 / 25.4;

  const MODI = [
    { id: "bilder", name: "Bilder → PDF", anzeigen: zeigeBilderZuPdf },
    { id: "zusammen", name: "PDFs zusammenfügen", anzeigen: zeigeZusammenfuegen },
    { id: "seiten", name: "Seiten bearbeiten", anzeigen: zeigeSeitenBearbeiten },
    { id: "pdfbilder", name: "PDF → Bilder", anzeigen: zeigePdfZuBildern },
    { id: "text", name: "Text → PDF", anzeigen: zeigeTextZuPdf }
  ];

  KD.registriere({
    id: "pdf",
    name: "PDF-Konverter",
    symbol: "pdf",
    beschreibung: "Bilder zu PDF, PDFs zusammenfügen, Seiten drehen/entfernen, PDF zu Bildern, Text zu PDF.",
    anzeigen: anzeigen
  });

  function anzeigen(inhalt) {
    const reiter = el("div", "reiter");
    const bereich = el("div");
    inhalt.appendChild(reiter);
    inhalt.appendChild(bereich);

    function wechsle(modus) {
      reiter.querySelectorAll("button").forEach(function (knopf) {
        knopf.classList.toggle("aktiv", knopf.dataset.id === modus.id);
      });
      bereich.innerHTML = "";
      modus.anzeigen(bereich);
      KD.speichereEinstellung("pdf-modus", modus.id);
    }

    MODI.forEach(function (modus) {
      const knopf = el("button", "", modus.name);
      knopf.type = "button";
      knopf.dataset.id = modus.id;
      knopf.addEventListener("click", function () {
        wechsle(modus);
      });
      reiter.appendChild(knopf);
    });

    const gespeichert = KD.leseEinstellung("pdf-modus");
    wechsle(MODI.find(function (m) { return m.id === gespeichert; }) || MODI[0]);
  }

  // ---------- gemeinsame Helfer ----------

  function karte(bereich, titel, beschreibung) {
    const box = el("div", "karte");
    box.appendChild(el("h2", "", titel));
    box.appendChild(el("p", "leise", beschreibung));
    bereich.appendChild(box);
    return box;
  }

  function knopf(text, zweitrangig) {
    const k = el("button", zweitrangig ? "knopf zweitrangig" : "knopf", text);
    k.type = "button";
    return k;
  }

  function auswahl(beschriftung, eintraege, standard) {
    const label = el("label", "", beschriftung);
    const select = document.createElement("select");
    eintraege.forEach(function (eintrag) {
      const option = document.createElement("option");
      option.value = eintrag[0];
      option.textContent = eintrag[1];
      select.appendChild(option);
    });
    if (standard !== undefined) {
      select.value = standard;
    }
    label.appendChild(select);
    return { label: label, select: select };
  }

  function istPdf(datei) {
    return datei.type === "application/pdf" || /\.pdf$/i.test(datei.name);
  }

  function istBild(datei) {
    return datei.type.startsWith("image/");
  }

  // Führt eine Aktion aus, sperrt dabei den Knopf und zeigt Fehler an
  async function mitWarten(k, aktion) {
    const alterText = k.textContent;
    k.disabled = true;
    k.textContent = "Bitte warten …";
    try {
      await aktion();
    } catch (fehler) {
      console.error(fehler);
      KD.meldung(fehlertext(fehler), true);
    } finally {
      k.disabled = false;
      k.textContent = alterText;
    }
  }

  function fehlertext(fehler) {
    const text = String(fehler && fehler.message ? fehler.message : fehler);
    if (/encrypt/i.test(text) || (fehler && fehler.name === "PasswordException")) {
      return "Die PDF ist passwortgeschützt und kann nicht bearbeitet werden.";
    }
    if (/Invalid PDF|No PDF header|Failed to parse/i.test(text)) {
      return "Die Datei ist keine gültige PDF.";
    }
    return "Fehler: " + text;
  }

  async function ladePdfLib(datei) {
    const bytes = await datei.arrayBuffer();
    return PDFLib.PDFDocument.load(bytes);
  }

  async function ladePdfJs(datei) {
    const bytes = new Uint8Array(await datei.arrayBuffer());
    return pdfjsLib.getDocument({ data: bytes }).promise;
  }

  // Zeichnet eine PDF-Seite in ein Canvas (mit weißem Hintergrund)
  async function zeichneSeite(pdf, nummer, skalierung) {
    const seite = await pdf.getPage(nummer);
    let ansicht = seite.getViewport({ scale: skalierung });

    // Riesige Seiten (Poster) begrenzen, sonst streikt der Browser
    const maxPixel = 40000000;
    if (ansicht.width * ansicht.height > maxPixel) {
      ansicht = seite.getViewport({ scale: skalierung * Math.sqrt(maxPixel / (ansicht.width * ansicht.height)) });
    }

    const canvas = document.createElement("canvas");
    canvas.width = Math.floor(ansicht.width);
    canvas.height = Math.floor(ansicht.height);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    await seite.render({ canvasContext: ctx, viewport: ansicht }).promise;
    seite.cleanup();
    return canvas;
  }

  function canvasZuBlob(canvas, typ, qualitaet) {
    return new Promise(function (fertig, fehler) {
      canvas.toBlob(function (blob) {
        if (blob) {
          fertig(blob);
        } else {
          fehler(new Error("Bild konnte nicht erzeugt werden."));
        }
      }, typ, qualitaet);
    });
  }

  // "1-3, 5, 8-" -> [0, 1, 2, 4, 7, 8, ...] (Seiten ab 0 gezählt)
  function leseSeitenbereich(text, anzahl) {
    const ergebnis = [];
    const teile = text.split(/[,;]/).map(function (t) { return t.trim(); }).filter(Boolean);
    if (teile.length === 0) {
      return null;
    }
    for (const teil of teile) {
      const treffer = teil.match(/^(\d*)\s*-\s*(\d*)$/);
      let von;
      let bis;
      if (treffer) {
        von = treffer[1] ? parseInt(treffer[1], 10) : 1;
        bis = treffer[2] ? parseInt(treffer[2], 10) : anzahl;
      } else if (/^\d+$/.test(teil)) {
        von = parseInt(teil, 10);
        bis = von;
      } else {
        return null;
      }
      if (von < 1 || bis > anzahl || von > bis) {
        return null;
      }
      for (let i = von; i <= bis; i++) {
        if (!ergebnis.includes(i - 1)) {
          ergebnis.push(i - 1);
        }
      }
    }
    return ergebnis;
  }

  // Liste mit Dateien, die sich sortieren und entfernen lassen
  function sortierbareListe(liste, dateien, zeile, beiAenderung) {
    function neuZeichnen() {
      liste.innerHTML = "";
      dateien.forEach(function (eintrag, index) {
        const reihe = el("div", "datei-zeile");
        zeile(reihe, eintrag);

        const aktionen = el("div", "aktionen");
        const hoch = el("button", "mini-knopf", "↑");
        const runter = el("button", "mini-knopf", "↓");
        const weg = el("button", "mini-knopf", "✕");
        hoch.title = "Nach oben";
        runter.title = "Nach unten";
        weg.title = "Entfernen";
        hoch.disabled = index === 0;
        runter.disabled = index === dateien.length - 1;

        hoch.addEventListener("click", function () {
          dateien.splice(index - 1, 0, dateien.splice(index, 1)[0]);
          neuZeichnen();
        });
        runter.addEventListener("click", function () {
          dateien.splice(index + 1, 0, dateien.splice(index, 1)[0]);
          neuZeichnen();
        });
        weg.addEventListener("click", function () {
          const entfernt = dateien.splice(index, 1)[0];
          if (entfernt.vorschau) {
            URL.revokeObjectURL(entfernt.vorschau);
          }
          neuZeichnen();
        });

        aktionen.appendChild(hoch);
        aktionen.appendChild(runter);
        aktionen.appendChild(weg);
        reihe.appendChild(aktionen);
        liste.appendChild(reihe);
      });
      beiAenderung();
    }
    return neuZeichnen;
  }

  // ---------- Bilder -> PDF ----------

  function zeigeBilderZuPdf(bereich) {
    const box = karte(bereich, "Bilder zu PDF", "JPG, PNG, WebP, GIF oder BMP – jedes Bild wird zu einer Seite. Reihenfolge lässt sich ändern.");
    const bilder = [];

    const liste = el("div", "dateiliste");
    const optionen = el("div", "optionen");
    const format = auswahl("Seitenformat", [
      ["a4auto", "A4 (Ausrichtung automatisch)"],
      ["a4hoch", "A4 Hochformat"],
      ["a4quer", "A4 Querformat"],
      ["bild", "Wie das Bild"]
    ], "a4auto");
    const rand = auswahl("Rand", [["0", "Kein Rand"], ["10", "10 mm"], ["20", "20 mm"]], "10");
    optionen.appendChild(format.label);
    optionen.appendChild(rand.label);

    const reihe = el("div", "knopfreihe");
    const erstellen = knopf("PDF erstellen");
    const leeren = knopf("Liste leeren", true);
    reihe.appendChild(erstellen);
    reihe.appendChild(leeren);

    const neuZeichnen = sortierbareListe(liste, bilder, function (zeile, eintrag) {
      const img = document.createElement("img");
      img.src = eintrag.vorschau;
      img.alt = "";
      zeile.appendChild(img);
      const name = el("div", "datei-name", eintrag.datei.name);
      name.appendChild(el("small", "", KD.dateigroesse(eintrag.datei.size)));
      zeile.appendChild(name);
    }, function () {
      erstellen.disabled = bilder.length === 0;
      erstellen.textContent = bilder.length > 0 ? "PDF erstellen (" + bilder.length + " Seiten)" : "PDF erstellen";
    });

    box.appendChild(KD.ablagezone({
      accept: "image/*",
      hinweis: "Mehrere Bilder auf einmal möglich",
      passt: istBild,
      beiDateien: function (dateien) {
        dateien.filter(istBild).forEach(function (datei) {
          bilder.push({ datei: datei, vorschau: URL.createObjectURL(datei) });
        });
        neuZeichnen();
      }
    }));
    box.appendChild(liste);
    box.appendChild(optionen);
    box.appendChild(reihe);
    neuZeichnen();

    leeren.addEventListener("click", function () {
      bilder.forEach(function (b) { URL.revokeObjectURL(b.vorschau); });
      bilder.length = 0;
      neuZeichnen();
    });

    erstellen.addEventListener("click", function () {
      mitWarten(erstellen, async function () {
        const pdf = await PDFLib.PDFDocument.create();
        const randPt = parseInt(rand.select.value, 10) * MM;

        for (const eintrag of bilder) {
          const bild = await bettBildEin(pdf, eintrag.datei);
          let seitenBreite;
          let seitenHoehe;

          if (format.select.value === "bild") {
            // Seite so groß wie das Bild, längste Seite höchstens A4-Länge
            const faktor = Math.min(1, A4[1] / Math.max(bild.width, bild.height));
            seitenBreite = bild.width * faktor + 2 * randPt;
            seitenHoehe = bild.height * faktor + 2 * randPt;
          } else {
            let quer = format.select.value === "a4quer";
            if (format.select.value === "a4auto") {
              quer = bild.width > bild.height;
            }
            seitenBreite = quer ? A4[1] : A4[0];
            seitenHoehe = quer ? A4[0] : A4[1];
          }

          const seite = pdf.addPage([seitenBreite, seitenHoehe]);
          const platzB = seitenBreite - 2 * randPt;
          const platzH = seitenHoehe - 2 * randPt;
          const faktor = Math.min(platzB / bild.width, platzH / bild.height);
          const b = bild.width * faktor;
          const h = bild.height * faktor;
          seite.drawImage(bild, {
            x: (seitenBreite - b) / 2,
            y: (seitenHoehe - h) / 2,
            width: b,
            height: h
          });
        }

        const name = bilder.length === 1 ? KD.ohneEndung(bilder[0].datei.name) + ".pdf" : "bilder.pdf";
        KD.herunterladen(await pdf.save(), name, "application/pdf");
        KD.meldung("PDF erstellt: " + name);
      });
    });
  }

  // PNG direkt übernehmen, alles andere über ein Canvas als JPG
  // (dabei wird auch die Drehung von Handyfotos berücksichtigt)
  async function bettBildEin(pdf, datei) {
    if (datei.type === "image/png") {
      try {
        return await pdf.embedPng(await datei.arrayBuffer());
      } catch (e) {
        // fällt unten auf den Canvas-Weg zurück
      }
    }

    let bitmap;
    try {
      bitmap = await createImageBitmap(datei, { imageOrientation: "from-image" });
    } catch (e) {
      throw new Error("Das Bild „" + datei.name + "“ kann der Browser nicht lesen (z. B. HEIC wird nicht unterstützt).");
    }
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0);
    bitmap.close();

    const blob = await canvasZuBlob(canvas, "image/jpeg", 0.92);
    return pdf.embedJpg(await blob.arrayBuffer());
  }

  // ---------- PDFs zusammenfügen ----------

  function zeigeZusammenfuegen(bereich) {
    const box = karte(bereich, "PDFs zusammenfügen", "Mehrere PDFs in der gewünschten Reihenfolge zu einer Datei verbinden.");
    const pdfs = [];

    const liste = el("div", "dateiliste");
    const reihe = el("div", "knopfreihe");
    const zusammen = knopf("Zusammenfügen");
    const leeren = knopf("Liste leeren", true);
    reihe.appendChild(zusammen);
    reihe.appendChild(leeren);

    const neuZeichnen = sortierbareListe(liste, pdfs, function (zeile, eintrag) {
      zeile.appendChild(el("div", "platzhalter-bild", "PDF"));
      const name = el("div", "datei-name", eintrag.datei.name);
      name.appendChild(el("small", "", KD.dateigroesse(eintrag.datei.size) + " · " + eintrag.seiten + " Seiten"));
      zeile.appendChild(name);
    }, function () {
      zusammen.disabled = pdfs.length < 2;
    });

    box.appendChild(KD.ablagezone({
      accept: "application/pdf,.pdf",
      hinweis: "Mindestens zwei PDFs",
      passt: istPdf,
      beiDateien: async function (dateien) {
        for (const datei of dateien.filter(istPdf)) {
          try {
            const doc = await ladePdfLib(datei);
            pdfs.push({ datei: datei, seiten: doc.getPageCount() });
          } catch (fehler) {
            KD.meldung(datei.name + ": " + fehlertext(fehler), true);
          }
        }
        neuZeichnen();
      }
    }));
    box.appendChild(liste);
    box.appendChild(reihe);
    neuZeichnen();

    leeren.addEventListener("click", function () {
      pdfs.length = 0;
      neuZeichnen();
    });

    zusammen.addEventListener("click", function () {
      mitWarten(zusammen, async function () {
        const ziel = await PDFLib.PDFDocument.create();
        for (const eintrag of pdfs) {
          const quelle = await ladePdfLib(eintrag.datei);
          const seiten = await ziel.copyPages(quelle, quelle.getPageIndices());
          seiten.forEach(function (s) { ziel.addPage(s); });
        }
        KD.herunterladen(await ziel.save(), "zusammengefuegt.pdf", "application/pdf");
        KD.meldung("Fertig: " + ziel.getPageCount() + " Seiten zusammengefügt.");
      });
    });
  }

  // ---------- Seiten bearbeiten ----------

  function zeigeSeitenBearbeiten(bereich) {
    const box = karte(bereich, "Seiten bearbeiten", "Seiten anklicken zum Auswählen, mit ⟳ drehen. Danach Auswahl speichern, entfernen oder alles einzeln exportieren.");
    let datei = null;
    let seiten = [];

    const werkbank = el("div", "versteckt");
    const optionen = el("div", "optionen");
    const bereichLabel = el("label", "", "Seiten auswählen (z. B. 1-3, 5)");
    const bereichEingabe = document.createElement("input");
    bereichEingabe.placeholder = "1-3, 5";
    bereichLabel.appendChild(bereichEingabe);
    const uebernehmen = knopf("Übernehmen", true);
    const alle = knopf("Alle", true);
    const keine = knopf("Keine", true);
    optionen.appendChild(bereichLabel);
    optionen.appendChild(uebernehmen);
    optionen.appendChild(alle);
    optionen.appendChild(keine);

    const info = el("div", "fortschritt");
    const raster = el("div", "seiten-raster");

    const reihe = el("div", "knopfreihe");
    const nurAuswahl = knopf("Auswahl als PDF speichern");
    const ohneAuswahl = knopf("Auswahl entfernen & speichern", true);
    const allesSpeichern = knopf("Alle Seiten speichern (mit Drehung)", true);
    const einzeln = knopf("Jede Seite einzeln (ZIP)", true);
    reihe.appendChild(nurAuswahl);
    reihe.appendChild(ohneAuswahl);
    reihe.appendChild(allesSpeichern);
    reihe.appendChild(einzeln);

    werkbank.appendChild(optionen);
    werkbank.appendChild(info);
    werkbank.appendChild(raster);
    werkbank.appendChild(reihe);

    box.appendChild(KD.ablagezone({
      accept: "application/pdf,.pdf",
      hinweis: "Eine PDF-Datei",
      mehrere: false,
      passt: istPdf,
      beiDateien: function (dateien) {
        oeffne(dateien[0]);
      }
    }));
    box.appendChild(werkbank);

    function aktualisiereInfo() {
      const anzahl = seiten.filter(function (s) { return s.gewaehlt; }).length;
      info.textContent = datei.name + " · " + seiten.length + " Seiten · " + anzahl + " ausgewählt";
      nurAuswahl.disabled = anzahl === 0;
      ohneAuswahl.disabled = anzahl === 0 || anzahl === seiten.length;
      seiten.forEach(function (s) {
        s.kachel.classList.toggle("gewaehlt", s.gewaehlt);
        s.canvas.style.transform = "rotate(" + s.drehung + "deg)";
      });
    }

    async function oeffne(neueDatei) {
      let pdf;
      try {
        pdf = await ladePdfJs(neueDatei);
      } catch (fehler) {
        KD.meldung(fehlertext(fehler), true);
        return;
      }
      datei = neueDatei;
      seiten = [];
      raster.innerHTML = "";
      werkbank.classList.remove("versteckt");

      for (let nr = 1; nr <= pdf.numPages; nr++) {
        const kachel = el("div", "seite-kachel");
        const haken = el("div", "haken", "✓");
        const drehen = el("button", "mini-knopf drehen", "⟳");
        drehen.type = "button";
        drehen.title = "90° drehen";
        const platz = document.createElement("canvas");
        platz.width = 100;
        platz.height = 140;
        const bild = el("div", "seite-bild");
        bild.appendChild(platz);
        kachel.appendChild(haken);
        kachel.appendChild(drehen);
        kachel.appendChild(bild);
        kachel.appendChild(el("div", "seiten-nr", "Seite " + nr));
        raster.appendChild(kachel);

        const eintrag = { kachel: kachel, canvas: platz, gewaehlt: false, drehung: 0 };
        seiten.push(eintrag);

        kachel.addEventListener("click", function () {
          eintrag.gewaehlt = !eintrag.gewaehlt;
          aktualisiereInfo();
        });
        drehen.addEventListener("click", function (e) {
          e.stopPropagation();
          eintrag.drehung = (eintrag.drehung + 90) % 360;
          aktualisiereInfo();
        });
      }
      aktualisiereInfo();

      // Vorschaubilder nacheinander zeichnen
      for (let nr = 1; nr <= pdf.numPages; nr++) {
        if (datei !== neueDatei) {
          pdf.destroy();
          return;
        }
        const seite = await pdf.getPage(nr);
        const skalierung = 220 / seite.getViewport({ scale: 1 }).height;
        const canvas = await zeichneSeite(pdf, nr, skalierung);
        canvas.style.transform = seiten[nr - 1].canvas.style.transform;
        seiten[nr - 1].canvas.replaceWith(canvas);
        seiten[nr - 1].canvas = canvas;
      }
      pdf.destroy();
    }

    uebernehmen.addEventListener("click", function () {
      const indizes = leseSeitenbereich(bereichEingabe.value, seiten.length);
      if (!indizes) {
        KD.meldung("Ungültige Seitenangabe. Beispiel: 1-3, 5", true);
        return;
      }
      seiten.forEach(function (s, i) { s.gewaehlt = indizes.includes(i); });
      aktualisiereInfo();
    });
    bereichEingabe.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        uebernehmen.click();
      }
    });
    alle.addEventListener("click", function () {
      seiten.forEach(function (s) { s.gewaehlt = true; });
      aktualisiereInfo();
    });
    keine.addEventListener("click", function () {
      seiten.forEach(function (s) { s.gewaehlt = false; });
      aktualisiereInfo();
    });

    // Neue PDF aus bestimmten Seiten (mit Drehung) bauen
    async function baue(quelle, indizes) {
      const ziel = await PDFLib.PDFDocument.create();
      const kopien = await ziel.copyPages(quelle, indizes);
      kopien.forEach(function (seite, i) {
        const drehung = seiten[indizes[i]].drehung;
        if (drehung) {
          seite.setRotation(PDFLib.degrees((seite.getRotation().angle + drehung) % 360));
        }
        ziel.addPage(seite);
      });
      return ziel.save();
    }

    function indizes(bedingung) {
      const liste = [];
      seiten.forEach(function (s, i) {
        if (bedingung(s)) {
          liste.push(i);
        }
      });
      return liste;
    }

    const name = function (zusatz) {
      return KD.ohneEndung(datei.name) + "_" + zusatz + ".pdf";
    };

    nurAuswahl.addEventListener("click", function () {
      mitWarten(nurAuswahl, async function () {
        const quelle = await ladePdfLib(datei);
        KD.herunterladen(await baue(quelle, indizes(function (s) { return s.gewaehlt; })), name("auswahl"), "application/pdf");
      });
    });
    ohneAuswahl.addEventListener("click", function () {
      mitWarten(ohneAuswahl, async function () {
        const quelle = await ladePdfLib(datei);
        KD.herunterladen(await baue(quelle, indizes(function (s) { return !s.gewaehlt; })), name("bearbeitet"), "application/pdf");
      });
    });
    allesSpeichern.addEventListener("click", function () {
      mitWarten(allesSpeichern, async function () {
        const quelle = await ladePdfLib(datei);
        KD.herunterladen(await baue(quelle, quelle.getPageIndices()), name("bearbeitet"), "application/pdf");
      });
    });
    einzeln.addEventListener("click", function () {
      mitWarten(einzeln, async function () {
        const quelle = await ladePdfLib(datei);
        const zip = new JSZip();
        const stellen = String(seiten.length).length;
        for (let i = 0; i < seiten.length; i++) {
          const nummer = String(i + 1).padStart(stellen, "0");
          zip.file(KD.ohneEndung(datei.name) + "_seite_" + nummer + ".pdf", await baue(quelle, [i]));
        }
        KD.herunterladen(await zip.generateAsync({ type: "blob" }), KD.ohneEndung(datei.name) + "_seiten.zip");
      });
    });
  }

  // ---------- PDF -> Bilder ----------

  function zeigePdfZuBildern(bereich) {
    const box = karte(bereich, "PDF zu Bildern", "Jede Seite wird als Bild gespeichert. Bei mehreren Seiten kommt eine ZIP-Datei.");
    let datei = null;

    const optionen = el("div", "optionen versteckt");
    const format = auswahl("Format", [["png", "PNG (verlustfrei)"], ["jpg", "JPG (kleiner)"]], "png");
    const aufloesung = auswahl("Auflösung", [["72", "72 DPI (Bildschirm)"], ["150", "150 DPI (Standard)"], ["300", "300 DPI (Druck)"]], "150");
    const bereichLabel = el("label", "", "Seiten (leer = alle)");
    const bereichEingabe = document.createElement("input");
    bereichEingabe.placeholder = "z. B. 1-3, 5";
    bereichLabel.appendChild(bereichEingabe);
    optionen.appendChild(format.label);
    optionen.appendChild(aufloesung.label);
    optionen.appendChild(bereichLabel);

    const info = el("div", "fortschritt");
    const reihe = el("div", "knopfreihe versteckt");
    const umwandeln = knopf("In Bilder umwandeln");
    reihe.appendChild(umwandeln);

    let seitenAnzahl = 0;

    box.appendChild(KD.ablagezone({
      accept: "application/pdf,.pdf",
      hinweis: "Eine PDF-Datei",
      mehrere: false,
      passt: istPdf,
      beiDateien: async function (dateien) {
        try {
          const pdf = await ladePdfJs(dateien[0]);
          seitenAnzahl = pdf.numPages;
          pdf.destroy();
        } catch (fehler) {
          KD.meldung(fehlertext(fehler), true);
          return;
        }
        datei = dateien[0];
        info.textContent = datei.name + " · " + seitenAnzahl + " Seiten";
        optionen.classList.remove("versteckt");
        reihe.classList.remove("versteckt");
      }
    }));
    box.appendChild(info);
    box.appendChild(optionen);
    box.appendChild(reihe);

    umwandeln.addEventListener("click", function () {
      mitWarten(umwandeln, async function () {
        let indizes = [];
        if (bereichEingabe.value.trim() === "") {
          for (let i = 0; i < seitenAnzahl; i++) {
            indizes.push(i);
          }
        } else {
          indizes = leseSeitenbereich(bereichEingabe.value, seitenAnzahl);
          if (!indizes) {
            throw new Error("Ungültige Seitenangabe. Beispiel: 1-3, 5");
          }
        }

        const pdf = await ladePdfJs(datei);
        const skalierung = parseInt(aufloesung.select.value, 10) / 72;
        const typ = format.select.value === "png" ? "image/png" : "image/jpeg";
        const basis = KD.ohneEndung(datei.name);
        const stellen = String(seitenAnzahl).length;
        const zip = new JSZip();
        let einzelBlob = null;
        let einzelName = "";

        for (let n = 0; n < indizes.length; n++) {
          info.textContent = "Seite " + (n + 1) + " von " + indizes.length + " wird umgewandelt …";
          const canvas = await zeichneSeite(pdf, indizes[n] + 1, skalierung);
          const blob = await canvasZuBlob(canvas, typ, 0.9);
          einzelName = basis + "_seite_" + String(indizes[n] + 1).padStart(stellen, "0") + "." + format.select.value;
          einzelBlob = blob;
          zip.file(einzelName, blob);
        }
        pdf.destroy();

        if (indizes.length === 1) {
          KD.herunterladen(einzelBlob, einzelName);
        } else {
          info.textContent = "ZIP-Datei wird gepackt …";
          KD.herunterladen(await zip.generateAsync({ type: "blob" }), basis + "_bilder.zip");
        }
        info.textContent = datei.name + " · " + seitenAnzahl + " Seiten · fertig";
        KD.meldung(indizes.length + " Bild(er) erstellt.");
      });
    });
  }

  // ---------- Text -> PDF ----------

  function zeigeTextZuPdf(bereich) {
    const box = karte(bereich, "Text zu PDF", "Text einfügen oder eine .txt-Datei laden – wird als A4-PDF mit automatischem Zeilenumbruch gespeichert.");

    const textfeld = document.createElement("textarea");
    textfeld.placeholder = "Hier Text eingeben …";
    textfeld.value = KD.leseEinstellung("pdf-text") || "";
    textfeld.addEventListener("input", function () {
      KD.speichereEinstellung("pdf-text", textfeld.value);
    });

    const optionen = el("div", "optionen");
    const schrift = auswahl("Schrift", [
      ["Helvetica", "Helvetica (Arial-ähnlich)"],
      ["TimesRoman", "Times"],
      ["Courier", "Courier (Schreibmaschine)"]
    ], "Helvetica");
    const groesse = auswahl("Schriftgröße", [["10", "10 pt"], ["11", "11 pt"], ["12", "12 pt"], ["14", "14 pt"], ["16", "16 pt"]], "11");
    const nameLabel = el("label", "", "Dateiname");
    const nameEingabe = document.createElement("input");
    nameEingabe.value = "text";
    nameLabel.appendChild(nameEingabe);
    optionen.appendChild(schrift.label);
    optionen.appendChild(groesse.label);
    optionen.appendChild(nameLabel);

    const reihe = el("div", "knopfreihe");
    const erstellen = knopf("PDF erstellen");
    const laden = knopf(".txt-Datei laden", true);
    reihe.appendChild(erstellen);
    reihe.appendChild(laden);

    const dateiEingabe = document.createElement("input");
    dateiEingabe.type = "file";
    dateiEingabe.accept = ".txt,.md,.csv,text/plain";
    dateiEingabe.hidden = true;

    box.appendChild(textfeld);
    box.appendChild(optionen);
    box.appendChild(reihe);
    box.appendChild(dateiEingabe);

    laden.addEventListener("click", function () {
      dateiEingabe.click();
    });
    dateiEingabe.addEventListener("change", async function () {
      const d = dateiEingabe.files[0];
      if (d) {
        textfeld.value = await d.text();
        nameEingabe.value = KD.ohneEndung(d.name);
        KD.speichereEinstellung("pdf-text", textfeld.value);
      }
      dateiEingabe.value = "";
    });

    erstellen.addEventListener("click", function () {
      mitWarten(erstellen, async function () {
        if (textfeld.value.trim() === "") {
          throw new Error("Bitte zuerst Text eingeben.");
        }
        const pdf = await PDFLib.PDFDocument.create();
        const font = await pdf.embedFont(PDFLib.StandardFonts[schrift.select.value]);
        const pt = parseInt(groesse.select.value, 10);
        const rand = 20 * MM;
        const breite = A4[0] - 2 * rand;
        const zeilenAbstand = pt * 1.35;

        const zeilen = umbrechen(bereinige(textfeld.value, font), font, pt, breite);
        let seite = pdf.addPage(A4);
        let y = A4[1] - rand - pt;

        zeilen.forEach(function (zeile) {
          if (y < rand) {
            seite = pdf.addPage(A4);
            y = A4[1] - rand - pt;
          }
          if (zeile !== "") {
            seite.drawText(zeile, { x: rand, y: y, size: pt, font: font, color: PDFLib.rgb(0.1, 0.1, 0.1) });
          }
          y -= zeilenAbstand;
        });

        const name = (nameEingabe.value.trim() || "text").replace(/[\\/:*?"<>|]/g, "_") + ".pdf";
        KD.herunterladen(await pdf.save(), name, "application/pdf");
        KD.meldung("PDF erstellt: " + name + " (" + pdf.getPageCount() + " Seiten)");
      });
    });
  }

  // Standardschriften kennen nur westeuropäische Zeichen – Rest wird zu "?"
  function bereinige(text, font) {
    const bekannt = {};
    let ergebnis = "";
    for (const zeichen of text.replace(/\t/g, "    ").replace(/\r/g, "")) {
      if (zeichen === "\n") {
        ergebnis += zeichen;
        continue;
      }
      if (bekannt[zeichen] === undefined) {
        try {
          font.widthOfTextAtSize(zeichen, 10);
          bekannt[zeichen] = true;
        } catch (e) {
          bekannt[zeichen] = false;
        }
      }
      ergebnis += bekannt[zeichen] ? zeichen : "?";
    }
    return ergebnis;
  }

  function umbrechen(text, font, pt, breite) {
    const zeilen = [];
    const passt = function (t) {
      return font.widthOfTextAtSize(t, pt) <= breite;
    };

    text.split("\n").forEach(function (absatz) {
      let zeile = "";
      absatz.split(" ").forEach(function (wort) {
        const versuch = zeile === "" ? wort : zeile + " " + wort;
        if (passt(versuch)) {
          zeile = versuch;
          return;
        }
        if (zeile !== "") {
          zeilen.push(zeile);
        }
        // Sehr lange Wörter (z. B. Links) buchstabenweise trennen
        zeile = "";
        for (const zeichen of wort) {
          if (!passt(zeile + zeichen)) {
            zeilen.push(zeile);
            zeile = "";
          }
          zeile += zeichen;
        }
      });
      zeilen.push(zeile);
    });
    return zeilen;
  }
})();
