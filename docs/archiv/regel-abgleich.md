# Regel-Abgleich: CLAUDE.md-Aufteilung (2026-09-28)

Kreuztabelle für die Aufteilung der ursprünglichen, 12.181-zeiligen `CLAUDE.md` in eine
schlanke `CLAUDE.md` (Ziel: alles, was jede Sitzung kennen muss) plus themensortiertes Archiv
unter `docs/archiv/`. Jede Zeile ist ein ursprünglicher `##`-Abschnitt (bzw. bei
"Stand bei Übergabe" und "Fachbegriffe & Domänenmodell" die einzelnen Unter-Bullets, da diese
beiden Abschnitte gemischt behandelt wurden -- ein Teil bleibt, ein Teil wandert ins Archiv).

**Nachtrag (zweiter Durchgang, direkt im Anschluss)**: die erste Kategorisierung erfolgte je
Abschnitt, nicht je Regelzeile -- der Grep-Vollständigkeitsnachweis belegt, dass nichts verloren
ging, aber nicht, dass modulübergreifende Vorgaben innerhalb eines als (c) eingestuften
Abschnitts auch außerhalb ihres Moduls sichtbar bleiben. Alle 33 (c)-Abschnitte wurden deshalb
gezielt nach Signalwort-Zeilen durchsucht, die über das eigene Modul hinaus gelten (Sicherheit,
Deploy, Microsoft-Konfiguration, Datenbank, Rechte, Testmethodik). Drei echte Funde wurden als
neue Regeln 16-18 in "Kritische, nicht verhandelbare Regeln" aufgenommen:

- **Regel 16** (Testmethodik, gefunden in `modul-kalender-und-outlook-sync.md`,
  `modul-buchhaltung.md`, `projektliste-und-mappe.md`, echo in `chronik-1.1-1.6.md`): jede
  Verifikation läuft gegen eine isolierte, temporäre Instanz, niemals gegen die echte
  Produktivdatenbank -- unabhängig vom Modul, bisher an vier unabhängigen Stellen wiederholt
  dieselbe Praxis, aber nirgends als eigene, allgemeine Regel festgehalten.
- **Regel 17** (Microsoft-Konfiguration, gefunden in `modul-kalender-und-outlook-sync.md`, exakt
  das vom Nutzer genannte Beispiel): ein neues Graph-Recht wird nie über die tenant-weite
  Administratorzustimmung erteilt, sondern ausschließlich über Exchange "RBAC for
  Applications" -- betrifft jedes künftige Graph-Recht (Calendars, Contacts, OneDrive, Teams,
  …), nicht nur den Kalender, für den es ursprünglich dokumentiert wurde; die bestehende
  `Mail.Send`-Berechtigung ist die einzige historische Ausnahme. *(Korrigiert 28.09.2026: diese
  Ausnahme gibt es nicht -- `Mail.Send` läuft ebenfalls über RBAC, in Entra ist keine
  Graph-Anwendungsberechtigung mehr erteilt; siehe Regel 17 in CLAUDE.md.)*
- **Regel 18** (Sicherheit/Datenschutz, gefunden in `modul-kalender-und-outlook-sync.md`,
  unabhängig bestätigt durch dieselbe Praxis im (b)-Abschnitt `ki-fundament.md`): ein Protokoll
  über eigene Funktionsaufrufe enthält nie den eigentlichen Inhalt, nur Metadaten -- zweimal
  unabhängig voneinander so gebaut (Kalender-Diagnose, KI-Kostenprotokoll), aber bisher nirgends
  als eigene, für jedes künftige Protokoll geltende Regel benannt.

Geprüfte, aber NICHT als neue Regel übernommene Kandidaten (bereits durch eine bestehende Regel
abgedeckt, keine Duplizierung nötig): `data/.erp_secret`-Löschverbot (bereits in "Produktivbetrieb",
kept verbatim), `Backup\`-Ordnerdisziplin (bereits Regel 9), Chrome-Prozess-Sicherheit (bereits
Regel 12), `OrderFieldAccessOut`-Union-Response-Muster (bereits in "Rechtekonzept (kurz)").

**Kategorien** (wie vom Nutzer vorgegeben):
- **(a)** durable Regel/Fakt, muss in der neuen, schlanken Datei stehen
- **(b)** bereits durch eine allgemeinere, bestehende Regel an anderer Stelle abgedeckt -- keine
  Duplizierung nötig, Archivierung der Herleitung verlustfrei möglich
- **(c)** rein historisch, kein zukunftsbindender Inhalt -- nur Archiv

**Vollständigkeitsnachweis** (mechanisch, nicht nur behauptet): ein Grep-Muster aus den
Signalwörtern `niemals|nie|immer|Pflicht|muss|müssen|darf nicht|dürfen nicht|verbindlich|nicht
verhandelbar|ausschließlich|zwingend|bewusst NICHT|STETS` traf in der ORIGINALEN CLAUDE.md auf
**678** eindeutige (deduplizierte) Zeilen. Ein zeilengenauer Abgleich (`comm -23`, sortierte,
deduplizierte Zeilenmengen) zwischen diesen 678 Zeilen und der Vereinigung aus neuer CLAUDE.md +
allen 16 Archivdateien ergab **null** Zeilen, die in der Originalfassung vorkamen, aber in der
neuen Aufteilung fehlen -- jede einzelne der 678 Zeilen ist wortgetreu wiederzufinden. Die neue
Aufteilung trifft insgesamt 686 Signalwort-Zeilen (678 erhalten + 8 echte Neuzugänge aus den neu
verfassten Kapiteln "Architekturentscheidungen"/"Modulübersicht"/"Rechtekonzept (kurz)"/
Regel 14+15/"Projektüberblick" -- keine davon dupliziert eine bestehende Aussage, jede ist eine
neue, absichtlich hinzugefügte Klarstellung). Die zusätzlich in einer früheren Zwischenschätzung
genannte Zahl 697 war eine grobe Vorabschätzung aus Runde 1 vor der tatsächlichen Extraktion und
wird durch diesen späteren, zeilengenauen Abgleich ersetzt, nicht bestätigt.

Zusätzlich per Skript geprüft (siehe `extract_archives.py`-Ausgabe): jede der 12.181 Zeilen der
Originaldatei ist in der Aufteilung genau einmal enthalten (Archiv ODER neue CLAUDE.md), mit
Ausnahme von vier Zeilen -- der "## Stand bei Übergabe"-Überschrift und drei reinen
Leerzeilen-Trennern zwischen Abschnitten --, die von Hand identisch nachgebildet bzw. als
bedeutungslose Trenner weggelassen wurden. Keine Zeile ist doppelt abgedeckt.

## Tabelle

| Ursprünglicher Abschnitt (Zeilen in der alten CLAUDE.md) | Ziel | Kategorie | Begründung |
|---|---|---|---|
| Stand bei Übergabe: Version/Pfad/Redesign-Bullets (L23, L212-215) | bleibt (verbatim) | a | aktueller Stand, muss jede Sitzung kennen |
| Stand bei Übergabe: Migrationskette-Bullet (L24-107) | `versionsverlauf.md` | c | reine Versions-für-Version-Historie, heutiger Stand steht kurz in "Stand bei Übergabe" + CHANGELOG.md |
| Stand bei Übergabe: Tests-Bullet (L108-211) | `versionsverlauf.md` | c | reine Testlauf-Historie je Version, aktueller Teststand durch `pytest -q` selbst verifizierbar |
| "Neu seit 1.1.0" … "Neu seit 1.6.0" (L216-1552) | `chronik-1.1-1.6.md` | c | abgeschlossene Feature-Historie, CHANGELOG.md deckt dasselbe knapper ab; auf Nutzerwunsch nicht gestrichen, sondern archiviert |
| Headless-Chrome-Verifikation über CDP (L1554-1587) | bleibt (verbatim, unter "Testen" einsortiert) | a | wiederverwendbare Testfähigkeit dieser Umgebung, projektübergreifend relevant |
| Produktivbetrieb (L1589-1838) | bleibt (verbatim) | a | Deploy-Ablauf, Migrations-Checkliste, Umgebungsvariablen -- ein Fehler hier kostet Produktivdaten |
| Stack & Struktur (L1839-1863) | bleibt (verbatim) | a | Grundlegende Architekturfakten, kurz genug, immer relevant |
| Kritische, nicht verhandelbare Regeln (L1864-2025) | bleibt (verbatim) + neue Regel 14+15 | a | explizit vom Nutzer als "ALLE verbindlichen Regeln" gefordert |
| Fachbegriffe: Vorgang/Kette/Quote/Order/Invoice/Reminder/Property (L2026-2060) | bleibt (verbatim) | a | Kern-Domänenmodell, in praktisch jeder Änderung relevant |
| Fachbegriffe: Dachflächen & Bauteile (L2061-2223) | `modul-wartungen-und-monteursansicht.md` | c | Modul-Detail, Grundfakt (Property→RoofArea-FK) bereits im gekürzten Property-Bullet erhalten |
| Fachbegriffe: TimeEntry/Plantafel/Mustervorgang/E-Mail-Versand/Modul-Umschalter (L2224-2267) | bleibt (verbatim) | a | Kern-Domänenmodell, modulübergreifend referenziert |
| Fachbegriffe: Aufgabe (Task) (L2268-2405) | `modul-aufgaben.md` | c | Modul-spezifische Sichtbarkeitslogik, keine projektweite Regel |
| Fachbegriffe: Wartungsvertrag (L2406-2537) | `modul-wartungen-und-monteursansicht.md` | c | Modul-Detail |
| Fachbegriffe: Einsatzbericht (L2538-2948) | `modul-wartungen-und-monteursansicht.md` | c | Modul-Detail (größter Einzelblock, sehr feingranular) |
| Fachbegriffe: Rechnung aus Zeitbuchungen (L2949-2995) | `modul-wartungen-und-monteursansicht.md` | c | Modul-Detail |
| Fachbegriffe: Schnellauftrag (L2996-3011) | `modul-wartungen-und-monteursansicht.md` | c | Modul-Detail |
| Fachbegriffe: Wartungshistorie (L3012-3018) | `modul-wartungen-und-monteursansicht.md` | c | Modul-Detail |
| Fachbegriffe: Dashboard-Widget "Fällige Wartungen" (L3019-3024) | `modul-wartungen-und-monteursansicht.md` | c | Modul-Detail |
| Fachbegriffe: Monteursansicht (L3025-3122) | `modul-wartungen-und-monteursansicht.md` | c | Modul-Detail |
| PDF-Rahmen (L3123-3276) | `pdf-architektur.md` | b | Architekturprinzip jetzt in "Architekturentscheidungen" kurz zusammengefasst |
| Kopfbereich / DIN5008 (L3277-3412) | `pdf-architektur.md` | b | dito |
| Gemeinsamer Dokumenttyp (L3413-4481) | `pdf-architektur.md` | b | dito -- inkl. `RENDERERS_USING_SHARED_FRAME`-Pflicht, jetzt kurz in Architekturentscheidungen |
| Mahnwesen: Löschen/Versenden/Bearbeiten (L4482-4552) | `mahnwesen.md` | c | abgeschlossenes Feature |
| Breadcrumb & Spaltenkopf-Ausrichtung (L4553-4605) | `projektliste-und-mappe.md` | c | abgeschlossener Fix |
| Direkteinstieg/Katalogauswahl/Abschlagsrechnung (L4606-4709) | `projektliste-und-mappe.md` | c | abgeschlossene Features |
| Leistungskatalog vs. Stammdaten (L4710-5090) | `stammdaten-und-sidebar.md` | b | Kernregel bereits Regel 10 ("jeder Stammdatenbereich folgt demselben Muster"), dies ist die Herleitung |
| Adressimport aus dem Altsystem (L5091-5237) | `adressimport-und-objekte.md` | c | abgeschlossenes, einmaliges Import-Feature |
| Objekte: Hauptadressen kennzeichnen (L5238-5317) | `adressimport-und-objekte.md` | c | abgeschlossenes Feature |
| Geheimnisse für den Serverbetrieb (L5318-5413) | `serverbetrieb-und-anmeldesicherheit.md` | b | Kernregel (`.erp_secret` nie löschen) bereits in Produktivbetrieb (bleibt) enthalten |
| Anmeldesicherheit für den Onlinebetrieb (L5414-5596) | `serverbetrieb-und-anmeldesicherheit.md` | c | Feature-Beschreibung (2FA existiert), keine Meta-Regel für künftige Sitzungen |
| Diesem Gerät für 30 Tage vertrauen (L5597-5712) | `serverbetrieb-und-anmeldesicherheit.md` | c | abgeschlossenes Feature |
| Serverseitige Anmeldeschranke für Seiten (L5713-5846) | `serverbetrieb-und-anmeldesicherheit.md` | c | abgeschlossenes Feature |
| PostgreSQL-Umstieg: Migrationskette repariert (L5847-6007) | `serverbetrieb-und-anmeldesicherheit.md` | b | Lehre ("prüfe, ob Migration wirklich gegen PostgreSQL läuft") bereits in Produktivbetrieb → "Was das für Migrationen heißt" (bleibt) |
| Firmenlogo in der Sidebar (L6008-6235) | `stammdaten-und-sidebar.md` | c | abgeschlossenes Feature |
| Umgestaltung der Sidebar (L6236-6572) | `stammdaten-und-sidebar.md` | c | abgeschlossenes Feature |
| Rechtekonzept, Etappe 1+2 (L6573-7583) | `rechtekonzept.md` | b | Kernregel bereits Regel 11 (Standardverweigerung) + neues Kapitel "Rechtekonzept (kurz)" |
| Dateiablage je Objekt (L7584-8055) | `rechtekonzept.md` | c | Modul-Detail |
| Büro-Suche (L8056-8330) | `rechtekonzept.md` | c | Modul-Detail |
| Umbau der Projektliste (L8331-8574) | `projektliste-und-mappe.md` | c | abgeschlossenes Feature |
| Umbau der Projekt-Detailseite (L8575-8683) | `projektliste-und-mappe.md` | c | abgeschlossenes Feature |
| Betriebsmittelverwaltung (L8684-9304) | `modul-betriebsmittel-und-betriebskosten.md` | b | Live-Auflösungs-Prinzip bereits in Architekturentscheidungen kurz zusammengefasst |
| Betriebskosten-Übersicht (L9305-9705) | `modul-betriebsmittel-und-betriebskosten.md` | c | Modul-Detail |
| Neugestaltung Stundenverrechnungssatz (L9706-9821) | `modul-betriebsmittel-und-betriebskosten.md` | c | reine UI-Umgestaltung |
| Schlechtwetter-Zeitarten/Abwesenheitskategorie (L9822-9952) | `zeiterfassung-und-abwesenheit.md` | c | Modul-Detail |
| Krankheitssichtbarkeit (L9953-10086) | `zeiterfassung-und-abwesenheit.md` | c | Modul-Detail |
| Netto und Brutto bei den Betriebskosten (L10087-10139) | `modul-betriebsmittel-und-betriebskosten.md` | c | abgeschlossene Nachbesserung |
| Betriebsmittel-Kosten fest als Kostenposten (L10140-10281) | `modul-betriebsmittel-und-betriebskosten.md` | c | abgeschlossene Nachbesserung |
| Ist-Werte im Produktivstunden-Rechner (L10282-10408) | `modul-betriebsmittel-und-betriebskosten.md` | c | abgeschlossene Nachbesserung |
| Buchhaltung (L10409-10812) | `modul-buchhaltung.md` | c | Modul-Detail |
| KI-Fundament (L10813-11056) | `ki-fundament.md` | b | Kernregel (`call_ai()`/`call_ai_async()`-Kapselung) jetzt in Architekturentscheidungen |
| Kalender-Modul & Outlook-Sync (L11057-11838) | `modul-kalender-und-outlook-sync.md` | c | Modul-Detail, inkl. Microsoft-365-Tenant-Einrichtung (einmalig, nicht Claude-Code-Verhalten) |
| Self-Seeding gegen gleichzeitigen ersten Zugriff (L11839-11870) | bleibt (verbatim) | a | verbindliches Muster für jede künftige `ensure_default_*()`-Funktion |
| Migrations-Workflow (L11871-11926) | bleibt (verbatim) | a | `DATABASE_URL`-Pflicht, `create_all()`-Fallstrick -- beides aktiv bindend |
| Testen (L11927-11982) | bleibt (verbatim) + neue `pytest -q`-Ergänzung | a | Testkonventionen, ständig gebraucht |
| Arbeitsweise, die sich bewährt hat (L11983-12014) | bleibt (verbatim) | a | Verhaltensregeln mit mehreren "nie/immer"-Aussagen |
| Bekannte, bewusst offene Punkte (L12015-12181) | bleibt (verbatim) + neuer utcnow-Punkt | a | aktive Liste offener technischer Schulden, muss bekannt bleiben |

## Zusammenfassung nach Kategorie

- **(a) bleibt in der neuen CLAUDE.md**: 13 Zeilen der Tabelle (Stand-bei-Übergabe-Kernbullets,
  Headless-Chrome, Produktivbetrieb, Stack & Struktur, Kritische Regeln, zwei Fachbegriffe-Blöcke,
  Self-Seeding, Migrations-Workflow, Testen, Arbeitsweise, Bekannte offene Punkte)
- **(b) bereits andernorts abgedeckt, keine Duplizierung nötig**: 9 Zeilen der Tabelle
  (vollständige Liste unten)
- **(c) rein historisch, nur Archiv**: 33 Zeilen der Tabelle

### Vollständige Liste Kategorie (b)

1. **PDF-Rahmen** (L3123-3276) → `pdf-architektur.md` -- abgedeckt durch
   "Architekturentscheidungen" → "PDF-Rahmen statt Einzel-Renderer"
2. **Kopfbereich / DIN5008** (L3277-3412) → `pdf-architektur.md` -- dito
3. **Gemeinsamer Dokumenttyp** (L3413-4481) → `pdf-architektur.md` -- dito
4. **Leistungskatalog vs. Stammdaten** (L4710-5090) → `stammdaten-und-sidebar.md` -- abgedeckt
   durch Regel 10 ("jeder Stammdatenbereich folgt demselben Muster")
5. **Geheimnisse für den Serverbetrieb** (L5318-5413) → `serverbetrieb-und-anmeldesicherheit.md`
   -- abgedeckt durch die `.erp_secret`-Regel in "Produktivbetrieb" (bleibt verbatim)
6. **PostgreSQL-Umstieg: Migrationskette repariert** (L5847-6007) →
   `serverbetrieb-und-anmeldesicherheit.md` -- abgedeckt durch "Produktivbetrieb" →
   "Was das für Migrationen heißt"
7. **Rechtekonzept, Etappe 1+2** (L6573-7583) → `rechtekonzept.md` -- abgedeckt durch Regel 11
   (Standardverweigerung) und das neue Kapitel "Rechtekonzept (kurz)"
8. **Betriebsmittelverwaltung** (L8684-9304) → `modul-betriebsmittel-und-betriebskosten.md` --
   abgedeckt durch "Architekturentscheidungen" → "Live-Auflösung statt Kopie"
9. **KI-Fundament** (L10813-11056) → `ki-fundament.md` -- abgedeckt durch
   "Architekturentscheidungen" → "KI-Aufrufe ausschließlich über `call_ai()`/`call_ai_async()`"
