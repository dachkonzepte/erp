# Vertragsgrundlage, Vertrag, Beteiligte, Anzeigen (Stufe 2b)

Stufe 2b des Stufe-2-Vorhabens (Stufe 2a: Unterschrift, Zweck, Versand -- siehe
`docs/archiv/modul-checklisten.md`, Etappenplan). 2b-1a gehört zum Kern (Kunde, Angebot, Auftrag),
kein Modul-Umschalter. Eine neue Sitzung liest diese Datei zuerst (Regel 14), dann den Etappenplan
unten, und prüft den Stand gegen `VERSION`/`CHANGELOG.md`/`git log`.

---

## Etappenplan

Je Version ein Commit (Regel 13), `VERSION` + `CHANGELOG.md` + `backup_windows.ps1` (Regeln 8/9).

| Runde | Version | Inhalt | Stand |
|---|---|---|---|
| **2b-1a** | 1.8.21 | Vertragsgrundlage: Verbraucher-Merkmal am Kunden, Vertragsgrundlage an Angebot und Auftrag, Klauseltext je Grundlage mit rechtlicher Prüfung, Übernahme/Abgleich, Fehler `tax_key_id`/`outro_text_2`, Feldliste Angebot/Auftrag | erledigt |
| **2b-1b Teil 1** | 1.8.32 | Vertragsvorlagen (Abschnitte, Platzhalter, nur bei Verbrauchern, Prüfung), Vertragsentwurf beim Beauftragen mit Fallfeldern, Ausführungszeitraum aus dem Angebot, PDF `contract` mit Angebot als Anlage und Wasserzeichen | erledigt |
| **2b-1b Teil 2a** | 1.8.33 | Vertrag festschreiben (Fassungen), Anlage aus der Ablage mit bewusster Wahl, Versand; Schnellauftrag ohne automatischen Entwurf | erledigt |
| **2b-1b Teil 2b** | 1.8.34 | Gemeinsame Unterschriftsvorlage, Unterschrift auf dem Gerät (Kunde und Betrieb, Ankreuzfelder, Unterschriftsblatt) oder Papier-Scan, Sperren nach der Unterschrift, Widerrufsfrist | erledigt |
| **2b-1b Abrundung** | 1.8.35 | Unterschriebene Abschrift (Fassung + Blatt bzw. Scan) für Versand und Zustellung, Größengrenze der Berichtsunterschrift, lesbare Fehler der Auftragsseite | erledigt |
| **2b-2** | 1.8.36, 1.8.37 | Vorab feste Uhr für uhrzeitabhängige Tests (1.8.36); Adressbuch als Stammdatenbereich, Beteiligte am Projekt mit fester Rolle, Kopie bei Anzeigen, Empfangsvollmacht mit Beleg, Reiter in der Projektmappe (1.8.37) | erledigt |
| **2b-3 Teil 1** | 1.8.38 | Behinderungsanzeige erfassen: Systemfelder in drei Abschnitten (Meldung, Anzeige nur Büro, Wegfall), Startvorlage, Folge nach der Unterschrift der Meldung, Tagesbericht-Regel mit Link zum Anlegen | erledigt |
| **2b-3 Teil 2** | — | Behinderungsanzeige: Brief-PDF und Versand | offen |
| **2b-4** | — | Bedenkenanzeige | offen |

Nach jeder Runde die Spalten "Version"/"Stand" nachziehen und unten einen Abschnitt
"Umsetzung 1.8.x" ergänzen.

---

## Umsetzung 1.8.21 (30.09.2026) -- Runde 2b-1a: Verbraucher-Merkmal und Vertragsgrundlage

Betreibervorgabe: (1) Kunde: festes Feld "Verbraucher (§ 13 BGB)", Vorgabe ja; Migration nein nur
bei Gewerbekunde, Öffentlicher Auftraggeber, Architekt/Planer, Versicherung. (2) Angebot:
Vertragsgrundlage in `QuoteDocumentMeta`, feste Schlüssel `vob_b`, `bgb_vob_c_4_5`, `bgb`; neue
Angebote Verbraucher → `bgb_vob_c_4_5`, sonst `vob_b`; im Editor sichtbar und änderbar; Bestand
`bgb`. (3) Einstellungen: Klauseltext je Grundlage mit "rechtlich geprüft am, durch"; Angebots- und
Auftrags-PDF drucken nur geprüfte Klauseln, sonst Warnung im Editor. (4) Beauftragen übernimmt die
Grundlage; Ändern am Auftrag nur mit Begründung (Historie); der Abgleich überschreibt eine so
geänderte nicht. (5) `tax_key_id` und `outro_text_2` beim Beauftragen und Abgleich mitkopieren; Test
mit Liste aller Felder. (6) Tests mit Gegenprobe.

- **Schlüssel und Texte** (`app/contract_basis.py`, rollenlos): `vob_b` "VOB/B",
  `bgb_vob_c_4_5` "BGB mit VOB/C Abschnitt 4 und 5", `bgb` "BGB (ohne VOB)". Die Schlüssel stehen in
  drei Tabellen und werden nie umbenannt; die Beschriftungen dürfen sich ändern.
- **Kunde**: `customers.is_consumer` (Boolean, NOT NULL, server_default wahr). Bewusst direkt am
  Kunden und nicht aus der Kategorie abgeleitet: die Kategorie ist eine frei umbenennbare
  Auswahlliste. `CustomerCreate.is_consumer` Vorgabe `True`; `CustomerUpdate.is_consumer` ist
  optional (`None` = unverändert), weil das Update sonst jedes Feld ersetzt und ein Aufrufer ohne
  das Feld es still zurücksetzen würde. Häkchen auf der Kundenseite (`customer.html`) und im
  Anlegeformular (`master_data_form.html`, vorbelegt).
- **Angebot**: `quote_document_meta.contract_basis` (String(30), server_default `bgb`). Die
  Vorgabe für neue Angebote setzt `ensure_quote_structure()` beim Anlegen der Kopfzeile aus
  `quote.project.customer` (`default_contract_basis_for_customer()`). Das trifft jeden Weg, auf dem
  ein Angebot entsteht (Projektseite, Anfrage umwandeln, Schnellauftrag), weil keiner selbst eine
  Kopfzeile anlegt. Ausnahme `_copy_quote_into_project()` (Vorgang kopieren, Mustervorgang), die
  eine eigene Kopfzeile baut: dort ebenfalls die Vorgabe aus dem Kunden des Zielprojekts, nicht die
  Wahl im Quellangebot -- die Kopie ist ein neues Angebot, beim Mustervorgang womöglich für einen
  anderen Kunden. `PUT /api/quotes/{id}/document-meta` nimmt `contract_basis` optional (fehlt =
  unverändert, unbekannter Schlüssel 422). Editor: Auswahl unter "Steuerschlüssel", gespeichert mit
  "Angebotsdetails speichern", Warnkasten sofort beim Umschalten.
- **Klauseln**: Tabelle `contract_basis_clauses` (`basis_key` eindeutig, `clause_text`,
  `reviewed_on`, `reviewed_by`, `updated_by_name`, `updated_at`). Kein Seeding und bewusst keine
  vorgegebenen Texte (Rechtstexte gehören geprüft, nicht vom ERP erfunden); eine Zeile entsteht
  beim ersten Speichern, im SAVEPOINT gegen gleichzeitiges erstes Speichern. Geprüft heißt: Text,
  Datum und Name gesetzt. Regeln in `update_clause()`: Datum und Name nur gemeinsam, Datum nicht in
  der Zukunft (`berlin_today()`), ohne Text keine Prüfangabe. **Festlegung (nicht vorgegeben,
  bitte bestätigen): ändert sich der Text und kommen dieselben Prüfangaben wie bisher mit, fallen
  sie weg** -- die Prüfung galt dem alten Text. Mit neuem Datum oder Namen bleibt sie. Die Antwort
  trägt `review_reset`, die Seite sagt es dazu. **Festlegung: Speichern nur Administratoren**
  (`PUT /api/settings/contract-basis-clauses/{key}`, `require_min_role(ROLE_ADMIN)`), Lesen Büro
  und Admin; die Prüfangabe entscheidet, ob ein Vertragstext auf Kundendokumente kommt. Für das Büro
  zeigt die Seite die Felder gesperrt. Auswahl samt Prüfstand für Editor und Auftragsseite:
  `GET /api/contract-bases`.
- **PDF**: `build_payment_tax_closing_block()` (`app/document_pdf.py`) hat `contract_clause_text`;
  gedruckt als "**Vertragsgrundlage:**" + Klausel nach dem Steuerhinweis, vor dem Schlusstext.
  `quote_framed_pdf.py` und `order_pdf.py` reichen `printable_clause_text(db, key)` durch, das nur
  eine geprüfte Klausel liefert. Die Klausel wird bei jedem PDF live gelesen, nicht am Auftrag
  eingefroren: ein versendetes PDF liegt seit 1.8.17 unveränderlich in der Ablage, ein Nachdruck
  nach einer Textänderung zeigt den neuen Text. Die alte Vergleichsansicht
  (`quote_layout_pdf.py`, "entfällt demnächst") druckt keine Klausel.
- **Auftrag**: `orders.contract_basis` (server_default `bgb`) und `orders.contract_basis_manual`
  (Boolean, server_default falsch). `create_order_from_quote()` und `_copy_quote_scope_to_order()`
  übernehmen `meta.contract_basis`, letzteres nur, solange `contract_basis_manual` falsch ist.
  Ändern ausschließlich über `PUT /api/orders/{id}/contract-basis` (Begründung Pflicht, höchstens
  2000 Zeichen, gleiche Grundlage abgelehnt) -- bewusst nicht Teil von `OrderUpdate`, sonst ginge
  es ohne Begründung. Historie in `order_contract_basis_changes` (alt, neu, Begründung, wer, wann;
  Relationship mit Kaskade am Auftrag, wird sonst nie geändert oder gelöscht), abrufbar über
  `GET /api/orders/{id}/contract-basis-changes`. Danach gilt die Grundlage als am Auftrag
  festgelegt: der Abgleich überschreibt sie nicht, und `order_matches_source_quote()` lässt sie aus
  dem Vergleich heraus, sonst stünde der Auftrag dauerhaft auf "Angebot geändert". Ein Weg zurück
  ("wieder dem Angebot folgen") ist nicht gebaut -- nicht verlangt. Auftragsseite: Karte
  "Vertragsgrundlage" unter "Auftragsdaten" mit Herkunft, Warnung, Auswahl, Begründung, Historie.
- **Fehler behoben (Punkt 5)**: `tax_key_id` und `outro_text_2` kopierten weder
  `create_order_from_quote()` noch `_copy_quote_scope_to_order()`; ein Auftrag verlor still den
  Steuerschlüssel (und damit den Hinweistext im PDF, z. B. §13b) und den zweiten Schlusstext. Beim
  Abgleich stand zusätzlich `vat_rate` aus dem Angebot neben einem `tax_key_id` vom Auftrag. Beide
  Felder werden jetzt übernommen UND stehen im Vergleich (`_quote_scope_payload()`/
  `_order_scope_payload()`) -- sonst hätte ein Angebot, das sich nur darin ändert, als unverändert
  gegolten und der Abgleich hätte früh abgebrochen. **Folge für den Bestand**: Aufträge, deren
  Angebot einen Steuerschlüssel oder zweiten Schlusstext hat, der am Auftrag fehlt, zeigen nach dem
  Update "Quellangebot nach Beauftragung geändert". Das ist eine echte Abweichung; die Migration
  zieht diese Werte bewusst nicht nach (bereits versendete Auftrags-PDFs sähen beim Nachdruck anders
  aus). Übernehmen ist ein bewusster Klick mit Revision wie bisher.
- **Feldliste** (`tests/test_v325_quote_order_copy_fields.py`): `ORDER_FIELDS` ordnet jede Spalte
  von `Order`, `OrderSection`, `OrderItem`, `OrderItemCalculationSnapshot`,
  `OrderItemMaterialSnapshot` ein -- übernommen (Quelle, "beim Beauftragen und beim Abgleich" oder
  "nur beim Beauftragen") oder `eigen(Begründung)`; `QUOTE_NOT_COPIED` begründet jede Spalte von
  `Quote`, `QuoteDocumentMeta`, `QuoteEmployeeAssignment`, `QuoteSection`, `QuoteItem`,
  `QuoteItemLayout`, `QuoteItemCalculation`, `QuoteItemMaterialCalculation`, die nirgends Quelle ist.
  Ein neues Feld auf einer der 13 Tabellen ohne Eintrag ist rot, mit Tabelle.Spalte und Anweisung in
  der Meldung. Zwei Verhaltenstests setzen jedes übernommene Feld auf einen eigenen Wert und
  vergleichen nach Beauftragen und nach Abgleich generisch über die Liste (Titel und Positionen über
  ihre Quell-IDs, `parent_id`/`section_id` über die Zuordnung der Titel); "nur beim Beauftragen"
  muss den Abgleich unverändert überstehen.
- **Migration `8af8137cc57c`**: Spalten und Tabellen wie oben; `is_consumer` falsch für Profile mit
  den vier Kategorien, verglichen ohne Leerzeichen und Groß-/Kleinschreibung (die Auswahlliste heißt
  "Architekt / Planer"); Kunden ohne Profil und "Hausverwaltung"/"Sonstige" bleiben Verbraucher
  (Vorgabe wörtlich: "sonst ja"). Angebote ohne Kopfzeile (die entstünde sonst erst beim ersten
  Öffnen, dann mit der Vorgabe für NEUE Angebote) bekommen sie hier mit `bgb` und den Werten, die
  `ensure_quote_structure()` setzen würde (Datum aus `created_at` in Europe/Berlin, Bindefrist
  30 Tage, Standard-Zahlungsbedingung). `downgrade()` bricht ab, sobald etwas verloren ginge
  (Klauseltext oder Prüfangabe, eine Änderung am Auftrag, eine Grundlage ungleich `bgb`, ein Kunde
  abweichend von der Kategorie-Regel), und lässt die angelegten Kopfzeilen stehen.
- **Verifikation**: `tests/test_v325_contract_basis.py` (17, darunter `upgrade()`/`downgrade()`
  der Migration auf einem nachgebauten Vorzustand) und `tests/test_v325_quote_order_copy_fields.py`
  (4); 24 Gegenproben rot (Skript im Scratchpad, je Punkt mindestens eine: Migrationsschritt weg,
  Vorgabe weg, ungeprüfte Klausel gedruckt, Klausel in einem der beiden PDFs weg, Rücksetzen weg,
  Büro darf speichern, Abgleich überschreibt geänderte Grundlage, Kopie von `tax_key_id`/
  `outro_text_2` weg, Feld nicht im Vergleich, neues Feld an Angebot bzw. Auftrag). Die Gegenprobe
  "`tax_key_id` nur auf einer Seite aus dem Vergleich" war zuerst falsch angesetzt (macht jeden
  Auftrag dauerhaft abweichend statt nie) -- ersetzt durch "auf beiden Seiten", die einseitige
  Variante fängt `test_beauftragen_copies_every_copied_field`. Migration gegen SQLite (Wegwerf-Datei,
  upgrade/downgrade/upgrade über die Alembic-Kommandozeile) und PostgreSQL 17 (Wegwerf-Schema in
  `spielwiese`, Kette bis `d1c4a7252554`, Bestandsdaten, upgrade, Downgrade-Abbruch bei einer
  Änderung am Auftrag, Downgrade ohne, erneut upgrade). Suite 2243 grün. Klicktest
  `scripts/klicktest_vertragsgrundlage.py` 30/30 (Kunde anlegen, Kundenseite, Angebots-Editor,
  Auftragsseite hell/dunkel, Einstellungen als Admin und Büro).

### Nebenbefunde (nur gemeldet)

1. **Einstellungsseite auf frischer Datenbank**: `labor-rate-settings` und `labor-rate-calculation`
   laufen parallel, beide legen den Singleton `labor_rate_settings` (id=1) an, einer scheitert mit
   `IntegrityError`, die Seite zeigt ein `alert()`. Die bekannte, offene Fehlerklasse
   "get_or_create_settings(id=1)" aus CLAUDE.md; beim Klicktest aufgefallen (der Dialog hielt den
   headless Chrome an). Der Klicktest sät den Singleton vorab und leitet `alert()` auf
   `console.error` um.
2. **`QuoteDocumentMeta.internal_note` wird bei jedem Speichern der Angebotsdetails geleert**:
   `saveHeader()` in `quote_editor.html` schickt fest `internal_note:null`, ein Eingabefeld gibt es
   nicht. Nur über die API oder eine Projektkopie gesetzte Notizen gehen dadurch verloren.
   **Behoben in 1.8.23**: der Editor schickt die Notiz nicht mehr mit, `PUT .../document-meta` lässt
   sie stehen, wenn sie im Aufruf fehlt (ausdrückliches `null` leert weiterhin).
   `tests/test_v327_quote_internal_note.py` schickt genau die Schlüssel, die `saveHeader()` im
   Template übergibt; Klicktest `scripts/klicktest_angebot_interne_notiz.py`. Ein Eingabefeld gibt
   es weiterhin nicht -- die Notiz ist im Editor weder sichtbar noch bearbeitbar.
3. **Beim Beauftragen geht der Freitext "Ausführungszeitraum" des Angebots verloren**: der Auftrag
   führt nur Beginn/Ende als Datum aus dem Dialog; das Auftrags-PDF zeigt den Zeitraum nur, wenn dort
   Daten eingetragen wurden. Ebenso ein alter Freitext-Ansprechpartner ohne Mitarbeiterbezug.
   Beides steht begründet in `QUOTE_NOT_COPIED`, fachlich zu entscheiden.
   **Ausführungszeitraum behoben in 1.8.32** (siehe unten); der Freitext-Ansprechpartner bleibt offen.
4. **Neue und importierte Kunden sind Verbraucher, unabhängig von der Kategorie** (Vorgabe ja): ein
   neu angelegter oder per Adressimport übernommener Gewerbekunde bekommt dadurch bei neuen
   Angeboten `bgb_vob_c_4_5`, bis jemand das Häkchen entfernt. Denkbar: Häkchen beim Wählen einer der
   vier Kategorien im Formular vorschlagen, Import aus der Kategorie ableiten.
5. **LV-Kopfzeile ragt bei 1400 px Breite in die rechte Spalte** (Angebots-Editor "GESAMTPREIS"
   über "Angebotstitel", Auftragsseite "GP" über der Karte) -- auf den Klicktest-Bildern sichtbar,
   unabhängig von dieser Runde.

---

## Umsetzung 1.8.32 (01.10.2026) -- Runde 2b-1b Teil 1: Vertragsvorlagen und Vertragsentwurf

Betreibervorgabe: (1) Einstellungen → Vertragsvorlagen: je Vertragsgrundlage eine Vorlage aus Abschnitten
mit Text und Platzhaltern (gemeinsames Platzhalter-Modul auf Basis von `_apply_placeholders`), Liste der
Platzhalter in der Oberfläche; ein Abschnitt kann "nur bei Verbrauchern" sein (Widerrufsbelehrung,
Muster-Widerrufsformular, Ankreuzfeld vorzeitiger Beginn); Prüfangaben wie bei den Klauseln, Textänderung
setzt sie zurück, speichern nur Admin, keine vorgegebenen Texte. (2) Beim Beauftragen ein Vertragsentwurf am
Auftrag, wenn es für dessen Grundlage eine Vorlage gibt; Fallfelder Ausführungszeitraum, Abschlagsplan,
Besonderheiten. (3) Fehler: der freie Ausführungszeitraum des Angebots ging beim Beauftragen verloren -- in
den Auftrag übernehmen, Vorgabe im Entwurf, Feldlisten-Test. (4) Dokumenttyp `vertrag` im gemeinsamen
Rahmen, Angebot als Anlage, bei ungeprüfter Vorlage "Entwurf – Vertragstext nicht geprüft" quer auf jeder
Seite. (5) Monteure kein Zugriff, Datengrenze-Test deckt die neuen Routen ab. (6) Tests mit Gegenprobe.
Festschreiben, Versand und Unterschrift: Teil 2.

- **Platzhalter** (`app/placeholders.py`): `apply_placeholders()` aus `reminders.py::_apply_placeholders()`
  hervorgegangen, ersetzt jetzt in EINEM Durchgang (vorher je Schlüssel ein `str.replace()` über den ganzen
  Text: ein eingesetzter Wert, der wie ein Platzhalter aussieht, wurde von einem späteren Schlüssel noch
  einmal ersetzt -- bei Beträgen nie, bei Freitext im Vertrag schon). `None` als Wert ergibt "" statt
  `TypeError`. Mahnung (Text und Mail) und die E-Mails von Angebot, Auftrag, Rechnung und Checkliste nutzen
  es statt eigener Schleifen. `placeholders_in()`/`unknown_placeholders()` für die Warnung in der Vorlage.
- **Vorlagen** (`app/contract_templates.py`, rollenlos): Tabellen `contract_templates` (`basis_key`
  eindeutig, `title`, `reviewed_on`, `reviewed_by`, wer/wann) und `contract_template_sections`
  (`sort_order`, `heading`, `body_text`, `consumer_only`, `with_checkbox`). 22 Platzhalter
  (`CONTRACT_PLACEHOLDERS`: Betrieb, Kunde/Objekt als Schnappschuss am Auftrag, Auftrag, Angebot, Vorgang,
  Vertragsgrundlage, Summen, Zahlungsbedingungen, die drei Fallfelder). Gespeichert wird immer die ganze
  Vorlage (`PUT /api/settings/contract-templates/{key}`, alle Felder Pflicht, Admin); leere Abschnitte
  fallen weg. Regeln wie `update_clause()`. **Festlegung (bitte bestätigen): jede inhaltliche Änderung
  setzt die Prüfung zurück** -- Titel, Überschrift, Text, Reihenfolge, "nur bei Verbrauchern",
  Ankreuzfeld --, nicht nur der Text; alles davon verändert den Vertrag. Die Seite meldet unbekannte
  Platzhalter und Fallfelder, deren Platzhalter die Vorlage nicht nutzt (ihr Inhalt käme sonst still
  nicht in den Vertrag). Eine Vorlage "existiert", sobald ein Abschnitt Inhalt hat; auch eine ungeprüfte
  erzeugt Entwürfe (mit Wasserzeichen). Kein Seeding.
- **Ankreuzfeld**: Schalter je Abschnitt statt eines Zeichens im Text -- Helvetica hat kein Kästchen, ein
  "☐" erschiene als fehlendes Zeichen. Gezeichnetes Kästchen (`_Checkbox` in `app/contract_pdf.py`) links
  neben dem Text.
- **Entwurf** (`order_contracts`, höchstens einer je Auftrag, Kaskade am Auftrag): Status `entwurf`,
  `execution_period`, `payment_plan`, `special_terms`, wer/wann. `create_order_from_quote()` legt ihn in
  derselben Transaktion an, wenn es für die Grundlage eine Vorlage gibt (lokaler Import, Regel 3) -- damit
  auch beim Schnellauftrag. **Festlegung: Entwurf auch von Hand** (`POST /api/orders/{id}/contract`, Karte
  "Vertrag" auf der Auftragsseite) -- sonst bekämen Aufträge von vor 1.8.32 und Aufträge, deren Vorlage erst
  später entsteht oder deren Grundlage geändert wurde, nie einen. Fallfelder per Teil-Update
  (`PUT /api/orders/{id}/contract`, `OrderContractUpdate(PartialUpdate)`), nur im Status `entwurf`. Der
  Ausführungszeitraum ist beim Anlegen aus dem Auftrag vorbelegt (`execution_period_text()`: Beginn/Ende und
  Freitext) und folgt späteren Änderungen am Auftrag nicht.
- **Live gelesen** (Teil 2 muss das beim Festschreiben einfrieren): Vorlage der HEUTIGEN Grundlage des
  Auftrags (nach einer Änderung der Grundlage ohne passende Vorlage: PDF 409, Karte sagt es), das
  Verbraucher-Merkmal vom Kunden des Vorgangs (der Auftrag hat keinen Schnappschuss davon), Summen und
  Angebot. Der Kopf zeigt "Stand" = heutiges Datum.
- **Ausführungszeitraum (Punkt 3)**: `orders.execution_period` (String(255)), beim Beauftragen aus
  `QuoteDocumentMeta.execution_period`; **nur beim Beauftragen**, der Abgleich lässt ihn stehen (am Auftrag
  änderbar, wie die Zahlungsbedingungen). Feldliste: `von("QuoteDocumentMeta.execution_period",
  NUR_BEAUFTRAGEN)`, aus `QUOTE_NOT_COPIED` gestrichen, beide Verhaltenstests setzen bzw. ändern ihn.
  Auftrags-PDF: "Ausführungszeitraum: 12.10.2026 – KW 42–44" (Daten und Freitext). Bestandsaufträge bleiben
  leer (wie `tax_key_id` 1.8.21: ein Nachdruck eines versendeten Auftrags sähe sonst anders aus); am Auftrag
  nachtragbar. `PUT /api/orders/{id}` dafür zum Teil-Update umgebaut (siehe `docs/archiv/teil-updates.md`).
- **PDF** (`app/contract_pdf.py`): Dokumenttyp `contract` in `RENDERERS_USING_SHARED_FRAME` und
  `DOCUMENT_TYPES` (Rückfall auf "default" wie alle). Kopf wie der Auftrag (Auftragsnr., Auftragsdatum, Ihr
  Angebot, Projekt, Kunden-Nr., Stand, Seite), Objektanschrift, Titel (Vorgabe "Vertrag"), Abschnitte,
  "Anlage: Angebot … vom …". Danach das Angebot aus `build_quote_framed_pdf()`, angehängt mit pypdfium2
  (`import_pages`). Wasserzeichen: neuer Parameter `watermark_text` an `render_framed_pdf()`, gezeichnet in
  `_NumberedCanvas.save()` halbtransparent über dem Inhalt, 54,7° (A4-Diagonale); `build_quote_framed_pdf()`
  reicht ihn durch, damit auch die Seiten der Anlage ihn tragen.
- **Rechte**: Vorlagen lesen ab `buero_auftrag`, speichern Admin; Vertrag lesen/anlegen/ändern/PDF ab
  `buero_auftrag`; Monteure 403 überall. `test_v326_monteur_datengrenze.py` ruft die drei neuen GET-Routen
  im Durchlauf auf und verlangt 403 (`test_vertragsrouten_im_durchlauf_fuer_monteure_gesperrt`).
- **Migration `8caedec524b4`**: drei Tabellen, eine Spalte. `downgrade()` verweigert, sobald eine Vorlage,
  ein Entwurf oder ein Ausführungszeitraum am Auftrag verloren ginge.
- **Verifikation**: `tests/test_v335_vertragsvorlagen.py` (27, darunter `downgrade()`/`upgrade()` der
  Migration), Feldliste (`test_v325_quote_order_copy_fields.py`), Datengrenze (`test_v326`), Strukturtest
  Teil-Updates (`test_v329`), Rollout-Status (`test_v229`) und `test_v333` (schickt jetzt auch den Zeitraum,
  den `saveOrder()` sendet) angepasst. 24 Gegenproben rot (Skript im Scratchpad, Datei byte-genau zurück):
  Verbraucher-Filter weg, Wasserzeichen nie/immer/nicht auf der Anlage/nicht gezeichnet, Anlage fehlt,
  Prüfung bleibt nach Textänderung, nur Text zählt als Änderung, Prüfangaben einzeln, Datum in der Zukunft,
  Büro speichert Vorlagen, Monteur darf Vertrag, Entwurf ohne Vorlage, kein Entwurf beim Beauftragen,
  Zeitraum nicht übernommen, Entwurf ohne Vorgabe, Auftrags-PDF ohne Freitext, Abgleich überschreibt
  Zeitraum, Auftrags-PUT und Fallfelder als volles Formular, abgeschlossener Vertrag änderbar, Platzhalter
  wieder nacheinander, Downgrade ohne Schutz, leere Vorlage zählt. Migration gegen SQLite (Wegwerf-Datei,
  Kommandozeile) und PostgreSQL 17 (Wegwerf-Schema in `spielwiese`: Kette bis `8af8137cc57c`, Bestand,
  upgrade, Unique-Schlüssel, Downgrade-Abbruch mit Vorlage und mit Zeitraum, downgrade, upgrade,
  `alembic check`). Klicktest `scripts/klicktest_vertragsvorlagen.py` 36/36 (Einstellungen als Admin und
  Büro, 412 px, Auftragsseite hell/dunkel, Entwurf von Hand).

### Nebenbefunde 1.8.32 (nur gemeldet)

1. **Die Anlage ist der heutige Stand des Angebots**, nicht die versendete Fassung aus der Ablage. Wurde das
   Angebot nach der Beauftragung geändert, weicht die Anlage vom Auftrag ab (die Karte sagt es). Für Teil 2
   zu entscheiden: welche Fassung beim Festschreiben angehängt wird. **Entschieden in 1.8.33** (Betreibervorgabe:
   die zuletzt versendete, bei Abweichung bewusste Wahl); das Entwurfs-PDF zeigt weiter den heutigen Stand.
2. **Briefpapier zweimal eingebettet**: Vertrag und Anlage sind zwei PDFs, jedes bettet den Hintergrund ein.
   Für die 3-MB-Grenze beim Versand (Teil 2) mit echtem Briefpapier nachmessen. **Gemessen in 1.8.33**: unkritisch.
3. **Textfelder der Auftragsseite in Festbreitenschrift**: `order.html` setzt für `textarea` keine Schrift,
   alle Textfelder der Seite (Vortext, Schlusstexte, Bemerkungen, jetzt auch die Fallfelder) erscheinen in
   der Browser-Vorgabe. Kosmetisch, bestand schon.
4. **Schnellauftrag**: läuft über `create_order_from_quote()` und bekommt damit ebenfalls einen Entwurf,
   sobald es für seine Grundlage eine Vorlage gibt. Folgerichtig, aber bei Wartungs-Schnellaufträgen
   vermutlich nicht gebraucht. **Seit 1.8.33 kein automatischer Entwurf mehr** (Betreibervorgabe Punkt 7).

---

## Umsetzung 1.8.33 (01.10.2026) -- Runde 2b-1b Teil 2a: Festschreiben, Anlage, Versand

Betreibervorgabe Teil 2 (acht Punkte): (1) Festschreiben: Vertrags-PDF mit Vorlagentext, Verbraucher-Merkmal,
Fallfeldern und Anlage einfrieren und mit Prüfsumme ablegen; danach Entwurf gesperrt, Änderungen nur als neue
Fassung, die alte bleibt sichtbar; vor dem Festschreiben folgt der Entwurf einer geänderten Vertragsgrundlage.
(2) Anlage: die zuletzt versendete Fassung des Angebots aus der Ablage; weicht der aktuelle Stand ab oder gibt es
keine, wählt das Büro bewusst, nie still. (3) Versand über `dispatch_email` (An vorbelegt mit dem Auftraggeber),
immer die festgeschriebene Fassung; Größe mit dem echten Briefpapier messen, bei Enge Vertrag und Anlage in einem
Durchgang rendern. (4) Gemeinsame Unterschriftsvorlage für Checkliste, Einsatzbericht und Vertrag. (5) Unterschrift
auf dem Gerät (Kunde und Betrieb, bindet die Prüfsumme des PDFs, Ankreuzfelder setzt der Kunde, Unterschriftsblatt in
der Ablage) oder Papier-Scan mit Datum und übertragenen Ankreuzfeldern. (6) Nach der Unterschrift Vertragsgrundlage
und Abgleich gesperrt. (7) Schnellaufträge ohne automatischen Entwurf. (8) Tests mit Gegenprobe. Bei zu großem
Umfang nach Punkt 3 committen und den Rest auflisten -- so geschehen: **1.8.33 = Punkte 1–3 und 7** (Punkt 7 hing
an derselben Stelle wie der Entwurf), Punkte 4–6 und deren Tests siehe "Offen für Teil 2b".

- **Inhalt** (`app/contract_templates.py::contract_content()`): alles, was im Vertrags-PDF steht, außer Briefpapier
  und Layout -- Titel und sichtbare Abschnitte mit eingesetzten Platzhaltern (je Abschnitt ein Schlüssel
  `abschnitt-N`, `with_checkbox`, `consumer_only`), Kopf- und Anschriftenangaben, Vertragsgrundlage,
  Verbraucher-Merkmal, Prüfangaben der Vorlage, Fallfelder, die Werte aller 22 Platzhalter und welche davon die
  Vorlage nutzt. Das Entwurfs-PDF rendert daraus live (`app/contract_pdf.py::build_contract_pdf()`), das
  Festschreiben friert genau diese Struktur ein und rendert einmal (`render_contract_pdf()`); eine Fassung wird
  danach nie neu gerendert. Kopf neu mit "Fassung" (Entwurf bzw. Nummer), auch in der Wiederholungszeile.
- **Fassungen** (`order_contract_versions`, `app/contract_versions.py`): `version_no` (eindeutig je Vertrag),
  `basis_key`, `is_consumer`, `frozen_content` (kanonisches JSON, sortierte Schlüssel) mit `content_sha256`,
  `sent_document_id` (das PDF in der Ablage, Art `vertrag`, Dokument-ID = Vertrag, Nummer "AUF-… · Fassung N"),
  `attachment_kind` (`versendet`/`aktuell`) und `attachment_document_id`, wer/wann, `superseded_at`.
  `OrderContract.status` jetzt `entwurf` | `festgeschrieben`. Festschreiben belegt zuerst den Entwurf per
  bedingtem UPDATE (Zeilensperre unter PostgreSQL, dazu der Unique-Schlüssel), rendert, legt ab, markiert die
  vorige Fassung als abgelöst, schreibt eine Zeile in die Änderungshistorie ("Vertrag festgeschrieben", Fassung und
  PDF-Prüfsumme, Projekt des Auftrags) und committet; scheitert etwas nach dem Ablegen, bleibt die Datei ohne
  Eintrag liegen (die Ablage löscht nie, wie 1.8.20). "Neue Fassung anlegen" macht wieder einen Entwurf (Fallfelder
  der letzten Fassung, Historie "Neue Fassung begonnen"). ORM-Sperre in `app/models.py`: nur `superseded_at`,
  einmal von leer; kein Löschen -- ein Auftrag mit festgeschriebenem Vertrag ist dadurch nicht mehr löschbar.
- **Festlegung (bitte bestätigen): festgeschrieben wird nur eine rechtlich geprüfte Vorlage.** Eine Fassung geht
  an den Kunden und wird unterschrieben; "Entwurf – Vertragstext nicht geprüft" auf jeder Seite passt dazu nicht.
  Der Knopf ist dann gesperrt, die Karte sagt warum.
- **Anlage** (`attachment_situation()`/`attachment_options()`, `GET /api/orders/{id}/contract/attachment-options`):
  "zuletzt versendet" = das jüngste abgelegte PDF des Angebots, auf das ein Versand mit Status "gesendet" verweist
  -- E-Mail oder nachgetragene Zustellung; Belege zählen nicht. **Festlegung: hängende und fehlgeschlagene Versände
  zählen nicht** (ob ein hängender hinausging, klärt das Büro im Versandprotokoll). Ob der heutige Stand abweicht,
  entscheidet der Text beider PDFs (`pdf_plain_text()`, Leerraum vereinheitlicht): das Angebot wird dafür neu
  gerendert. Die Bytes zu vergleichen ginge nicht (Zeitstempel und Kennungen im PDF). **Folge: auch ein geänderter
  Briefkopf-Text, eine geänderte Klausel der Vertragsgrundlage oder Zahlungsbedingung gilt als Abweichung** -- der
  Kunde sähe heute etwas anderes als damals; das Briefpapier-Bild dagegen nicht (kein Text). Gleich: Anlage ohne
  Rückfrage, die Karte sagt es. Sonst wählt das Büro über sichtbare Optionen ohne Vorauswahl (Regel 4); die API
  verlangt dann `attachment` = `versendet` mit der ID genau dieser Fassung (eine inzwischen neuere → 409) oder
  `aktuell`. Eine beschädigte Fassung in der Ablage wird nie angehängt. Im Vertragstext: "Anlage: Angebot … vom …, in
  der am … versendeten Fassung" bzw. "…, Stand …".
- **Passt die Fassung noch?** (`version_differences()`): Vertragsgrundlage am Auftrag, Verbraucher-Merkmal des
  Kunden und der Wert jedes Platzhalters, den die Vorlage nutzt (z. B. Auftragssumme nach einer Änderung im LV),
  verglichen mit dem eingefrorenen Wert. Eine Änderung an der Vorlage selbst zählt bewusst nicht -- vereinbart ist
  der festgeschriebene Text. **Festlegung (bitte bestätigen): eine abweichende Fassung wird weder per E-Mail
  versendet noch als zugestellt nachgetragen** (409 bzw. 400 mit der Liste); die Karte zeigt die Abweichungen und
  "Neue Fassung anlegen". Ebenso kein Versand, solange eine neue Fassung im Entwurf ist.
- **Versand** (`send_contract_email()`, `POST /api/orders/{id}/contract/send-email`): Regel 21, Art `vertrag`,
  `archived_document` = die Fassung (keine zweite Datei, `dispatch_email()` prüft die Prüfsumme), An = aktuelle
  Kunden-E-Mail wie bei Angebot und Auftrag. E-Mail-Vorlage `contract` (Einstellungen → E-Mail-Vorlagen).
  `app/dispatch_documents.py` kennt `vertrag` (Zustellung nachtragen mit der abgelegten Fassung, dieselben
  Bedingungen). Versandverlauf an der Karte nennt die Fassung je Versand; `/versandprotokoll` mit Art "Vertrag",
  Link auf den Auftrag (`order_id` je Zeile aus `list_dispatches()`). `GET /api/orders/{id}/contract/pdf` liefert
  festgeschrieben die abgelegten Bytes (Kopfzeile `X-DK-Ablage`, 409/410 bei beschädigter Datei), im Entwurf das
  Entwurfs-PDF; ältere Fassungen über `/api/sent-documents/{id}/file`.
- **Größe (Punkt 3)**: gemessen mit dem echten Briefpapier aus dem lokalen Datenordner (JPEG 1655×2340, 104 KB,
  hochgeladen am 11.09.) in einer Wegwerf-Datenbank: Vertrag mit 13 Abschnitten (darunter Widerrufsbelehrung und
  Muster-Formular) plus Angebot mit 30 Positionen 236.758 Bytes, 11 Seiten, 0,16 s; dasselbe Briefpapier als PNG
  656.203 Bytes. Weit unter 3.000.000 -- **kein gemeinsamer Renderdurchgang gebaut** (er ginge ohnehin nur für den
  heutigen Stand, nicht für die versendete Fassung aus der Ablage). Ob das Briefpapier auf dem Server dasselbe ist,
  ist von hier nicht prüfbar. Die Karte warnt, wenn eine Fassung über 3 MB liegt (dann auf anderem Weg zustellen).
- **Punkt 7**: `create_order_from_quote(..., contract_draft=False)` aus `app/quick_service_orders.py`; von Hand
  bleibt der Entwurf über die Karte möglich.
- **Oberfläche** (`order.html`, Karte "Vertrag"): Entwurf mit Fallfeldern, "Entwurf als PDF", Block "Festschreiben"
  (Erklärung, Anlage, Knopf "Fassung N festschreiben" mit `confirm()`); festgeschrieben: Kopf mit Fassung, Datum,
  Wer, Grundlage, Verbraucher, Anlage, gekürzte PDF-Prüfsumme (voll im `title`), Größe, "PDF öffnen"; Fallfelder nur
  lesbar; Abweichungen; Versand An/CC; Versandverlauf; "Neue Fassung anlegen"; Liste "Fassungen" (gültig / zuletzt
  festgeschrieben / abgelöst am …).
- **Rechte**: alle neuen Endpunkte ab `buero_auftrag`, Monteure 403 (`test_v326`: Durchlauf um
  `/contract/attachment-options` erweitert).
- **Migration `091e7f52649b`**: eine Tabelle. `downgrade()` verweigert, sobald es eine Fassung oder einen nicht mehr
  im Entwurf befindlichen Vertrag gibt.
- **Verifikation**: `tests/test_v336_vertrag_festschreiben.py` (19 Tests: Festschreiben friert Inhalt und PDF ein
  und sperrt; Vorlage danach geändert → PDF byte-gleich, Gegenprobe Entwurf der neuen Fassung liest den neuen Text;
  ungeprüft nicht festschreibbar; Entwurf folgt der geänderten Grundlage, danach ist die Fassung abweichend und der
  Versand gesperrt; geänderte Auftragssumme; neue Fassung und Ablösen; Anlage ohne versendete Fassung, unverändert
  versendet (angehängte Seiten = versendete Fassung), nach dem Versand geändert, fehlgeschlagener Versand,
  beschädigte Ablage; Versand = abgelegte Bytes ohne neue Datei, derselbe Schlüssel nicht zweimal, Link im
  Protokoll; E-Mail-Vorlage; Zustellung nachtragen; Monteur 403; Schnellauftrag; Unveränderlichkeit; Migration).
  `test_v324` (Verlauf an der Karte) und `test_v326` angepasst. Gegenproben (Schutz ausgehebelt, Test rot, Datei
  byte-genau zurück, Skript im Scratchpad): 23 rot -- PDF festgeschrieben neu gerendert, Fallfelder änderbar,
  ungeprüfte Vorlage, Anlage ohne Vergleich, ohne versendete Fassung still der heutige Stand, überholte Fassung des
  Angebots angenommen, fehlgeschlagener Versand zählt, Textvergleich immer gleich, beschädigte Ablage nicht erkannt,
  Versand rendert neu, Versand im Entwurf, Versand einer abweichenden Fassung, Platzhalterwerte nicht verglichen,
  Monteur darf, Schnellauftrag mit Entwurf, Fassung änderbar, Fassung löschbar, Ablösen fehlt, Downgrade ohne Schutz,
  kein Historieneintrag, E-Mail-Vorlage ignoriert, Protokoll ohne Link, Zustellung im Entwurf. "Versand im Entwurf"
  blieb zuerst grün: der Test schickte erst nach einer Änderung am Fallfeld, die 409 kam aus der Abweichungsprüfung --
  Test umgestellt (Versand direkt nach "Neue Fassung"), danach rot. Die neuen Tests und die von 1.8.32 zusätzlich
  gegen PostgreSQL 17 (Wegwerf-Schema je Test in `spielwiese`, Scratchpad-Plugin): 44 grün. Migration: SQLite
  (Wegwerf-Datei, Kommandozeile hin/zurück/hin, `alembic check`) und PostgreSQL (Wegwerf-Schema: Kette bis
  `8caedec524b4`, Bestand mit Vertragsentwurf über den App-Code, upgrade, `alembic current`, Constraints, zweimal
  Festschreiben über den App-Code mit Zeilensperre und ORM-Sperre, Downgrade-Abbruch mit Fassungen und mit Status,
  downgrade, upgrade, `alembic check`). Volle Suite 2423 grün. Klicktest `scripts/klicktest_vertrag_festschreiben.py`
  40/40 (nie versendet → Wahl, ohne Wahl abgewiesen; Fassung 1, PDF-SHA wie die Fassung, Versand an SMTP-Empfänger im
  Skript, Anhang = Fassung, Verlauf nennt die Fassung; neue Fassung, Fassung 2 gültig, 1 abgelöst; versendet und
  unverändert ohne Rückfrage; geändert → zwei Optionen ohne Vorauswahl; Protokoll-Link; E-Mail-Vorlage; hell, dunkel,
  412 px; Monteur 403). `klicktest_vertragsvorlagen.py` (Knopf heißt im Entwurf "Entwurf als PDF") 36/36,
  `klicktest_versandprotokoll.py` 45/45, `klicktest_versandverlauf.py` 32/32.

### Offen für Teil 2b (Punkte 4–6 und ihre Tests aus Punkt 8) -- erledigt in 1.8.34, siehe unten

1. **Gemeinsame Unterschriftsvorlage** (Punkt 4): Zeichenfeld heute zweimal -- `checklist.html` (`setupPad()`, je
   Feld, mit `devicePixelRatio`, weißer Hintergrund, Datei-Upload) und `service_reports.html` (`initSignaturePad()`,
   ein Feld für Monteur und Kunde nacheinander, Base64 im JSON, ohne `devicePixelRatio`). Vorschlag:
   `_unterschrift.html` mit Stil und einer Funktion, die ein Zeichenfeld liefert (leer?, leeren, als PNG); beide
   Seiten und der Vertrag nutzen sie. Dabei aufgefallen: das Feld im Einsatzbericht hat `background:var(--card)` und
   Strichfarbe `#182420` -- im dunklen Theme ist die Unterschrift beim Zeichnen kaum zu sehen (die Checkliste setzt
   Weiß fest).
2. **Unterschrift auf dem Gerät** (Punkt 5): Kunde und Betrieb; die Anfrage trägt die PDF-Prüfsumme der Fassung, die
   der Kunde gesehen hat (abweichend → 409); Ankreuzfelder = Abschnitte mit `with_checkbox` aus `frozen_content`
   (Schlüssel `abschnitt-N`), alle ausdrücklich gesetzt, Teil des unterschriebenen Inhalts (kanonisches JSON mit
   Prüfsumme); Ergebnis: Unterschriftsblatt (PDF) in der Ablage. Alternativ Papier-Scan (am Inhalt erkannt wie der
   Beleg in 1.8.20) mit Datum und vom Büro übertragenen Ankreuzfeldern. Nur eine gültige, nicht abweichende Fassung
   (`deliverable_version()`). Status `unterschrieben`; danach keine neue Fassung.
3. **Nach der Unterschrift gesperrt** (Punkt 6): `change_order_contract_basis()` und `sync_order_from_source_quote()`
   (409), Karte "Quellangebot" ohne Übernehmen-Knopf, Karte "Vertragsgrundlage" ohne Ändern.
4. **Tests** (Punkt 8): Unterschrift gegen falsche Prüfsumme abgelehnt, Ankreuzfeld im unterschriebenen Inhalt,
   Sperren nach Unterschrift, Monteur 403; Klicktest mit Zeichnen über CDP-Zeigerereignisse.

### Nebenbefunde 1.8.33 (nur gemeldet)

1. **Lokaler Datenordner enthält 843 Briefpapier-Dateien aus alten Testläufen** (`data/document_layout_backgrounds`,
   11.–26.09., 69-Byte-PNGs und 23-KB-JPEGs): aus der Zeit vor der Test-Umlenkung in `tests/conftest.py` (Runde 0e).
   Harmlos, nur lokal; die beiden echten Dateien (104 KB, 11.09.) sind identisch.
2. **Der Anlage-Vergleich rendert das Angebot bei jedem Laden der Karte im Entwurf** (0,1–0,3 s gemessen) --
   bewusst, damit die Auswahl dem Stand beim Festschreiben entspricht; das Festschreiben prüft ohnehin erneut.
3. **Gleichzeitiges Festschreiben** ist über bedingtes UPDATE, Zeilensperre (PostgreSQL) und Unique-Schlüssel
   abgesichert, aber nicht mit zwei echten gleichzeitigen Anfragen getestet (nur nacheinander, auch gegen
   PostgreSQL).
4. Bekannt und unverändert: Textfelder der Auftragsseite in Festbreitenschrift (1.8.32 Nr. 3), "GP" der
   LV-Kopfzeile ragt bei 1400 px in die rechte Spalte (1.8.21 Nr. 5) -- beide auf den Klicktest-Bildern sichtbar.

---

## Umsetzung 1.8.34 (01.10.2026) -- Runde 2b-1b Teil 2b: Unterschrift unter dem Vertrag

Betreibervorgabe: (1) gemeinsame Unterschriftsvorlage für Checkliste, Einsatzbericht und Vertrag, Zeichenfläche in
beiden Themes hell mit dunklem Strich; (2) Unterschrift auf dem Gerät, Kunde und Betrieb, bindet die Prüfsumme der
festgeschriebenen Fassung, Ankreuzfelder setzt der Kunde und sie gehören zum unterschriebenen Inhalt, Ergebnis ein
Unterschriftsblatt in der Ablage; alternativ Papier-Scan mit Datum und vom Büro übertragenen Ankreuzfeldern; (3) danach
Vertragsgrundlage und Abgleich gesperrt, spätere Änderungen am Auftrag nur als Hinweis; (4) bei Verbrauchern
voraussichtliches Ende der Widerrufsfrist (14 Tage ab Unterschrift) mit Vermerk zum vorzeitigen Beginn; (5) Tests mit
Gegenprobe, Monteur 403, gleichzeitiges Festschreiben und Unterschreiben mit echten parallelen Anfragen gegen
PostgreSQL.

- **Gemeinsame Vorlage** (`app/templates/_unterschrift.html`): Regel `canvas.dk-unterschrift` (weiß, gestrichelter
  Rand in fester Farbe, `touch-action:none`, Höhe 170 px, die Seite darf sie überschreiben) und
  `unterschriftsfeld(canvas)` → `{leer(), leeren(), alsBlob(), alsDataUrl()}`: Zeigerereignisse mit
  `setPointerCapture`, Geräteauflösung (`devicePixelRatio`), Strich `#111`, PNG mit durchsichtigem Hintergrund wie
  bisher (auf dem PDF liegt es über dem Briefpapier). Checkliste (`setupPad()`/`clearPad()` sind nur noch Hüllen, IDs
  `pad_…`/`padName_…` unverändert, damit die Klicktests weiterlaufen), Einsatzbericht (`initSignaturePad()`,
  `#sigCanvas` 220 px, Monteur und Kunde nacheinander) und Vertragsdialog nutzen sie. Der Einsatzbericht zeichnet
  dadurch jetzt in Geräteauflösung (vorher CSS-Pixel) -- das PNG ist auf einem Tablet entsprechend größer.
- **Unterschrift auf dem Gerät** (`app/contract_signatures.py::sign_contract_on_device()`,
  `POST /api/orders/{id}/contract/sign`, JSON mit `version_id`, `pdf_sha256`, `checkboxes`, zwei Namen und zwei PNG
  als Base64): Sperre der Vertragszeile, danach alles frisch gelesen (`expire_all()`); abgelehnt (409), wenn der
  Vertrag nicht festgeschrieben oder schon unterschrieben ist, `version_id` nicht die gültige Fassung ist, die
  Prüfsumme nicht die ihres PDFs ist, das PDF in der Ablage nicht mehr unversehrt ist oder die Fassung nicht mehr zum
  Auftrag passt (`version_differences()`). Eingaben (400): Namen Pflicht, PNG am Inhalt erkannt, höchstens 2 MB, nicht
  leer (sichtbares Pixel bzw. bei deckendem Hintergrund ein dunkles). Ankreuzfelder = Abschnitte mit Ankreuzfeld aus
  dem eingefrorenen Inhalt (`checkbox_sections()`, Schlüssel `abschnitt-N`); jedes muss als true/false kommen
  (`StrictBool`, fehlend oder unbekannt 400). Ablage: beide PNG und das Unterschriftsblatt (Art `vertrag`, Dokument-ID
  = Vertrag, Nummer wie die Fassung). Unterschriftsblatt (`app/contract_pdf.py::render_signature_sheet_pdf()`, Rahmen
  `contract`): Kopf wie der Vertrag, Fassung mit Datum und Vertragsgrundlage, PDF-Prüfsumme der Fassung, Ankreuzfelder
  mit gezeichnetem Kreuz und "(angekreuzt)"/"(nicht angekreuzt)", zwei Unterschriften mit Namen, Zeitpunkt, erfasst von,
  Prüfsumme des unterschriebenen Inhalts.
- **Unterschriebener Inhalt** (`order_contract_signatures.signed_content`, kanonisches JSON wie die Fassung,
  `content_sha256`): Vertrag, Auftrag, Fassung (ID, Nummer, Inhalts- und PDF-Prüfsumme), Grundlage,
  Verbraucher-Merkmal der Fassung, Weg, Datum, je Ankreuzfeld Schlüssel/Überschrift/Text/Kennzeichen/Stand, Namen und
  SHA-256 der Bilder bzw. des Scans, erfasst wann und von wem. Die Karte prüft bei jedem Abruf die Prüfsumme und die
  Datei in der Ablage.
- **Papier** (`record_paper_signature()`, `POST /api/orders/{id}/contract/sign-paper`, multipart): Scan PDF/JPEG/PNG/WebP
  am Inhalt erkannt (`app/email_dispatch.py::receipt_content_type()`, bisher `_receipt_content_type`), höchstens 15 MB,
  Datum nicht in der Zukunft und nicht vor dem Festschreiben der Fassung, Ankreuzfelder als JSON wie oben, dieselbe
  Fassungsbindung. **Festlegung (bitte bestätigen): eine Abweichung vom Auftrag sperrt das Eintragen des Papiers nicht**
  -- der Kunde hat womöglich vor der Änderung unterschrieben; die Karte zeigt die Abweichung danach als Hinweis. Die
  Seite bietet die Ankreuzfelder als "angekreuzt"/"nicht angekreuzt" ohne Vorauswahl an (Regel 4).
- **Status "unterschrieben"** (`OrderContract.status`, `FROZEN_STATUSES` in `app/contract_versions.py`): keine neue
  Fassung, kein Festschreiben, kein zweites Unterschreiben (bedingtes UPDATE auf `festgeschrieben` plus Unique
  `contract_id`). `app/contract_basis.py::ensure_contract_not_signed()` sperrt die Vertragszeile und wirft
  `ContractSignedError` (409) in `change_order_contract_basis()` und `sync_order_from_source_quote()`. Seite: Karte
  "Quellangebot" ohne Übernehmen-Knopf mit Erklärung, Karte "Vertragsgrundlage" ohne Änderungsteil. Abweichungen der
  unterschriebenen Fassung erscheinen als Hinweis "der unterschriebene Vertrag bleibt gültig". **Festlegung (bitte
  bestätigen): die unterschriebene Fassung bleibt versendbar und zustellbar, auch bei späteren Abweichungen**
  (`deliverable_version()`), als Abschrift für den Kunden. Unterschriften sind unveränderlich (ORM-Sperre).
- **Widerrufsfrist** (`withdrawal_info()`): nur wenn die Fassung als Verbrauchervertrag festgeschrieben wurde.
  Tag der Unterschrift + 14 Tage; **Festlegung: fällt das Ende auf Samstag oder Sonntag, der Montag** (§ 193 BGB),
  Feiertage kennt das ERP nicht (die Karte sagt es, ebenso "gilt nur bei ordnungsgemäßer Widerrufsbelehrung").
  Vermerk zum vorzeitigen Beginn aus dem gekennzeichneten Ankreuzfeld. **Festlegung: neues Kennzeichen
  `contract_template_sections.early_start`** ("= Verlangen des vorzeitigen Beginns" im Vorlagen-Editor) statt einer
  Ableitung aus "nur bei Verbrauchern" + Ankreuzfeld -- eine Vorlage kann mehrere solche Ankreuzfelder haben (z. B.
  "Belehrung erhalten"). Nur an einem Ankreuzfeld "nur bei Verbrauchern", höchstens eins je Vorlage, **setzt die
  Prüfung nicht zurück** (ändert keinen Text im Vertrag). Eingefroren in der Fassung; Fassungen von vor 1.8.34 haben
  es nicht, dann sagt die Karte, dass kein Ankreuzfeld gekennzeichnet ist.
- **Gleichzeitigkeit**: Unterschreiben, Festschreiben, neue Fassung, Grundlage ändern und Abgleich sperren dieselbe
  Zeile (`SELECT … FOR UPDATE`); Statuswechsel zusätzlich bedingt; Unique an Fassung und Unterschrift. Getestet mit
  echten parallelen HTTP-Anfragen gegen PostgreSQL (eigene Verbindung je Anfrage, die ersten Sperren warten an einer
  Schranke aufeinander): zweimal Festschreiben → eine Fassung (schließt 1.8.33 Nebenbefund 3), dreimal
  Unterschreiben → eine Unterschrift, Unterschrift gegen "Neue Fassung" + Festschreiben → nie beides (beide Ausgänge
  kamen in fünf Runden vor), Unterschrift gegen Grundlage ändern → nie beides.
- **Rechte**: beide neuen Endpunkte ab `buero_auftrag`, Monteure 403; keine neue GET-Route (die Unterschrift steht im
  Vertragsstand, Blatt/Scan/Bilder über `/api/sent-documents/{id}/file`).
- **Migration `65e3431d5bb6`**: Tabelle `order_contract_signatures`, Spalte `early_start` (server_default falsch).
  `downgrade()` verweigert bei einer Unterschrift, einem unterschriebenen Vertrag oder einem gekennzeichneten
  Abschnitt.
- **Verifikation**: `tests/test_v337_vertrag_unterschrift.py` (17 Tests: Bindung an Fassung und PDF, Ankreuzfeld im
  Inhalt und auf dem Blatt, falsche/abgelöste/entworfene/abweichende/beschädigte Fassung abgelehnt, leere und
  ungültige Bilder, Papier mit Datum und übertragenen Ankreuzfeldern, Sperren nach der Unterschrift mit Gegenprobe am
  nicht unterschriebenen Auftrag, Nachtrag bleibt möglich und Abschrift versendbar, Widerrufsfrist und Wochenende,
  Kennzeichen-Regeln, Monteur 403, Unveränderlichkeit, gemeinsame Zeichenfläche in den drei Seiten, Migration, vier
  PostgreSQL-Paralleltests). Gegenproben (Schutz im Code ausgehebelt, Test rot, Datei byte-genau zurück, Skript im
  Scratchpad): 27 rot -- falsche Prüfsumme angenommen, Fassungsbindung ganz weg, abweichende Fassung unterschreibbar,
  beschädigte Ablage nicht erkannt, Ankreuzfelder nicht im Inhalt, fehlendes Ankreuzfeld still "nicht angekreuzt",
  leere Unterschrift, Blatt ohne Ankreuzfelder, Grundlage bzw. Abgleich nach der Unterschrift möglich, neue Fassung
  danach (Statusprüfung UND bedingtes UPDATE ausgehebelt -- jede allein hält), Papier vor dem Festschreiben datiert,
  Scan ohne Inhaltserkennung, Monteur darf, Unterschrift änderbar/löschbar, Widerrufsfrist ohne Wochenende, Vermerk
  fehlt, Kennzeichen ohne Ankreuzfeld, Kennzeichen nicht eingefroren, Downgrade ohne Schutz, Einsatzbericht ohne
  gemeinsame Vorlage, Fläche dunkel; gegen PostgreSQL: Unterschrift ohne Sperre und mit unbedingtem Statuswechsel
  ([200, 500, 500] statt [200, 409, 409]), Festschreiben ebenso (zwei Fassungen), Unterschrift gewinnt gegen eine neue
  Fassung, Grundlage ändern ohne Sperre (Unterschrift und Änderung gehen beide durch). Migration SQLite (Kommandozeile hin/zurück/hin, `alembic check`) und
  PostgreSQL 17 (Wegwerf-Schema: Kette bis `091e7f52649b`, Bestand mit Ankreuzfeld, upgrade, Constraints, Unterschrift
  über den App-Code, Sperren, drei Downgrade-Abbrüche, downgrade, upgrade, `alembic check`). Volle Suite 2440 grün (mit den opt-in-Tests gegen PostgreSQL).
  Klicktest `scripts/klicktest_vertrag_unterschrift.py` 43/43 (Dialog dunkel: Fläche weiß, Strich dunkel, ohne
  Zeichnung abgewiesen; Unterschrift mit Ankreuzfeld, Karte, Widerrufsfrist, Blatt-Prüfsumme, Sperren; Papier mit
  Datei über `DOM.setFileInputFiles`, 412 px; Checkliste und Einsatzbericht über die gemeinsame Fläche; hell;
  Kennzeichen im Vorlagen-Editor als Administratorin; Monteur 403). Unverändert grün:
  `klicktest_checkliste_unterschrift.py` 24/24, `klicktest_checkliste_abschnitte.py` 25/25,
  `klicktest_checkliste_verwerfen.py` 23/23, `klicktest_vertrag_festschreiben.py` 40/40,
  `klicktest_vertragsvorlagen.py` 36/36.

### Nebenbefunde 1.8.34 (nur gemeldet)

1. *(Erledigt in 1.8.35: unterschriebene Abschrift, siehe unten.)* **Das Unterschriftsblatt geht nicht per E-Mail hinaus**: der Versand schickt die Fassung (ein Anhang), das Blatt
   liegt in der Ablage und ist an der Karte abrufbar. Eine Abschrift mit Unterschrift für den Kunden (bei
   Verbrauchern womöglich Pflicht, Bestätigung des Vertrags auf einem dauerhaften Datenträger) bräuchte einen Versand
   mit zwei Anhängen oder ein zusammengeführtes, eigens abgelegtes PDF -- fachlich zu entscheiden.
2. *(Erledigt in 1.8.35.)* **Die Berichtsunterschrift hat serverseitig keine Größengrenze** (`app/routers/service_reports.py::
   _decode_signature_png()`), anders als Checkliste und Vertrag (2 MB). Mit der Geräteauflösung werden die PNG auf
   einem Tablet größer (typisch einige zehn KB), kein akutes Problem.
3. *(Erledigt in 1.8.35 für die Auftragsseite.)* **422-Fehler der Auftragsseite erscheinen als "[object Object]"**: `api()` in `order.html` reicht die Feldliste
   einer Pydantic-Ablehnung unverändert an `Error()` weiter (vorbestehend, betrifft alle Formulare der Seite).
4. Bekannt und unverändert: "GP" der LV-Kopfzeile ragt bei 1280–1400 px in die rechte Spalte (1.8.21 Nr. 5), dazu ein
   waagrechter Scrollbalken der Auftragsseite bei 1280 px -- auf den Klicktest-Bildern sichtbar.
5. **Ein PostgreSQL-Test, der mit offener Sitzung scheitert, hängt beim Aufräumen**: `DROP SCHEMA` wartet auf die
   Sperren der Sitzung ("idle in transaction"). Im ersten Gegenprobenlauf so passiert (eigenen pytest-Prozess über
   die PID beendet, Restschema entfernt); die neue Fixture schließt deshalb alle Sitzungen und beendet die eigenen
   Verbindungen über `application_name`. Die älteren opt-in-PostgreSQL-Tests (`test_v297`, `test_v322`, `test_v323`)
   räumen nicht so auf -- solange sie grün sind, unschädlich.

---

## Umsetzung 1.8.35 (01.10.2026) -- Abrundung: unterschriebene Abschrift, Grenze im Einsatzbericht, Fehler

Betreibervorgabe: (1) nach der Unterschrift ein PDF aus Fassung und Unterschriftsblatt mit eigener Prüfsumme in der
Ablage, der Versand nach der Unterschrift verschickt diese Abschrift (§ 312f BGB: Abschrift des unterzeichneten
Vertrags bei Verbrauchern außerhalb von Geschäftsräumen); (2) Unterschrift im Einsatzbericht serverseitig höchstens
2 MB wie Checkliste und Vertrag, Test mit Gegenprobe; (3) Auftragsseite: Fehlermeldungen (422, 409) lesbar statt
"[object Object]". Erledigt damit die Nebenbefunde 1–3 aus 1.8.34.

- **Abschrift** (`app/contract_signatures.py`, `OrderContractSignature.copy_document_id`): in derselben Transaktion
  wie die Unterschrift `merge_pdfs([Fassung, Unterschriftsblatt])` (pypdfium2, Seiten unverändert übernommen) als
  neues PDF in der Ablage, Art `vertrag`, Dokument-ID = Vertrag, Nummer "AUF-… · Fassung N · unterschrieben", Datei
  `Vertrag_…_Fassung_N_unterschrieben.pdf`. Die Historienzeile "Vertrag unterschrieben" nennt ihre Prüfsumme.
  **Festlegung (bitte bestätigen): auf Papier = Fassung + Scan** -- ein Scan-PDF mit allen Seiten, ein Foto als eigene
  A4-Seite (hoch oder quer wie das Bild, 10 mm Rand, nach EXIF gedreht, ein JPEG ohne Drehung ohne Neukodierung
  eingebettet, sonst JPEG mit Durchsichtigem auf Weiß). Enthält der Scan schon den ganzen Vertrag, steht der Text zweimal darin;
  dafür ist die Abschrift auch dann vollständig, wenn nur die Unterschriftsseite gescannt wurde. **Folge: ein
  Scan-PDF muss sich öffnen lassen** (`scan_pages()`, vorher genügte der Anfang `%PDF-`), sonst 400 ohne Ablage.
  Gemessen: ein JPEG von 1,39 MB ergibt eine Seite von 1,74 MB (reportlab schreibt die Bilddaten ASCII85-kodiert,
  rund ein Viertel mehr). Ein Handyfoto von einigen MB hebt die Abschrift damit leicht über 3 MB -- dann warnt die
  Karte wie bei der Fassung (`copy_too_large`), Zustellung auf anderem Weg (siehe Nebenbefund 5).
- **Versand und Zustellung** (`app/contract_versions.py::deliverable_document()`): festgeschrieben die Fassung, nach
  der Unterschrift die Abschrift -- für `send_contract_email()` und die nachgetragene Zustellung
  (`app/dispatch_documents.py`, Bezeichnung "…, Fassung N, unterschrieben"). Verwiesen, nicht noch einmal abgelegt.
  Der Zustand wird weiter zuerst geprüft (409), bevor Empfänger und Abschrift drankommen. `GET …/contract/pdf` liefert
  weiter die Fassung (sie liest der Kunde vor dem Unterschreiben); die Abschrift über ihren Link
  (`/api/sent-documents/{id}/file`). Die E-Mail-Vorlage `contract` ist unverändert ("anbei erhalten Sie den Vertrag …
  (Fassung N) mit unserem Angebot als Anlage") -- passt weiterhin, nennt die Unterschrift aber nicht.
- **Unterschriften von vor 1.8.35** (`ensure_signed_copy()`): ohne Abschrift, bis der erste Versand oder die erste
  nachgetragene Zustellung sie erzeugt -- aus Fassung und Blatt bzw. Scan in der Ablage (beide nur mit stimmender
  Prüfsumme, sonst 409 bzw. 400 und nichts versendet). Unter der Vertragssperre, eingetragen als bedingtes UPDATE von
  leer; Historie "Unterschriebene Abschrift nachgeholt". Die ORM-Sperre der Unterschrift bleibt unverändert streng
  (auch `copy_document_id` über das ORM: ArchiveImmutableError). **Festlegung: kein Nachholen beim bloßen Anzeigen**
  (GET bleibt lesend) und keins in der Migration (sie liest keine Dateien der Ablage); die Karte sagt "noch nicht
  erzeugt – entsteht beim ersten Versand".
- **Karte** (`order.html`): Zeile "Unterschriebene Abschrift: Prüfsumme … · Größe · Abschrift öffnen" im Block der
  Unterschrift, Prüfung der Datei bei jedem Abruf wie beim Blatt; Versandblock "Unterschriebene Abschrift (Fassung N)
  per E-Mail senden", Knopf "Abschrift senden"; Größenwarnung nach der Unterschrift für die Abschrift.
  Versandverlauf (`_email_dispatch.html`): alles nach der Auftragsnummer, also "Fassung N · unterschrieben".
- **Einsatzbericht** (`app/service_reports.py::sign_report()`): je Bild höchstens 2 MB (`MAX_SIGNATURE_PNG_BYTES`),
  geprüft direkt nach dem Status, vor allen Vollständigkeitsprüfungen und bevor eine Datei geschrieben wird
  (400 "Die Unterschrift des Monteurs/des Kunden ist zu groß").
- **Fehlermeldungen** (`app/templates/_fehlertext.html`, `fehlerText(body, status, felder)`): `detail` als Text
  unverändert; als Liste (422) "Bitte die Eingabe prüfen – <Feld> <Art>." mit deutscher Art je Pydantic-Fehlertyp
  (fehlt, ist kein gültiges Datum, muss eine Zahl sein (ohne Tausenderpunkt), ist zu kurz …), unbekannter Typ mit der
  Originalmeldung, Feld über `FELDNAMEN` der Seite (sonst der API-Name); als Objekt dessen `message`; ohne
  verwertbares `detail` ein Text je Status (409 "Der Stand hat sich inzwischen geändert …", 5xx "Serverfehler").
  Eingebunden nur in `order.html` (`api()`); alle Aufrufe der Seite laufen darüber, außer dem E-Mail-Versand
  (`postEmailDispatch()` hatte schon eigene Texte).
- **Migration `71460718a43e`**: eine Spalte mit benanntem Fremdschlüssel. `downgrade()` verweigert, solange eine
  Abschrift zugeordnet ist, und entfernt die Spalte ohne `drop_constraint` (PostgreSQL entfernt den Fremdschlüssel mit
  der Spalte, SQLite baut neu) -- so läuft er auch gegen ein Schema aus `create_all()`.
- **Verifikation**: `tests/test_v338_vertrag_abschrift.py` (10 Tests: Abschrift = Fassung + Blatt, Text und
  Seitenzahl; Versand und Zustellung danach mit der Abschrift, vorher mit der Fassung, nichts neu abgelegt; Papier mit
  zweiseitigem PDF, gedrehtem Foto, durchsichtigem PNG, kaputtem PDF; Nachholen genau einmal und nicht aus beschädigter
  Ablage; ORM-Sperre; Migration; gleichzeitiges Nachholen gegen PostgreSQL; Berichtsunterschrift an und über der
  Grenze; `api()` der Auftragsseite in node mit echten 422-/409-Antworten der App; Einbindung). `test_v337` nutzt
  jetzt ein echtes Scan-PDF. Gegenproben (Schutz im Code ausgehebelt, Test rot, Datei byte-genau zurück, Skript im
  Scratchpad): 19 rot -- Abschrift nur aus der Fassung, Versand bzw. Zustellung mit der Fassung, Foto ohne Drehung,
  Durchsichtiges auf Schwarz, Scan-PDF ungeprüft, kein Nachholen, Nachholen aus beschädigter Ablage, ohne Zeilensperre
  bzw. ohne Sperre und unbedingt (PostgreSQL), ORM-Sperre gelockert, Downgrade ohne Schutz, Schema ohne Abschrift,
  Historie ohne Prüfsumme, Bericht ohne Grenze, altes `api()`, ohne Feldnamen, Objekt-`detail` ignoriert, ohne
  Einbindung. `test_v336`–`test_v338` zusätzlich gegen PostgreSQL 17 (Wegwerf-Schema je Test, Scratchpad-Plugin):
  46 grün. Migration: SQLite (Kommandozeile hin/zurück/hin, Fremdschlüssel, `alembic check`) und PostgreSQL
  (Wegwerf-Schema: Kette bis `65e3431d5bb6`, upgrade, Fremdschlüssel mit Namen, Unterschrift mit Abschrift über den
  App-Code, Downgrade-Abbruch, downgrade mit Bestand, upgrade auf Bestand, Nachholen über den App-Code,
  `alembic check`). Volle Suite 2448 grün, 2 rot -- `test_v321::test_field_responses_carry_nothing_from_the_dispatch` und `test_v326::test_monteur_endpunkte_liefern_200_und_alle_anderen_403`, beide nach 19 Uhr (Feierabend, 401 an `/api/field-view/today`), auf dem unveränderten Stand 1.8.34 in einem eigenen Worktree um 19:39 ebenso rot. Klicktest `scripts/klicktest_vertrag_abschrift.py` 26/26 (Abschrift auf
  der Karte mit Prüfsumme wie in der Ablage, Versand an SMTP-Empfänger im Skript mit Anhang = Abschrift, Verlauf
  "Fassung 1 · unterschrieben"; ältere Unterschrift nachgeholt; Papier-Foto dunkel 412 px; 422 Auftragsdatum und
  Abschlag, 409 auf veralteter Seite; Monteur 403). `klicktest_vertrag_unterschrift.py` 43/43 (echtes Scan-PDF, neue
  Überschrift, Feierabend-Grenze im Bestand), `klicktest_versandverlauf.py` 32/32, `klicktest_vertrag_festschreiben.py`
  39/40 (Monteur-Prüfung abends 401, siehe Nebenbefund 3).

### Nebenbefunde 1.8.35 (nur gemeldet)

1. **36 weitere Vorlagen reichen `detail` roh an `Error()` weiter** (Muster `….detail||r.statusText`), darunter
   `_checklists_section.html`, das auch auf der Auftragsseite steckt ("Checkliste starten"): eine 422 erscheint dort
   weiter als "[object Object]". `fehlerText()` steht bereit; Umstellung je Seite mit ihren `FELDNAMEN`.
2. **`make_order_with_item()` (`tests/test_v133_invoices.py`) legt einen Auftrag mit `source_quote_id=1` ohne
   Angebot an** -- unter PostgreSQL scheitert das am Fremdschlüssel; die 39 Testdateien, die den Helfer nutzen, laufen
   so nur unter SQLite. Aufgefallen beim PostgreSQL-Lauf der neuen Tests (dort jetzt echte Beauftragung).
3. **Klicktests mit Monteur über `/mobil` hängen von der Uhrzeit ab**: nach `MobileSettings.shift_end_time` (Vorgabe
   19:00) meldet `/mobil` den Monteur ab, die folgende 403-Prüfung sieht 401. In `klicktest_vertrag_unterschrift.py`
   und dem neuen Klicktest steht die Grenze im Bestand jetzt auf 23:59; `klicktest_vertrag_festschreiben.py` hat es
   noch (abends 39/40). **Dasselbe in pytest**: `test_v321::test_field_responses_carry_nothing_from_the_dispatch` und
   `test_v326::test_monteur_endpunkte_liefern_200_und_alle_anderen_403` rufen `/api/field-view/today` als Monteur auf
   und sind nach 19 Uhr (Europe/Berlin) rot (401 "Feierabend") -- eine volle Suite am Abend ist deshalb nie ganz grün.
   Abhilfe: in beiden Tests `shift_end_time` setzen oder die Uhr festhalten. **Behoben in 1.8.36** (feste Uhr in
   pytest und Klicktests, siehe "Umsetzung 1.8.36").
4. Bekannt und unverändert: "GP" der LV-Kopfzeile ragt bei 1280 px in die rechte Spalte, waagrechter Scrollbalken der
   Auftragsseite bei 1280 px (1.8.21 Nr. 5, 1.8.34 Nr. 4).
5. **Ein Papier-Scan als Handyfoto macht die Abschrift oft zu groß für die E-Mail**: der Scan darf 15 MB haben, die
   Versandgrenze ist 3 MB, und die Bildseite ist durch ASCII85 ein Viertel größer als das Foto. Abhilfe wäre, das
   Foto für die Abschrift zu verkleinern (z. B. auf 150 dpi bei A4) oder ohne ASCII85 einzubetten -- fachlich zu
   entscheiden, ob die Abschrift dann noch "das Papier" ist; der Scan selbst bleibt ohnehin unverändert in der Ablage.

---

## Umsetzung 1.8.36 (02.10.2026) -- Runde 2b-2, Punkt 0: feste Uhr für uhrzeitabhängige Tests

Betreibervorgabe: die uhrzeitabhängigen Tests (`test_v321`, `test_v326` und die Klicktests mit Feierabend-Grenze)
laufen mit fester Uhr über `berlin_time`, unabhängig von der Tageszeit; Gegenprobe Uhr auf 19:30 → weiter grün.
Behebt Nebenbefund 3 aus 1.8.35.

- **pytest** (`tests/uhr.py::uhr_festhalten(uhrzeit=10:00)`): ersetzt `app.berlin_time._utc_now` (die eine Uhr der
  App, Regel 20) durch eine laufende Uhr ab heute 10:00 Europe/Berlin; "heute" kommt von der Uhr davor. Laufend
  statt stehend, damit Dauer und Reihenfolge innerhalb eines Tests stimmen. Fixture `feste_uhr` (conftest) für
  einen Test; `test_v326` setzt sie in der Modul-Fixture `durchlauf` als Kontext (eine Modul-Fixture kann keine
  Funktions-Fixture nutzen). `test_v321::test_field_responses_carry_nothing_from_the_dispatch` nimmt die Fixture.
  Gespeicherte Zeitstempel (`datetime.utcnow()`) laufen weiter mit der echten Zeit.
- **Gegenprobe ohne Warten auf den Abend**: `pytest --wanduhr HH:MM` (conftest, sitzungsweite Autouse-Fixture) lässt
  die Suite laufen, als wäre es heute HH:MM -- eine feste Uhr setzt sich darüber. Vor der Umstellung mit
  `--wanduhr 19:30` genau die beiden bekannten Tests rot (401 "Feierabend"), mit `--wanduhr 10:00` grün; danach
  beide grün.
- **Klicktests** (`scripts/cdp_klicktest.py`): `klicktest_main(..., uhr="10:00")` -- die Uhr gilt im Befüllen-Prozess
  und im Server der Instanz. Der Server startet dafür als `cdp_klicktest.py --server-mit-uhr` (uvicorn im selben
  Prozess wie die gesetzte Uhr; `python -m uvicorn` hätte sie nicht). Beide Prozesse rechnen von derselben Marke
  (Startzeit in UTC + echte Zeit des Augenblicks, Umgebungsvariable `KLICKTEST_UHR`) weiter, die Uhr springt
  zwischen ihnen nicht zurück. `--wanduhr HH:MM` täuscht wie bei pytest eine Uhrzeit vor; ein Skript mit `uhr=`
  bleibt bei seiner. Ohne beides unverändert `python -m uvicorn`. Die Uhr des Browsers bleibt echt.
- **Die drei Vertrags-Klicktests** (`festschreiben`, `unterschrift`, `abschrift`) öffnen `/mobil` als Monteur und
  setzen `uhr="10:00"`; der Notbehelf "Grenze im Bestand auf 23:59" entfällt. Nur `mobil.html` ruft
  `/api/field-view/today` auf -- `/mobil/stundenzettel` (`klicktest_zeitbuchungen_liste.py`) ist nicht betroffen.
- **Tests** (`tests/test_v339_feste_uhr.py`, 6): am echten Endpunkt abends (vorgetäuscht 19:30) 401, mit fester Uhr
  darüber 200, danach wieder 401; feste Uhr nimmt das Datum der Uhr davor; Klicktest-Marke setzt die Uhr der App,
  ohne Marke bleibt die echte; jeder `scripts/klicktest_*.py`, der `/mobil` öffnet, setzt `uhr=` und keiner setzt
  die Feierabend-Grenze im Bestand (Gegenprobe: `uhr=` in `klicktest_vertrag_festschreiben.py` entfernt → rot).
- **Verifikation**: volle Suite 2456 grün (vormittags). Gegenprobe mit `--wanduhr 19:30`: vor der Umstellung
  `test_v321::test_field_responses_carry_nothing_from_the_dispatch` und
  `test_v326::test_monteur_endpunkte_liefern_200_und_alle_anderen_403` rot, danach `test_v321`, `test_v326`, `test_v339`
  79 grün. Klicktests mit fester Uhr: `klicktest_vertrag_festschreiben.py` 40/40, `klicktest_vertrag_unterschrift.py`
  43/43, `klicktest_vertrag_abschrift.py` 26/26; Festschreiben mit `--wanduhr 19:30` 40/40, derselbe Klicktest ohne
  feste Uhr (Wrapper im Scratchpad) bei 19:30 39/40 -- "Monteur: Vertrag per API gesperrt" 401 statt 403, genau der
  alte Abendfehler.

---

## Umsetzung 1.8.37 (02.10.2026) -- Runde 2b-2: Beteiligte mit Adressbuch

Betreibervorgabe: (1) Adressbuch als Stammdatenbereich (Regel 10): Kontakt als Person oder Firma mit Funktion,
Telefon, Mobil, E-Mail und Adresse; Archivieren statt Löschen, sobald ein Kontakt in einem Projekt verwendet wird; in
der Büro-Suche. (2) Beteiligte am Projekt: Projekt--Kontakt--Rolle, Rollen fest im Code, eindeutig je Projekt,
Kontakt und Rolle; Häkchen "Kopie bei Anzeigen" und "empfangsbevollmächtigt für den Auftraggeber" (Vollmacht als
Beleg hochladbar); der Kunde bleibt Auftraggeber und wird nicht zusätzlich geführt. (3) Reiter "Beteiligte" nach dem
Muster des Termine-Reiters, beim Hinzufügen erst suchen, dann neu anlegen. (4) Nur Büro, Monteur 403, Datengrenze-Test
deckt die neuen Routen ab. (5) Tests mit Gegenprobe. Kern, kein Modul.

- **Adressbuch** (`app/contacts.py`, Tabelle `contacts`, rollenlos): `kind` "person" (Nachname Pflicht, Vorname und
  Firma der Person optional) oder "firma" (Firmenname Pflicht, Namen leer); Funktion, Telefon, Mobil, E-Mail, Straße,
  PLZ, Ort; `archived`/`archived_at`. Anzeigename Person "Vorname Nachname", Firma der Firmenname. Eine Suche
  (`contact_search_filter()`: Name, Firma, Funktion, Telefon, Mobil, E-Mail, Ort, "Vorname Nachname") für Liste,
  Auswahl in der Projektmappe und Büro-Suche; sortiert nach Nachname bzw. Firmenname, dann Vorname.
  **Festlegungen (nicht vorgegeben, bitte bestätigen)**: keine Anrede/kein Titel (nicht verlangt -- für ein Anschreiben
  in 2b-3 womöglich nötig); Archivieren geht immer, Löschen nur ohne Projekt (409 "… in N Projekten eingetragen …
  bitte archivieren"; gleichzeitiges Eintragen hält unter PostgreSQL der Fremdschlüssel, die Geschäftslogik meldet
  dasselbe); ein archivierter Kontakt fehlt in der Auswahl beim Hinzufügen, lässt sich keinem Projekt neu zuordnen
  (400 "archiviert – bitte erst wiederherstellen") und bleibt in seinen Projekten stehen, gekennzeichnet; die
  Büro-Suche findet auch archivierte, im Untertitel "archiviert".
- **Stammdaten** (Regel 10): `master_data.html` Bereich "Adressbuch" (nach Lieferanten), Liste zuerst mit Name/Firma,
  Art, Funktion, Telefon/E-Mail, Ort, Anzahl Projekte, Status; "Archivierte auch anzeigen"; Bearbeiten, Archivieren/
  Wiederherstellen, Löschen nur bei Kontakten ohne Projekt. Anlegen und Bearbeiten auf `master_data_form.html`
  (`contactForm()`, Person/Firma umschaltbar), beim Bearbeiten darunter "Eingetragen in Projekten" mit Rolle und Link
  in den Reiter. Seitenrouten `/master-data/contacts/new|{id}/edit` wie die übrigen Bereiche (Büro).
- **Beteiligte** (`app/project_participants.py`, Tabelle `project_participants`, Zusatztabelle ohne Relationship am
  Projekt, Regel 6): `role` aus `ROLES`, fest im Code -- `architekt_planer` "Architekt/Planer", `bauleitung_ag`
  "Bauleitung des Auftraggebers", `hausverwaltung`, `eigentuemer`, `sachverstaendiger` "Sachverständiger/Gutachter",
  `versicherung`, `anderes_gewerk` "Anderes Gewerk", `sonstiges`; die Schlüssel stehen in der Datenbank und werden
  nie umbenannt. UNIQUE `(project_id, contact_id, role)`: derselbe Kontakt darf in einem Projekt zwei Rollen haben
  und dieselbe Rolle in mehreren Projekten. Doppelt: Vorprüfung (409 mit Text), bei gleichzeitigen Anfragen der
  Constraint im SAVEPOINT (Muster Self-Seeding), beim Rollenwechsel der Constraint beim Commit. Keine Rolle
  "Auftraggeber": der Kunde ist kein Kontakt des Adressbuchs.
- **Häkchen und Vollmacht**: `copy_on_notices` und `authorized_recipient` unabhängig, einzeln änderbar (Teil-Update,
  Regel 22). Vollmacht als Beleg (`poa_*`: Dateiname, Art, Größe, SHA-256, Zeitpunkt, wer) unter
  `DACHKONZEPTE_PARTICIPANT_FILE_ROOT` (Vorgabe `ERP_DATA_DIR/participant_documents`, in `.env.example`), am Inhalt
  erkannt wie der Beleg einer Zustellung (PDF, JPEG, PNG, WebP), höchstens 15 MB. **Festlegungen (bitte bestätigen)**:
  Hochladen nur mit gesetzter Empfangsvollmacht (400); wird das Häkchen später entfernt, bleibt der Beleg (ein
  Dokument, keine Einstellung) und lässt sich ausdrücklich entfernen; Ersetzen löscht die alte Datei; der Beleg liegt
  nicht in der unveränderlichen Ablage -- für 2b-3 zu entscheiden, ob eine Anzeige an einen Bevollmächtigten die
  Vollmacht dieses Zeitpunkts einfrieren soll.
- **Reiter "Beteiligte"** (`project_folder.html`, `sec-participants`, nach "Termine", ohne Modul-Gate): oben der
  Kunde als "Auftraggeber" (nur Anzeige, "Kunde öffnen"), darunter je Beteiligtem Name, Funktion/Firma, Telefon/
  Mobil/E-Mail, Adresse, Rolle als Auswahl (speichert beim Wechsel), beide Häkchen, Vollmacht (öffnen, ersetzen,
  entfernen), "Kontakt bearbeiten", "Aus dem Projekt entfernen". "+ Beteiligten hinzufügen" öffnet einen Dialog:
  Suchfeld mit Fokus, Treffer aus dem Adressbuch (ohne Archivierte, je Treffer "bereits als …"), dann Rolle (Pflicht)
  und Häkchen. **Neu anlegen** über "Neuen Kontakt im Adressbuch anlegen" -- die Formularseite des Adressbuchs (ein
  Formular für den Kontakt, Regel 10), Suchtext als Nachname vorbelegt; nach dem Speichern zurück in die Projektmappe
  (`?kontakt=<id>#sec-participants`), der Dialog öffnet mit dem neuen Kontakt, die Adresse wird bereinigt.
- **Projekt löschen** (`delete_project()`): löscht die Beteiligten (vor dem Projekt geflusht, Fremdschlüssel) und nach
  dem Commit ihre Belege; die Kontakte bleiben. **Festlegung**: Kopieren/Mustervorgang übernimmt keine Beteiligten
  (projektbezogen).
- **Historie** (`app/audit.py`): "Kontakt (Adressbuch)" und "Projektbeteiligter" (Bezeichnung "Name · Rolle", mit
  `project_id` -- erscheint im Reiter Historie der Projektmappe). Ein Rollenwechsel steht mit Beschriftungen da
  ("Hausverwaltung → Eigentümer"), nicht mit den Schlüsseln.
- **Büro-Suche**: Quelle `contacts` "Adressbuch" (19. Quelle, nach Lieferanten), Treffer auf die Formularseite;
  `search_results.html` und die Vollständigkeitstests nachgezogen.
- **Rechte**: alle 15 Routen (`app/routers/contacts.py`, `app/routers/project_participants.py`)
  `require_min_role(ROLE_OFFICE_AUFTRAG)`. Datengrenze-Test: `contact_id`/`participant_id` in `PFAD_WERTE`, neue
  Prüfung, dass der Durchlauf die fünf GET-Routen als Monteur aufruft und jede 403 liefert.
- **Fehlermeldungen**: `project_folder.html`, `master_data.html` und `master_data_form.html` lesen abgelehnte Antworten
  jetzt über `fehlerText()` (Architekturentscheidung 1.8.35: eine angefasste Seite stellt um), mit Feldnamen der Seite.
- **Migration `d99494185ce7`**: zwei neue Tabellen (Vorgaben `kind` 'person', Häkchen und `archived` falsch),
  UNIQUE mit Namen `uq_project_participant`, Fremdschlüssel auf `projects` und `contacts`. `downgrade()` bricht ab,
  solange eine der Tabellen Zeilen hat.
- **Verifikation**: `tests/test_v340_beteiligte_adressbuch.py` (18 Tests, einer gegen PostgreSQL 17 im Wegwerf-Schema:
  zwei gleichzeitige gleiche Zuordnungen -- genau eine angelegt, die andere abgelehnt; Kontakt in Verwendung nicht
  löschbar, auch roh per SQL am Fremdschlüssel; Projekt mit Beteiligtem löschbar). Gegenproben (Skript im Scratchpad,
  Datei byte-genau zurück): 14 rot -- Löschen ohne Verwendungsprüfung, archivierter Kontakt zuordenbar, Eindeutigkeit
  ohne Projekt, ohne Constraint, ohne SAVEPOINT, Rollenwechsel ohne Prüfung und Abfangen, Adressbuch bzw. Beteiligte
  für Monteure offen (auch `test_v326` rot), Projekt löschen ohne Beteiligte, Vollmacht ohne Empfangsvollmacht bzw.
  ohne Inhaltsprüfung, Adressbuch nicht in der Suche, Teil-Update übernimmt alles (auch `test_v329` rot). Die
  Rolle in der Historie als Schlüssel (14. Probe, rot). Die
  Vorprüfung beim Rollenwechsel allein auszuhebeln bleibt grün -- der Constraint beim Commit hält, die Vorprüfung ist
  nur der Weg zur Meldung. Migration: SQLite und PostgreSQL (ganze Kette im leeren Schema) hin, Bestand über den
  App-Code, Downgrade verweigert, leer zurück, hin, `alembic check`. JS der geänderten Seiten mit `node --check`
  (gerendert über die Seitenrouten). Volle Suite 2475 grün. Klicktest `scripts/klicktest_beteiligte.py` 43/43 (der
  erste Lauf fand zwei Fehler der Oberfläche: Häkchen im Dialog erbten `width:100%` aus `.field input`, die
  Adressbuch-Tabelle hatte mit zehn Spalten einen waagrechten Scrollbalken -- beide behoben, jetzt geprüft).

### Nebenbefunde 1.8.37 (nur gemeldet)

1. **Häkchen in der Stammdatenliste 260 px breit**: `master_data.html` setzt global `input{min-width:260px}`, das trifft
   auch die Häkchen "Archivierte auch anzeigen" (Leistungs-, Materialkataloge) und "Hauptadressen anzeigen" (Objekte);
   die Beschriftung steht dadurch weit rechts (im Browser gemessen: 260 px, beim Adressbuch mit `min-width:0` 13 px).

---

## Umsetzung 1.8.38 (02.10.2026) -- Runde 2b-3 Teil 1: Behinderungsanzeige erfassen

Betreibervorgabe: (1) Zweck `behinderungsanzeige` mit Systemfeldern in drei Abschnitten -- Meldung (bekannt seit als
Datum und Uhrzeit, Beschreibung, Fotos, Unterschrift des Meldenden), Anzeige (Ursache als Auswahl: fehlende Vorleistung
eines anderen Gewerks, fehlende Pläne oder Freigaben, Zugang oder Gerüst, vom Auftraggeber zu lieferndes Material,
außergewöhnliche Witterung, Sonstiges -- mit Beschreibung; betroffene Leistungen, Beginn, voraussichtliche Dauer,
Unterschrift Büro; bei Witterung der Hinweis "übliche Witterung ist nach § 6 Abs. 2 VOB/B keine Behinderung"), Wegfall
(beendet am, Arbeit wieder aufgenommen am, Unterschrift). (2) Startvorlage als Entwurf, startbar am Auftrag im Büro und
in `/mobil`. (3) Folgen auch nach der Unterschrift eines bestimmten Abschnitts, idempotent; nach der Unterschrift der
Meldung Aufgabe "Behinderungsanzeige versenden", fällig am selben Tag, an den Sachbearbeiter, sonst ohne Zuständigkeit.
(4) Tagesbericht "Behinderung = ja" legt stattdessen eine Aufgabe mit Link zum Anlegen an, keine doppelten. (5) Tests mit
Gegenprobe. Brief-PDF und Versand: Teil 2. Modul `checklisten` (Kern der Stufe 2b nur fachlich, technisch Checkliste).

- **Registry** (`app/checklist_purposes.py`, Herleitung des Zweck-Mechanismus in `docs/archiv/modul-checklisten.md`,
  "Umsetzung 1.8.16"): `OBSTRUCTION_SYSTEM_FIELDS`, Schlüssel `behinderungsanzeige.<name>` (`bekannt_seit`,
  `beschreibung`, `fotos`, `unterschrift_meldung`, `ursache` mit Optionen `vorleistung`, `plaene_freigaben`,
  `zugang_geruest`, `material_ag`, `witterung`, `sonstiges`, `ursache_beschreibung`, `betroffene_leistungen`, `beginn`,
  `dauer`, `unterschrift_buero`, `beendet_am`, `wieder_aufgenommen_am`, `unterschrift_wegfall`) -- die Schlüssel stehen
  in der Datenbank und werden nie umbenannt. Neu an `SystemField`: `section` (Abschnitt), `office_only`, `option_hints`,
  dazu `multiline`/`signer_label` als Vorschläge beim Anlegen; an `FollowUp`: `after_signature`.
- **Abschnitte geprüft**: `section_order_problem()` -- beim Veröffentlichen müssen die Systemfelder in der Reihenfolge
  ihrer Abschnitte stehen, jede Unterschrift am Ende ihres Abschnitts; innerhalb eines Abschnitts und für gewöhnliche
  Felder bleibt die Reihenfolge frei. **Festlegung (abweichend von 1.8.16 "Reihenfolge frei", bitte bestätigen)**: ohne
  diese Prüfung könnte ein umsortiertes Feld der Meldung unter ihrer Unterschrift landen -- die Unterschrift versiegelte
  es nicht, und die Folge liefe auf einem halben Stand. `_sync_system_fields()` legt fehlende Systemfelder mit Abschnitt
  als Abschnittsname an.
- **Festlegungen zu den Feldern (nicht vorgegeben, bitte bestätigen; an Systemfeldern im Editor nicht änderbar)**:
  Pflicht sind bekannt seit, Beschreibung, Unterschrift der Meldung, Ursache, Beschreibung der Ursache, betroffene
  Leistungen, Beginn, Unterschrift Büro, beendet am, wieder aufgenommen am, Unterschrift Wegfall; ohne Pflicht Fotos
  (ohne Mindestanzahl, Startvorlage höchstens 10) und voraussichtliche Dauer (Text, oft "nicht absehbar"). "Ursache mit
  Beschreibung" ist ein eigenes Textfeld. Beginn, beendet am, wieder aufgenommen am sind Datumsfelder; bekannt seit
  Datum und Uhrzeit ohne Vorbelegung "jetzt" (der Zeitpunkt des Bekanntwerdens, nicht der Meldung).
- **Nur Büro** (`office_only`, Abschnitt Anzeige samt "Unterschrift Büro"): `app/routers/checklists.py::
  _require_field_writable()` weist Antwort, Foto und Unterschrift eines Monteurs in diesen Feldern mit 403 ab, auch an
  seiner eigenen Checkliste; `can_fill_office_fields` im Abruf, `office_only`/`option_hints` je Feld (aus der Vorgabe,
  `field_to_dict(..., purpose_key)`). **Festlegung**: der Monteur sieht den Abschnitt lesend ("füllt das Büro aus", nicht
  als fehlend markiert); die Vorgabe "sieht keine Büro-Daten" ist wie in 1.8.16 als Folgen, Aufgaben, Regeln und
  Sachbearbeiter verstanden. Soll er die Anzeige auch nicht lesen, bräuchte es eine Ausblendung je Feld im Router.
  Wegfall füllt Monteur oder Büro.
- **Witterung**: `option_hints` am Systemfeld Ursache; die Ausfüllseite zeigt den Hinweis unter den Kacheln, solange
  "außergewöhnliche Witterung" gewählt ist; im Editor steht er am Feld. Im PDF noch nicht (Teil 2).
- **Folge nach einer Unterschrift** (`app/checklist_follow_ups.py`): `follow_up_due()` -- mit `after_signature` fällig,
  sobald im Feld eine gültige (nicht verworfene) Unterschrift steht, auch am Entwurf; sonst nach dem Abschluss wie bisher.
  `add_attachment()` ruft `run_follow_ups_after_signature()` NACH dem Commit der Unterschrift (Muster des Abschlusses, Fund 4);
  `run_checklist_follow_ups()` lehnt einen Entwurf nicht mehr ab, sondern führt aus, was fällig ist. Wiederholt ein Gerät
  dieselbe Unterschrift (gleiche `client_uuid`, Stufe-3-Vorbereitung), entsteht keine zweite, aber eine offene Folge wird
  nachgeholt -- sonst bliebe sie nach einem Abbruch direkt nach dem Commit bis zum Nachholen im Büro liegen. Idempotenz unverändert
  über `checklist_follow_ups` (eine Zeile je Checkliste und Folge): Abschluss, Nachholen, Verwerfen und erneutes
  Unterschreiben führen nichts doppelt aus. Die Übersicht (`GET /api/checklists?open_rules=true`, "Alle nachholen") nimmt
  offene Folgen mit; die Ausfüllseite zeigt dem Büro die Karte "Folgen" (Auslöser, Status, Link auf die Aufgabe,
  "Folgen nachholen").
- **Aufgabe "Behinderungsanzeige versenden"** (`app/obstruction_notices.py::create_send_task()`): fällig am Tag der
  Unterschrift in Europe/Berlin -- auch beim Nachholen, dann eben überfällig --, an `Order.caseworker_employee_id`, sonst
  ohne Zuständigkeit für `buero_auftrag` aufwärts; Projekt des Auftrags, Link auf die Behinderungsanzeige, Modul
  `aufgabenmanagement` (aus → `modul_aus`, nachholbar). **Festlegung**: Priorität hoch (die Anzeige muss unverzüglich
  hinaus); die Beschreibung nennt nur wer, wann, welcher Auftrag, nicht den gemeldeten Text.
- **Tagesbericht** (`app/checklist_rules.py`): neue Regel-Einstellung "Aufgabe verlinkt auf" (`link_purpose`, jeder Zweck
  außer "allgemein", der am Auftrag erlaubt ist). Die Aufgabe verlinkt dann auf
  `/checklisten/auftrag/{id}?zweck=<Zweck>` -- die Seite hebt "<Zweck> anlegen" mit genau den Vorlagen dieses Zwecks hervor
  und nennt schon offene Entwürfe; angelegt wird erst auf Klick. **Festlegung "keine doppelten Aufgaben"**: solange eine
  Aufgabe mit demselben Link (gleicher Auftrag, gleicher Zweck) offen ist, legt die Regel keine zweite an -- die
  Ausführung steht dann als "Aufgabe war schon offen" (`aufgabe_vorhanden`, verweist auf die offene, wird nie
  nachgeholt). Erledigt oder archiviert: der nächste Tagesbericht mit "ja" legt wieder eine an. Restrisiko: zwei genau
  gleichzeitig abgeschlossene Tagesberichte können beide eine anlegen (keine Sperre über Checklisten hinweg).
- **Migration `d6ac03a06d6f`**: Spalte `checklist_template_rules.link_purpose`; Startvorlage "Behinderungsanzeige"
  (Entwurf, nur Auftrag, `field_readable` aus, statt des FaSi-Satzes ein Hinweis "Vor Veröffentlichung prüfen" und ein
  Hinweis "Behinderung sofort melden" für den Monteur); Tagesbericht-Regel umgestellt nur, wenn die Vorlage eine einzige
  Fassung im Entwurf hat und die Regel wie 1.8.5 ist. **Auf dem Server**: ist der Tagesbericht dort schon
  veröffentlicht, bleibt er wie er ist -- dann im Editor einen neuen Entwurf anlegen, an der Regel "Behinderung
  aufgetreten ist Ja" "Aufgabe verlinkt auf: Behinderungsanzeige am Auftrag anlegen" wählen, Titel anpassen,
  veröffentlichen. `downgrade()` stellt die Regel zurück, bricht ab, solange eine andere Regel einen Link trägt, und
  entfernt die Startvorlage nur unveröffentlicht und unbenutzt.
- **Fehlermeldungen**: `checklist.html`, `checklist_template.html`, `checklists.html` und `checklist_order.html` lesen
  abgelehnte Antworten über `fehlerText()` (Architekturentscheidung 1.8.35); `_checklists_section.html` nutzt es, wenn die
  einbindende Seite `_fehlertext.html` hat, sonst nur einen Text-`detail`. **Mitbehoben**: lange Optionstexte liefen auf
  der Ausfüllseite aus ihrer Kachel ("außergewöhnliche Witterung" bei sechs Kacheln in einer Reihe) -- jetzt Umbruch im
  Wort mit Silbentrennung, wo der Browser sie kann.
- **Verifikation**: `tests/test_v341_behinderungsanzeige.py` (17 Tests; einer gegen PostgreSQL 17 im Wegwerf-Schema: zwei
  gleichzeitige "Nachholen", die beide die offene Zeile gelesen haben, legen genau eine Aufgabe an; die Abfrage nach einer
  offenen Aufgabe mit demselben Link läuft). `test_v320` angepasst (die Behinderungsanzeige hat jetzt Systemfelder; der
  Konsistenz-Wächter prüft zusätzlich Auslöser, Abschnitte und Hinweise). 20 Gegenproben rot (Skript im Scratchpad, Datei
  byte-genau zurück): Abschnittsreihenfolge, feste Eigenschaften, keine Folge nach der Unterschrift, erledigte Folge erneut,
  Folge ohne Unterschrift fällig, Nachholen am Entwurf abgelehnt, Büro-Felder offen, ohne Sachbearbeiter, ohne Fälligkeit,
  Tagesbericht ohne Prüfung auf offene Aufgabe, "vorhanden" nachholbar, Link fehlt, Migration bei veröffentlichtem
  Tagesbericht bzw. veröffentlichter Startvorlage, unbekannter Zweck auf der Seite, Link-Zweck ungeprüft, neuer Entwurf ohne
  Link, Folgen-Feld im Monteur-Schema (Scan), wiederholte Unterschrift holt nichts nach, Nachholen ohne bedingte Belegung
  (PostgreSQL). Zwei Proben blieben zuerst
  grün und haben die Tests geschärft: "vorhanden" nachholbar (erst nach dem Erledigen der ersten Aufgabe schädlich) und die
  PostgreSQL-Probe (ein Thread war fertig, bevor der andere las -- jetzt warten beide nach dem Lesen aufeinander).
  Migration SQLite und PostgreSQL (ganze Kette im leeren Schema): hin, Downgrade mit fremdem Link verweigert, zurück, hin,
  `alembic current`, `alembic check`. JS der geänderten Seiten (zehn Seitenrouten, Büro und Monteur) gerendert und mit
  `node --check` geprüft. Volle Suite 2492 grün. Klicktest `scripts/klicktest_behinderungsanzeige.py` 35/35 (Monteurin 412 px hell: starten,
  Abschnitte, Anzeige gesperrt, Meldung unterschreiben, 403; Büro 1400 px dunkel: Folgen-Karte, Witterungs-Hinweis, Anzeige
  unterschreiben, Aufgabe an die Sachbearbeiterin; Link aus der Tagesbericht-Aufgabe; Editor). Der erste Lauf fand den
  Kachel-Überlauf (Gegenprobe: ohne die CSS-Änderung 33/35). Die vier Checklisten-Klicktests (Unterschrift, Abschnitte,
  Verwerfen, Zweck) und `klicktest_versandverlauf.py` unverändert grün.

### Nebenbefunde 1.8.38 (nur gemeldet)

1. **Keine Behinderung -- und nun?** Stellt das Büro fest, dass keine Behinderung vorliegt (z. B. übliche Witterung),
   lässt sich die Anzeige weder abschließen (Pflichtfelder Anzeige und Wegfall) noch löschen (eine unterschriebene
   Checkliste ist nicht löschbar, 1.8.13). Sie bleibt Entwurf und steht beim Monteur unter "Offene Checklisten" in
   `/mobil`, bis sie abgeschlossen ist -- das gilt auch für jede echte Behinderung bis zum Wegfall. Fachlich zu
   entscheiden: ein Abschluss "keine Behinderung" mit Begründung, oder offene Behinderungsanzeigen in `/mobil` gesondert.
2. **`_checklists_section.html` ohne `_fehlertext.html`** auf `mobil_objekt.html`, `property.html`,
   `operational_asset.html`, `operational_asset_field.html`: dort zeigt der Abschnitt bei einer 422 nur "Fehler 422"
   statt der Felder -- nicht mehr "[object Object]", aber auch nicht lesbar. Umstellung beim nächsten Anfassen der Seiten.
3. **Die Aufgabe heißt "versenden", versendet wird erst ab Teil 2** -- bis dahin schickt das Büro die Anzeige von Hand
   (z. B. als PDF der Checkliste nach dem Abschluss, das aber erst nach dem Wegfall entsteht).
4. **Arbeitskopie mit CRLF**: einige Dateien liegen wegen `core.autocrlf` in der Arbeitskopie mit CRLF vor (z. B.
   `app/routers/checklists.py`, `app/schemas.py`); die in dieser Runde angefassten wurden auf LF gebracht -- Git speichert
   ohnehin LF, kein Unterschied im Commit.
