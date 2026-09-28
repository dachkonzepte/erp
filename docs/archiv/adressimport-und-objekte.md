# Adressimport aus dem Altsystem, Hauptadressen

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## Adressimport aus dem Altsystem (seit 1.3.31)

Einmaliger Import einer CSV-/Excel-Datei mit Adressen aus dem alten Programm (345 Zeilen, 19
Spalten in der ersten realen Datei). Das Altsystem vergibt jeder Adresse eine Adressnummer;
zusätzlich haben manche Zeilen eine Kundennummer oder eine Lieferantennummer -- daraus ergibt sich
die Klassifikation.

### Die vier vorab abgestimmten Berichtspunkte

1. **Wo die Altsystem-Adressnummer hingehört**: als neue Spalte `legacy_address_number` direkt auf
   `Customer` **und** `Supplier` (nicht über `CustomerProfile` -- `Supplier` hat kein
   Profil-Äquivalent, für dasselbe Konzept sollten beide denselben Ort nutzen). Dient beim
   erneuten Import derselben Datei der Wiedererkennung bereits übernommener Zeilen.
2. **openpyxl**: war weder in `requirements.txt` noch im `.venv` vorhanden (geprüft) -- als neue,
   leichtgewichtige Abhängigkeit ergänzt (MIT-lizenziert, Standard für xlsx-Lesen). CSV läuft über
   die Python-Stdlib, keine weitere Abhängigkeit nötig.
3. **Rückgängigmachen**: eine `ImportRun`-Tabelle (Zeitstempel, Dateiname, Zähler je Klassifikation)
   -- jeder dabei erzeugte `Customer`/`Supplier` trägt ein nullable `import_run_id`. Ein Lauf lässt
   sich vollständig rückgängig machen (Kunden/Lieferanten werden gelöscht, `ImportRun.status` wird
   `"reverted"`), aber nur alles-oder-nichts: sobald an EINEM der dabei erzeugten Kunden/
   Lieferanten bereits etwas hängt (Projekt, Anfrage, eigenständig hinzugefügtes Objekt über die
   automatische Hauptadresse hinaus, Verwendung in der Arbeitsvorbereitung) oder eine seiner
   unzugeordneten Zeilen bereits manuell aufgelöst wurde, wird der GANZE Lauf abgelehnt -- kein
   Teil-Rückgängig, das wäre schwerer nachzuvollziehen als gar keins. Kein Verweis auf "dann eben
   Backup zurückspielen" nötig, da sich das sauber und ohne unverhältnismäßigen Aufwand bauen ließ.
4. **Zweite E-Mail-Adresse**: `Customer.email_2` (neu, nullable) -- bewusst **rein informativ**,
   fließt NICHT in `get_quote_recipient_email()`/`get_order_recipient_email()`/
   `get_invoice_recipient_email()`/`get_reminder_recipient_email()` (`app/projects.py`,
   `orders.py`, `invoices.py`, `reminders.py`) ein. Grund: alle vier Versandfunktionen kennen
   strukturell nur einen einzigen Empfänger (`to_email: str`, ein SMTP-/Graph-Empfänger je
   Sendevorgang, `_send_via_smtp()`/`_send_via_graph()` in `app/email_sending.py`) -- echte
   Mehrfachempfänger-Unterstützung dort einzubauen wäre ein eigener, größerer Umbau, kein
   Nebeneffekt eines Adressimports.

### Name-Zusammensetzung -- die größte, nachträglich vereinbarte Erweiterung

Die Quelldaten trennen Anrede/Titel/Vorname/Name, `Customer` kannte davon bisher nur ein einziges
Feld `name`. Nach Rückfrage entschieden: **volle Ablösung**, nicht nur eine Vorbefüllung.
`Customer` bekommt vier neue Spalten `salutation`/`title`/`first_name`/`last_name` --
`last_name` ist das eigentliche Pflichtfeld (trägt bei Firmenkunden den Firmennamen, die übrigen
drei bleiben dann leer). `Customer.name` wird seither AUSSCHLIESSLICH serverseitig berechnet
(`app.crm.compose_customer_name()`, in `create_customer()`/`update_customer()` aufgerufen) --
`CustomerCreate`/`CustomerUpdate` nehmen `name` nicht mehr entgegen, `CustomerOut` führt es
weiterhin als reines Ausgabefeld (für Dokumente/PDFs/Sortierung unverändert nutzbar, keine
Änderung an irgendeiner Lese-/Druckstelle nötig).

**Vor der Umsetzung ausdrücklich der Kostenpunkt zurückgemeldet, dann auf ausdrücklichen Wunsch
trotzdem umgesetzt**: `CustomerCreate(name=...)`/`CustomerUpdate(name=...)` wurden in 20 Testdateien
direkt konstruiert (24 Aufrufe), zusätzlich in 24 weiteren Dateien wurde `Customer(name=...)` roh
als ORM-Objekt gebaut (37 Aufrufe) -- zusammen 61 Konstruktionsaufrufe in 44 Testdateien, alle auf
`last_name=` (zusätzlich zu `name=` bei der rohen ORM-Variante, da dort keine automatische
Ableitung greift) umgestellt. Kein Fallback/keine Kompatibilitätsbrücke für die alte `name=`-Kwarg
eingebaut -- entspräche einer stillen Sonderregel nur für Tests, die die eigentliche
Modellinvariante (last_name ist Pflicht) aufweichen würde.

**Migration mit Backfill statt Sonderfall**: `last_name` ist NOT NULL auf einer bereits gefüllten
Tabelle (Regel 1) -- die Migration legt die Spalte zunächst mit `server_default=''` an, führt
`UPDATE customers SET last_name = name` aus (bestehende Kunden zeigen dadurch exakt denselben
Namen wie vorher, da `compose_customer_name(None, None, None, last_name)` nur `last_name` selbst
zurückgibt) und entfernt den Default danach wieder. Gegen die echte, migrierte Datenbank geprüft:
0 Kunden mit leerem `last_name` nach dem Backfill.

**Weitere, beim Spaltenabgleich gefundene Lücken, jeweils einzeln abgestimmt:**
- **Mobil**: `Customer` hatte kein `mobile`-Feld (nur `phone`/`fax`) -- auf Wunsch eine echte neue
  Spalte `Customer.mobile` (nicht über `CustomerExtraInfo`, wie zunächst vorgeschlagen).
- **Land**: `Customer` hatte kein `country`-Feld (`Supplier` schon, mit Default "Deutschland").
  Neue Spalte `Customer.country`, gleicher Default. Auf Wunsch AUCH `Property.country` ergänzt
  (ursprünglich als akzeptierte Lücke vorgeschlagen, dann doch mitgenommen) -- `resolve_as_property()`
  übernimmt das Land der Adressimport-Zeile jetzt vollständig, nichts geht beim Umwandeln in ein
  Objekt verloren.
- Alle drei neuen Personenfelder plus Land/Mobil/zweite E-Mail sind auf Wunsch auch im normalen
  Kundenformular sichtbar und editierbar (`customer.html`, `master_data_form.html`s
  `customerForm()`) -- nicht nur reine Importdaten. Anrede läuft über eine neue, self-seedende
  Optionsgruppe `customer_salutations` (Muster `customer_categories`), Titel/Vorname/Nachname
  bleiben freier Text.

### Ablauf (dreistufig, wie gefordert)

1. **Hochladen** (`POST /api/address-import/upload`, multipart): `parse_address_file()` liest CSV
   (Stdlib `csv`, Encoding-Fallback utf-8-sig → cp1252 → latin-1, Trennzeichen per
   `csv.Sniffer()`) oder Excel (`openpyxl`, `read_only=True`) anhand der SPALTENÜBERSCHRIFTEN
   (nicht der Reihenfolge) ein. Fehlt eine benötigte Spalte, wird die GANZE Datei mit einer klaren
   Meldung abgelehnt (`AddressImportError`). Telefon/Fax/Mobil werden unverändert als Text
   übernommen -- keine Reparatur, kein Erraten (bewusst auch bei absurden Werten wie `-373367`).
   Einzige technische (keine inhaltliche) Normalisierung: eine von openpyxl als `float` gelesene
   Ganzzahl-Zelle (z. B. `2404669530.0`) wird ohne die sonst entstehende `.0`-Endung dargestellt --
   das ist eine Python-Artefakt-Korrektur, keine Interpretation der Telefonnummer selbst.
2. **Vorschau**: jede Zeile wird sofort klassifiziert (`classify_row()`) und als `ImportedAddress`
   mit `status="previewing"` gespeichert (noch OHNE `ImportRun` -- der entsteht erst beim
   Bestätigen). Klassifikation: `"customer"` (Kundennummer gesetzt), `"supplier"`
   (Lieferantennummer gesetzt), `"unassigned"` (keine von beiden), `"duplicate"` (Adressnummer
   bereits als Kunde/Lieferant/bestätigte `ImportedAddress`-Zeile bekannt -- wird bei Bestätigung
   übersprungen). `validation_notes` sammelt die geforderten Auffälligkeiten: fehlender Name,
   fehlende Adresse, Adressnummer mehrfach in derselben Datei, bereits vergebene Kunden-/
   Lieferantennummer. Ein neuer Upload verwirft automatisch eine zuvor nie bestätigte Vorschau
   (`discard_pending_preview()`), damit deren Adressnummern nicht fälschlich als "bereits
   importiert" gelten.
3. **Bestätigen** (`POST /api/address-import/confirm`): legt für `"customer"`/`"supplier"`
   tatsächlich `Customer`/`Supplier` an (inkl. `CustomerProfile`/automatischer
   "Hauptadresse"-`Property`, exakt das bestehende Muster aus `create_customer()`), lässt
   `"unassigned"` als offene Zeile stehen (das ist die Arbeitsliste) und `"duplicate"` unverändert
   (reiner Nachweis, dass die Adressnummer erneut vorkam). Schlägt eine einzelne Zeile fehl (z. B.
   doch noch ein Konflikt bei der Kundennummer), wird die GESAMTE Bestätigung zurückgerollt
   (`db.rollback()`) -- nichts bleibt halb geschrieben.

`ImportedAddress` ist bewusst EINE Tabelle für zwei Zwecke (Vorschau-Zwischenspeicher UND
dauerhafte Arbeitsliste) -- eine Zeile wird nach dem Bestätigen nie gelöscht (außer beim
Rückgängigmachen des ganzen Laufs), sonst würde ein erneuter Import derselben Datei dieselbe
Adressnummer fälschlich als neu erkennen.

### Arbeitsliste (`GET /api/address-import/unassigned`)

Zeigt alle `ImportedAddress`-Zeilen mit `classification="unassigned"` und `resolution IS NULL`.
Freitextsuche über Name/Straße/Ort/PLZ/E-Mail/Telefon/Adressnummer (client-seitig unnötig, da die
Liste ohnehin klein bleibt -- serverseitige Filterung in `list_unassigned()`). Drei Aktionen,
jede setzt `resolution`/`resolved_at` und blendet die Zeile damit aus der Liste aus:
- **Als Objekt zuordnen** (`resolve_as_property()`): legt ein `Property` beim gewählten
  Bestandskunden an, übernimmt Straße/PLZ/Ort/Land aus der Zeile.
- **Als neuen Kunden anlegen** (`resolve_as_new_customer()`): ruft denselben
  `_create_customer_from_row()`-Helfer wie die reguläre Bestätigung auf.
- **Verwerfen** (`discard_unassigned()`): setzt nur `resolution="discarded"`, erzeugt nichts.

Ist die Liste leer, zeigt die Seite einen Hinweistext statt der Tabelle (kein separates Ausblenden
des ganzen Abschnitts -- Wartungen/Mängel-Muster mit komplett verschwindendem Abschnitt wäre hier
nicht nötig gewesen, da der Abschnitt ohnehin nur auf der eigens dafür gebauten Importseite steht).

### Wo der Import liegt (Punkt 1)

`/address-import`, verlinkt aus Einstellungen → neue Gruppe **"Importe"** (unterhalb der
bestehenden "System"-Gruppe) -- nicht in den Stammdaten, da ein Import in der Regel einmalig
läuft. Geprüft, ob es dort schon etwas Vergleichbares gibt: der XML-Import für Leistungen
(`app/routers/imports.py`, `/leistungskatalog`) wäre ein Kandidat, künftig ebenfalls in diese
Gruppe zu wandern -- **bewusst nicht in dieser Etappe**, nur als Vermerk für später. Die gesamte
Adressimport-Oberfläche ist admin-gated (eigene, echte Kunden-/Lieferantenanlage, keine
Tagesbetrieb-Aktion).

### Tests

`tests/test_v247_address_import.py` -- Einlesen (CSV inkl. defekter Telefonnummern unverändert,
Excel inkl. Float-Formatierung, fehlende Pflichtspalte), Klassifikation (alle vier Fälle plus die
vier Auffälligkeits-Meldungen), der komplette Vorschau-Verwerfen/Bestätigen-Ablauf, Wiedererkennung
bei erneutem Import (inkl. des Sonderfalls "eine nie bestätigte Vorschau blockiert nichts"), die
Arbeitsliste mit allen drei Aktionen plus Suche, sowie Rückgängigmachen (Erfolgsfall, zwei
Ablehnungsfälle, und dass ein rückgängig gemachter Lauf seine Adressnummern wieder freigibt) --
sowohl direkt gegen `app/address_import.py` als auch einmal über echte Routen
(`router_test_client`). Mehrere ältere Tests wurden auf `last_name=` umgestellt, siehe oben.

## Objekte: Hauptadressen kennzeichnen und ausblenden (seit 1.3.32)

Nach dem Adressimport (1.3.31) bestand die Stammdaten-Objektliste überwiegend aus reinen
Hauptadress-Kopien -- jeder Kunde bekommt beim Anlegen automatisch ein Objekt namens
"Hauptadresse" (seine eigene Adresse, damit sofort auf sie gebucht werden kann, siehe
`create_customer()` oben). Die eigentlich interessanten, zusätzlichen Objekte (Baustellen,
Zweitgebäude) gingen darin unter.

### Punkt 1: `Property.is_primary_address` statt Namensvergleich

Neue Spalte `is_primary_address` (Boolean, NOT NULL, `server_default="0"`, indiziert) --
ersetzt den bisher überall verstreuten, fragilen String-Vergleich `p.name === 'Hauptadresse'`
durch ein echtes, robustes Flag. Gesetzt wird es **ausschließlich** an den drei Stellen, an
denen eine Hauptadresse automatisch entsteht -- nie über das normale Objektformular:

- `create_customer()` (`app/routers/customers.py`): das automatisch angelegte erste Objekt.
- `update_customer()` (`app/routers/customers.py`): die Suche nach der vorhandenen Hauptadresse
  lief bisher über den Namen (`p.name == "Hauptadresse"`) -- jetzt zuerst über das Flag, mit
  einem Namens-Fallback UND Selbstheilung (`main_property.is_primary_address = True` wird immer
  gesetzt, unabhängig davon, über welchen der drei Wege -- Flag, Name, Neuanlage -- die Zeile
  gefunden/erzeugt wurde). Verteidigung in der Tiefe: ohne diesen Fallback würde eine Zeile, die
  aus irgendeinem Grund den Namen trägt, aber nicht geflaggt ist, bei der nächsten
  Kundenbearbeitung eine zweite, doppelte "Hauptadresse"-Zeile erzeugen, statt gefunden zu
  werden -- in der echten Datenbank aktuell kein realer Fall (siehe Migrationsergebnis unten),
  aber ein günstiger, dauerhafter Schutz.
- `_create_customer_from_row()` (`app/address_import.py`): dieselbe automatische Anlage beim
  Adressimport.

**Migration `2fffb80e5567`, Erkennungssicherheit vor dem Schreiben geprüft und berichtet (wie
verlangt)**: von 163 Objekten in der echten Datenbank trugen 161 den Namen "Hauptadresse". Bei
**allen 161** stimmt zusätzlich Straße/PLZ/Ort exakt mit dem jeweiligen Kunden überein -- 0
unsichere Fälle, 0 Abweichungen zwischen Namens- und Adresskriterium. Die Migration markiert
deshalb bewusst konservativ nur, wenn **beide** Kriterien gemeinsam zutreffen
(`_resolve_primary_address_property_ids()`, direkt nach dem etablierten Migrations-Testmuster
eigenständig testbar, siehe `tests/test_v248_primary_address_flag.py`) -- ein Namenstreffer ohne
Adressübereinstimmung wird NICHT markiert. Begründung (Nutzervorgabe): lieber eine echte
Hauptadresse übersehen als eine echte Liegenschaft fälschlich aus der Objektliste verschwinden
zu lassen, was niemandem auffallen würde. Die beiden übrigen Objekte sind keine unsicheren
Namenstreffer, sondern schlicht keine Hauptadressen (kein "Hauptadresse"-Name) -- die Migration
lässt sie unverändert.

### Punkt 2: wo Hauptadressen ausgeblendet werden -- Fundstellen-Übersicht

Alle Orte im Projekt geprüft, an denen Objekte gelistet oder ausgewählt werden, mit
unterschiedlicher, begründeter Behandlung je Fundstelle:

| Ort | Behandlung | Begründung |
|---|---|---|
| `master_data.html` (Stammdaten-Objektliste) | ausgeblendet, Kontrollkästchen "Hauptadressen anzeigen" zum Wiedereinblenden | Standardfall dieser Anfrage -- die Liste soll auf die eigentlich interessanten Objekte fokussieren, ohne echte Daten unerreichbar zu machen |
| `findings.html` (Objekt-Filterdropdown) | ausgeblendet, eigenes Kontrollkästchen "Hauptadressen in Objektliste anzeigen" | vom Nutzer ausdrücklich "genauso" wie die Stammdaten-Liste gefordert |
| `maintenance_contracts.html`/`maintenance_contract.html` (`propertyOptionsHtml()`, Objektauswahl beim Wartungsvertrag) | Hauptadressen aus der Auswahlliste gefiltert, kein zusätzliches Kontrollkästchen | die bereits bestehende Option "— Hauptadresse verwenden —" deckt genau diesen Fall bereits redundant ab -- `contract_to_dict()` liefert für `property_id=None` byte-identisch dasselbe Ergebnis wie eine explizit gewählte Hauptadresse-Zeile, ein zweiter, gleichwertiger Eintrag in der Liste wäre nur verwirrend |
| `project_folder.html`/`project_form.html` (Objektauswahl beim Projekt/Vorgang), `inquiries.html` (Objektauswahl bei Anfragen) | **unverändert, Hauptadresse bleibt wählbar** | geprüft anhand `_copy_quote_scope_to_order()` (`app/orders.py`): `NULL` und eine explizit gewählte Hauptadresse-Zeile erzeugen dort tatsächlich unterschiedliche Ergebnisse im eingefrorenen Auftrags-Schnappschuss (siehe Punkt 3), die Auswahl darf deshalb nicht verschwinden |
| `customer.html` (Objektliste auf der Kundenseite) | **alle Objekte bleiben sichtbar**, Hauptadresse nur noch über das Flag statt den Namen markiert (Badge, `main`-CSS-Klasse, ausgeblendeter "Bearbeiten"-Button) | ausdrückliche Vorgabe (Punkt 3) -- der "Objekt hinzufügen"-Button bleibt unverändert |
| `property.html` (Einzelobjekt-Detailseite) | keine Änderung nötig | reine Detailansicht eines bereits bekannten Objekts, kein Listen-/Auswahlkontext |

In der Stammdaten-Objektliste durchsucht die Suche weiterhin **alle** Objekte (auch versteckte),
bevor der Sichtbarkeitsfilter greift -- ein Anruf, bei dem nur eine Adresse bekannt ist, muss
weiterhin etwas finden können, unabhängig vom Hauptadresse-Status.

### Punkt 3: Nebenbefund behoben, nicht nur gemeldet

Ein Wartungsvertrag ohne Objekt zeigt "Hauptadresse" (`contract_to_dict()`,
`app/maintenance_contracts.py`, synthetisiert das seit 1.2.9) -- ein daraus per Schnellauftrag
erzeugter Auftrag zeigte dagegen **gar kein** Objekt. Dieselbe Sache, zweimal unterschiedlich
dargestellt. `_copy_quote_scope_to_order()` (`app/orders.py`, die einzige Stelle, die den
eingefrorenen Auftrags-Schnappschuss `property_name`/`property_address` befüllt, für ALLE
Beauftragungswege inkl. Schnellauftrag) schreibt jetzt im `property is None`-Fall denselben
Wert, den `contract_to_dict()` für die Anzeige liefert ("Hauptadresse" +
`_address(customer.street, city_line)`), statt zuvor `None`. **Bestehende Aufträge bleiben
unangetastet** -- der Snapshot ist eingefroren, nur künftige Beauftragungen sind betroffen.
Regressionstest: `tests/test_v209_quick_service_orders.py`.

### Tests

`tests/test_v248_primary_address_flag.py` -- alle drei Setzstellen des Flags (`create_customer()`,
`update_customer()` inkl. Selbstheilung einer unflagged, aber namensgleichen Zeile), die Migration
isoliert (Name-und-Adresse-Kriterium vs. nur-Name). `tests/test_v247_address_import.py` um eine
Flag-Prüfung ergänzt. `tests/test_v209_quick_service_orders.py` um den Nebenbefund-Regressionstest
ergänzt (mit und ohne hinterlegte Kundenadresse).
