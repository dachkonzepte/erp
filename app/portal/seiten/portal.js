/* Kundenportal (seit 1.11.14, Stufe P1e; Bauplan P1, Abschnitt 5) -- die Abläufe der Seite: A Link prüfen, B Code senden, C Code eingeben,
   D Willkommen, E Fehlerseite. Nur Text über textContent (nie innerHTML: die Seite verlangt Trusted Types, CSP ohne Inline-Skript).

   - Der Link steht nur im #-Fragment (er geht nie als Adresse zum Server); das Skript nimmt ihn sofort aus der Adresszeile und dem Verlauf
     (history.replaceState) und schickt ihn einmal in der Kopfzeile X-Portal-Link (POST /api/link).
   - Was der Server antwortet, entscheidet; jeder Grund, aus dem ein Link nicht gilt, ist dieselbe Fehlerseite (nie ein Hinweis auf den Grund).
   - Die Sitzung liegt nur in Cookies (HttpOnly) -- das Skript sieht sie nicht. Im Speicher dieses Tabs (sessionStorage) steht während der Anmeldung
     nur der Schritt, die verdeckte Adresse („m***@…“) und wann der Code angefordert wurde, damit ein Neuladen (etwa nach dem Wechsel in die Mail-App)
     beim Code weitermacht.
   - Seit 1.11.16 (Antwort P1e-4): wartet ein Code nach 30 Sekunden noch auf den Postboten, geht die Seite weiter zu C mit dem Hinweis „Der Versand
     dauert länger als sonst …“ und fragt weiter nach dem Stand (alle 5 Sekunden) -- ein Auftrag gilt 10 Minuten; „gescheitert“ erst, wenn der Postbote
     gescheitert oder verworfen meldet oder nach 10 Minuten nichts ging (sonst forderte der Kunde neu an, und der erste Code käme danach und gälte nicht
     mehr). „Neuen Code senden“ bleibt erst 60 Sekunden nach der Anforderung.
   - Hell oder dunkel nach dem Gerät: data-theme an <html> wie im ERP (ds.css), auch wenn das Gerät umschaltet. */
(function () {
  'use strict';

  // --- hell / dunkel (vor dem ersten Zeichnen; das Skript steht im Kopf) -----------------------------------------------------------------
  var dunkel = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function thema() { document.documentElement.setAttribute('data-theme', dunkel && dunkel.matches ? 'dark' : 'light'); }
  thema();
  if (dunkel && dunkel.addEventListener) dunkel.addEventListener('change', thema);

  var CODE_SEKUNDEN = 60;      // ein neuer Code frühestens nach 60 Sekunden (portal_code_anfordern())
  var LANGSAM_MS = 30000;      // seit 1.11.16: wartet der Code so lange, weiter zu C mit dem Hinweis „Der Versand dauert länger als sonst …“
  var AUFTRAG_MS = 600000;     // ein Auftrag an den Postboten gilt 10 Minuten -- danach gilt der Versand als gescheitert
  var STAND_MS = 1000;         // so oft fragt die Seite nach dem Stand, bis 30 Sekunden um sind …
  var STAND_LANGSAM_MS = 5000; // … danach so oft
  var SPEICHER = 'dkportal';
  var LEERZEICHEN = /[    ]/g;  // wie der Server (app/portal/routen.py::CODE_LEERZEICHEN)

  // E: Überschrift und Satz je Fall (Entwurf Portal-Handy, „eine Seite für alles, nur der Text wechselt“)
  var FEHLER = {
    link: ['Dieser Link funktioniert nicht', 'Bitte nutzen Sie den Link aus unserer letzten E-Mail. Gern senden wir Ihnen auch einen neuen.'],
    lesezeichen: ['Bitte über den Link anmelden', 'Öffnen Sie das Kundenportal über den Link aus unserer E-Mail.'],
    abgemeldet: ['Sie sind abgemeldet', 'Zum erneuten Anmelden öffnen Sie den Link aus unserer E-Mail.'],
    zu_viele: ['Zu viele Versuche', 'Bitte versuchen Sie es in einigen Minuten erneut.'],
    nicht_gefunden: ['Diese Seite gibt es nicht', 'Öffnen Sie das Kundenportal über den Link aus unserer E-Mail.'],
    technisch: ['Gerade klappt etwas nicht', 'Bitte versuchen Sie es später erneut oder rufen Sie uns an.'],
    wartung: ['Gleich wieder da', 'Das Kundenportal ist in wenigen Minuten wieder erreichbar.']
  };
  var TEXT = {
    gesendet_fehler: 'Der Code konnte gerade nicht gesendet werden. Bitte versuchen Sie es gleich noch einmal oder rufen Sie uns an.',
    wieder_moeglich: function (n) { return 'Ein neuer Code ist in ' + n + (n === 1 ? ' Minute' : ' Minuten') + ' wieder möglich.'; },
    falsch: function (n) { return 'Dieser Code stimmt nicht. Noch ' + n + (n === 1 ? ' Versuch.' : ' Versuche.'); },
    sechs: 'Bitte geben Sie die 6 Ziffern aus der E-Mail ein.',
    senden: 'Code senden', wird_gesendet: 'Wird gesendet …', anmelden: 'Anmelden', wird_geprueft: 'Wird geprüft …',
    neu: 'Neuen Code senden'
  };

  var el = function (id) { return document.getElementById(id); };
  var adresse = '';          // verdeckte Adresse („m***@beispiel.de“) aus POST /api/link
  var uhr = null;            // Zähler bis „Neuen Code senden“
  var sperreBis = 0;         // Zeitpunkt (ms), bis „Code senden“ gesperrt bleibt (Bremse)
  var angefordert = 0;       // Zeitpunkt (ms), zu dem der letzte Code angefordert wurde
  var versandLauf = 0;       // nur die jüngste Frage nach dem Stand läuft weiter (ein neuer Code beendet die alte)

  // --- Speicher dieses Tabs (nur Schritt und verdeckte Adresse) ---------------------------------------------------------------------------
  function merken(schritt) {
    try { window.sessionStorage.setItem(SPEICHER, JSON.stringify({ schritt: schritt, adresse: adresse, seit: angefordert })); } catch (e) { /* ohne Speicher geht es auch */ }
  }
  function vergessen() { try { window.sessionStorage.removeItem(SPEICHER); } catch (e) { /* nichts */ } }
  function gemerkt() {
    try {
      var d = JSON.parse(window.sessionStorage.getItem(SPEICHER) || 'null');
      return d && (d.schritt === 'b' || d.schritt === 'c') && typeof d.adresse === 'string' && typeof d.seit === 'number' ? d : null;
    } catch (e) { return null; }
  }

  // --- Anfragen ----------------------------------------------------------------------------------------------------------------------------
  function anfrage(methode, pfad, koerper, kopf) {
    var optionen = { method: methode, credentials: 'same-origin', cache: 'no-store', headers: kopf || {} };
    if (koerper !== undefined) {
      optionen.headers['Content-Type'] = 'application/json';
      optionen.body = JSON.stringify(koerper);
    }
    return window.fetch(pfad, optionen).then(function (r) {
      return r.text().then(function (t) {
        var daten = null;
        try { daten = t ? JSON.parse(t) : null; } catch (e) { daten = null; }
        return { status: r.status, daten: daten || {} };
      });
    }, function () { return { status: 0, daten: {} }; });
  }

  // ein Status, den kein Ablauf erwartet -> Fehlerseite
  function fallVon(status) {
    if (status === 401) return 'lesezeichen';
    if (status === 429) return 'zu_viele';
    if (status === 502 || status === 504) return 'wartung';  // nginx, solange der Dienst neu startet
    return 'technisch';
  }

  // --- Anzeige -----------------------------------------------------------------------------------------------------------------------------
  var ABSCHNITTE = ['seite-a', 'seite-b', 'seite-c', 'seite-d', 'seite-e'];
  function zeigen(id) {
    ABSCHNITTE.forEach(function (a) { el(a).hidden = a !== id; });
    var angemeldet = id === 'seite-d';
    el('kopf-abmelden').hidden = !angemeldet;
    document.body.classList.toggle('angemeldet', angemeldet);
    var titel = el(id).querySelector('h1');
    if (titel && id !== 'seite-a') titel.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }

  function fehler(fall) {
    var f = FEHLER[fall] || FEHLER.technisch;
    vergessen();
    anhalten();
    el('e-titel').textContent = f[0];
    el('e-satz').textContent = f[1];
    zeigen('seite-e');
  }

  function meldung(seite, text, mitTelefon) {
    el(seite + '-meldung-text').textContent = text || '';
    el(seite + '-meldung').hidden = !text;
    var tel = el(seite + '-telefon');
    if (tel) tel.hidden = !(text && mitTelefon);
  }

  function knopf(id, text, gesperrt) {
    var k = el(id);
    k.textContent = text;
    k.disabled = !!gesperrt;
  }

  // --- A: Link prüfen ---------------------------------------------------------------------------------------------------------------------
  function linkPruefen(wert) {
    zeigen('seite-a');
    return anfrage('POST', '/api/link', undefined, { 'X-Portal-Link': wert }).then(function (r) {
      if (r.status === 200 && r.daten.stand === 'angemeldet') return willkommen();
      if (r.status === 200 && r.daten.stand === 'code_noetig') {
        adresse = String(r.daten.email_anzeige || '');
        merken('b');
        return zeigeB();
      }
      if (r.status === 200) return fehler('link');  // „ungueltig“: aus welchem Grund auch immer -- dieselbe Seite
      return fehler(fallVon(r.status));
    });
  }

  // ohne Link: angemeldet? sonst eine laufende Anmeldung dieses Tabs fortsetzen, sonst Fehlerseite
  function ohneLink() {
    return anfrage('POST', '/api/sitzung/weiter').then(function (r) {
      if (r.status === 200) return willkommen();
      if (r.status !== 401) return fehler(fallVon(r.status));
      var g = gemerkt();
      if (!g) return fehler('lesezeichen');
      adresse = g.adresse;
      angefordert = g.seit;
      return anfrage('GET', '/api/code/stand').then(function (s) {
        if (s.status !== 200) return fehler(fallVon(s.status));
        if (s.daten.stand === 'gesendet') return zeigeC('gesendet');
        if (s.daten.stand === 'wartet' && angefordert && Date.now() - angefordert >= LANGSAM_MS) { zeigeC('dauert'); return warteAufVersand('c', true); }
        if (s.daten.stand === 'wartet') { zeigeB(); knopf('b-senden', TEXT.wird_gesendet, true); return warteAufVersand('b'); }
        zeigeB();
        if (s.daten.stand === 'fehler' || s.daten.stand === 'verworfen') meldung('b', TEXT.gesendet_fehler, true);
        return null;
      });
    });
  }

  // --- B: Code senden ---------------------------------------------------------------------------------------------------------------------
  function zeigeB() {
    el('b-adresse').textContent = adresse;
    meldung('b', '');
    knopf('b-senden', TEXT.senden, Date.now() < sperreBis);
    zeigen('seite-b');
  }

  function codeSenden(seite) {
    var k = seite === 'b' ? 'b-senden' : (el('c-neu-haupt').hidden ? 'c-neu' : 'c-neu-haupt');
    meldung(seite, '');
    knopf(k, TEXT.wird_gesendet, true);
    return anfrage('POST', '/api/code').then(function (r) {
      if (r.status === 200) { angefordert = Date.now(); merken(seite); return warteAufVersand(seite); }
      if (r.status === 429) {
        var n = Math.max(1, parseInt(r.daten.minuten, 10) || 1);
        sperreBis = Date.now() + n * 60000;
        knopf(k, TEXT[seite === 'b' ? 'senden' : 'neu'], true);
        meldung(seite, TEXT.wieder_moeglich(n), false);
        window.setTimeout(function () { if (Date.now() >= sperreBis) knopf(k, TEXT[seite === 'b' ? 'senden' : 'neu'], false); }, n * 60000);
        return null;
      }
      return fehler(fallVon(r.status));
    });
  }

  // der Postbote schickt den Code; die Seite fragt den Stand (wartet, gesendet, fehler, verworfen). Seit 1.11.16: nach 30 Sekunden weiter zu C mit dem
  // Hinweis, weiter fragen; gescheitert nur auf Meldung des Postboten oder nach 10 Minuten.
  function warteAufVersand(seite, schonLangsam) {
    var langsam = !!schonLangsam;
    var lauf = ++versandLauf;
    function nochmal() {
      return new Promise(function (ok) { window.setTimeout(ok, langsam ? STAND_LANGSAM_MS : STAND_MS); }).then(frage);
    }
    function frage() {
      if (lauf !== versandLauf) return null;
      return anfrage('GET', '/api/code/stand').then(function (s) {
        if (lauf !== versandLauf) return null;
        if (s.status !== 200) return fehler(fallVon(s.status));
        var alter = Date.now() - angefordert;
        if (s.daten.stand === 'gesendet') {
          merken('c');
          if (langsam) { el('c-dauert').hidden = true; el('c-gesendet').hidden = false; return null; }  // die Eingabe bleibt stehen
          return zeigeC('gesendet');
        }
        if (s.daten.stand === 'wartet' && alter < AUFTRAG_MS) {
          if (!langsam && alter >= LANGSAM_MS) { langsam = true; merken('c'); zeigeC('dauert'); }
          return nochmal();
        }
        // gescheitert, verworfen, keiner -- oder nach 10 Minuten nichts
        versandGescheitert(langsam ? 'c' : seite);
        return null;
      });
    }
    return frage();
  }

  function versandGescheitert(seite) {
    if (seite === 'b') { knopf('b-senden', TEXT.senden, false); meldung('b', TEXT.gesendet_fehler, true); return; }
    el('c-dauert').hidden = true;
    el('c-gesendet').hidden = true;
    anhalten();
    neuKnoepfe(false);
    meldung('c', TEXT.gesendet_fehler, true);
  }

  // --- C: Code eingeben -------------------------------------------------------------------------------------------------------------------
  // art: 'gesendet' (Hinweis „Code gesendet an …“), 'dauert' (seit 1.11.16: „Der Versand dauert länger als sonst …“) oder leer
  function zeigeC(art) {
    el('c-adresse').textContent = adresse;
    el('c-adresse-2').textContent = adresse;
    el('c-gesendet').hidden = art !== 'gesendet';
    el('c-dauert').hidden = art !== 'dauert';
    el('c-titel').textContent = 'Code eingeben';
    el('c-feld').hidden = false;
    el('c-abgelaufen').hidden = true;
    el('c-anmelden').hidden = false;
    el('c-neu-haupt').hidden = true;
    el('c-neu').hidden = false;
    el('c-neu-gilt').hidden = true;
    el('c-gilt').hidden = false;
    feldFehler('');
    meldung('c', '');
    knopf('c-anmelden', TEXT.anmelden, false);
    var feld = el('c-code');
    feld.value = '';
    zeigen('seite-c');
    var rest = angefordert ? Math.ceil((angefordert + CODE_SEKUNDEN * 1000 - Date.now()) / 1000) : 0;  // 60 Sekunden ab der Anforderung
    if (rest > 0) zaehlen(rest);
    else neuKnoepfe(false);
    feld.focus({ preventScroll: true });
  }

  function feldFehler(text) {
    el('c-fehler-text').textContent = text;
    el('c-fehler').hidden = !text;
    var feld = el('c-code');
    if (text) { feld.setAttribute('aria-invalid', 'true'); feld.setAttribute('aria-describedby', 'c-fehler'); }
    else { feld.removeAttribute('aria-invalid'); feld.setAttribute('aria-describedby', 'c-gilt'); }
  }

  function anhalten() { if (uhr) { window.clearInterval(uhr); uhr = null; } }

  function neuKnoepfe(gesperrt, rest) {
    var text = TEXT.neu + (gesperrt && rest > 0 ? ' · in ' + Math.floor(rest / 60) + ':' + ('0' + (rest % 60)).slice(-2) : '');
    knopf('c-neu', text, gesperrt);
    knopf('c-neu-haupt', TEXT.neu, gesperrt);
  }

  // „Neuen Code senden · in 0:48“ -- erst nach 60 Sekunden
  function zaehlen(sekunden) {
    anhalten();
    var ende = Date.now() + sekunden * 1000;
    function schritt() {
      var rest = Math.ceil((ende - Date.now()) / 1000);
      if (rest <= 0) { anhalten(); neuKnoepfe(false); return; }
      neuKnoepfe(true, rest);
    }
    schritt();
    uhr = window.setInterval(schritt, 250);
  }

  function zeigeNeuAnfordern() {
    el('c-gesendet').hidden = true;
    el('c-dauert').hidden = true;
    el('c-titel').textContent = 'Neuen Code anfordern';
    el('c-feld').hidden = true;
    el('c-abgelaufen').hidden = false;
    el('c-anmelden').hidden = true;
    el('c-neu').hidden = true;
    el('c-neu-haupt').hidden = false;
    el('c-neu-gilt').hidden = false;
    meldung('c', '');
    anhalten();
    neuKnoepfe(false);
    el('c-titel').focus({ preventScroll: true });
  }

  function codePruefen() {
    var feld = el('c-code');
    var code = String(feld.value || '').replace(LEERZEICHEN, '');
    if (!/^[0-9]{6}$/.test(code)) { feldFehler(TEXT.sechs); feld.focus(); return null; }
    feldFehler('');
    el('c-gesendet').hidden = true;
    el('c-dauert').hidden = true;
    knopf('c-anmelden', TEXT.wird_geprueft, true);
    return anfrage('POST', '/api/code/pruefen', { code: code }).then(function (r) {
      knopf('c-anmelden', TEXT.anmelden, false);
      if (r.status === 200 && r.daten.stand === 'angemeldet') { vergessen(); anhalten(); versandLauf += 1; return willkommen(); }
      if (r.status === 200 && r.daten.stand === 'falsch' && r.daten.rest > 0) {
        el('c-gilt').hidden = true;
        feldFehler(TEXT.falsch(r.daten.rest));
        feld.focus();
        return null;
      }
      if (r.status === 200) return zeigeNeuAnfordern();  // „neu_anfordern“ (abgelaufen, verbraucht, 5 Fehlversuche) oder kein Versuch mehr
      return fehler(fallVon(r.status));
    });
  }

  // --- D: Willkommen ----------------------------------------------------------------------------------------------------------------------
  function willkommen() {
    return anfrage('GET', '/api/willkommen').then(function (r) {
      if (r.status !== 200) return fehler(fallVon(r.status));
      vergessen();
      el('d-gruss').textContent = String(r.daten.begruessung || 'Guten Tag');
      zeigen('seite-d');
      return bereichZeigen(bereichAusAdresse(), true);  // seit 1.11.46: der Bereich aus ?bereich=…, sonst die Übersicht
    });
  }

  function abmelden(ueberall) {
    var dialog = el('dialog-ueberall');
    return anfrage('POST', '/api/abmelden', { ueberall: !!ueberall }).then(function (r) {
      if (dialog.open) dialog.close();
      if (r.status === 200) return fehler('abgemeldet');
      return fehler(fallVon(r.status));
    });
  }


  // --- Bereiche (seit 1.11.46, Stufe P2e; Entwürfe P2, Seiten 1–5) ---------------------------------------------------------------------------
  // Jede Zahl und jeder Text kommt fertig vom Server (POST /api/uebersicht, /api/unterlagen, /api/rechnungen, /api/termine); hier nur Text über
  // textContent. Der Bereich steht in der Adresse als ?bereich=… (nie im #-Fragment: dort steht der Link der Anmeldung). „Ansehen“ fordert die
  // Datei an und öffnet sie im selben Tab; die Vorschau eines Fotos kommt ohne Anforderung (/datei/<n>/vorschau).
  var BEREICHE = ['uebersicht', 'unterlagen', 'rechnungen', 'termine', 'fotos'];
  var WEG = { uebersicht: '/api/uebersicht', unterlagen: '/api/unterlagen', rechnungen: '/api/rechnungen', termine: '/api/termine', fotos: '/api/unterlagen' };
  var JE_SEITE = 12;
  var B = {
    nicht_verfuegbar: ['Nicht mehr verfügbar.', 'Diese Unterlage ist nicht mehr verfügbar. Bei Fragen rufen Sie uns gern an'],
    zu_viele: ['Zu viele Abrufe.', 'Bitte versuchen Sie es in einigen Minuten erneut.'],
    technisch: ['Gerade klappt etwas nicht.', 'Bitte versuchen Sie es später erneut oder rufen Sie uns an.'],
    oeffnet: 'Wird geöffnet …', ansehen: 'Ansehen', herunterladen: 'Herunterladen', mehr: 'Weitere 12 Fotos laden',
    stand_alt: ' – wird in Kürze aktualisiert.',
    leer: {
      uebersicht: ['Noch keine Unterlagen', 'Sobald es Unterlagen zu Ihrem Auftrag gibt, finden Sie sie hier. Bis dahin erhalten Sie alles wie gewohnt per E-Mail oder Post.'],
      unterlagen: ['Noch keine Unterlagen', 'Hier erscheinen Angebote, Verträge und Protokolle zu Ihren Aufträgen.'],
      rechnungen: ['Noch keine Rechnungen', 'Hier erscheinen Ihre Rechnungen, sobald wir sie Ihnen geschickt haben.'],
      termine: ['Zurzeit keine festen Termine', 'Sobald Ihre Baustelle fest eingeplant ist, sehen Sie hier die Tage.'],
      fotos: ['Noch keine Fotos', 'Fotos Ihrer Baustelle stellen wir hier für Sie ein.']
    },
    keine_weiteren: 'Zurzeit keine weiteren Termine', vergangen: 'Vergangen', alles_bezahlt: 'Alles bezahlt – vielen Dank', alles_bezahlt_kachel: 'Alles bezahlt',
    kein_termin: 'Zurzeit kein fester Termin', heute: 'heute'
  };
  var bereich = 'uebersicht';
  var bereichLauf = 0;
  var fotoListe = [];   // alle Fotos der Seite „Fotos“ in Reihenfolge (für „groß ansehen“)
  var fotoStelle = -1;

  function neu(tag, klasse, text) {
    var e = document.createElement(tag);
    if (klasse) e.className = klasse;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }
  function nummer(n) { var z = Number(n); return Number.isInteger(z) && z > 0 && z < 2147483648 ? z : 0; }
  // Die einzigen Stellen, die eine Adresse setzen: fester lokaler Anfang, dahinter nur eine ganze Zahl (Freigabe)
  function zurDatei(freigabe, herunterladen) {
    var n = nummer(freigabe);
    if (n) window.location.assign('/datei/' + n + (herunterladen ? '/herunterladen' : ''));  // im selben Tab, „Zurück“ führt hierher
  }
  function vorschauSetzen(bild, freigabe, gross) {
    var n = nummer(freigabe);
    if (n) bild.setAttribute('src', '/datei/' + n + (gross ? '' : '/vorschau'));
  }

  function hinweisIn(behaelter, art, mitTelefon) {
    var t = B[art] || B.technisch;
    var h = neu('div', 'hinweis neutral bereich-hinweis');
    h.setAttribute('role', 'alert');
    var s = neu('span');
    s.append(neu('strong', '', t[0]), document.createTextNode(' ' + t[1]));
    var tel = el('seite-d').getAttribute('data-telefon');
    if (mitTelefon && tel) s.append(document.createTextNode(': ' + tel + '.'));
    else if (mitTelefon) s.append(document.createTextNode('.'));
    h.append(s);
    var alt = behaelter.querySelector('.bereich-hinweis');
    if (alt) alt.remove();
    behaelter.prepend(h);
  }

  function platzhalter(liste) {
    var k = neu('div', 'karte laedt');
    k.setAttribute('aria-busy', 'true');
    for (var i = 0; i < 3; i++) k.append(neu('div', 'platzhalter-zeile'));
    liste.replaceChildren(k);
  }

  function leerKarte(art) {
    var k = neu('div', 'karte leer');
    k.append(neu('h2', '', B.leer[art][0]), neu('p', 'leise', B.leer[art][1]));
    return k;
  }

  function standText(stand) {
    if (!stand || !stand.text) return '';
    return 'Stand: ' + stand.text + (stand.alt ? B.stand_alt : '');
  }
  function standZeigen(id, stand, vorsatz) {
    var p = el(id);
    var t = standText(stand);
    p.textContent = t ? (vorsatz ? t.replace('Stand: ', vorsatz) : t) : '';
    p.hidden = !t;
    p.classList.toggle('alt', !!(stand && stand.alt && stand.text));
  }

  function gruppenKopf(g, zahlText) {
    var kopf = neu('div', 'gruppe-kopf');
    var links = neu('div', 'gruppe-titel');
    links.append(neu('h2', '', g.titel));
    if (g.unter) links.append(neu('p', 'leise', g.unter));
    kopf.append(links);
    if (zahlText) kopf.append(neu('span', 'leise gruppe-zahl', zahlText));
    return kopf;
  }

  function dateiKnoepfe(freigabe, behaelter) {
    var box = neu('div', 'datei-knoepfe');
    var ansehen = neu('button', 'knopf zweit klein ansehen', B.ansehen);
    ansehen.type = 'button';
    var laden = neu('button', 'knopf zweit klein herunterladen');
    laden.type = 'button';
    laden.setAttribute('aria-label', B.herunterladen);
    laden.append(symbolKopie('sym-herunter'));
    ansehen.addEventListener('click', function () { anfordern(freigabe, false, ansehen, behaelter); });
    laden.addEventListener('click', function () { anfordern(freigabe, true, laden, behaelter); });
    box.append(ansehen, laden);
    return box;
  }
  // die Symbole stehen einmal verborgen in der Seite (Vorlage); kopiert, nie aus Text gebaut
  function symbolKopie(id) {
    var v = el(id);
    var s = v ? v.cloneNode(true) : neu('span');
    s.removeAttribute('id');
    s.hidden = false;
    return s;
  }

  function anfordern(freigabe, herunterladen, knopfEl, behaelter) {
    var vorher = knopfEl.textContent;
    var nurSymbol = knopfEl.classList.contains('herunterladen');
    knopfEl.disabled = true;
    if (!nurSymbol) knopfEl.textContent = B.oeffnet;
    return anfrage('POST', '/api/datei/anfordern', { freigabe: nummer(freigabe) }).then(function (r) {
      if (r.status === 200) {
        if (herunterladen) { knopfEl.disabled = false; if (!nurSymbol) knopfEl.textContent = vorher; }
        zurDatei(freigabe, herunterladen);
        return null;
      }
      knopfEl.disabled = false;
      if (!nurSymbol) knopfEl.textContent = vorher;
      if (r.status === 401) return fehler('lesezeichen');
      hinweisIn(behaelter, r.status === 404 ? 'nicht_verfuegbar' : r.status === 429 ? 'zu_viele' : 'technisch', r.status === 404);
      return null;
    });
  }

  // --- Zeichnen je Bereich ----------------------------------------------------------------------------------------------------------------
  function zeichneUebersicht(d) {
    var r = d.rechnungen;
    el('k-rechnungen-zahl').textContent = r.offen ? r.offen + ' offen' : '';
    el('k-rechnungen-zahl').hidden = !r.offen;
    el('k-rechnungen-wert').textContent = r.offen ? r.betrag + ' offen' : B.alles_bezahlt_kachel;
    el('k-rechnungen-satz').textContent = r.faellig || '';
    el('k-einsatz-wert').textContent = d.einsatz ? d.einsatz.wann : B.kein_termin;
    el('k-einsatz-satz').textContent = d.einsatz ? d.einsatz.wo : '';
    el('k-unterlagen-wert').textContent = d.unterlagen.zahl + (d.unterlagen.zahl === 1 ? ' Unterlage' : ' Unterlagen');
    el('k-unterlagen-satz').textContent = d.unterlagen.zuletzt ? 'Zuletzt: ' + d.unterlagen.zuletzt : '';
    el('k-fotos-wert').textContent = d.fotos.zahl + (d.fotos.zahl === 1 ? ' Foto' : ' Fotos');
    el('k-fotos-satz').textContent = d.fotos.zuletzt ? 'Zuletzt hinzugefügt am ' + d.fotos.zuletzt : '';
    var nichts = !r.offen && !d.einsatz && !d.unterlagen.zahl && !d.fotos.zahl && !r.faellig;
    el('d-leer').hidden = !nichts;
    standZeigen('d-stand', d.stand);
  }

  function zeichneUnterlagen(d) {
    var liste = el('u-liste');
    if (!d.unterlagen.length) { liste.replaceChildren(leerKarte('unterlagen')); return; }
    liste.replaceChildren.apply(liste, d.unterlagen.map(function (g) {
      var k = neu('section', 'karte gruppe');
      k.append(gruppenKopf(g, g.zahl_text));
      g.zeilen.forEach(function (z) {
        var zeile = neu('div', 'zeile');
        var kachel = neu('span', 'kachel');
        kachel.append(symbolKopie('sym-' + (z.art === 'angebot' ? 'stift' : z.art === 'brief' ? 'mail' : z.art === 'einsatzbericht' ? 'schraube'
          : (z.art === 'abnahmeprotokoll' || z.art === 'checkliste') ? 'protokoll' : 'vertrag')));
        var text = neu('div', 'zeile-text');
        text.append(neu('span', 'zeile-titel', z.titel), neu('span', 'leise zeile-art', z.art_text + ' · ' + z.datum));
        var kn = dateiKnoepfe(z.freigabe, el('bereich-unterlagen'));
        text.addEventListener('click', function () { kn.firstChild.click(); });  // auf dem Handy: die Zeile antippen (Entwurf Seite 4)
        zeile.append(kachel, text, neu('span', 'leise nur-breit zeile-art-breit', z.art_text), neu('span', 'mono nur-breit zeile-datum', z.datum), kn);
        k.append(zeile);
      });
      return k;
    }));
  }

  function zeichneRechnungen(d) {
    var liste = el('r-liste');
    el('r-summe').hidden = !d.gruppen.length;
    el('r-offen-titel').textContent = d.alles_bezahlt ? B.alles_bezahlt : 'Offen insgesamt';
    el('r-offen').textContent = d.offen || '';
    el('r-offen').hidden = !d.offen;
    standZeigen('r-stand', d.stand, 'Stand der Zahlungen: ');
    if (!d.gruppen.length) { liste.replaceChildren(leerKarte('rechnungen')); return; }
    liste.replaceChildren.apply(liste, d.gruppen.map(function (g) {
      var k = neu('section', 'karte gruppe');
      k.append(gruppenKopf(g, g.zahl_text));
      g.zeilen.forEach(function (z) {
        var block = neu('div', 'zeile-block');
        var zeile = neu('div', 'zeile');
        var kachel = neu('span', 'kachel');
        kachel.append(symbolKopie('sym-rechnung'));
        var text = neu('div', 'zeile-text');
        text.append(neu('span', 'zeile-titel', z.titel), neu('span', 'leise mono', [z.nummer, z.datum].filter(Boolean).join(' · ')));
        var zustand = neu('div', 'zustand');
        if (z.kennzeichen) zustand.append(neu('span', 'chip ' + (z.farbe || 'neutral'), z.kennzeichen));
        z.hinweis.forEach(function (h) { zustand.append(neu('span', 'zustand-hinweis', h)); });
        var kn = dateiKnoepfe(z.freigabe, el('bereich-rechnungen'));
        text.addEventListener('click', function () { kn.firstChild.click(); });
        zeile.append(kachel, text, neu('span', 'mono betrag', z.betrag || ''), zustand, kn);
        block.append(zeile);
        z.mahnungen.forEach(function (m) {
          var mz = neu('div', 'zeile mahnung');
          mz.append(neu('span', 'mahnung-linie'), neu('span', 'zeile-titel', m.titel), neu('span', 'mono leise', m.datum),
            dateiKnoepfe(m.freigabe, el('bereich-rechnungen')));
          block.append(mz);
        });
        k.append(block);
      });
      return k;
    }));
  }

  function termineGruppen(gruppen, vergangen) {
    return gruppen.map(function (g) {
      var k = neu('section', 'karte gruppe' + (vergangen ? ' vergangen' : ''));
      k.append(gruppenKopf(g, ''));
      g.zeilen.forEach(function (t) {
        var z = neu('div', 'termin' + (t.heute ? ' heute' : ''));
        var w = neu('div', 'termin-text');
        w.append(neu('span', 'termin-wann', t.wann), neu('span', 'leise', t.dauer));
        z.append(w);
        if (t.heute) z.append(neu('span', 'chip ok', B.heute));
        k.append(z);
      });
      return k;
    });
  }
  function zeichneTermine(d) {
    var liste = el('t-liste');
    standZeigen('t-stand', d.stand);
    var teile = [];
    if (!d.kommend.length && !d.vergangen.length) { liste.replaceChildren(leerKarte('termine')); return; }
    if (!d.kommend.length) { var k = neu('div', 'karte leer'); k.append(neu('h2', '', B.keine_weiteren)); teile.push(k); }
    teile = teile.concat(termineGruppen(d.kommend, false));
    if (d.vergangen.length) { teile.push(neu('p', 'leise abschnitt', B.vergangen)); teile = teile.concat(termineGruppen(d.vergangen, true)); }
    liste.replaceChildren.apply(liste, teile);
  }

  function zeichneFotos(d) {
    var liste = el('f-liste');
    fotoListe = [];
    if (!d.fotos.length) { liste.replaceChildren(leerKarte('fotos')); return; }
    liste.replaceChildren.apply(liste, d.fotos.map(function (g) {
      var k = neu('section', 'karte gruppe');
      k.append(gruppenKopf(g, g.zahl_text));
      var raster = neu('div', 'foto-raster');
      var mehr = neu('button', 'knopf zweit klein foto-mehr', B.mehr);
      mehr.type = 'button';
      var gezeigt = 0;
      function weiter() {
        g.zeilen.slice(gezeigt, gezeigt + JE_SEITE).forEach(function (f) {
          var stelle = fotoListe.length;
          fotoListe.push(f);
          var b = neu('button', 'foto');
          b.type = 'button';
          b.setAttribute('aria-label', f.titel + ' · ' + f.datum);
          var bild = neu('img');
          bild.alt = '';
          bild.loading = 'lazy';
          bild.addEventListener('error', function () { b.classList.add('ohne-bild'); });
          vorschauSetzen(bild, f.freigabe, false);
          b.append(bild);
          b.addEventListener('click', function () { fotoGross(stelle); });
          raster.append(b);
        });
        gezeigt = Math.min(gezeigt + JE_SEITE, g.zeilen.length);
        mehr.hidden = gezeigt >= g.zeilen.length;
      }
      mehr.addEventListener('click', weiter);
      weiter();
      k.append(raster, mehr);
      return k;
    }));
  }

  function fotoGross(stelle) {
    var f = fotoListe[stelle];
    if (!f) return null;
    fotoStelle = stelle;
    var dialog = el('foto-gross');
    el('foto-gross-titel').textContent = 'Foto ' + (stelle + 1) + ' von ' + fotoListe.length;
    el('foto-gross-text').textContent = f.bildtext;
    el('foto-gross-zurueck').disabled = stelle === 0;
    el('foto-gross-vor').disabled = stelle === fotoListe.length - 1;
    var bild = el('foto-gross-bild');
    bild.removeAttribute('src');
    if (!dialog.open) dialog.showModal();
    return anfrage('POST', '/api/datei/anfordern', { freigabe: nummer(f.freigabe) }).then(function (r) {
      if (fotoStelle !== stelle) return null;
      if (r.status === 200) { vorschauSetzen(bild, f.freigabe, true); return null; }
      dialog.close();
      if (r.status === 401) return fehler('lesezeichen');
      hinweisIn(el('bereich-fotos'), r.status === 404 ? 'nicht_verfuegbar' : r.status === 429 ? 'zu_viele' : 'technisch', r.status === 404);
      return null;
    });
  }

  var ZEICHNEN = { uebersicht: zeichneUebersicht, unterlagen: zeichneUnterlagen, rechnungen: zeichneRechnungen, termine: zeichneTermine, fotos: zeichneFotos };
  var LISTE = { unterlagen: 'u-liste', rechnungen: 'r-liste', termine: 't-liste', fotos: 'f-liste' };

  function bereichLaden(name) {
    var lauf = ++bereichLauf;
    var pane = el('bereich-' + name);
    var alt = pane.querySelector('.bereich-hinweis');
    if (alt) alt.remove();
    if (LISTE[name]) platzhalter(el(LISTE[name]));
    pane.setAttribute('aria-busy', 'true');
    return anfrage('POST', WEG[name]).then(function (r) {
      if (lauf !== bereichLauf) return null;
      pane.removeAttribute('aria-busy');
      if (r.status === 200) { ZEICHNEN[name](r.daten); return null; }
      if (r.status === 401) return fehler('lesezeichen');
      if (LISTE[name]) el(LISTE[name]).replaceChildren();
      hinweisIn(pane, r.status === 429 ? 'zu_viele' : 'technisch', false);
      return null;
    });
  }

  function bereichZeigen(name, ohneAdresse) {
    if (BEREICHE.indexOf(name) < 0) name = 'uebersicht';
    bereich = name;
    BEREICHE.forEach(function (b) {
      el('bereich-' + b).hidden = b !== name;
      document.querySelectorAll('[data-bereich="' + b + '"]').forEach(function (k) {
        if (b === name) k.setAttribute('aria-current', 'page'); else k.removeAttribute('aria-current');
      });
    });
    if (!ohneAdresse) window.history.replaceState(null, '', name === 'uebersicht' ? '/' : '/?bereich=' + name);
    var titel = el('bereich-' + name).querySelector('h1');
    if (titel) titel.focus({ preventScroll: true });
    window.scrollTo(0, 0);
    return bereichLaden(name);
  }

  function bereichAusAdresse() {
    var m = /(?:^|[?&])bereich=([a-z]+)(?:&|$)/.exec(window.location.search || '');
    return m && BEREICHE.indexOf(m[1]) >= 0 ? m[1] : 'uebersicht';
  }

  function bereicheVerbinden() {
    document.querySelectorAll('[data-bereich]').forEach(function (k) {
      k.addEventListener('click', function () { bereichZeigen(k.getAttribute('data-bereich')); });
    });
    el('foto-gross-zu').addEventListener('click', function () { fotoStelle = -1; el('foto-gross').close(); });
    el('foto-gross-zurueck').addEventListener('click', function () { fotoGross(fotoStelle - 1); });
    el('foto-gross-vor').addEventListener('click', function () { fotoGross(fotoStelle + 1); });
    el('foto-gross-laden').addEventListener('click', function () {
      var f = fotoListe[fotoStelle];
      if (f) anfordern(f.freigabe, true, el('foto-gross-laden'), el('bereich-fotos'));
    });
  }

  // --- Start ------------------------------------------------------------------------------------------------------------------------------
  function start() {
    el('b-senden').addEventListener('click', function () { codeSenden('b'); });
    el('c-anmelden').addEventListener('click', codePruefen);
    el('c-code').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); codePruefen(); } });
    el('c-code').addEventListener('input', function () { if (!el('c-fehler').hidden && el('c-fehler-text').textContent === TEXT.sechs) feldFehler(''); });
    el('c-neu').addEventListener('click', function () { codeSenden('c'); });
    el('c-neu-haupt').addEventListener('click', function () { codeSenden('c'); });
    el('kopf-abmelden').addEventListener('click', function () { abmelden(false); });
    el('d-abmelden').addEventListener('click', function () { abmelden(false); });
    el('d-ueberall').addEventListener('click', function () { el('dialog-ueberall').showModal(); });
    el('dialog-ueberall-ja').addEventListener('click', function () { abmelden(true); });
    el('dialog-ueberall-nein').addEventListener('click', function () { el('dialog-ueberall').close(); });
    bereicheVerbinden();  // seit 1.11.46

    var fall = document.body.getAttribute('data-fall');
    if (fall) return fehler(fall);  // der Server setzt nur nicht_gefunden und technisch
    var hash = window.location.hash || '';
    if (hash) window.history.replaceState(null, '', window.location.pathname + window.location.search);  // der Link nie in Adresszeile und Verlauf
    if (hash.indexOf('#z=') === 0) {
      var wert = hash.slice(3);
      if (/^[A-Za-z0-9_-]{1,256}$/.test(wert)) return linkPruefen(wert);
      return fehler('link');
    }
    return ohneLink();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
