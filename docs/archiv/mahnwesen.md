# Mahnwesen: Löschen/Versenden/Bearbeiten

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## Mahnwesen: Löschen/Versenden/Bearbeiten (seit 1.3.21)

Zwei gemeldete Lücken im Mahnwesen behoben, unabhängig vom PDF-Umbau oben.

- **"Alle Mahnungen" bot für Entwürfe keine Aktion.** `delete_reminder_draft()`/
  `DELETE /api/reminders/{id}` existierten bereits und waren korrekt auf `status="entwurf"`
  beschränkt, waren aber nur in `invoice_detail.html` und der "Benötigt Aufmerksamkeit"-Tabelle
  (`mahnwesen.html`) angebunden -- nicht in "Alle Mahnungen", der einzigen Stelle, an der ein
  Betreiber üblicherweise die gesamte Historie durchsieht und ein Entwurf über die Statusspalte
  klar erkennbar ist. `renderAllRows()` zeigt für `status==='entwurf'` jetzt dieselben
  Versenden-/PDF-/Löschen-Aktionen wie `renderAttentionRows()`, über dieselben, bereits
  bestehenden `sendReminder()`/`deleteReminder()`-Funktionen -- keine Geschäftslogik dupliziert.
  Geprüft, ob es weitere Tabellen mit derselben Lücke gibt: `invoice_detail.html` war bereits
  korrekt (Versenden+Löschen für Entwürfe, PDF für alle), Dashboard/Finanzen zeigen nur
  zusammenfassende Widgets ohne Zeilenaktionen -- kein weiterer Fund.
- **Bearbeiten fehlte komplett.** Neu: `update_reminder_draft(db, reminder, *, text, fee_amount,
  new_due_date)` (`app/reminders.py`) -- lehnt mit `ValueError` ab, wenn `reminder.status !=
  "entwurf"` ist, GENAU wie `update_report()` beim Einsatzbericht (`app/service_reports.py`); der
  Schutz sitzt damit in der Geschäftslogik, nicht nur in der Oberfläche, ein direkter API-Aufruf
  kann ihn nicht umgehen. Schema `ReminderUpdate`, Endpunkt `PUT /api/reminders/{id}`
  (`app/routers/reminders.py`, `ValueError` -> 400). `text` bleibt bewusst das ROHE Feld mit
  unaufgelösten Platzhaltern (`{mahngebuehr}` usw.) -- exakt dieselbe Konvention wie beim
  Bearbeiten einer Mahnstufe selbst (Einstellungen → Mahnstufen, `ReminderLevel.text_template`),
  keine zweite Konvention für dasselbe Konzept eingeführt. Oberfläche (Regel 4: kein `prompt()`,
  ein bereits sichtbares, vorausgefülltes Formular auf der Seite): ein "Bearbeiten"-Knopf bei
  jedem Entwurf (beide Tabellen in `mahnwesen.html`, teilen sich EIN Panel, das an den zuletzt
  geklickten Entwurf gebunden wird -- ein Entwurf kann ohnehin immer nur von einem Panel
  gleichzeitig bearbeitet werden) bzw. ein eigenes, kleineres Panel direkt in der
  Mahnwesen-Karte von `invoice_detail.html`.
- **Untersucht: Zusammenspiel von Mahntext und Zahlen.** Die Sorge war, dass eine Bearbeitung
  von `fee_amount`/`new_due_date` einen im Fließtext bereits eingesetzten, jetzt veralteten Wert
  stehen lassen könnte. Tatsächliches Verhalten beim Anlegen, geprüft direkt am Code
  (`create_reminder()`/`format_reminder_text()`): der Text wird NICHT einmalig erzeugt und
  gespeichert, sondern `Reminder.text` bleibt für die gesamte Lebensdauer eines Entwurfs die rohe
  Vorlage mit unaufgelösten Platzhaltern -- `formatted_text` (`reminder_to_dict()`) wird bei
  JEDEM Lesezugriff frisch aus `text` + den aktuellen Feldwerten zusammengesetzt, nie
  zwischengespeichert. Eine Änderung von `fee_amount`/`new_due_date` wirkt sich dadurch beim
  nächsten Lesen bereits automatisch auf den Fließtext aus, SOLANGE die Platzhalter im Text
  erhalten bleiben -- die ursprünglich befürchtete Gefahr (Fließtext zeigt eine andere Zahl als
  die Forderungsaufstellung) tritt in dieser Form also nicht ein. Das eigentliche, engere Risiko
  entsteht erst, wenn jemand über die neue Bearbeiten-Funktion einen Platzhalter manuell durch
  eine fest eingetippte Zahl ersetzt -- dann läuft genau dieser Wert bei einer späteren
  Zahlenänderung unbemerkt auseinander, weil nichts mehr automatisch nachzieht.
- **Entscheidung gegen eine Erkennungsspalte -- ein Hinweis statt Erkennung.** Ob ein Text
  "manuell bearbeitet" wurde, ließe sich nur über eine zusätzliche, beim Speichern gesetzte
  Spalte feststellen (z. B. `text_manually_edited: bool`) -- bewusst NICHT gebaut. Begründung:
  `formatted_text` wird ohnehin bei jedem Lesezugriff frisch aus `text` + den aktuellen
  Feldwerten neu zusammengesetzt (siehe oben), das Restrisiko betrifft ausschließlich den
  Sonderfall eines manuell ersetzten Platzhalters -- dafür genügt ein Hinweis im Moment des
  Speicherns, eine dauerhaft mitgeführte Spalte (samt der Frage, wann sie zurückgesetzt werden
  müsste) wäre unverhältnismäßig. Stattdessen zwei kleine, rein im Bearbeiten-Panel wirkende
  Maßnahmen (`app/templates/mahnwesen.html`/`invoice_detail.html`, kein Backend-Code nötig):
  1. **Nicht-blockierender Hinweis beim Speichern** (`reminderMissingPlaceholderWarning()`, in
     beiden Templates dupliziert -- kein gemeinsames JS-Modul in diesem Projekt, siehe
     Design-System-Konvention): prüft beim Klick auf "Speichern", ob `{mahngebuehr}` im Text
     fehlt (Feld `fee_amount` ist immer gesetzt) bzw. `{neue_frist}` fehlt, während
     `new_due_date` einen Wert trägt. Speichert trotzdem immer (kein `return` vor dem
     `PUT`-Aufruf) -- reiner `alert()` danach, GENAU wie die bereits bestehenden
     Fehlermeldungen in diesen Dateien, keine neue Interaktionsart. Es kann gute Gründe geben,
     einen Platzhalter absichtlich zu ersetzen; das wird nicht verhindert, nur sichtbar gemacht.
  2. **Platzhalterliste mit Bedeutung statt nur Token** direkt im Bearbeiten-Panel (vorher, seit
     der ersten 1.3.21-Fassung, nur eine flache Token-Zeile -- dabei fiel auf, dass sie
     fälschlich `{mahnstufe}` auflistete, das laut `_reminder_placeholders()`/
     `send_reminder_email()` NUR für die E-Mail-Vorlagen gilt, nicht für `Reminder.text`; jetzt
     korrigiert). Geprüft, ob eine solche Liste beim Bearbeiten einer Mahnstufe (Einstellungen →
     Mahnstufen, `renderReminderLevels()` in `settings.html`) schon existiert: ja, aber nur als
     flacher Token-String ohne Bedeutung -- dessen Token-Auswahl (korrekt ohne `{mahnstufe}`)
     wurde für die neue, um Bedeutungen ergänzte Liste übernommen, `settings.html` selbst blieb
     unangetastet (nicht Teil dieser Anfrage, weiterhin nur der flache Token-String dort). Wer
     sieht, dass es einen Platzhalter für die Mahngebühr gibt, tippt die Zahl seltener von Hand.
