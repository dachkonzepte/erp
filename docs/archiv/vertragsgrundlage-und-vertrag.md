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
| **2b-1b Teil 2b** | — | Gemeinsame Unterschriftsvorlage, Unterschrift auf dem Gerät (Kunde und Betrieb, Ankreuzfelder, Unterschriftsblatt) oder Papier-Scan, Sperren nach der Unterschrift | offen, siehe "Offen für Teil 2b" |
| **2b-2** | — | Beteiligte mit Adressbuch | offen |
| **2b-3** | — | Behinderungsanzeige | offen |
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

### Offen für Teil 2b (Punkte 4–6 und ihre Tests aus Punkt 8)

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
