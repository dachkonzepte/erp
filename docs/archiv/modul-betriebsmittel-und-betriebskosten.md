# Betriebsmittelverwaltung, Betriebskosten-Übersicht, Neugestaltung Stundenverrechnungssatz, Netto/Brutto, Betriebsmittel-Kosten, Ist-Werte

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## Betriebsmittelverwaltung (seit 1.4.0, Modul "betriebsmittel")

Erstes neues Modul seit der Monteursansicht (die aber bewusst KEIN Modul ist, siehe dort) --
Befund zuvor separat berichtet (kein Code), dann fünf vom Nutzer bestätigte Bau-Entscheidungen
umgesetzt. Dreistufig: diese Version liefert ausschließlich **Stufe 1** -- Datenmodell mit
Ressourcenbezug, Prüffristen, Kosten, Stammdatenpflege, Modulschalter. QR-Code +
rollenabhängige Ansicht (Stufe 2) und Betriebsmittel im Bericht (Stufe 3) sind bewusst noch
nicht gebaut, folgen erst nach Rückmeldung zu dieser Etappe.

**Der Modulschalter zuerst, wie ausdrücklich verlangt**: `OPTIONAL_MODULES["betriebsmittel"] =
"Betriebsmittelverwaltung"` (`app/modules.py`) war der allererste Codeschritt dieser Version --
erst danach entstand ein einziger Endpunkt. Jeder Endpunkt in
`app/routers/operational_assets.py` prüft `is_module_enabled()` (403, exaktes Muster aus
`app/routers/maintenance_contracts.py`, eigener `_require_module_enabled(db)`-Helfer,
`MODULE_KEY = "betriebsmittel"`).

### Eigene Inventarschicht statt Erweiterung von `OperationalResource` -- die zentrale Entscheidung

`OperationalAsset` (`app/models.py`) ist eine eigene, neue Tabelle mit einem OPTIONALEN Bezug
zu genau einer `OperationalResource` (`resource_id`, `UniqueConstraint` -- höchstens ein
Betriebsmittel je Ressource, verhindert Doppelerfassung bereits auf Datenbankebene, nicht nur
in der Anwendungslogik). Genau die vom Nutzer vorgegebene Unterscheidung: "Ein Kran ist ein
Betriebsmittel MIT Ressourcenbezug -- inventarisiert und planbar. Eine Leiter ist ein
Betriebsmittel OHNE." Ein Kran bleibt über den komplett unveränderten `Team`/`TeamResource`/
`WorkPreparationTeamResource`/`PlanningSlot`-Weg in der Plantafel disponierbar, eine Leiter hat
mit diesem Weg nie etwas zu tun.

**Live-Auflösung statt Kopie, der eigentliche Schutz gegen Doppelerfassung/Namensdivergenz**:
ist ein Asset verknüpft (`resource_id` gesetzt), bleiben seine eigenen Identitätsfelder
(`name`/`asset_type`/`manufacturer`/`model`/`identifier`) auf der Datenbank IMMER `NULL` --
`app/operational_assets.py::asset_to_dict()` löst sie bei JEDEM Lesezugriff live aus der
verknüpften `OperationalResource` auf, niemals aus einer gespeicherten Kopie. Benennt jemand
die Ressource um, zeigt das Betriebsmittel sofort den neuen Namen, ohne selbst angefasst zu
werden -- ein klassisches "zwei Kopien laufen auseinander" kann dadurch strukturell nicht
entstehen. Ist kein Ressourcenbezug gewählt, sind dieselben Felder die einzige Quelle, `name`
wird dann zur Pflicht (Pydantic-`model_validator` in `OperationalAssetCreate`, bewusst NICHT
als DB-`NOT NULL`-Constraint, da die Spalte im verknüpften Fall zwingend `NULL` bleiben muss).
Die Business-Logik (`create_asset()`/`update_asset()`) setzt beim Verknüpfen zusätzlich die
eigenen Felder aktiv auf `NULL` zurück, falls vorher eigenständig befüllt.

**Ausdrückliche, dauerhafte Warnung -- bewusst im Klassendocstring von `OperationalAsset`
UND hier festgehalten, damit sie niemand übersieht**: `OperationalResource` und
`OperationalAsset` dürfen NIE zu einer einzigen Tabelle zusammengeführt werden. Die
Plantafel-Disposition referenziert ausschließlich `operational_resources.id` und kennt
`OperationalAsset` an keiner Stelle -- eine Zusammenführung würde diese Fremdschlüssel brechen
oder eine riskante ID-Migration erfordern. Das ist die bewusste Form von "Ressourcen
erweitern", die der Nutzer angefragt hat: eine zweite, optional angehängte Schicht, kein Umbau
der bestehenden.

### Fälligkeitslogik: Muster übernommen, Code bewusst NICHT wiederverwendet

Geprüft, ob `MaintenanceContractItem`s `_is_item_due()`/`_is_item_overdue()`
(`app/maintenance_contracts.py`) sich direkt wiederverwenden lassen -- Ergebnis: nein.
`_is_item_overdue()` ist an die saisonalen `MaintenanceWindow`-Fenster der Wartungsverträge
gekoppelt (`_window_close_date()`, Start-/Endmonat statt Kalendertage) -- das passt fachlich
nicht auf eine turnusmäßige Geräteprüfung wie "TÜV alle 12 Monate", die kein saisonales Fenster
kennt, nur ein festes Intervall. Beide Funktionen sind außerdem privat und eng an
`MaintenanceContract`/`MaintenanceContractItem` gekoppelt.

Übernommen ist deshalb nur das PATTERN, nicht der Code -- exakt die vom Nutzer verlangte
"gemeinsame Funktion, wenn sie sich anbietet, sonst dasselbe Muster mit dokumentierter
Trennung, wie bei den Pipeline-Spalten"-Vorgabe. Neue, eigenständige Funktionen
`is_inspection_due()`/`is_inspection_overdue()` (`app/operational_assets.py`): `is_due` prüft
eine konfigurierbare Vorlaufzeit VOR der eigentlichen Fälligkeit (`next_due_date <= heute +
reminder_lead_days`), `is_overdue` prüft unabhängig davon, ob das Datum bereits verstrichen ist
(`next_due_date < heute`) -- dieselbe Zwei-Stufen-Idee wie beim Wartungsmodul, aber ohne dessen
Fenster-Semantik. Eigene, unabhängige Singleton-Einstellung `OperationalAssetSettings.
reminder_lead_days` (Default 30 Tage) -- kein gemeinsamer Datensatz mit `MaintenanceSettings`.

Ein Asset aggregiert über alle seine Prüffristen: `is_due`/`is_overdue` sind `true`, wenn
MINDESTENS EINE Prüffrist das jeweils erfüllt, `next_due_date` (fürs Sortieren/Anzeigen) ist die
früheste aller künftigen Fristen.

### Datenmodell

- **`OperationalAsset`**: `resource_id` (optional, unique), eigene Identitätsfelder (nur
  relevant ohne Ressourcenbezug), `asset_number`, `notes`, `acquisition_date`,
  `acquisition_cost`, `recurring_cost_per_month`, `cost_notes`, `active`.
- **`OperationalAssetInspection`**: `asset_id`, `inspection_type` (aus der neuen, self-seedenden
  Optionsgruppe `operational_asset_inspection_types` -- TÜV/HU, Leiterprüfung, UVV-Prüfung,
  Wartung, Sonstige Prüfung), `interval_months`, `last_inspection_date`, `next_due_date`,
  `inspector`, `document_filename`/`document_original_name`, `notes`. Cascade beim Löschen des
  Assets (`cascade="all, delete-orphan"`).
- **`OperationalAssetSettings`**: Singleton (`reminder_lead_days`).

`asset_type` selbst nutzt bewusst dieselbe, bereits bestehende Optionsgruppe `resource_types`
wie `OperationalResource` -- keine zweite, parallele Typliste nur für eigenständige
Betriebsmittel.

**Migration `5917bb099776`** legt alle drei Tabellen an UND backfillt in derselben Migration
für jede der zum Zeitpunkt des Schreibens real bestehenden 5 `OperationalResource`-Zeilen
(3× Fahrzeug, 1× Kran, 1× Anhänger) ein verknüpftes `OperationalAsset` (nur `resource_id`
gesetzt, eigene Felder `NULL`) -- ohne diesen Schritt wären alle 5 Bestandsressourcen aus der
Stammdaten-Übersicht verschwunden, sobald diese (bei aktivem Modul) auf die Asset-Ansicht
umgestellt wird. Die Backfill-Logik steckt als eigenständige, direkt testbare Funktion
(`_backfill_assets_for_existing_resources()`) in der Migrationsdatei selbst (Muster aus
1.2.19/1.3.12/1.3.22, siehe "Testen" unten) -- gegen die echte, migrierte Datenbank verifiziert:
alle 5 Zeilen korrekt verknüpft, 0 verwaiste Ressourcen.

**Dokument-Ablage für Prüffristen** (`app/operational_asset_documents.py`, Muster
`app/roof_area_sketches.py`): eigener `data/operational_asset_documents/`-Ordner (neue
Umgebungsvariable `DACHKONZEPTE_OPERATIONAL_ASSET_FILE_ROOT`, in `.env.example` ergänzt, zehnte
Variable dieser Art), PDF zusätzlich zu PNG/JPEG/WebP erlaubt (Prüfprotokolle/Plaketten-Fotos,
anders als bei der reinen Bild-Skizze der Dachfläche), 10 MB-Grenze.

### Kosten: monatsnormalisiert statt Intervall+Betrag -- Vorbereitung für eine künftige Gesamtkostenübersicht

`recurring_cost_per_month` (ein einzelner, bereits auf den Monat umgerechneter Betrag) statt
eines Intervall+Betrag-Paars -- bewusste Vorentscheidung, weil der Nutzer eine spätere
"Gesamtkostenübersicht" bereits angekündigt hat: eine solche Auswertung kann dadurch trivial
über alle Assets `SUM(recurring_cost_per_month)` bilden, ohne zuvor unterschiedliche Intervalle
(monatlich/jährlich/quartalsweise) umrechnen zu müssen. **Merkposten für diese künftige
Auswertung**: `acquisition_cost` (einmalig) und `recurring_cost_per_month` (laufend) sind die
beiden Felder, die sie lesen wird -- beide bereits vorhanden, nichts davon ist noch zu ergänzen,
nur die Auswertung selbst fehlt noch.

### "Fuhrpark & Maschinen" wird zur Weiche, nicht zu zwei Parallelpflegen

Dieselbe Weiche wie bei Mitarbeitern in 1.3.26 ("die Stammdatenseite führt auf die
Betriebsmittelverwaltung, statt eine ärmere Parallelpflege zu bleiben"), aber ohne dass die
alte Seite entfällt -- die 5 Bestandsressourcen dürfen nie verschwinden, auch nicht bei
deaktiviertem Modul:

- **EIN Stammdaten-Navigationsknopf** (`master_data.html`, Jinja-bedingte Beschriftung: "Betriebsmittel"
  bei aktivem Modul, sonst weiterhin "Fuhrpark & Maschinen") statt zwei getrennter Einträge.
- **Modul an**: die reiche Asset-Liste (`GET /api/operational-assets`) -- eigener,
  `.catch(()=>[])`-abgesicherter Fetch-Zweig in `load()`s `Promise.all(...)`, da dieser
  Endpunkt (anders als jeder andere, bisher unbedingt geladene Fetch dieser Datei) modulgated
  ist und 403 liefern könnte, sobald das Modul während einer Sitzung abgeschaltet wird. Ein
  "Fällige Prüffristen"-Panel steht oben, "+ Hinzufügen" führt auf `/master-data/assets/new`.
- **Modul aus**: unverändert die alte, rohe Ressourcenliste (`GET /api/resources`, weiterhin
  ungegatet, Kern-ERP -- diese Datei fragt sie ohnehin immer ab, da `teamForm()` sie unabhängig
  vom Betriebsmittel-Modul braucht), "+ Hinzufügen" führt weiterhin auf
  `/master-data/resources/new`.
- **Anlegen** läuft über `master_data_form.html`s neue `assetForm()` (Ressourcenbezug-
  Umschalter, bereits verknüpfte Ressourcen werden aus der Auswahl ausgeschlossen). **Bearbeiten
  bewusst NICHT über dasselbe Formular** -- Regel-10-Präzedenzfall "eigene, reichere
  Detailseite statt generischem Formular, wenn ein Bereich das rechtfertigt" (wie Property/
  Wartungsvertrag): `master_data_form.html` bounct bei `type==='assets'&&editing` sofort auf
  `GET /betriebsmittel/{id}` (`app/templates/operational_asset.html`, Muster
  `maintenance_contract.html`), Anlegen bounct nach dem Speichern ebenso dorthin. Die
  Detailseite verlinkt bei verknüpfter Ressource zusätzlich auf deren eigene Stammdatenseite
  (`/master-data/resources/{id}/edit`), damit reine Ressourcenfelder (Kennzeichen, Hersteller
  bei Fuhrpark) weiterhin erreichbar bleiben, ohne sie auf der Betriebsmittelseite zu
  duplizieren.

### Sichtbarkeit auf Übersicht und Dashboard

Dashboard-Widget "Fällige Betriebsmittelfristen" (`due_assets`, Muster `due_maintenance`,
`app/templates/dashboard.html`, blendet sich über `isModuleEnabled('betriebsmittel')` selbst
aus) UND das "Fällige Prüffristen"-Panel auf der Stammdaten-Betriebsmittelliste decken die
verlangte Sichtbarkeit "auf einer Übersicht und im Dashboard" ab, ohne eine dritte, eigene
Seite dafür zu bauen.

### Einstellungen

Einstellungen → System → "Betriebsmittel" (neuer Abschnitt, `settings.html`, Muster
"Wartungen"): einziges konfigurierbares Feld ist `reminder_lead_days`, mit demselben
Deaktiviert-Hinweis-Mechanismus wie beim Wartungsmodul (`operationalAssetModuleDisabledNotice`).

### Verifikation

Per echtem, CDP-gesteuertem Headless-Chrome gegen eine isolierte, temporäre SQLite-Instanz
verifiziert (Muster 1.3.73/1.3.74, Büro-Testkonto statt Admin, um die 1.3.34-Zwei-Faktor-Pflicht
nicht extra einzurichten): Stammdatenliste zeigt korrekt "Betriebsmittel"/die Nächste-Prüffrist-
Spalte, Anlegen bounct tatsächlich zu `/betriebsmittel/{id}`, eine Prüffrist mit einem Datum in
der Vergangenheit lässt sofort das "⚠ PRÜFUNG ÜBERFÄLLIG"-Badge UND das "Fällige Prüffristen"-
Panel auf der Übersicht erscheinen, der Einstellungen-Abschnitt lädt den Wert 30 korrekt, und --
das Modul direkt in der Datenbank deaktiviert -- der vollständige Rückfall auf die alte
Fuhrpark-Ansicht (Sidebar-Label, Seitentitel, Add-Link, die alten Ressourcenspalten) samt
funktionierendem `403` auf `GET /api/operational-assets`. Keine JavaScript-Konsolenfehler
außer dem plattformweit üblichen fehlenden `favicon.ico`. `pytest` vollständig grün (1410
Tests, 17 davon neu in `tests/test_v276_operational_assets.py`: Doppelerfassungs-Schutz,
Live-Auflösung bei Umbenennung der Ressource, Name-Pflicht-Validator, Fälligkeits-Aggregation
über mehrere Prüffristen, Migrations-Backfill isoliert gegen eine frische Verbindung, Rollen-
UND Modul-Gate über echte Router-Endpunkte).

### Stufe 2 (seit 1.4.1): QR-Code-Etikett, rollenabhängige Ansicht

Zweite Etappe, nach Bestätigung von Stufe 1 gebaut. Vier Punkte plus ein abschließender, vom
Nutzer verlangter Angriffstest.

**Punkt 1 -- zwei neue Felder, nur für Büro/Admin.** `article_number` (Artikelnummer, Freitext)
und `product_url` (Produktlink) auf `OperationalAsset` -- beide gehören laut Nutzervorgabe "zur
Beschaffung, nicht zur Bedienung" und erscheinen deshalb NIE in der reduzierten Monteursansicht
(siehe Punkt 3). **`product_url` bewusst strikt validiert**: ein Feld, das eine beliebige
Zeichenkette als Link ausgibt, ist sonst ein Einfallstor (Nutzerformulierung) --
`app/schemas.py::_require_http_url()` (gemeinsamer, modulweiter `field_validator`-Helfer, per
`urlparse` auf Schema `http`/`https` und ein vorhandenes `netloc` geprüft) lehnt alles andere
mit 422 ab, insbesondere `javascript:`-Links. Derselbe Helfer sichert zusätzlich das neue
`GeneralSettings.public_base_url` (siehe Punkt 2) ab -- eine öffentliche Basis-URL trägt
dasselbe Risiko wie ein Produktlink, wenn sie ungeprüft bliebe. Der Link öffnet im
Bearbeiten-Formular über eine Vorschau mit `target="_blank" rel="noopener"` (verhindert, dass
die geöffnete Seite über `window.opener` Zugriff auf die ERP-Seite bekommt).

**Implizite Zusatzanforderung, transparent aufgelöst statt stillschweigend geraten**: Punkt 3
der Anfrage nennt "Bedienungshinweise -- falls es die gibt" als Monteur-sichtbares Feld, ohne
dass Punkt 1 es unter den neuen Feldern ausdrücklich benennt. Als drittes neues Feld
`usage_notes` (Text, nullable) ergänzt -- eine bewusste, offen kommunizierte Interpretation,
keine verdeckte Annahme, konsistent mit der sonst in diesem Projekt geübten Praxis (siehe
z. B. die 1.3.60-Prämisse-Korrektur zur Tätigkeit im Nachtrag).

**Punkt 2 -- QR-Code, Bibliotheks- und Domain-Entscheidung.** Vor jeder Codeänderung geprüft
(wie ausdrücklich verlangt): `qrcode[pil]` ist bereits seit 1.3.34 Projektabhängigkeit (für die
TOTP-Ersteinrichtung, BSD-3-Clause) -- keine neue, zusätzlich lizenzpflichtige Bibliothek nötig.
Wiederverwendet über ein neues, eigenständiges Modul `app/qr_codes.py`
(`qr_code_png_bytes(data: str) -> bytes`), NICHT durch eine Erweiterung des
sicherheitskritischen `app/two_factor.py` -- getrennte Verantwortlichkeiten, kein Risiko für den
Zwei-Faktor-Code durch eine unverwandte neue Funktion. Der Code enthält die VOLLSTÄNDIGE
Ziel-URL inklusive Domain (`asset_qr_target_url()`, `app/operational_assets.py`), damit ein
Scan mit der Telefonkamera direkt die Seite öffnet -- eine reine relative Pfadangabe hätte auf
dem Telefon nichts Sinnvolles ergeben.

**Woher die Domain kommt, bewusst nicht hartkodiert**: geprüft, ob im Projekt bereits ein
Mechanismus für eine öffentliche Basis-URL existiert -- keiner gefunden (`request.base_url`
wird an keiner Stelle projektweit für einen absoluten Link nach außen verwendet). Neues,
optionales `GeneralSettings.public_base_url` (Einstellungen → Unternehmensstammdaten,
"Öffentliche Adresse") hat Vorrang; ist es leer, fällt `_resolve_public_base_url()`
(`app/routers/operational_assets.py`) auf `request.base_url` zurück. Begründung für den
konfigurierbaren Vorrang statt eines blinden Vertrauens in `request.base_url` allein: die
Produktionsumgebung läuft hinter einem Nginx-Reverse-Proxy (siehe "Produktivbetrieb" oben),
ohne dass diese Sitzung eine bestätigte `ProxyHeadersMiddleware`/Trusted-Proxy-Konfiguration
vorgefunden hat -- `request.base_url` allein könnte dadurch das falsche Schema (`http` statt
`https`) oder die falsche interne Adresse liefern, "alle Codes zeigen auf localhost" ist genau
das vom Nutzer benannte Risiko. Neuer, Büro/Admin-only-Endpunkt
`GET /api/operational-assets/{asset_id}/qr-code.png` (`_role_dep`, wie jeder andere
Verwaltungs-Endpunkt dieses Routers außer dem in Punkt 3 erweiterten Einzelabruf) liefert das
PNG direkt als `Response(media_type="image/png")`.

**Button "Etikett drucken"**: auf `/betriebsmittel/{id}` (`operational_asset.html`) ergänzt --
zeigt ein druckbares Etikett mit QR-Code über der Bezeichnung. Umgesetzt über eine
`@media print`-Regel, die `.app-layout` komplett ausblendet und ausschließlich das
Etikett-Element einblendet. **Selbst gefundener und vor jedem Testlauf korrigierter CSS-Fehler**:
der erste Entwurf platzierte das Etikett-`<div>` verschachtelt innerhalb von `.app-layout` --
`display:none` auf einem Vorfahren blendet Nachfahren unabhängig von deren eigenem
`display`-Wert aus, das Etikett wäre beim Drucken also mit ausgeblendet worden. Behoben, indem
das Etikett-Element zu einem direkten Geschwisterelement von `.app-layout` verschoben wurde
(unmittelbar vor dem `<script>`-Tag) -- per echtem `Page.printToPDF` (CDP) bestätigt, dass beim
Drucken ausschließlich QR-Code + Name erscheinen, keine Sidebar/Topbar.

**Punkt 3 -- die rollenabhängige Ansicht, das Kernstück dieser Stufe.** Der QR-Code führt JEDEN
(Büro UND Monteur) auf dieselbe URL `/betriebsmittel/{id}` -- Inhalt ist rollenabhängig, Zugang
bleibt offen: exakt dasselbe Muster wie bei `time_tracking_page()` ("die Weiche hängt an der
Rolle, nicht am Weg"). `app/routers/pages.py::operational_asset_page()` ist von `_role_dep`
(Büro/Admin) auf `_any_role_dep` erweitert und wählt serverseitig die Vorlage:
`operational_asset_field.html` (neu, Muster `_mobile_header.html`, zeigt ausschließlich
Bezeichnung/Art/Hersteller/Modell/Bedienungshinweise) für `field`, unverändert
`operational_asset.html` für Büro/Admin.

`GET /api/operational-assets/{asset_id}` ist ebenfalls von `_role_dep` auf `_any_role_dep`
erweitert, `response_model=OperationalAssetOut | OperationalAssetFieldOut`. Neues Schema
`OperationalAssetFieldOut` (id/name/asset_type/manufacturer/model/usage_notes -- genau sechs
Felder, NICHT Prüffristen/Kosten/Artikelnummer/Produktlink). Der Router konstruiert je Rolle
EXPLIZIT `OperationalAssetFieldOut.model_validate(...)` bzw.
`OperationalAssetOut.model_validate(...)` -- niemals ein bloßes Dict zurückgegeben, Muster
`OrderOut | OrderFieldAccessOut` (Rechtekonzept, `app/routers/orders.py::get_order()`), das
Pydantics sonst mehrdeutige Union-Serialisierung vermeidet.

**Serverseitig geprüft, nicht pfadbasiert -- genau die vom Nutzer verlangte Härte**: ein Monteur,
der die volle Büro-URL `/betriebsmittel/{id}` statt des mobilen Wegs aufruft, bekommt
garantiert dieselbe reduzierte Seite UND dieselbe reduzierte API-Antwort, unabhängig vom Pfad --
die Rollenprüfung sitzt an `_any_role_dep`/der Router-internen Verzweigung, nicht an einer
zweiten, für Monteure gedachten Route. Verifiziert per rekursivem Schlüssel-Scan (Fehlerklasse
`purchase_price` -- ein Feld, das in der Antwort steht, aber nicht in der Oberfläche gezeigt
wird, ist trotzdem sichtbar) sowohl auf reiner Schema-Ebene (`asset_field_dict()`) als auch am
echten, über `router_test_client()` abgerufenen Router-Response.

**Punkt 4 -- kein dedizierter Scanner, wie ausdrücklich verlangt nicht ungefragt gebaut.**
Geprüft, ob ein eigener In-App-QR-Scanner nötig ist: moderne Telefone öffnen einen per
Kamera-App gescannten QR-Code direkt als anklickbaren Link, ohne dass die Anwendung selbst
etwas dafür bereitstellen muss. Kein Scanner umgesetzt -- sollte sich in der Praxis ein Gerät
(z. B. ein älteres Tablet ohne funktionierende Kamera-App-Integration) finden, das das nicht
leistet, ist ein eigener In-App-Scanner ein separat zu bewertender, eigenständiger Aufwand
(zusätzliche Berechtigungsanfrage für die Kamera, eine JS-Bibliothek für das Decodieren), kein
kleiner Nachtrag.

**Angriffstest, wie vom Nutzer verlangt, mit echtem Browser statt nur `pytest`**: per
CDP-gesteuertem Headless-Chrome gegen eine isolierte, temporäre SQLite-Datenbank (niemals gegen
`dachkonzepte_erp.db`) mit zwei echten Rollenkonten geprüft. Büro sieht die volle Ansicht
inklusive der drei neuen Felder, eine funktionierende QR-Code-Vorschau und -- ein
`PUT`-Request mit `product_url: "javascript:alert(1)"` -- eine 422-Ablehnung. Monteur bekommt
über dieselbe URL `/betriebsmittel/1` exakt die sechs erlaubten JSON-Schlüssel (keine Kosten,
keine Artikelnummer, kein Produktlink, keine Prüffristen), keinen "Etikett drucken"-Button im
Markup, und 403 beim direkten Aufruf des QR-Endpunkts -- null "durchgelassen".

**Tests/Migration**: 14 neue Tests (`tests/test_v277_operational_assets_stufe2.py`) -- Punkte im
Einzelnen: URL-Validierung (gültige/ungültige Schemata), Persistenz der drei neuen Felder,
exakte Schlüsselmenge des reduzierten Schemas (Funktionsebene UND Router-Response mit
rekursivem Scan), 403 für Monteur bei deaktiviertem Modul, die reine
`asset_qr_target_url()`-Funktion, PNG-Gültigkeit über Pillow, 403 für Monteur auf dem
QR-Endpunkt, unterschiedlicher QR-Inhalt mit/ohne `public_base_url`-Override,
Seitenvorlagen-Auswahl je Rolle. Migration `ccb5c4c0915b` (vier neue, nullable Spalten -- Regel
1 greift nicht, da keine NOT-NULL-Spalte auf einer bestehenden Tabelle entsteht) erfolgreich
gegen die echte, lokale `dachkonzepte_erp.db` angewendet. Volle Suite: 1424 Tests grün.

### Vier Ergänzungen (seit 1.4.2)

Vierter Auftrag zur Betriebsmittelverwaltung, unabhängig von der weiterhin gesperrten Stufe 3
(Betriebsmittel im Bericht) -- vier vom Nutzer benannte Punkte, ausdrücklich reine Bürofunktion
("Alle drei reine Bürofunktion, kein Monteur betroffen" -- tatsächlich vier Punkte plus der
abschließende Angriffstest).

**Punkt 1 -- automatische Fälligkeitsberechnung der Prüffristen, mit der entscheidenden
Feinheit.** `app/operational_assets.py::_compute_next_due_date(interval_months,
last_inspection_date, acquisition_date)` -- neu, wird von `create_inspection()`/
`update_inspection()` aufgerufen, sobald `interval_months` gesetzt ist:

```python
base = last_inspection_date or acquisition_date
if base is None:
    return None
return add_months(base, interval_months) - timedelta(days=1)
```

`add_months()` wird unverändert aus `app/date_utils.py` wiederverwendet (bereits geteilt zwischen
`maintenance_contracts.py`/`service_reports.py`, siehe dort). **Erste Fälligkeit beim Anlegen mit
Anschaffungsdatum**: `Anschaffungsdatum + Intervall − 1 Tag`, nie das Anschaffungsdatum selbst --
bei Anschaffung ist noch nichts fällig, exakt wie vom Nutzer verlangt. **Die entscheidende
Feinheit, mit eigenem Test belegt**: die Basis ist nach einer erledigten Prüfung IMMER das
tatsächliche `last_inspection_date`, nie eine kumulative Fortschreibung ab dem ursprünglichen
Anschaffungsdatum -- verspätet sich eine Prüfung, verschiebt sich der gesamte Rhythmus mit,
driftet nicht auseinander. `test_late_inspection_advances_next_due_date_from_actual_date_not_
cumulatively_from_acquisition()` (`tests/test_v278_operational_assets_erweiterungen.py`) legt eine
Prüfung deutlich verspätet an (statt am geplanten 2024-12-31 erst am 2025-02-15) und belegt
explizit, dass die neue Fälligkeit vom TATSÄCHLICHEN Datum aus (2026-02-14) berechnet wird, nicht
von der (falschen) kumulativen Rechnung ab dem Anschaffungsdatum (2025-12-31). **Eine Prüffrist
ohne Intervall (einmalige Prüfung) bleibt vollständig manuell** -- geprüft, dass es diesen Fall
gibt (`OperationalAssetInspectionCreate.next_due_date` existierte bereits, wird bei
`interval_months is None` unverändert direkt vom Client übernommen) und ihn sauber behandelt:
kein Server-Eingriff, `next_due_date` bleibt exakt, was der Client sendet, auch beim Wechsel von
intervallbasiert zurück auf manuell.

**Punkt 2 -- Meldung und Aufgabe vier Wochen vorher, derselbe Auslöser wie bei den
Wartungsverträgen.** `check_due_asset_inspections_and_create_reminders()` (neu,
`app/operational_assets.py`) -- **On-Demand, kein Scheduler**: geprüft, wie die Wartungsverträge
ihre Erinnerungen erzeugen (`check_due_contracts_and_create_reminders()`,
`app/maintenance_contracts.py`) -- derselbe Mechanismus wiederverwendet, ausgelöst per
Fire-and-Forget-`fetch()` (`master_data.html`s `load()`, gated auf `bmModuleEnabled`) beim Öffnen
der Stammdaten-Betriebsmittelliste, über einen neuen, literalen Endpunkt `POST
/api/operational-assets/check-due` (deklariert vor `/{asset_id}`, Muster
`POST /api/maintenance-contracts/check-due`). **Idempotenz über denselben Stempel-Mechanismus wie
`MaintenanceContract`**: neue, nullable Spalte `OperationalAssetInspection.last_reminder_due_date`
-- pro Prüffrist und Fälligkeitstermin genau einmal, nicht bei jedem Durchlauf erneut. **Ohne
expliziten Reset**, anders als bei `MaintenanceContract` (das ihn an mehreren Stellen zurücksetzt):
`next_due_date` wird bei diesem Feature bei JEDER Prüfung frisch neu berechnet (Punkt 1), weicht
dadurch automatisch vom alten Stempel ab, sobald sich etwas ändert -- ein Reset wäre redundant.
`test_check_due_reminds_again_after_next_due_date_actually_changes()` belegt das explizit: nach
einer neuen Prüfung mit geänderter Fälligkeit erinnert der nächste Aufruf erneut, ohne dass irgend
etwas den Stempel manuell zurücksetzen musste.

Die Aufgabe geht **unassigned** ("allgemein ans Büro", `assigned_employee_id=None`) mit Verweis
auf das Betriebsmittel (`source_module="betriebsmittel"`, `source_url="/betriebsmittel/{id}"`) --
wortgetreu wie vom Nutzer verlangt, es gibt (anders als `MaintenanceContract.
responsible_employee_id`) kein Zuständigkeits-Feld je Betriebsmittel oder eine passende
Modul-Einstellung dafür. **Dabei ein bereits bestehendes, transparent gemeldetes Verhalten des
Task-Systems entdeckt, nicht neu eingeführt**: `GET /api/tasks` (`app/routers/tasks.py`) erzwingt
für jeden NICHT-Admin-Aufrufer `employee_id == request.state.erp_user.employee_id` -- eine
unassigned Aufgabe ist damit für ein Büro-Konto ohne Admin-Rolle in der heutigen Aufgabenliste
unsichtbar, nur ein Administrator sieht sie. Bewusst NICHT durch ein ungefragtes, neues
`default_responsible_employee_id`-Einstellungsfeld umgangen -- die Anfrage sagte ausdrücklich
"allgemein ans Büro", eine stillschweigende Zuweisung an eine erratene Person hätte diese Vorgabe
unterlaufen. **Kein zweites Dashboard-Widget**: die Prüffristen erscheinen weiterhin nur im
bestehenden, seit Stufe 1 vorhandenen "Fällige Prüffristen"-Panel, die Aufgabe im Aufgabenbereich.

**Punkt 3 -- Betriebsmittel in der Büro-Suche.** 18. Eintrag in `OFFICE_SEARCH_SOURCES`
(`app/search.py`) -- `SearchSource("operational_assets", "Betriebsmittel", OFFICE_ROLES,
_search_operational_assets, _operational_asset_row, module_key="betriebsmittel")`. Mindestrolle
Büro (`OFFICE_ROLES = {ROLE_ADMIN, ROLE_OFFICE}`, dieselbe Konstante wie jede andere Quelle) -- ein
Monteur findet Betriebsmittel in der Suche NICHT, die Registry erbt die Rollenprüfung automatisch
über den bereits bestehenden `search_office()`-Dispatcher UND den primär sichernden
`GET /api/search`-Router (`require_role(ROLE_ADMIN, ROLE_OFFICE)`, ROLE_FIELD ausdrücklich nicht
dabei). Nur wenn das Modul "betriebsmittel" aktiv ist (`module_key="betriebsmittel"`, dritte,
bereits bestehende Achse des Dispatchers). Durchsucht Bezeichnung/Art/Hersteller/Modell/
Kennzeichen/Artikelnummer, führt auf `/betriebsmittel/{id}`.

**Live-Auflösung beachtet, sonst wären ressourcenverknüpfte Assets unauffindbar gewesen**: ein
Asset MIT `resource_id` trägt seine eigenen Identitätsfelder (`name`/`asset_type`/`manufacturer`/
`model`/`identifier`) als `NULL` (siehe Stufe 1, "Live-Auflösung statt Kopie") -- ein Suchfilter,
der nur `OperationalAsset` selbst prüft, hätte jeden Kran/Fahrzeug/Anhänger nie gefunden.
`_search_operational_assets()` joint deshalb zusätzlich per `outerjoin` auf `OperationalResource`
und filtert auf BEIDE Tabellen; `_operational_asset_row()` nutzt für den angezeigten Namen denselben
`resolve_asset_identity()`-Helfer wie `asset_to_dict()`/`asset_field_dict()` -- dafür musste die
Funktion umbenannt werden (`_resolve_identity()` → `resolve_asset_identity()`, ohne führenden
Unterstrich, da sie jetzt modulübergreifend genutzt wird), damit Suche, Büro-Ansicht und
Monteur-Ansicht (Stufe 2) für dasselbe Asset garantiert nie unterschiedliche Namen zeigen können.
Der Registry-Vollständigkeitstest (`EXPECTED_OFFICE_SEARCH_KEYS`,
`tests/test_v270_office_search.py`) deckt den neuen Eintrag mit ab -- inkl. eines neuen Tests, der
belegt, dass die Quelle beim Deaktivieren des Moduls "betriebsmittel" verschwindet. **Nebeneffekt
korrigiert**: `search_results.html`s clientseitig hartcodierte `TYPE_LABELS`-Liste (17 Einträge,
seit Etappe 2 der Büro-Suche) musste um den 18. Eintrag ergänzt werden, sonst hätte der
bestehende Abgleichstest (`test_search_results_page_type_filter_keys_match_the_registry`) die
Divergenz sofort angezeigt -- genau der Zweck dieses Tests.

**Punkt 4 -- Dokumentenablage am Betriebsmittel, für Anschaffungsrechnung, Leasingvertrag u. Ä.**
Vor dem Bauen geprüft, wie ausdrücklich verlangt, ob die Kategorie-Stammdaten aus 1.3.62
(`DocumentCategory`) genutzt werden können oder eine schlanke eigene Ablage genügt -- Ergebnis:
**schlanke eigene Ablage**, `DocumentCategory`s gesamter Zweck (`is_sensitive`/`is_field_visible`,
zwei unabhängige Schlösser gegen "sensible Kategorie für Monteure sichtbar") ist hier
gegenstandslos, da Betriebsmittel-Dokumente AUSNAHMSLOS Büro/Admin-only sind -- es gibt keine
Feld-sichtbare Stufe, die ein Schloss überhaupt bräuchte. Stattdessen dasselbe leichtgewichtige
Muster wie `OperationalAssetInspection.inspection_type`: eine neue, self-seedende Optionsgruppe
`operational_asset_document_types` (`app/option_settings.py`, drei Werte: Anschaffungsrechnung,
Leasingvertrag, Sonstiges).

Neue Tabelle `OperationalAssetDocument` (`app/models.py`) -- bewusst NICHT das bestehende
1:1-Muster je Prüffrist (`OperationalAssetInspection.document_filename`, ersetzt immer die
vorherige Datei) wiederverwendet, da ein Betriebsmittel beliebig viele UNABHÄNGIGE Dokumente
tragen kann (Anschaffungsrechnung UND Leasingvertrag UND ...). Neue Relationship
`OperationalAsset.documents` (`cascade="all, delete-orphan"`). Speicherort: derselbe Ordner/dieselbe
Umgebungsvariable wie die bestehende Prüffristen-Ablage (`app/operational_asset_documents.py`,
`DACHKONZEPTE_OPERATIONAL_ASSET_FILE_ROOT`, über `ERP_DATA_DIR` wie jeder Upload dieses Projekts)
-- neue `save_document()`-Funktion für das unabhängige, mehrere-Dateien-Muster, neben der
bestehenden `replace_document()` für die 1:1-Ablage. **Löschen räumt die Datei auf**: neues
`@event.listens_for(OperationalAssetDocument, "before_delete")` (Muster
`app/roof_areas.py::_delete_roof_area_sketch_file()`) -- feuert für JEDEN ORM-Löschweg, auch
kaskadiert beim Löschen des ganzen Betriebsmittels, kein separater Aufräum-Aufruf in
`delete_asset_document()`/`delete_asset()` nötig.

Drei neue Endpunkte (`app/routers/operational_assets.py`), **ausnahmslos** `_role_dep` (Büro/Admin,
NIE `_any_role_dep`, anders als der Einzelabruf aus Stufe 2): `POST
/api/operational-assets/{asset_id}/documents` (multipart, `document_type`+`notes` als Form-Felder,
`file` als Upload -- Existenzprüfung des Assets VOR dem Speichern der Datei, damit eine Datei für
ein nicht existierendes Betriebsmittel nie erst auf die Platte geschrieben wird), `GET
/api/operational-asset-documents/{document_id}/file`, `DELETE
/api/operational-asset-documents/{document_id}`.

**Abschließender Angriffstest, wie explizit für nach dieser Runde verlangt**: ein Monteur kommt
über keinen Weg an eine Betriebsmittel-Rechnung, auch nicht über eine geratene Datei-ID --
`test_field_can_never_reach_an_operational_asset_document_via_any_path()` prüft alle drei
Endpunkte sowohl mit einer echten, existierenden `document_id` als auch mit geratenen,
fortlaufenden IDs (1, 2, 9999): durchgängig 403, `require_role()` schließt die Rolle strukturell
aus, unabhängig davon, ob die ID existiert -- kein 404-vs-403-Unterschied, der verraten könnte, ob
ein Dokument existiert. Und die Büro-Suche liefert einem Monteur kein Betriebsmittel --
`test_office_search_endpoint_never_returns_an_operational_asset_to_field_role()` ruft den echten
`GET /api/search`-Router mit `role="field"` auf und erwartet 403, bevor `search_office()` auch nur
eine Zeile liest. Beide Tests in `tests/test_v278_operational_assets_erweiterungen.py`, 0
"durchgelassen".

**Verifiziert**: 16 neue Tests (`tests/test_v278_operational_assets_erweiterungen.py`) --
Fälligkeitsberechnung (Erst-Fälligkeit, verspätete Prüfung, manuelle Prüffrist, Wechsel
manuell→intervallbasiert, `_compute_next_due_date()` isoliert), Erinnerungs-Idempotenz (inkl. des
Falls "erinnert erneut nach echter Änderung" und "Modul deaktiviert"), Suche (ressourcenverknüpft
UND eigenständig, Rollenausschluss auf Funktionsebene), Dokumentenablage (voller Upload/Ansehen/
Löschen-Zyklus über den Router, Datei-Aufräumen von der Platte), die beiden Angriffstests. Dabei
zwei bereits bestehende Tests korrigiert (nicht Regressionen, sondern durch dieses Feature
tatsächlich veraltete Annahmen): `tests/test_v276_operational_assets.py::
test_office_role_full_crud_flow_via_router` sendete bisher `interval_months` UND `next_due_date`
gemeinsam und erwartete, dass der manuelle Wert übernommen wird -- genau das Verhalten, das Punkt 1
bewusst ändert; umgestellt auf `interval_months=None` (die weiterhin manuelle Variante), da der
Test generisch den CRUD-Fluss prüft, nicht die neue Berechnung selbst. `tests/
test_v271_office_search_ui.py`s hartcodierter Registrierungs-Zähler (`== 17`) und ein
Docstring-Verweis wurden auf 18 aktualisiert. Migration `ed896599a211` (neue Tabelle
`operational_asset_documents`, neue, nullable Spalte
`operational_asset_inspections.last_reminder_due_date` -- Regel 1 greift bei keiner der beiden,
da weder eine NOT-NULL-Spalte auf einer bestehenden Tabelle noch Bestandsdaten für die neue
Tabelle existieren) erfolgreich gegen die echte, lokale `dachkonzepte_erp.db` angewendet. Volle
Suite: 1441 Tests grün.

### Stufe 3 (seit 1.4.5): Eingesetzte Betriebsmittel im Einsatzbericht

Reine Dokumentation -- kein Preis, keine Menge, keine Betriebsstunden in dieser Version. Erst
Befund (Aufbau des Einsatzberichts, welches Vorbild passt, wo im PDF), dann drei vom Betreiber
entschiedene Punkte, dann in einer Runde gebaut.

**Vorbild war `ServiceReportMaterial`, nicht `ServiceReportPhoto`**: Material ist strukturell
ein reiner Datenbezug (FK + Zusatzfelder), ein Betriebsmitteleinsatz ist keine Datei. Die
Bedienung ist bewusst dieselbe wie bei Material -- ein vierter, gleichrangiger Panel-Umschalter
"Betriebsmittel" auf der Berichtskarte (neben Prüfpunkte/Mängel/Material), Tabelle + Erfassungszeile,
solange der Bericht Entwurf ist. **Ein Unterschied zu Material**: statt einer debounced
Katalogsuche ein einfaches `<select>` -- die freigegebene Liste bleibt in der Praxis kurz (Kran,
Hubsteiger, …), eine Suche wäre hier unnötiger Aufwand.

**Das Flag "im Bericht auswählbar"** (`OperationalAsset.selectable_in_reports`, Standard AUS,
`server_default='0'`) -- dasselbe restriktive Vorgabemuster wie `DocumentCategory.is_field_visible`
(1.3.62): das Büro gibt bewusst frei, was in einen Bericht darf, sonst wächst die Liste mit jedem
Kleingerät zu. Nur über die Betriebsmittel-Bearbeitungsseite änderbar (neues Feld neben "Status").
**Die 5 Bestandsressourcen** wurden bei der Migration (`b2226e22b9f0`) auf "nicht auswählbar"
gesetzt -- keine Vermutung, welche gemeint sein könnten, das Büro gibt sie gezielt frei.

**Die Freigabeprüfung gilt für JEDEN Aufrufer gleich, auch Büro/Admin** -- bewusst keine
Rollenausnahme: wer ein nicht freigegebenes Betriebsmittel einsetzen will, gibt es zuerst in der
Betriebsmittelverwaltung frei (ein Klick), statt dass die Business-Logik zwei unterschiedliche
Regeln für Büro und Monteur führen müsste. Das ist zugleich die serverseitige Absicherung gegen
eine geratene `asset_id` über den Endpunkt (`add_asset_usage()` in `app/service_reports.py`),
unabhängig davon, was die Auswahlliste selbst anzeigt.

**`ServiceReportAsset` -- die Tabelle, so geschnitten, dass die Kostenerweiterung später
sauber andockt** (siehe Klassendocstring in `app/models.py` für die volle Begründung, hier die
Kurzfassung): `service_report_id` + `asset_id` (Pflicht -- ein Betriebsmittel wird immer aus dem
Katalog gewählt, nie frei eingetippt, anders als `ServiceReportMaterial.material_id`) +
`asset_name_snapshot` (Pflicht, physisch eingefroren bei der Erfassung) + `notes` (das einzige
Zusatzfeld dieser Stufe, bleibt intern) + `sort_order`/`created_by_employee_id`/`client_uuid`
(letzteres dasselbe "vorbereiten, nicht vorbauen"-Muster wie bei Fotos/Material). **Beides, wie
verlangt**: `asset_id` bleibt als echter Verweis für eine spätere Kostenauswertung erhalten, UND
`asset_name_snapshot` zeigt unabhängig davon, was zum Zeitpunkt der Erfassung eingesetzt wurde --
dasselbe Muster wie die Bauteil-/Dachflächennamen seit 1.3.12. Bewusst KEIN `roof_area_id` (anders
als Material) -- ein Kran/Hubsteiger gehört üblicherweise zum ganzen Einsatz, nicht einer
einzelnen Dachfläche. **Diese Tabelle ist die vorgesehene Stelle für die spätere Kosten-/
Abrechnungserweiterung** (Betriebsstunden, Mietdauer, abrechenbare Menge, die in eine Rechnung
fließen) -- ein Datensatz je Einsatz, kein Name in einer Liste. Kommt diese Erweiterung, sind es
nullable `ALTER TABLE ADD COLUMN`-Ergänzungen auf genau dieser Zeile, keine Strukturänderung --
der nächste Durchgang soll das hier vorfinden, nicht neu herleiten müssen.

**`delete_asset()` blockiert jetzt, solange ein Bericht (Entwurf ODER unterschrieben) das Asset
referenziert** -- bewusst strenger als `delete_roof_component()` (das nur bei bereits
unterschriebenen Berichten blockiert): `ServiceReportAsset.asset_id` ist NICHT NULL, ein Löschen
würde die Fremdschlüsselbeziehung sonst in JEDEM Fall verletzen, nicht nur bei einem bereits
abgeschlossenen Nachweisdokument. Archivieren (`active=False`) bleibt dafür uneingeschränkt
möglich -- der übliche Weg, ein nicht mehr genutztes Betriebsmittel auszublenden, ohne seine
Verwendung in Berichten zu gefährden.

**QR-Scan im Bericht -- geprüft, nicht gebaut, wie verlangt.** Der bestehende QR-Code kodiert die
volle Ziel-URL `/betriebsmittel/{id}` für die Kamera-App des Telefons -- ein Scan öffnet eine neue
Seite und verlässt damit den gerade bearbeiteten Bericht vollständig, kein natürlicher Andock-Punkt
für "während der Erfassung kurz scannen". Ein echter In-Bericht-Scanner bräuchte Kamera-Zugriff im
Browser (`getUserMedia`) plus eine Dekodier-Bibliothek -- nichts davon existiert im Projekt, ein
eigener, spürbarer Aufwand mit Cross-Browser-Risiko (keine zuverlässige native `BarcodeDetector`-
Unterstützung auf allen Zielgeräten). Zurückgestellt, bis sich im Betrieb zeigt, dass die
Auswahlliste zu umständlich ist -- für jetzt: Auswahl aus der freigegebenen Liste.

**Einfrieren nach der Unterschrift** wie Material/Fotos/Prüfpunkte -- `add_asset_usage()`/
`update_asset_usage()`/`delete_asset_usage()` nutzen dieselbe `_require_draft_report()`-Sperre,
kein neuer Mechanismus. `sign_report()` bekommt dafür KEINE neue Pflichtprüfung (Muster Material:
ein Einsatz ohne Betriebsmittel ist normal).

**Im Kundenbericht**: neuer Abschnitt "Eingesetzte Betriebsmittel" (`app/service_report_pdf.py`),
direkt nach "Verbrauchtes Material", nur wenn tatsächlich welche erfasst wurden (Muster Material/
Mängel). Bewusst KEINE Tabelle (keine Menge/Einheit wie bei Material) und KEINE Gruppierung nach
Dachfläche (ServiceReportAsset kennt kein `roof_area_id`) -- eine schlichte, komma-getrennte
Namensliste aus den eingefrorenen `asset_name_snapshot`-Werten, über den gemeinsamen Rahmen, mit
`KeepTogether` wie die anderen Abschnitte. `notes` erscheint NIE im PDF -- bleibt der interne
Vermerk, wie `OperationalAsset.cost_notes` auch nie in einem Dokument auftaucht. Erscheint
unbedingt auch im reduzierten Feld-PDF (`build_service_report_pdf_for_field()`,
`include_time_entries=False`) -- anders als Zeitbuchungen sind eingesetzte Betriebsmittel keine
fremden Personendaten.

**Neuer, für jede Rolle erreichbarer Endpunkt** `GET /api/operational-assets/selectable-for-report`
(bewusst literal VOR `/{asset_id}` deklariert, Muster `/due`/`/check-due`) -- liefert IMMER
`OperationalAssetFieldOut` (die fünf bereits aus Stufe 2 bekannten feldsicheren Felder), gefiltert
auf `selectable_in_reports UND active`, unabhängig von der Rolle: ein Bericht braucht nie Kosten-/
Fristendaten, egal wer ihn füllt. Rekursiver Schlüssel-Scan bestätigt: kein Kosten-/Fristen-/
Artikelnummernfeld in der Antwort, für `field`/`office`/`admin` gleichermaßen.

**Modul-Doppelgate**: `POST/GET/PUT/DELETE .../service-reports/{id}/assets*` prüfen zusätzlich zu
`is_module_enabled(db, "wartungen")` auch `is_module_enabled(db, "betriebsmittel")` -- ein
Einsatzbericht kann Betriebsmittel nur dokumentieren, wenn BEIDE Module aktiv sind, sonst bliebe
die Betriebsmittelverwaltung über diesen Umweg nutzbar, obwohl sie deaktiviert ist.

**Verifiziert**: 26 neue Tests (`tests/test_v280_operational_assets_stufe3.py`) -- Namens-Snapshot
(bleibt bei Umbenennung/Archivierung des Assets unverändert), Freigabe-Flag (Standard aus, gilt für
jeden Aufrufer gleich, unbekannte/nicht freigegebene `asset_id` abgelehnt), `list_selectable_assets()`
(gefiltert auf freigegeben+aktiv, live aufgelöster Name bei ressourcenverknüpften Assets, sortiert),
`delete_asset()`-Blockade (Entwurf UND unterschrieben, Archivieren bleibt frei), Einfrieren nach
Unterschrift, PDF (Abschnitt erscheint/verschwindet korrekt, Name bleibt nach späterer Umbenennung
eingefroren, `notes` nie im PDF, auch im Feld-PDF vorhanden), Router-CRUD, der verlangte rekursive
Schlüssel-Scan über alle drei Rollen, und die beiden Angriffstests (nicht freigegebene/geratene
`asset_id` liefert 400 statt stillem Erfolg; ein Monteur kann keinem fremden Bericht ein
Betriebsmittel hinzufügen). Migration `b2226e22b9f0` (neue Tabelle `service_report_assets`, neue
NOT-NULL-Spalte `operational_assets.selectable_in_reports` mit `server_default='0'`, Regel 1
befolgt) erfolgreich gegen die echte, lokale `dachkonzepte_erp.db` angewendet, Bestandsdaten
geprüft (alle 5 Assets korrekt auf `False`). Volle Suite: 1492 Tests grün.

### Dokument-Upload schon beim Erstellen des Betriebsmittels (seit 1.5.6)

Nachbesserung, unabhängig von den Stufen 1-3 oben. Bis dahin ließ sich ein Dokument
(Anschaffungsrechnung, Leasingvertrag) erst nach dem Speichern -- im Bearbeiten-Modus -- an ein
Betriebsmittel hängen; das Anlegen-Formular (`master_data_form.html::assetForm()`) hatte keinen
Upload. **Ursache, wie vermutet und bestätigt**: `POST /api/operational-assets/{asset_id}/documents`
(1.4.2, siehe "Vier Ergänzungen" oben) verlangt zwingend eine bereits existierende `asset_id` als
Pfadparameter (`if db.get(OperationalAsset, asset_id) is None: raise HTTPException(404, ...)`) --
beim Anlegen gibt es diesen Datensatz naturgemäß noch nicht. Der Endpunkt selbst war korrekt und
brauchte keine Änderung.

**Gewählter Weg (Option a: erst speichern, dann anhängen) statt Option b (Dateien
zwischenhalten, nach dem Anlegen automatisch anhängen)**: `File`-Objekte lassen sich in
Vanilla-JS nicht über einen echten Seitenwechsel hinweg persistieren, und das Anlegen-Formular
und die Betriebsmittel-Detailseite sind zwei getrennte Templates/URLs (`master_data_form.html`
vs. `operational_asset.html`) -- Option b hätte entweder einen echten Navigations-Umweg
gebraucht (der das Problem gar nicht löst) oder eine Persistenz über `sessionStorage`/IndexedDB
nur für diesen einen Formularschritt, unverhältnismäßig für ein einziges Feld. Option a bleibt
für den Nutzer EIN Vorgang (ein Klick auf "Speichern"), intern zwei Schritte: das Betriebsmittel
zuerst per `POST /api/operational-assets` anlegen, danach die vorgemerkten Dateien sequenziell
an die zurückgegebene `id` hängen -- beides innerhalb derselben `save()`-Ausführung, kein
Seitenwechsel dazwischen.

**Mechanismus**: eine Client-seitige Warteschlange `pendingAssetDocuments` (Array aus
`{file, document_type, notes}`) -- "+ Vormerken" fügt eine Datei samt Art/Notiz hinzu, ohne
etwas zu senden; erst `save()` lädt jede vorgemerkte Datei nacheinander per
`fetch(...,{method:'POST',body:FormData})` an `/api/operational-assets/{saved.id}/documents`
hoch, NACHDEM der `POST` für das Betriebsmittel selbst erfolgreich war.

**Fehlerfall, wie ausdrücklich verlangt geprüft**: die Datei-Upload-Schleife steht im Code
zwingend NACH `const saved=await api(url,{method,...})` (der eigentlichen Anlage). Schlägt dieser
Aufruf fehl (Pflichtfeld fehlt, 422-Validierung), wirft er eine Ausnahme -- die Ausführung springt
direkt in den umschließenden `catch(e){el('msg').textContent='Fehler: '+e.message}`-Block, die
Upload-Schleife wird nie erreicht. Damit gilt zugleich: **kein verwaistes Betriebsmittel**
(es wurde ja gar nicht erst angelegt) und **keine verlorenen Dateien** (`pendingAssetDocuments`
und die Datei-Auswahl im Formular bleiben unverändert stehen, ein erneuter Speichern-Versuch nach
Korrektur des fehlenden Felds braucht keine erneute Dateiauswahl). Schlägt dagegen NUR ein
einzelner Dokument-Upload NACH erfolgreicher Anlage fehl (z. B. ein zu großes Dokument), bleibt
das Betriebsmittel bestehen (kein Rollback der Anlage selbst, die bereits abgeschlossen ist) --
`save()` sammelt fehlgeschlagene Uploads in einer Liste und zeigt sie nach der Navigation zur
neuen Detailseite per `alert()` an ("... bitte auf der Betriebsmittelseite erneut versuchen"),
statt sie stillschweigend zu verschlucken.

**Bewusst nur an dieser einen Stelle** -- die Anfrage stellte ausdrücklich klar, dass das Muster
laut Betreiber nicht verallgemeinert werden soll ("gilt nur beim Betriebsmittel, nicht
anderswo"), deshalb keine geteilte Hilfsfunktion/kein neuer, allgemeiner Mechanismus, nur die
eine Formular-Datei (`master_data_form.html`) geändert. `app/routers/operational_assets.py`
selbst wurde nicht angefasst.

**Verifikation**: `node --check` gegen den extrahierten `<script>`-Block (nach Neutralisierung der
beiden Jinja-Platzhalter `{{ data_type }}`/`{{ record_id|default('null') }}`, Projektkonvention
für Jinja-templatetes JS) -- keine Syntaxfehler. Kein Backend-Verhaltensänderung, deshalb keine
neuen `pytest`-Tests; die Absicherung dieser Version stützt sich ausschließlich auf sorgfältige
Kontrollfluss-Lektüre (`save()`s try/catch-Struktur) und `node --check`, **kein echter
Browser-Klicktest** in dieser Runde (bekannte, wiederholt dokumentierte Werkzeug-Einschränkung
dieser Sitzung war für diesen einen Punkt nicht aktiviert) -- sollte bei Gelegenheit im Browser
nachgeprüft werden (Anlegen mit zwei vorgemerkten Dokumenten, Anlegen mit absichtlich fehlendem
Pflichtfeld -- Dateien müssen erhalten bleiben).

## Betriebskosten-Übersicht (seit 1.5.0, Modul "betriebskosten")

Erstes neues Modul seit der Betriebsmittelverwaltung (`module_key "betriebskosten"`,
`OPTIONAL_MODULES`, buero_finanzen/admin-only -- siehe "Rechtekonzept" -> "Vier Rollen": die
Betriebskosten-Übersicht war dort bereits als künftiger, buero_finanzen-verengter Bereich
vorgemerkt, dieses Modul löst genau diesen Vormerkposten ein). Schicht 1 -- ausschließlich die
Kostenerfassung, wie beauftragt; der eigentliche Schritt zum Verrechnungssatz bleibt eine
spätere, eigene Schicht 3. Erst ein reiner Befund zu fünf Rückfragen berichtet (Herleitung des
Stundenverrechnungssatzes, bestehende Kostendatenquellen, Modellform, Aufgaben-Zielgruppe,
Summenansicht), dann vier vom Nutzer entschiedene Punkte gebaut.

### Zwei Kostenquellen nebeneinander, keine Migration

`RecurringCost` (`app/models.py`) ist eine neue, eigene Tabelle für den detaillierten
wiederkehrenden Vertrag (Miete, Leasing, Versicherung, Software-Abo u. Ä. -- Partner,
Kündigungsfrist, Dokument). **Bewusst NICHT** die bestehenden `OperationalAsset.
acquisition_cost`/`recurring_cost_per_month` (seit 1.4.0) migriert oder ersetzt -- Begründung des
Betreibers: die monatliche Kosten-Notiz am Betriebsmittel ist eine schnelle Notiz beim Anlegen,
der neue Kostenposten der ausführliche Vertrag. Beide Quellen bestehen unabhängig nebeneinander,
`app/recurring_costs.py::overview_summary()` führt sie ausschließlich in der SUMME zusammen.

**Doppelzählung verhindert, nicht nur erkannt** (die vom Nutzer selbst benannte Gefahr: "wenn
jemand für dieselbe Leasingrate sowohl `monthly_cost` am Transporter ALS AUCH einen Kostenposten
anlegt, zählt die Summe sie doppelt"): zeigt ein `RecurringCost` über sein optionales `asset_id`
auf ein Betriebsmittel, ERSETZT er dessen `recurring_cost_per_month` in `overview_summary()`,
statt sie zu addieren -- `annual_from_asset_quick_costs` schließt jedes Asset, dessen `id` unter
mindestens einem aktiven, verknüpften Kostenposten auftaucht, explizit aus. Bewusst **kein**
`UniqueConstraint` auf `RecurringCost.asset_id` -- ein Betriebsmittel kann mehrere unabhängige
Kostenposten tragen (z. B. Leasingrate UND Versicherung für denselben Transporter), die
Ersetzungsregel greift bereits, sobald IRGENDEIN aktiver Posten existiert, nicht erst bei genau
einem. Zwei nicht persistierte Transparenz-Hinweise (Muster `material_markup_hint`,
`app/invoices.py` seit 1.2.23) machen die Ersetzung sichtbar, statt sie stillschweigend
geschehen zu lassen: `RecurringCostOut.asset_quick_cost_hint` (nur bei gesetztem `asset_id`) und
`OperationalAssetOut.has_linked_recurring_cost` (NICHT auf `OperationalAssetFieldOut` -- ein
Monteur bekommt diesen rein bürowirtschaftlichen Hinweis nie zu sehen). Letzteres berechnet
`app/operational_assets.py::asset_to_dict()` über einen neuen, optionalen `db`-Parameter (nur
wenn übergeben, sonst konservativ `False`) -- alle bestehenden Aufrufer (Stufe 1-3, die
Büro-Suche) wurden geprüft und angepasst, wo sinnvoll (Einzelabruf/Liste/Anlegen/Ändern), keiner
musste sich strukturell ändern.

### `annual_amount` -- der Andockpunkt für den späteren Verrechnungssatz-Kreislauf

`RecurringCost.annual_amount` ist ein **gespeichertes** Feld (nicht bei jeder Summierung aus
`amount`/`billing_interval` neu berechnet) -- `app/recurring_costs.py::normalize_to_annual()`
berechnet es bei jedem Anlegen/Ändern. **Das ist ausdrücklich der Wert, den Schicht 2 nur noch
aufsummiert und Schicht 3 in die Gemeinkosten einspeist**, wie vom Nutzer verlangt hier
festgehalten, mit Verweis auf die konkrete, im Befund gefundene Stelle:
`app/labor_rate.py::calculate_labor_rate()` berechnet `fixed_overhead` bereits heute als reine
Summe (aktuell: `LaborRateOverheadSettings.fixed_overhead_value`, Modus `"eur"`, ein einzelner,
händisch gepflegter Betrag) -- die Summe aller aktiven `RecurringCost.annual_amount`-Werte
(`overview_summary()["annual_total"]`, zusammen mit den nicht-doppelt-gezählten
Betriebsmittel-Notizen) ist exakt der Wert, den ein künftiger, automatischer Kreislauf dort
einsetzen wird, statt ihn weiterhin von Hand einzutragen. Diese Version baut den Kreislauf
selbst NICHT (Schicht 3, separat) -- nur das Feld, auf dem er andocken wird.

**Seit 1.5.5 präzisiert**: `amount` hieß damals noch so und trug keine Steuersemantik -- seit
1.5.5 heißt das Feld `net_amount`, `annual_amount` wird ausschließlich daraus berechnet, nie aus
einem Bruttobetrag. Siehe Abschnitt "Netto und Brutto bei den Betriebskosten" unten für die
vollständige Herleitung.

### Rhythmus als fester Code-Wert, "einmalig" bereits vorbereitet

`BILLING_INTERVALS` (`app/recurring_costs.py`) ist ein festes Code-Tupel wie `SEVERITIES`/
`ACTIONS`/`STATUSES` bei `Finding` -- **keine** Optionsgruppe, da der Rhythmus eine Rechenregel
trägt (`normalize_to_annual()`s Multiplikator), keine freie Konfiguration: `monatlich`
(×12), `vierteljaehrlich` (×4), `halbjaehrlich` (×2), `jaehrlich` (×1), `einmalig` (×0).

**Punkt 4 der Anfrage, geprüft statt geraten**: "einmalig" ist bereits ein gültiger, im Modell
unbeschränkter Wert -- `billing_interval` ist auf keiner Ebene per DB-`CHECK`-Constraint
begrenzt (kein einziges Vorkommen davon im ganzen Projekt), nur Pydantic
(`RecurringCostCreate.billing_interval`) validiert die erlaubte Menge, erweiterbar ohne
Migration. `normalize_to_annual()` liefert für `"einmalig"` bewusst `0` -- kein laufender
Beitrag zur wiederkehrenden Summe, der Posten selbst bleibt trotzdem in `list_costs()`/der
Oberfläche sichtbar, kein Sonderfall, der ihn ausblendet (siehe
`test_normalize_to_annual_einmalig_is_zero_but_model_accepts_the_value`). **Das Modell steht
einmaligen Kosten nicht im Weg** -- eine eigene Erfassungsoberfläche dafür (z. B. ohne
Kündigungsfrist-Felder, die für einen einmaligen Posten keinen Sinn ergeben) ist NICHT Teil
dieser Version, bleibt aber eine kleine, spätere Erweiterung, keine Baustelle.

### Kündigungsfrist: reine Ableitung, keine gespeicherte Spalte

`app/recurring_costs.py::cancellation_deadline(contract_end_date, notice_period_months)` = 
`add_months(contract_end_date, -notice_period_months)` (`app/date_utils.py`, negatives Vorzeichen
-- dieselbe, bereits bestehende Funktion, wiederverwendet statt einer eigenen Rückwärtsrechnung).
Bewusst NICHT gespeichert (anders als `OperationalAssetInspection.next_due_date`, das ein
"zuletzt tatsächliches Datum" bräuchte, um korrekt fortzuschreiben) -- hier gibt es kein solches
Zwischenereignis, die Frist ergibt sich vollständig und stabil aus zwei bereits gespeicherten
Feldern, ändert sich nur durch eine bewusste Vertragsänderung. `is_cancellation_due()`/
`is_cancellation_overdue()` -- dasselbe, bereits etablierte Zwei-Stufen-Muster wie bei den
Betriebsmittel-Prüffristen (`is_inspection_due()`/`is_inspection_overdue()`, 1.4.0), eigene,
unabhängige `RecurringCostSettings.reminder_lead_days` (Singleton wie `OperationalAssetSettings`,
Default 30 Tage) -- kein gemeinsamer Datensatz mit einem anderen Modul.

### Kündigungsfrist-Aufgabe: `Task.min_visible_role`, die allgemeine Erweiterung

Siehe Abschnitt "Aufgabe" -> "Ziel-Mindestrolle für empfängerlose Aufgaben" oben für die volle
Herleitung des neuen, allgemeinen `Task.min_visible_role`-Felds -- hier nur der konkrete
Anwendungsfall: `check_due_cancellations_and_create_reminders()` (On-Demand wie
`check_due_asset_inspections_and_create_reminders()`, 1.4.2 -- läuft nur beim Aufruf von
`/betriebskosten`, kein Hintergrundjob) erzeugt eine Aufgabe MIT
`min_visible_role=ROLE_OFFICE_FINANZEN`, NICHT unassigned "ans ganze Büro" wie bei den
Betriebsmittel-Prüffristen -- eine Kündigungsfrist geht nur Finanzen/Admin etwas an, nicht die
Auftragsbearbeitung (Nutzervorgabe, wörtlich). `last_reminder_due_date` ist derselbe
Idempotenz-Stempel wie bei `OperationalAssetInspection`, ohne expliziten Reset -- ändert sich die
berechnete Frist (Vertragsänderung), unterscheidet sie sich automatisch vom alten Stempel.

### Dokumentenablage und Optionsgruppen

`RecurringCostDocument` (Muster `OperationalAssetDocument`, 1.4.2) -- mehrere unabhängige
Dateien je Kostenposten, `document_type` aus der neuen, self-seedenden Optionsgruppe
`recurring_cost_document_types` (`app/option_settings.py`), Löschen räumt die Datei über ein
`before_delete`-Event (`app/recurring_costs.py`) auf, kaskadiert auch beim Löschen des ganzen
Kostenpostens. `app/recurring_cost_documents.py` (eigener Ordner, neue Umgebungsvariable
`DACHKONZEPTE_RECURRING_COST_FILE_ROOT`, `.env.example` ergänzt) trägt bewusst nur das
unabhängige "mehrere Dateien"-Muster (`save_document()`), kein 1:1-Ersetzungsfall wie bei
Betriebsmittel-Prüffristen -- den gibt es hier nicht. Zweite neue Optionsgruppe
`recurring_cost_categories` für die freie Kategorisierung (Miete/Leasing/Versicherung/Software/
Wartungsvertrag/Sonstiges).

### Oberfläche und Einstellungen

`GET /betriebskosten` (`app/routers/pages.py::recurring_costs_page()`, `app/templates/
recurring_costs.html`) -- Summenkarte (Monats-/Jahresbetrag, Kostenposten-Zähler, Zähler der
noch nicht ersetzten Betriebsmittel-Notizen, Kündigungsfristen hervorgehoben mit fällig getrennt
von überfällig ausgewiesen), Anlegen/Bearbeiten-Formular samt Dokumentenablage (erst nach dem
ersten Speichern sichtbar, Muster: ein Dokument braucht eine `recurring_cost_id`), Liste mit
Betriebsmittel-Bezug (Name live über die bereits geladene Assets-Liste aufgelöst) und dem
`asset_quick_cost_hint`-Tooltip. Bewusst `_finanzen_role_dep` (eigene, neue Konstante in
`app/routers/pages.py`, `require_min_role(ROLE_OFFICE_FINANZEN)`) statt des generischen
`_role_dep`/`_any_role_dep` dieser Datei -- die einzige Seite in `pages.py`, die diese engere
Schwelle direkt auf sich selbst trägt (Kalkulationsgrundlagen/Mitarbeiterformular hatten das
zuvor nur über spezielle Helfer).

Sidebar-Link unter Finanzen, aber in einem EIGENEN `{% if %}`-Block, STRENGER gegated als
"Finanzen"/"Mahnwesen" selbst (`is_module_enabled('betriebskosten') and can(current_user,
'admin', 'buero_finanzen')`, kein `buero_auftrag`) -- ein `buero_auftrag`-Konto sieht "Finanzen"/
"Mahnwesen" weiterhin, nur diesen einen neuen Eintrag nicht. Neue Einstellungen-Gruppe
"Betriebskosten" (Vorlaufzeit für Kündigungsfristen) innerhalb desselben, bereits bestehenden
`buero_finanzen`-gegateten Menüblocks wie Kalkulationsgrundlagen/Stundenverrechnungssatz --
`loadRecurringCostsSettingsSection()` wird deshalb (wie die dortigen Felder) nur innerhalb von
`if(canSeeCalculationSettings){...}` in `load()` aufgerufen, nie unbedingt, da die zugehörigen
DOM-Elemente für `buero_auftrag` serverseitig aus dem Markup entfernt sind.

### Angriffstest

`buero_auftrag` und `field` kommen über KEINEN Weg an die Betriebskosten -- geprüft mit einem
rekursiven Schlüssel-Scan und je einem Testkonto pro Rolle
(`tests/test_v283_recurring_costs.py`): die Liste (`GET /api/recurring-costs`), der Einzelabruf,
die Übersicht/Summe (`GET /api/recurring-costs/overview`), Anlegen/Ändern/Löschen, die
Dokumentenablage (Hochladen/Ansehen/Löschen -- auch über eine geratene, gar nicht existierende
Datei-ID, dieselbe 403 wie bei einer echten), die Einstellungen, UND die finanz-adressierte
Erinnerungs-Aufgabe (weder in der Liste noch im gemeinsamen Eingang sichtbar, auch mit bekannter
ID nicht übernehmbar -- 403 statt 400/200). Null durchgelassen. Migration `fc79aa5629d0`
(`recurring_costs`/`recurring_cost_documents`/`recurring_cost_settings` neu, `tasks.
min_visible_role` als neue, nullable Spalte auf der bestehenden Tabelle), 26 neue Tests, volle
Suite: 1558 Tests grün.

### Verrechnungssatz-Kreislauf Schicht 3 (seit 1.5.1)

Vorbereitet durch einen reinen Befund (Punkt 1 der Anfrage: wie `labor_rate.py` den Satz heute
bildet, Prozent-oder-Betrag, fix/variabel getrennt oder nicht, die Umrechnungsformel), danach
sechs Betreiberentscheidungen -- die wichtigste davon (der Begriffskonflikt bei "variabel")
ausdrücklich VOR jedem Bauen der Einordnung/Einspeisung zu klären. Diese Version liefert
ausschließlich die beiden Teile, die der Betreiber selbst als unabhängig vom Konflikt markiert
hat (Produktivstunden-Rechner, `overview_summary()`-Erweiterung); die Einspeisung selbst (Schreiben
in `LaborRateOverheadSettings`, Modus-Zwang, Vergleichsansicht) und die endgültigen Einordnungs-
Labels warten auf die Bestätigung des folgenden Vorschlags.

#### Punkt 1 -- Befund: wie `calculate_labor_rate()` den Satz heute bildet

Vier Kostenblöcke, alle im Rückgabe-Dict von `calculate_labor_rate()` (`app/labor_rate.py`)
wiederzufinden: `gross_wages` (Bruttolöhne der direkt zugeordneten Mitarbeiter),
`employer_costs` (`gross_wages * employer_cost_pct/100`), `total_overhead` (=
`fixed_overhead` + `variable_overhead`) und `target_profit_pct` (Aufschlag auf die
Selbstkosten). **Fix/variabel sind bereits heute getrennte Felder**, keine neue Unterscheidung
nötig: `LaborRateOverheadSettings.fixed_overhead_mode/fixed_overhead_value` und
`.variable_overhead_mode/variable_overhead_value`, jedes Feld unabhängig als `"eur"` (absoluter
Jahresbetrag) oder `"pct"` (Prozent der direkten Lohnkosten inkl. AG-Nebenkosten) pflegbar --
reale Werte in der Datenbank: `fixed_overhead_value=73500` (Modus `"eur"`),
`variable_overhead_value=150000` (Modus `"eur"`).

**Die zentrale Zusammensetzung, die den Begriffskonflikt auslöst**: `variable_overhead` wird
NICHT nur aus dem gepflegten `variable_overhead_value` gebildet, sondern als
`manual_variable_overhead + variable_employee_costs` -- `variable_employee_costs` ist die Summe
aus Jahresbrutto + AG-Nebenkosten aller Mitarbeiter mit der Kosten-Zuordnung
`allocation_type="variable_overhead"` (`EmployeeCostAllocationSettings`, siehe
`effective_cost_allocation()` in `app/employees.py`) -- in der Praxis die Verwaltungslöhne
(Büro, Geschäftsführung), automatisch zum manuell gepflegten Betrag addiert.

**Produktive Jahresstunden** (`annual_productive_hours`) = `paid_hours * productive_time_pct /
100`, wobei `paid_hours` bereits die AGGREGIERTE Summe über alle direkt zugeordneten Mitarbeiter
ist (Wochenstunden × `weeks_per_year`, summiert). **Keine detaillierte Herleitung existiert
heute** -- `productive_time_pct` ist ein einzelner, pauschal gepflegter Prozentsatz (realer
Wert in der Datenbank: 95 %, eine reine Schätzung ohne Bezug zu Urlaub/Krankheit/Feiertagen) --
genau die Lücke, die der neue Produktivstunden-Rechner schließt.

#### Punkt 1 -- die Frage des Betreibers: ist die Vermischung fachlich richtig oder falsch?

Wörtlich: "Wenn ein Betriebskostenposten als 'variabel' (im Auslastungs-Sinn) eingeordnet wird
und in `variable_overhead_value` fließt, vermischt er sich dort mit den automatisch addierten
Verwaltungslöhnen (`variable_employee_costs`). Ist das fachlich richtig oder falsch?"

**Antwort**: rechnerisch harmlos, terminologisch riskant. Rechnerisch, weil Addition vor der
abschließenden Division durch die produktiven Stunden assoziativ ist -- ob ein Auslastungs-
Posten in `variable_overhead_value` oder in einem dritten, separaten Feld steht, ändert am
Ergebnis (`suggested_labor_rate`) nichts, solange am Ende alles in `total_overhead` zusammenläuft
(was ohnehin passiert). Terminologisch riskant, weil zwei fachlich verschiedene Bedeutungen von
"variabel" denselben Codenamen tragen: BWL-Sinn (steigt mit der Auslastung -- Diesel,
Verschleiß, Entsorgung) vs. Code-Sinn (Verwaltungslöhne, die nichts mit Auslastung zu tun haben,
nur mit einer Kosten-Zuordnungsentscheidung je Mitarbeiter). Verschärft dadurch, dass in DIESEM
System kein einziger Kostenposten -- fix oder variabel im BWL-Sinn -- tatsächlich dynamisch mit
der realisierten Auslastung mitläuft: jeder `RecurringCost` ist ein statischer Jahresbetrag,
unabhängig von der Klassifikation. Der Betreiber (und jeder spätere Bediener) könnte deshalb
leicht annehmen, "Auslastungsabhängige Kosten" würden sich im Verrechnungssatz automatisch nach
der tatsächlichen Auslastung richten -- das tun sie nicht, sie werden nur einmalig addiert.

#### Vorschlag zur Auflösung (noch nicht bestätigt)

1. **Die Betriebskosten-Einordnung vermeidet das Wort "variabel" bewusst** -- Werte `"fix"`/
   `"auslastungsabhaengig"`/`"keine"` statt `"fix"`/`"variabel"`/`"keine"`. Label
   "Auslastungsabhängige Kosten (z. B. Kraftstoff, Verschleiß, Entsorgung)" macht die
   BWL-Bedeutung explizit, ohne den Code-Bucket-Namen zu wiederholen.
2. **Die Kern-Felder `variable_overhead_mode`/`variable_overhead_value`
   (`LaborRateOverheadSettings`) werden NICHT umbenannt** -- eine minimale, risikoarme Änderung:
   Umbenennen würde jeden bestehenden Aufrufer/Test/jede Spalte anfassen, für einen Bucket, der
   inhaltlich unverändert bleibt (weiterhin manuelle Kosten + automatisch addierte
   Verwaltungslöhne).
3. **Transparenz statt Umbenennung**: beim Einspeisen (Schicht 3, noch nicht gebaut) zeigt die
   Vergleichsansicht einen Hinweis, dass die Summe der "auslastungsabhaengig" klassifizierten
   Posten mit den automatisch berechneten Verwaltungslöhnen zusammen in `variable_overhead_value`
   einfließt -- der Bediener sieht die Vermischung, statt dass sie stillschweigend passiert.
4. **CLAUDE.md dokumentiert die Begriffsunterscheidung** (dieser Abschnitt) als dauerhafte
   Referenz, damit ein künftiger Bearbeiter nicht erneut über dieselbe Verwechslung stolpert.

**Zum Zeitpunkt von 1.5.1 waren diese vier Punkte noch NICHT umgesetzt** -- die Klassifikations-
werte `keine`/`fix`/`auslastungsabhaengig` waren zwar bereits im Code angelegt (siehe unten, für
die `overview_summary()`-Erweiterung), aber ausdrücklich als vorläufig gekennzeichnet. **Seit
1.5.2 bestätigt und vollständig umgesetzt** -- siehe Unterabschnitt "Die Einspeisung (seit
1.5.2)" unten für alle vier Punkte inkl. Punkt 3 (Vergleichsansicht mit Pflicht-Hinweis).

#### Produktivstunden-Rechner (`app/productive_hours.py`)

Neue Singleton-Tabelle `ProductiveHoursSettings` (`weekly_hours`/`daily_hours`/`vacation_days`/
`public_holidays`/`average_sick_days`/`weather_loss_days`/`unproductive_time_pct`, alle mit
Standardwerten für einen typischen Dachdeckerbetrieb: 40h/8h/30/10/10/5/15 %, ergibt bei 52
Wochen/Jahr rund 67 % statt der bisherigen, pauschal geschätzten 95 %). `calculate_productive_hours()`
ist eine reine Funktion (Settings + `weeks_per_year` → Dict mit jedem Zwischenschritt): Bruttojahres-
stunden (`weekly_hours * weeks_per_year`) minus Urlaub/Feiertage/Ø Krankheit/Schlechtwetter (je in
Tagen × `daily_hours`) minus unproduktive Zeit (Prozentsatz der verbleibenden Stunden) = produktive
Jahresstunden, daraus ein Prozentsatz der Bruttojahresstunden.

**`weeks_per_year` kommt bewusst aus `LaborRateSettings`, kein eigenes Feld** -- exakt die vom
Betreiber selbst gezogene Lehre aus den drei divergierenden `build_customer_and_meta_block()`-
Kopien ("eine Quelle, ein Wert"): ändert sich `weeks_per_year` im Stundensatz-Rechner, zieht der
Produktivstunden-Rechner beim nächsten Lesezugriff automatisch nach, keine zweite, potenziell
abweichende Zahl.

**Schreibt nur nach bewusstem Klick**: `apply_productive_hours_to_labor_rate()` (Muster
`apply_labor_rate_calculation()`, Router `app/routers/labor_rate.py`) überschreibt
AUSSCHLIESSLICH `LaborRateSettings.productive_time_pct` -- kein anderes Feld, kein Automatismus.
`calculate_labor_rate()` selbst ist an keiner Stelle geändert; es liest weiterhin nur
`productive_time_pct`, ohne zu wissen, wie dieser Wert entstanden ist -- **keine zweite,
parallele Formel für dieselbe Zahl** (die andere, vom Betreiber selbst benannte Lehre aus den
drei `build_customer_and_meta_block()`-Kopien).

Neue Endpunkte `GET/PUT /api/productive-hours-settings` + `POST .../apply` (`app/routers/
labor_rate.py`, co-located mit dem bestehenden Stundensatz-Rechner, dieselbe
`require_min_role(ROLE_OFFICE_FINANZEN)`-Schwelle). Oberfläche: neuer Block direkt unterhalb des
bestehenden Stundenverrechnungssatz-Rechners in Einstellungen → Kalkulationsgrundlagen (`settings.html`,
`settings-labor-rate`-Sektion) -- sieben Eingabefelder, ein Rechenweg-Ergebnis (Muster
`renderLaborRate()`) und ein "Übernehmen"-Knopf, der zusätzlich das Feld "Produktive Zeit %" oben
UND die Stundensatz-Berechnung selbst aktualisiert (`refreshLaborRate()`).

Die spätere, in der Anfrage bereits vorgemerkte Ist-Wert-Verfeinerung aus
`TimeEntry.counts_as_productive` (echte Buchungen statt Annahmen) ist bewusst NICHT Teil dieser
Version -- nur hier als künftiger Punkt vermerkt, wie verlangt.

#### `overview_summary()`-Erweiterung (`app/recurring_costs.py`)

Neue, indizierte Spalte `RecurringCost.overhead_classification` (String, `server_default='keine'`
nach Regel 1) -- fester Code-Wert (`OVERHEAD_CLASSIFICATIONS = ("keine", "fix",
"auslastungsabhaengig")`) wie `billing_interval`, keine Optionsgruppe: die Einordnung bestimmt
eine künftige Rechenregel (welcher Gemeinkosten-Bucket gespeist wird), keine freie Anzeigeliste.
"keine" ist der restriktive Default -- ein Posten fließt erst nach bewusster Einordnung in eine
der beiden Summen ein.

`overview_summary()` liefert zusätzlich zur unveränderten `annual_total` (weiterhin die Summe
ALLER aktiven Posten, für die bestehende Anzeige) drei getrennte Jahressummen:
`annual_fixed_from_costs`, `annual_usage_dependent_from_costs`, `annual_none_from_costs` --
Summe der drei Gruppen ergibt exakt `annual_total`. `recurring_costs.html` zeigt sie als
zusätzliche Kennzahlen-Kacheln unterhalb der bestehenden Summenkarte, das Anlegen-/Bearbeiten-
Formular bekommt ein neues Auswahlfeld ("Kalkulatorische Einordnung"), die Kostenliste eine neue
Spalte -- zum Zeitpunkt von 1.5.1 trug jede dieser drei Stellen einen sichtbaren Hinweis
"vorläufige Bezeichnung, siehe Bericht zu Punkt 1", damit niemand die Werte für final hielt,
bevor der Vorschlag oben bestätigt war. **Seit 1.5.2 entfernt** -- die Einordnung ist bestätigt,
siehe unten.

Migration `57062a31dba7` (neue Spalte `recurring_costs.overhead_classification` PLUS neue Tabelle
`productive_hours_settings`), 15 neue Tests (`tests/test_v284_productive_hours_and_overhead_classification.py`),
volle Suite: 1573 Tests grün.

#### Die Einspeisung (seit 1.5.2)

Fortsetzung von 1.5.1, nach der Betreiber-Bestätigung des oben stehenden Vorschlags zu Punkt 1 --
wörtlich: "Der Vorschlag zu Punkt 1 ist richtig, bau ihn so. [...] Die Code-Felder
`variable_overhead_*` bleiben unangetastet, wie du sagst -- kein Umbenennen eines inhaltlich
unveränderten Buckets." Damit sind die vier Vorschlagspunkte oben final:

- `OVERHEAD_CLASSIFICATIONS`/`OVERHEAD_CLASSIFICATION_LABELS` (`app/recurring_costs.py`) sind
  nicht mehr "vorläufig" -- der Erklärtext bei `"auslastungsabhaengig"` lautet jetzt "z. B.
  Kraftstoff, Verschleiß, Entsorgung -- fließt zusammen mit den Verwaltungslöhnen in den
  variablen Gemeinkosten-Bucket", exakt wie vom Betreiber vorgegeben. Alle "vorläufig"/
  "siehe Bericht zu Punkt 1"-Marker sind aus `recurring_costs.html` entfernt (Metrik-Zeile,
  `editClassification`-Feldlabel, das `auslastungsabhaengig`-`<option>`).
- `LaborRateOverheadSettings.variable_overhead_mode`/`.variable_overhead_value` bleiben
  wortwörtlich unverändert -- kein Umbenennen, keine Migration.

Danach die Einspeisung selbst, nach fünf vom Betreiber vorgegebenen Punkten:

**Punkt 1 -- der Pflicht-Hinweis in der Vergleichsansicht.** `recurring_cost_overhead_proposal()`
(neu, `app/labor_rate.py`) baut eine reine Vorschau -- schreibt nichts -- und zeigt getrennt:
"Auslastungsabhängige Betriebskosten: X. Plus automatisch berechnete Verwaltungslöhne: Y. Ergibt
variable Gemeinkosten: X+Y.", sowohl für "aktuell" (die tatsächlich hinterlegten
`LaborRateOverheadSettings`-Werte) als auch für "Vorschlag" (die Summen aus
`overview_summary()["annual_fixed_from_costs"]`/`["annual_usage_dependent_from_costs"]`). Ohne
diesen Hinweis würde ein Betreiber sich wundern, warum der "variable" Gemeinkostenwert höher ist
als die Summe seiner auslastungsabhängigen Posten -- X, Y und X+Y stehen jetzt einzeln da.

**Punkt 2 -- Modus-Zwang, keine stille Semantikänderung.** `apply_recurring_cost_overhead_proposal()`
(neu, `app/labor_rate.py`) setzt `fixed_overhead_mode`/`variable_overhead_mode` IMMER auf `"eur"`
-- unabhängig davon, welcher Modus vorher galt. Das ist eine echte Bedeutungsänderung eines
Feldes (Prozent der Lohnkosten vs. absoluter Jahresbetrag), nicht nur ein neuer Wert -- die
Warnung dafür sitzt bewusst im FRONTEND, vor dem Aufruf (`settings.html::
applyOverheadProposal()`, `confirm()`-Dialog, Regel 4: kein `prompt()`, `confirm()` für
Ja/Nein-Bestätigungen ist etabliert), nicht in der Business-Funktion selbst -- die schreibt
unbedingt, sobald sie aufgerufen wird. Der Dialogtext benennt explizit, welches der beiden Felder
(falls überhaupt eines) vom bisherigen Prozent-Modus betroffen wäre.

**Punkt 3 -- die dreistufige Aufschlüsselung.** Summe (die beiden Kennzahlen-Kacheln oben) → fix/
auslastungsabhängig getrennt (zwei `.metric`-Kacheln, `renderOverheadProposal()` in
`settings.html`) → einzelne Posten aufklappbar (natives HTML `<details>`/`<summary>`, `ocpItemsHtml()`,
gespeist aus `proposal["fixed_costs"]`/`["usage_dependent_costs"]` -- denselben Listen, die
`recurring_cost_overhead_proposal()` über `list_costs(db, include_inactive=False)` gefiltert nach
Klassifikation liefert, "keine" und inaktive Posten bleiben draußen). Gegenüberstellung Vorschlag
gegen aktuell für beide Buckets getrennt, wie oben in Punkt 1 beschrieben.

**Punkt 4 -- eine Formel, eine Quelle.** `calculate_labor_rate()` bekommt einen neuen,
KEYWORD-ONLY-Parameter `overhead_override: dict | None = None` (Default bewahrt exakt das
bisherige Verhalten für jeden bestehenden Aufrufer, keine Signaturänderung an bestehenden
Aufrufstellen nötig). Ist er gesetzt, ersetzt er `fixed_overhead_mode`/`fixed_overhead_value`/
`variable_overhead_mode`/`variable_overhead_value` rein IN-MEMORY für genau diesen einen Aufruf --
die Datenbank wird nicht gelesen verändert, `get_or_create_overhead_settings()` liefert danach
unverändert den alten Stand. `recurring_cost_overhead_proposal()` ruft `calculate_labor_rate()`
deshalb ZWEIMAL auf (einmal unverändert für "aktuell", einmal mit dem Vorschlag als Override für
"Vorschlag") statt selbst eine zweite Kopie der Formel zu pflegen -- `annual_productive_hours`
UND jede andere im Ergebnis-Dict stehende Größe kommen für beide Zustände aus exakt demselben
Code, kein zweiter, hier nachgebauter Rechenweg (das ist die im Punkt-1-Befund selbst gezogene
Lehre, hier konkret angewendet).

**Punkt 5 -- zweistufig, zwei getrennte Knöpfe.** Der neue Knopf "Betriebskosten-Vorschlag
übernehmen" (Schritt 1, `settings.html::applyOverheadProposal()`,
`POST /api/recurring-cost-overhead-proposal/apply`) speist AUSSCHLIESSLICH die beiden
Gemeinkosten-Felder (`fixed_overhead_mode`/`fixed_overhead_value`/`variable_overhead_mode`/
`variable_overhead_value`, plus das Legacy-Spiegelfeld `LaborRateSettings.annual_overhead` im
Gleichschritt mit `fixed_overhead_value` -- dasselbe Muster wie beim bestehenden
`PUT /api/labor-rate-settings`). Er rührt `CalculationSettings.labor_rate` NICHT an. Der
bestehende Knopf "Als aktuellen Verrechnungssatz übernehmen" (Schritt 2,
`apply_labor_rate_calculation()`, unverändert) bleibt der davon getrennte zweite Schritt -- kein
Knopf erledigt beide Schritte in einem.

**Router**: `GET /api/recurring-cost-overhead-proposal` (reine Vorschau) und
`POST /api/recurring-cost-overhead-proposal/apply` (Schritt 1, gibt danach dieselbe Vorschau-
Struktur mit dem neuen Stand zurück), beide co-located im bestehenden `labor_rate`-Router,
dieselbe `require_min_role(ROLE_OFFICE_FINANZEN)`-Schwelle wie der übrige Stundensatz-Rechner
und der Produktivstunden-Rechner. Neue Schemas `OverheadProposalStateOut`/
`RecurringCostOverheadProposalItemOut`/`RecurringCostOverheadProposalOut` (`app/schemas.py`).

**Kein neues Datenmodell, keine Migration** -- die Einspeisung schreibt ausschließlich in bereits
bestehende `LaborRateOverheadSettings`-Spalten, `overhead_override` ist ein reiner
Funktionsparameter ohne Persistenz.

**Oberfläche**: neuer Block "Betriebskosten-Vorschlag für die Gemeinkosten" direkt unterhalb des
Produktivstunden-Rechners in Einstellungen → Kalkulationsgrundlagen (`settings.html`,
`settings-labor-rate`-Sektion) -- `loadOverheadProposalSection()` lädt beim Öffnen der Seite,
`renderOverheadProposal()` baut die beiden Bucket-Kacheln inkl. der aufklappbaren Postenlisten
und der Vorschau, wie sich `suggested_labor_rate` durch die Übernahme ändern würde (rein
informativ, ändert nichts, solange Schritt 2 nicht separat ausgeführt wird).

**Abschließender Angriffstest, wie vom Betreiber verlangt**: `buero_auftrag` und `field` kommen
über KEINEN Teil des Kreislaufs -- weder an die Einordnung (`POST /api/recurring-costs` mit
`overhead_classification`), noch an die Vergleichsansicht (`GET .../recurring-cost-overhead-proposal`),
noch an den Übernehmen-Knopf (`POST .../apply`), noch an den Produktivstunden-Rechner
(`GET/POST /api/productive-hours-settings*`) -- alles ausschließlich `buero_finanzen`/`admin`.
Per rekursivem Schlüssel-Scan bestätigt (kein Kalkulationsfeld wie `suggested_labor_rate`/
`fixed_overhead_annual`/`variable_employee_costs` taucht in einer 403-Antwort auf), ein
Testkonto je Rolle (`router_test_client(db, ..., role=...)`, `ALL_ROLES = ("field",
"buero_auftrag", "buero_finanzen", "admin")`). Null "durchgelassen".

9 neue Tests (`tests/test_v285_recurring_cost_overhead_proposal.py`), volle Suite: 1582 Tests
grün.

## Neugestaltung der Seite Stundenverrechnungssatz (seit 1.5.10)

Umbau von Einstellungen → Kalkulationsgrundlagen → Stundenverrechnungssatz (`app/templates/
settings.html`, `id="settings-labor-rate"`) -- erst ein reiner Befund + Vorschlag (keine
Codeänderung, drei Berichtspunkte), dann nach Bestätigung des Betreibers mit drei präzisierenden
Entscheidungen gebaut. Reine Oberflächenänderung -- kein Endpunkt, kein Schema, keine
Business-Logik geändert.

**Befund (Kurzfassung, vollständig als Text an den Betreiber geliefert)**: die Seite bündelte
DREI eng verzahnte Blöcke (Stundenkostenverrechnungssatz mit 19 Kacheln, Produktivstunden-
Rechner mit 9 Kacheln, Betriebskosten-Vorschlag) in einer Section, nur durch `<hr>` getrennt --
nicht zwei, wie ursprünglich angenommen. Beide unteren Blöcke schreiben beim Klick auf ihren
jeweiligen "Übernehmen"-Knopf sofort in die oberen Felder und lösen sofort ein sichtbares
Neu-Rechnen aus (`refreshLaborRate()`) -- ein Argument für "eine Seite statt Reiter", da ein
Reiterwechsel die gerade erzeugte Bestätigung verstecken würde. Vorschlag: eine Seite (kein
Reiter), drei Zonen (Eingaben / prominentes Ergebnis / aufklappbarer Rechenweg), lange
Fließtextblöcke aus der Fläche.

**Die drei Entscheidungen des Betreibers, umgesetzt:**

1. **Eine Seite, kein Reiter -- bestätigt.** Zusätzlich: der Produktivstunden-Rechner sitzt
   nicht mehr als eigenständiger Block weiter unten, sondern als aufklappbarer Bereich
   ("Produktive Zeit % herleiten (Produktivstunden-Rechner)") **direkt am Feld, das er speist**
   -- räumlich gelöst über CSS-Grid-Platzierung: das `<details class="calc-subsection"
   style="grid-column:1/-1">`-Element steht im DOM direkt nach dem Feld "Produktive Zeit %"
   innerhalb derselben `.rate-grid` (`grid-template-columns:repeat(5,...)`) -- ein
   vollbreites Grid-Item kann in der aktuellen Zeile nicht mehr Platz finden (Spalte 1 ist durch
   das vorherige Feld bereits belegt) und bricht deshalb zuverlässig in eine eigene, volle Zeile
   genau an dieser Stelle um, ohne dass eine feste `grid-row` nötig wäre -- funktioniert
   identisch im schmalen Einspaltenlayout (`@media(max-width:1000px)`), da dort ohnehin jedes
   Grid-Item in reiner DOM-Reihenfolge untereinandersteht. Derselbe Mechanismus für den
   Betriebskosten-Vorschlag ("Betriebskosten-Vorschlag für die Gemeinkosten anzeigen"), platziert
   direkt nach den beiden Gemeinkosten-Feldern (Fixe/Variable Gemeinkosten Wert), die er speist.
   Beide Bereiche starten geschlossen (`<details>` ohne `open`-Attribut, "nur gelegentlich
   gebraucht") -- laden ihre Daten aber unverändert unbedingt beim Seitenaufruf
   (`loadProductiveHoursSection()`/`loadOverheadProposalSection()` bleiben Teil des ungeänderten
   `load()`-Ablaufs, seit 1.5.1/1.5.2) -- nur die Sichtbarkeit ist neu, nicht der Ladezeitpunkt.
2. **Drei-Zonen-Gliederung.** Neue `.zone-label`-Beschriftung ("Eingaben"/"Ergebnis") über den
   jeweiligen Bereichen. Von den bisherigen 19 Kacheln des oberen Rechners (`renderLaborRate()`)
   bleiben **vier** immer sichtbar (neuer Container `#laborRateBasics`, `.rate-result`-Grid):
   Gewichteter Mittellohn, Produktive Jahresstunden, Selbstkosten/h, Ermittelter Satz. **Zwei**
   (Aktueller Satz, Abweichung) wandern in die prominente Ergebnisanzeige (`#laborRateApply`)
   direkt neben die große Satz-Zahl ("Aktuell hinterlegt: X €/h · Abweichung: Y €") -- bewusst
   gebündelt, da eine Abweichung ohne ihren Bezugswert nicht lesbar ist. **Eine** (Direkte
   Mitarbeiter) wird zur sichtbaren Zusatzangabe direkt in der Mittellohn-Kachel
   (`<div class="muted small">N Mitarbeiter</div>`) statt einer eigenen Kachel -- die Zahl bleibt
   damit ohne Hover sichtbar, nur ohne eigene Kachel. Die verbleibenden **13** (Mitarbeiter
   variable GK, Direkte Jahresbruttolöhne, AG-Nebenkosten direkt, Direkte Lohnkosten gesamt,
   Lohnkosten/produktive h, Fixe GK/Jahr, Fixe GK/produktive h, Variable MA-Kosten/Jahr,
   Zusätzliche variable GK/Jahr, Variable GK gesamt/Jahr, Variable GK/produktive h, GK gesamt/
   produktive h, Wagnis & Gewinn/h) stehen **vollständig**, nur zugeklappt, unter
   `#laborRateDetailsPanel` ("Rechenweg im Detail") -- per echtem Browsertest nachgewiesen
   (`document.querySelectorAll('#laborRateResult .metric').length === 13`, unverändert sowohl im
   zugeklappten als auch im aufgeklappten Zustand -- `<details>` entfernt seinen Inhalt nie aus
   dem DOM, blendet ihn nur aus). Der `!r.can_calculate`-Zustand ("Berechnung noch nicht
   möglich") zeigt sich jetzt prominent in der Ergebniszone statt versteckt in den (dann leeren)
   Detailkacheln.
3. **Erklärtext aus der Fläche.** Die beiden langen `.hint`/`.formula`-Blöcke des oberen Rechners
   (Mittellohn-Gewichtung inkl. Link zu Stammdaten → Mitarbeiter, vollständiger Rechenweg)
   wandern unverändert in `#laborRateDetailsPanel`, vor die 13 Kacheln. Die beiden Erklärblöcke
   der Unterrechner wandern mit diesen in deren jeweils eigenen Aufklapp-Bereich. **Geprüft, ob
   ein Fragezeichen-Tooltip sauberer ist als ein Textblock**: ja, für zwei kurze, linkfreie
   Erklärungen, die vorher GAR KEINE Erklärung hatten -- neue `.info-ico`-CSS-Klasse (kleines
   rundes "?", reines `title`-Attribut, keine neue JS-Logik, `cursor:help`) an "Wochen pro Jahr"
   (verweist auf dieselbe Quelle wie der Produktivstunden-Rechner -- "eine Quelle, kein zweites
   Feld", das bereits mehrfach im Projekt etablierte Prinzip) und an "Gewichteter Mittellohn"
   (Gewichtungserklärung). Ein natives `title`-Attribut kann jedoch **keine Links** tragen --
   Erklärungen mit Link (Stammdaten-Verweis) bleiben deshalb bewusst ein echter `.hint`-Block,
   wandern aber ebenfalls in den aufklappbaren Bereich statt in der Fläche zu stehen.

**Nichts geht verloren, wie gefordert**: alle 19 Kacheln, alle 9 Produktivstunden-Kacheln, die
komplette Betriebskosten-Vorschlags-Aufschlüsselung, alle Eingabefelder samt ihrer Schrittweiten
(1.5.9, unverändert) und beide Übernehmen-Abläufe (Produktivstunden-Vorschlag übernehmen → Satz
übernehmen, zwei bewusste Schritte) bleiben vollständig funktionsfähig -- nur ihre Anordnung/
Sichtbarkeit hat sich geändert.

**Alle Text-Referenzen auf "oben"/"unten" wurden an die neue räumliche Anordnung angepasst** --
insbesondere der Betriebskosten-Vorschlag-Hinweistext (der Knopf "Als aktuellen
Verrechnungssatz übernehmen" sitzt jetzt UNTERHALB der Eingaben-Zone, nicht mehr darüber) und die
beiden zugehörigen JS-Statusmeldungen nach dessen Übernahme (`renderOverheadProposal()`/
`applyOverheadProposal()`).

**Unabhängiger, vorbestehender Fund, nicht nur gemeldet, sondern behoben**: beim ersten echten
Browsertest (siehe unten) warf `loadRecurringCostsSettingsSection()` (Betriebskosten-**Modul**-
Einstellungen unter Einstellungen → System -- ein komplett anderer Abschnitt, mit dem
Verrechnungssatz-Umbau inhaltlich nicht verwandt) einen `ReferenceError: moduleStates is not
defined` in der Browser-Konsole. Ursache, per `git diff` bestätigt UNABHÄNGIG von diesem Umbau
bereits vorher so im Code: `load()` ruft `loadRecurringCostsSettingsSection()` innerhalb des
`if(canSeeCalculationSettings){...}`-Blocks auf, an einer Stelle VOR der Zeile, die `moduleStates`
zum allerersten Mal zuweist (`moduleStates=ms;` stand bisher erst später im selben `load()`, ohne
vorheriges `let`/`var` -- die Variable existiert vorher als Binding schlicht nicht). Blieb
unbemerkt, weil die Funktion ohne `await`/`.catch()` aufgerufen wird -- eine daraus resultierende
Promise-Ablehnung ("Uncaught (in promise)") stört die übrige Seite nicht sichtbar, nur die
Konsole. Behoben durch Vorziehen der `moduleStates=ms;`-Zuweisung vor den `if`-Block (ein
zusätzliches `renderModuleStates()` an der alten Stelle bleibt bestehen, harmlos redundant).

**Rollen-Check unverändert**: `{% if can(current_user, 'admin', 'buero_finanzen') %}`
(`app/templates/settings.html`) umschließt die Section nach wie vor, unverändert an derselben
Stelle -- per `git diff` UND per rekursivem Grep bestätigt, dass der Umbau daran nichts geändert
hat.

**Verifiziert**: vollständiger `pytest`-Lauf (1668 Tests) grün; `node --check` gegen den
extrahierten Skriptblock (Jinja-Platzhalter `canSeeCalculationSettings` vorher neutralisiert,
Muster aus früheren Sitzungen). Zusätzlich ein echter, CDP-gesteuerter Headless-Chrome-Durchlauf
gegen eine isolierte, temporäre SQLite-Instanz (Bootstrap-Admin, Zwei-Faktor-Ersteinrichtung mit
`pyotp`, ein Testmitarbeiter für einen berechenbaren Fall -- niemals gegen `dachkonzepte_erp.db`):
beide `<details>`-Bereiche öffnen/schließen sich per Klick auf `<summary>` (`.open`-Property
bestätigt), der Euro/Prozent-Umschalter der Gemeinkosten-Felder wechselt Label UND Schrittweite
weiterhin korrekt (`syncOverheadLabels()` unverändert wiederverwendet, `100`↔`0.5` bestätigt),
und der komplette Zwei-Schritt-Ablauf läuft Ende-zu-Ende durch: "Übernehmen" (Produktivstunden)
setzt `productiveTimePct` sichtbar von 70,00 auf 67,02 %, die Satzanzeige aktualisiert sich sofort
(44,64 → 46,63 €/h); "Als aktuellen Verrechnungssatz übernehmen" schreibt danach den Satz ins
Kalkulationsgrundlagen-Feld und die Abweichungsanzeige geht auf 0,00 € zurück. Browser-Konsole
nach der `moduleStates`-Behebung ohne jede Meldung, auch kein einziges JS-Fehler-Log während des
gesamten Durchlaufs.


## Netto und Brutto bei den Betriebskosten (seit 1.5.5)

Nachbesserung an der Betriebskosten-Übersicht (Schicht 1, siehe "Betriebskosten-Übersicht" oben)
-- unabhängig von der Krankheitssichtbarkeit dieser Version, ein eigener, kleiner Auftrag.

**Befund vor dem Bauen**: das bestehende `RecurringCost.amount`-Feld trug keine Steuersemantik --
weder das Modell noch `normalize_to_annual()` kannten einen Steuersatz, der Betrag war einfach
"der Betrag". 0 Bestandszeilen in der echten Datenbank (erneut frisch geprüft) -- eine Migration
war damit für Bestandsdaten folgenlos, aber die Frage "ist der alte Wert netto oder brutto
gemeint" musste trotzdem inhaltlich entschieden werden: `annual_amount` speist direkt in den
Verrechnungssatz-Kreislauf (Schicht 3), und ein Aufwand für die Kalkulation ist wirtschaftlich
immer der Netto-Betrag -- die Vorsteuer ist ein durchlaufender Posten, kein Aufwand. Der
Altbestand wird deshalb rückwirkend als "war schon immer netto gemeint" behandelt, die einzig
konsistente Lesart.

**Umsetzung**: echte Spalten-Umbenennung `amount` -> `net_amount` (kein Drop+Add -- ein
add/drop hätte für eine Installation MIT Bestandsdaten den alten Betrag ersatzlos verworfen, ein
`alter_column()` bewahrt ihn, hier folgenlos bei 0 Zeilen, aber die korrekte Wahl unabhängig
davon). Neue Spalte `tax_rate_pct` (`Numeric(5,2)`, `server_default='19.00'`, Regel 1 beachtet)
-- fester Code-Wert wie `billing_interval`/`overhead_classification` (`TAX_RATES = (19.00, 7.00,
0.00)` in `app/recurring_costs.py`, keine Optionsgruppe: der Satz bestimmt eine Rechenregel für
`gross_amount`, keine freie Anzeigeliste), **je Posten, kein globaler Wert** -- eine
Versicherung mit 0 % und ein Steuerberater-Honorar mit 19 % stehen nebeneinander. Neue Funktion
`gross_amount(net_amount, tax_rate_pct)` -- reine Anzeige-Ableitung wie
`cancellation_deadline()` (selbe Datei), **nie gespeichert, nie Rechenbasis für
`annual_amount`**.

**`overview_summary()` und die Gemeinkosten-Einspeisung aus Schicht 3 (`app/labor_rate.py::
recurring_cost_overhead_proposal()`) mussten NICHT geändert werden** -- beide lesen
ausschließlich das bereits gespeicherte `annual_amount` (über `RecurringCost`-ORM-Objekte bzw.
`cost_to_dict()`s `"annual_amount"`-Schlüssel), niemals `net_amount`/`amount` direkt. Da
`_payload_fields()` `annual_amount` jetzt ausschließlich aus `net_amount` berechnet
(`normalize_to_annual(net_amount, billing_interval)`, Parameter umbenannt, Formel unverändert),
ist die gesamte nachgelagerte Kette automatisch netto-basiert, ohne einen einzigen weiteren
Codepfad anzufassen -- exakt das erwartete Ergebnis einer bereits vorher etablierten "eine
Quelle, keine zweite Berechnung"-Architektur. Ein Korrektheitstest belegt das explizit
(`test_annual_amount_is_computed_from_net_not_gross`): zwei identische Netto-Beträge mit
unterschiedlichem Steuersatz (0 % und 19 %) ergeben denselben `annual_amount` -- wäre die
Rechnung brutto, kämen 1200 vs. 1428 EUR/Jahr heraus statt beide Male 1200.

**Oberfläche** (`recurring_costs.html`): "Netto-Betrag"-Feld ersetzt "Betrag", neues
Steuersatz-Dropdown (19 %/7 %/0 %, Vorgabe 19 %), ein `readonly`-Feld "Brutto-Betrag" wird
client-seitig live nachgerechnet (`updateGrossPreview()`, rein informativ -- der Server
berechnet `gross_amount` beim Speichern ohnehin selbst erneut, es wird nie mitgesendet). Die
Kostenliste zeigt beide Beträge in einer Zelle (netto, brutto nur als kleiner Zusatz, wenn der
Steuersatz > 0 % ist).

Migration `9b3600be64af`, 11 neue Tests
(`tests/test_v288_recurring_cost_netto_brutto.py`), drei bestehende Testdateien
(`test_v283_recurring_costs.py`, `test_v284_productive_hours_and_overhead_classification.py`,
`test_v285_recurring_cost_overhead_proposal.py`) auf `net_amount` umgestellt (reine
Umbenennung ihrer Testdaten, keine inhaltliche Änderung). Volle Suite: 1631 Tests grün.

## Betriebsmittel-Kosten fest als Kostenposten (seit 1.5.7)

Nachbesserung an der Betriebskosten-Übersicht (1.5.0) und der Betriebsmittelverwaltung (1.4.0)
-- löst die 1.5.0-Doppelzählungs-Sonderbehandlung vollständig ab. Erst ein reiner Befund
(berichtet, bevor gebaut wurde, siehe Chatverlauf für die vollständige Herleitung), dann nach
Bestätigung der Bau.

### Befund, in Kurzform

`recurring_cost_per_month` war die einzige Betriebsmittel-Kostenquelle, die ANLEGEN nirgends
kannte -- `master_data_form.html::assetForm()` hatte nie ein Feld dafür, nur die Edit-Seite
(`operational_asset.html`). Per direkter, lesender SQLite-Abfrage gegen die echte, lokale
Datenbank bestätigt: **0** `OperationalAsset`-Zeilen trugen einen Wert, **0** `RecurringCost`-
Zeilen existierten überhaupt -- die Migration war für echte Daten damit folgenlos, blieb aber
inhaltlich nötig (jede andere Installation, der künftige Betrieb). Die Doppelzählungs-Logik aus
1.5.0 (`overview_summary()`s `linked_asset_ids`/`assets_with_quick_cost`/
`annual_from_asset_quick_costs`/`asset_quick_cost_count`, `RecurringCostOut.
asset_quick_cost_hint`, `OperationalAssetOut.has_linked_recurring_cost`) wurde damit zu totem
Code, sobald `recurring_cost_per_month` als zweite Quelle verschwindet -- bestätigt und
ersatzlos entfernt.

### Eine Quelle statt zwei

`OperationalAsset.recurring_cost_per_month` entfällt als eigene Spalte (Migration
`eda89bb8082a`). Eine laufende Rate am Betriebsmittel-Formular erzeugt/ändert/entfernt seither
einen echten `RecurringCost` mit dem neuen Flag `RecurringCost.is_asset_quick_entry=True`
(`app/operational_assets.py::sync_asset_recurring_cost()`, die EINE Stelle, die diesen einen
Posten je Betriebsmittel anfasst). `asset_to_dict()` liefert `recurring_cost_per_month` als
API-Feld unverändert weiter -- jetzt aber LIVE aus dem verknüpften quick-entry-Posten gelesen
(zusätzlich `recurring_cost_id`, damit Finanzen/Admin direkt in die Betriebskosten-Übersicht
springen können).

**Mehrere Postens je Betriebsmittel bleiben möglich, ohne Verwechslungsgefahr.**
`RecurringCost.asset_id` trägt weiterhin bewusst KEIN Unique-Constraint (Leasingrate UND
Versicherung für denselben Transporter bleiben zwei unabhängige, über die allgemeine
Betriebskosten-Oberfläche verknüpfte Zeilen) -- `is_asset_quick_entry` markiert ausschließlich
DEN EINEN Posten, den das Betriebsmittel-Formular selbst verwaltet. "Höchstens ein
`is_asset_quick_entry=True`-Posten je `asset_id`" ist eine reine ANWENDUNGS-Invariante
(`sync_asset_recurring_cost()` sucht immer zuerst den bestehenden, bevor ein neuer angelegt
wird) -- bewusst KEIN DB-Constraint dafür, dieselbe Zurückhaltung wie beim ebenfalls fehlenden
Unique-Constraint auf `asset_id` selbst. `overview_summary()` braucht dadurch keine
Doppelzählungs-Ausnahme mehr: jeder aktive Posten (quick-entry oder eigenständig) fließt genau
einmal in `annual_total` ein.

### Nullsetzen der Rate entfernt den Posten -- mit einer geprüften Ausnahme

Betreiberentscheidung: "ein Posten, der nichts zählt, ist ein Widerspruch -- läuft der
Leasingvertrag aus, soll kein Posten mehr da sein. Trägt man später wieder eine Rate ein,
entsteht ein neuer." `sync_asset_recurring_cost(db, asset, net_amount=None)` löscht den
verknüpften Posten deshalb, statt ihn mit `net_amount=0` stehen zu lassen.

**Die verlangte Prüfung, ob dabei Dokumente/ein Vertragspartner verloren gehen könnten**: ein
frisch aus der Betriebsmittel-Rate erzeugter Posten trägt tatsächlich keine -- ABER er ist ein
vollwertiger `RecurringCost` und über die allgemeine Betriebskosten-Oberfläche (`/betriebskosten`)
später frei nachbearbeitbar (Vertragspartner, Notizen, Kategorie, Vertragsende/Kündigungsfrist,
Dokumente). Genau das kann passieren: jemand trägt nachträglich einen Vertragspartner ein oder
lädt die Leasingrechnung hoch, und Monate später wird die Rate am Betriebsmittel auf null
gesetzt. `_quick_entry_carries_extra_data()` prüft deshalb bei jedem Entfernen, ob der Posten
etwas trägt, das die Betriebsmittel-Rate selbst NIE setzt (`vendor`/`notes`/`category`/
`contract_end_date`/`notice_period_months`/Dokumente) -- ist das der Fall, wird NICHT
stillschweigend gelöscht: `LinkedRecurringCostHasDataError` (statt eines gewöhnlichen
`ValueError`, damit der Router es von Geschäftsregelfehlern unterscheiden kann). Der neue
Endpunkt macht daraus **409** mit `document_count`/`vendor` im Detail -- die Oberfläche
(`operational_asset.html::saveRecurringCost()`) zeigt eine `confirm()`-Nachfrage mit genau
diesen Angaben (Regel 4: kein `prompt()`, `confirm()` für Ja/Nein ist etabliert) und sendet bei
Bestätigung erneut mit `force_remove=true`. Wird die Rate nur GEÄNDERT (nicht auf null
gesetzt), greift die Prüfung nie -- sie betrifft ausschließlich das Entfernen, Steuersatz/
Einordnung/Vertragspartner, die zwischenzeitlich über `/betriebskosten` ergänzt wurden, bleiben
bei einer reinen Betragsänderung unberührt.

### Fest gebunden beim Löschen -- über den bestehenden `before_delete`-Weg, nicht mehr

`delete_asset()` (`app/operational_assets.py`) behandelt verknüpfte `RecurringCost`-Zeilen jetzt
zweigleisig: der EINE quick-entry-Posten wird per `db.delete()` entfernt -- NICHT per
Cascade-Relationship (eine `OperationalAsset.recurring_costs`-Relationship mit
`cascade="all, delete-orphan"` hätte, ohne einen einschränkenden `primaryjoin`, versehentlich
auch jeden eigenständig verlinkten Posten mitgerissen; ein zusätzlicher, auf
`is_asset_quick_entry=True` beschränkter `primaryjoin` wäre nötig gewesen, um das zu vermeiden
-- stattdessen eine einfache, explizite Vorab-Schleife in `delete_asset()` selbst, die dieselbe
Absicherung ohne die Overlap-Komplexität zweier Relationships auf demselben Fremdschlüssel
erreicht). `db.delete()` löst dabei zuverlässig das bereits bestehende `before_delete`-Event auf
`RecurringCostDocument` (1.5.0) aus, das dessen Dateien von der Festplatte entfernt --
`RecurringCost.documents` trägt bereits `cascade="all, delete-orphan"`, kein neuer Mechanismus
nötig. JEDER ANDERE, über `/betriebskosten` eigenständig verlinkte Posten (z. B. die
Versicherung desselben Fahrzeugs) bleibt dagegen bestehen -- nur sein `asset_id` wird auf
`NULL` gesetzt (`RecurringCost.asset_id` ist nullable). Ohne dieses Entkoppeln hätte das
anschließende `db.delete(asset)` unter PostgreSQL (das Fremdschlüssel im Gegensatz zur hier
ungeprüften lokalen SQLite-Entwicklungsdatenbank immer durchsetzt) mit einer
Integritätsverletzung abgebrochen -- geprüft, ob SQLite in diesem Projekt `PRAGMA
foreign_keys` überhaupt setzt: nein, `app/database.py` tut das nicht, das Problem wäre lokal
also unbemerkt geblieben, bis es in Produktion aufgetreten wäre.

### Vorgaben für neu erzeugte Posten

Wie vom Betreiber vorgegeben: **19 % Steuersatz, Einordnung "keine Gemeinkosten"** -- restriktiv,
fließt nicht ungefragt in den Verrechnungssatz-Kreislauf (Schicht 3, siehe oben), der Betreiber
ordnet später bewusst zu, was tatsächlich in die Gemeinkosten gehört. `billing_interval` ist
immer `"monatlich"` (dieselbe Normierung wie die abgelöste Spalte). Diese drei Felder sind im
Betriebsmittel-Formular selbst NICHT editierbar -- wer sie ändern will, tut das über die
allgemeine Betriebskosten-Oberfläche, wo der Posten als ganz normale Zeile erscheint (mit einem
kleinen ⓘ-Hinweis, dass er vom Betriebsmittel-Formular verwaltet wird).

### Rechte-Lücke geschlossen, bevor sie entstehen konnte

Die laufende Rate erzeugt einen echten `RecurringCost` -- Betriebskosten sind seit Etappe 2 des
Rechtekonzepts (1.4.8) ausschließlich `buero_finanzen`/`admin` vorbehalten
(`require_min_role(ROLE_OFFICE_FINANZEN)`, `app/routers/recurring_costs.py`). Das
Betriebsmittel-Formular selbst bleibt aber für `buero_auftrag` offen
(`require_min_role(ROLE_OFFICE_AUFTRAG)`, `app/routers/operational_assets.py`) -- Fuhrpark/
Maschinen-Bestand ist ein Auftrags-, kein Finanz-Datensatz. Ohne Gegenmaßnahme hätte
`buero_auftrag` über das für sie offene Betriebsmittel-Formular indirekt einen `RecurringCost`
erzeugen/ändern/löschen können, obwohl der gesamte `/betriebskosten`-Bereich für sie gesperrt
ist -- exakt die Art Lücke, die der abschließend verlangte Angriffstest aufdecken sollte.

Behoben durch einen **eigenen, engeren Endpunkt**: `PUT /api/operational-assets/{asset_id}/
recurring-cost` (`require_min_role(ROLE_OFFICE_FINANZEN)`, GETRENNT vom allgemeinen `PUT
/api/operational-assets/{asset_id}`) ist die einzige Stelle, die `sync_asset_recurring_cost()`
aufruft. `recurring_cost_per_month` ist aus `OperationalAssetCreate`/`-Update` vollständig
entfernt -- ein über den allgemeinen Endpunkt untergeschobener Wert wird von Pydantic schlicht
ignoriert, bewirkt nichts (per Test belegt: `buero_auftrag` sendet ihn, die Antwort zeigt
`recurring_cost_per_month: null`, kein `RecurringCost` entsteht). Clientseitig
(`operational_asset.html`) liest `init()` `GET /api/auth/status` und deaktiviert das Eingabefeld
für jede Rolle unterhalb `buero_finanzen` (`canManageRecurringCost`), mit dem Hinweis "Nur
Finanzen/Admin können diesen Wert ändern." -- `buero_auftrag` sieht die aktuelle Rate weiterhin
(reine Information, unverändert seit jeher öffentlich für Büro-Rollen), kann sie aber nicht mehr
ändern, weder über die Oberfläche noch über einen direkten API-Aufruf.

### Angriffstest

`buero_auftrag` und `field` kommen an keinen Teil der Betriebskosten, auch nicht an den neu
verknüpften Posten (`tests/test_v289_asset_recurring_cost_link.py`) -- geprüft: der neue,
engere Endpunkt liefert für beide Rollen 403; der allgemeine Betriebsmittel-Endpunkt lässt sich
mit einem untergeschobenen Kosten-Feld aufrufen, ohne dass sich am verknüpften `RecurringCost`
etwas ändert; der komplette `/betriebskosten`-Router bleibt gesperrt, auch mit der bekannten
`cost_id` (kein 404-vs-403-Unterschied, der die Existenz verraten würde). Rekursiver
Schlüssel-Scan, ein Testkonto pro Rolle, null durchgelassen.

Migration `eda89bb8082a` (Spalte entfernt, `is_asset_quick_entry` neu mit `server_default='0'`
-- Regel 1), 18 neue Tests, drei bestehende Testdateien (`test_v277_operational_assets_stufe2.py`,
`test_v280_operational_assets_stufe3.py`, `test_v283_recurring_costs.py`) auf die neue Quelle
umgestellt. Volle Suite: 1649 Tests grün.

## Ist-Werte im Produktivstunden-Rechner (seit 1.5.8)

Nachbesserung am Produktivstunden-Rechner (1.5.1) -- drei der fünf Annahmen (Feiertage,
Schlechtwetter, Krankheit) bekommen einen aus echten Daten hergeleiteten Vergleichswert. Erst
ein Befund (berichtet, bevor gebaut wurde, siehe Chatverlauf), dann drei vom Betreiber
vorgegebene Entscheidungen. Urlaub und unproduktive Zeit bleiben bewusst reine Annahmen ohne
Ist-Wert-Vergleich (Urlaub ist geplant, nicht gemessen; unproduktive Zeit ist keine für sich
buchbare Größe).

### Feiertage: errechnet, aber übersteuerbar

`count_workday_holidays(db, start, end)` (neu, `app/planning.py`, direkt neben `_holiday_rows()`/
`_working_weekdays()`) zählt aktive `PlanningHoliday`-Zeilen im Zeitraum, die auf einen laut
`PlanningSettings` konfigurierten Arbeitstag fallen -- ein Feiertag am Wochenende zieht keine
Arbeitsstunden ab. Wiederverwendet dieselbe Arbeitstage-Definition wie die Kapazitätsplanung
(`_working_weekdays()`), keine zweite, abweichende "Wochenende"-Annahme nur für diesen Rechner.

**Prämisse korrigiert**: `PlanningHoliday` trägt entgegen der ursprünglichen Annahme KEIN
Bundesland-Feld -- es ist eine einzige, unternehmensweite flache Liste (`holiday_date`, `name`,
`active`). Das ändert an der Zählbarkeit nichts: regionale Feiertage (Fronleichnam, Allerheiligen
für NRW) werden einfach als ganz normale Zeilen in dieselbe Liste eingetragen und dadurch
unterschiedslos gezählt wie jeder andere Feiertag -- es gibt nur keine eigene "regional"-Spalte,
die man separat auswerten könnte.

`public_holidays_suggestion(db)` (`app/productive_hours.py`) wertet das laufende Kalenderjahr aus
und liefert den Vorschlag als zusätzliches Feld `public_holidays_suggested` neben dem
unveränderten, frei editierbaren `public_holidays` -- die Oberfläche zeigt ihn mit einem
"übernehmen"-Link, der das Eingabefeld nur vorbefüllt (`applyHolidaySuggestion()`,
`settings.html`), schreibt ihn nie selbst. Real geprüft: 0 `PlanningHoliday`-Zeilen in der
lokalen Datenbank -- der Vorschlag liefert heute `0`, bis die Feiertage über die bestehende
Verwaltung (`/api/planning/holidays`) gepflegt sind.

### Schlechtwetter/Krankheit: Ist-Wert als Orientierung, rollierende 12 Monate

**Personenkreis, die wichtigste Korrektur dieser Runde**: "Monteure, die in den
Verrechnungssatz eingehen" wird über `effective_cost_allocation()=="labor_rate"` bestimmt
(`labor_rate_employees()`, `app/productive_hours.py`) -- dieselbe Personenmenge, die
`calculate_labor_rate()` (`app/labor_rate.py`) bereits als `direct_employees` behandelt. BEWUSST
NICHT über `AppUser.role=="field"`: die Rolle sitzt auf dem Login-Konto, nicht auf `Employee`,
und die meisten Monteure haben gar kein ERP-Login. Real geprüft: **0** `AppUser`-Konten mit
`role='field'`, aber **7** aktive Mitarbeiter mit `effective_cost_allocation()=="labor_rate"` --
ein Filter auf die Rolle hätte den Nenner auf 0 gesetzt und jeden Durchschnitt undefiniert
gemacht.

**Umrechnungsgröße Schlechtwetter (Stunden → Tage), geprüft statt erfunden**: drei
"gepflegte Sollarbeitszeiten" existieren im Projekt --
`ProductiveHoursSettings.daily_hours` (lokal zu genau diesem Rechner, Default 8,00),
`WorkTimeModel.daily_target_hours` (per Mitarbeiter, sommer-/winterabhängig, aus dem
Zeiterfassungs-Backoffice) und `PlanningSettings.daily_work_hours` (Kapazitätsplanung der
Plantafel, kombiniert mit `Employee.weekly_hours` in `_employee_daily_gross_hours()`). Gewählt:
**`ProductiveHoursSettings.daily_hours`** -- NICHT, weil es die genaueste der drei Größen ist
(die beiden anderen sind sogar präziser, weil mitarbeiter-/kalenderspezifisch), sondern weil es
GENAU die Größe ist, mit der `calculate_productive_hours()` bereits heute die Annahme
(`weather_loss_days`) in Stunden umrechnet. Der ganze Zweck dieser Anzeige ist ein direkter
Vergleich "Annahme X Tage vs. Ist-Wert Y Tage" -- dieser Vergleich braucht auf BEIDEN Seiten
dieselbe Definition von "ein Tag". Ein Wechsel auf eine der beiden anderen, für sich genommen
"besseren" Größen hätte die Vergleichbarkeit innerhalb dieses einen Rechners gebrochen, ohne
einen Nutzen zu bringen, der diesen Preis wert wäre. Die Herleitung bleibt in der Oberfläche
nachvollziehbar (`settings.html::renderProductiveHours()` zeigt "X Std. Schlechtwetter über N
Monteure ÷ Y Std./Tag ÷ N Monteure").

`weather_days_actual(db)` summiert `TimeEntry.hours` über `entry_type IN (weather_winter,
weather_summer)`, `status="booked"`, für `labor_rate_employees()` im rollierenden 12-Monats-
Fenster, teilt durch `daily_hours` und die Monteurzahl. Braucht KEINE Anonymitäts-Untergrenze --
Schlechtwetter ist keine Personalinformation.

`sick_days_actual(db)` zählt Kalendertage (inkl. Wochenende -- dieselbe Konvention wie
`average_sick_days` selbst, `calculate_productive_hours()` unterscheidet bei keiner der vier
"Tage"-Annahmen nach Wochentag) aus `EmployeeAbsence` mit `absence_category=="krankheit"`, auf
das Fenster zugeschnitten, gemittelt über dieselbe Personenmenge.

### Anonymitäts-Untergrenze bei Krankheit -- die wichtige Entscheidung

Bei wenigen Monteuren verrät der Durchschnitt eine einzelne Krankheit: drei Monteure,
Durchschnitt "8 Tage", zwei gesund -- jeder kann auf 24 Tage für den Dritten zurückrechnen.
`sick_days_actual()` liefert deshalb unter `MIN_EMPLOYEES_FOR_SICK_DAYS_AVERAGE` (fester
Code-Wert, **5**, wie vom Betreiber vorgeschlagen und für plausibel befunden -- dieselbe
Größenordnung wie in vielen Datenschutz-Leitfäden übliche Small-Cell-Suppression-Schwellen)
WEDER `average_days` NOCH `total_days` -- `total_days` allein würde die Durchschnittsbildung
(`total/count`) für jeden trivial zurückrechenbar machen, der die (nicht geheime) Monteurzahl
kennt. Nur `employee_count` bleibt sichtbar (Organisationsgröße, keine Gesundheitsinformation).
Bewusst KEIN konfigurierbares Einstellungsfeld für diese Schwelle -- ein Betreiber könnte sie
versehentlich oder bewusst herabsetzen und damit genau den Schutz aufheben, den sie garantieren
soll.

**Real geprüft**: 7 `labor_rate`-Monteure heute -- über der Schwelle, der Krankheits-Ist-Wert
wäre technisch sichtbar. Da aber 0 `EmployeeAbsence`-Zeilen in der lokalen Datenbank existieren,
zeigt er heute ohnehin `0 Tage` bei `0 von 12 Monaten` Datengrundlage -- die Untergrenze greift
erst, wenn die Belegschaft unter 5 `labor_rate`-Mitarbeiter fällt, was für die reale
Installation aktuell nicht der Fall ist.

### Datengrundlage-Anzeige: Pflicht, ehrlich auch bei "0 von 12"

"Beruht auf N von 12 Monaten" -- ein Monat zählt als "mit Daten", wenn mindestens eine gebuchte
`TimeEntry` (beliebiger Zeitart, für Schlechtwetter) bzw. eine `EmployeeAbsence` beliebiger
Kategorie (für Krankheit) für einen der gezählten Monteure existiert. Bewusst DATENGETRIEBEN
statt eines hart codierten Einführungsdatums der neuen Zeitarten/Kategorien (1.5.3) --
unterscheidet "in diesem Monat gab es kein Schlechtwetter/keine Krankheit" (echte Null) von
"in diesem Monat wurde noch gar nichts erfasst" (fehlende Daten), ohne ein Versionsdatum im
Code zu verankern. Bei Krankheit zählt dafür bewusst JEDE Abwesenheitsart (nicht nur Krankheit
selbst) -- ein Monat mit erfasstem Urlaub, aber ohne Krankheit, signalisiert "Abwesenheits-
erfassung war aktiv", nicht "keine Daten vorhanden". `_rolling_window()` liefert dafür
IMMER exakt 12 volle Kalendermonate (bis einschließlich des laufenden, unvollständigen Monats),
nie 11 oder 13 je nach Tagesdatum -- ein einfaches "heute minus 365 Tage" hätte je nach
Monatslängen schwankend viele Kalendermonate berührt.

Real geprüft, Stand der lokalen Datenbank: 0 `EmployeeAbsence`-Zeilen, 0 Schlechtwetter-
Buchungen -- beide Ist-Werte zeigen heute ehrlich "0 von 12 Monaten". Kurz nach Einführung der
Zeitarten ist kaum Aussagekraft da, und die Anzeige darf das nicht beschönigen -- genau die
Nutzervorgabe.

### Keine Doppelzählung, kein neues Datenmodell

`calculate_productive_hours()`/`calculate_labor_rate()` bleiben unangetastet, lesen weiterhin
ausschließlich die gepflegten Settings-Felder (`public_holidays`/`average_sick_days`/
`weather_loss_days`) -- die drei Ist-Werte sind zusätzliche, nie geschriebene Felder in der
API-Antwort (`ProductiveHoursCalculationOut.public_holidays_suggested`/`weather_days_actual`/
`sick_days_actual`), keine neue Spalte, keine Migration nötig. `GET/PUT /api/productive-hours-
settings`/`.../apply` bleiben unverändert `require_min_role(ROLE_OFFICE_FINANZEN)`-gated --
kein neuer Endpunkt nötig, die Ist-Werte hängen sich an die bestehende Antwort.

**Angriffstest**: `buero_auftrag`/`field` bekommen 403 auf den gesamten Endpunkt, wie schon
vorher. Rekursiver Schlüssel-Scan auf der Antwort bestätigt: keine personenbezogenen Bezeichner
(kein `employee_id`/`employee_name`/`first_name`/`last_name`), unter der Anonymitäts-Untergrenze
weder `average_days` noch `total_days` für Krankheit. 19 neue Tests
(`tests/test_v291_produktivstunden_ist_werte.py`), volle Suite: 1668 Tests grün.
