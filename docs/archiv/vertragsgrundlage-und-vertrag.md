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
| **2b-1b** | — | Vertragsvorlagen und Vertrag | offen |
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
4. **Neue und importierte Kunden sind Verbraucher, unabhängig von der Kategorie** (Vorgabe ja): ein
   neu angelegter oder per Adressimport übernommener Gewerbekunde bekommt dadurch bei neuen
   Angeboten `bgb_vob_c_4_5`, bis jemand das Häkchen entfernt. Denkbar: Häkchen beim Wählen einer der
   vier Kategorien im Formular vorschlagen, Import aus der Kategorie ableiten.
5. **LV-Kopfzeile ragt bei 1400 px Breite in die rechte Spalte** (Angebots-Editor "GESAMTPREIS"
   über "Angebotstitel", Auftragsseite "GP" über der Karte) -- auf den Klicktest-Bildern sichtbar,
   unabhängig von dieser Runde.
