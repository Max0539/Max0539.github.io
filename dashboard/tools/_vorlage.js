// Vorlage für ein neues Werkzeug (wird nicht geladen).
// 1. Datei kopieren, z. B. nach tools/notizen.js
// 2. In index.html unter den anderen Werkzeugen eintragen:
//      <script src="tools/notizen.js?v=1"></script>
// 3. In sw.js die Datei in DATEIEN eintragen und VERSION erhöhen.
// Das Werkzeug belegt dann automatisch den nächsten freien Stellplatz.

(function () {
  const el = KD.element;

  KD.registriere({
    id: "beispiel",                 // erscheint in der Adresse: #/beispiel
    name: "Beispiel-Werkzeug",
    symbol: "frei",                 // Name aus SYMBOLE in app.js oder eigenes <svg>
    beschreibung: "Kurzer Text für die Kachel auf der Übersicht.",
    anzeigen: function (inhalt) {
      const karte = el("div", "karte");
      karte.appendChild(el("h2", "", "Beispiel"));
      karte.appendChild(el("p", "leise", "Hier kommt das Werkzeug hin."));
      inhalt.appendChild(karte);
    }
  });
})();
