# DACHKONZEPTE ERP – Prototype 1.0.96

Behebt beide echten Fehler aus deinem Testlauf. Danke dafür – genau das ist der Zweck vollständiger Testläufe.

## Fehler 1: echter Datenintegritäts-Bug beim Löschen (der wichtigere)
`QuoteSection` überlebte das Löschen eines Projekts als verwaiste Zeile. Ursache: `Quote` hat zu `QuoteSection`, `QuoteDocumentMeta` und `QuoteEmployeeAssignment` gar keine ORM-Beziehung – nur eine rohe Fremdschlüsselspalte, Zugriff läuft im ganzen Projekt über gezielte Abfragen statt über ein Attribut (dieselbe migrationsarme Bauweise, die auch bei anderen Zusatztabellen dieses Projekts verwendet wird). Dasselbe gilt für `QuoteItem` zu `QuoteItemLayout`. Ohne ORM-Beziehung greift auch keine automatische Kaskade beim Löschen.

**Behoben:** `delete_project()` löscht diese vier Tabellen jetzt vorab explizit, bevor das eigentliche Projekt gelöscht wird. Der bestehende Test dafür wurde erweitert, damit alle vier betroffenen Tabellen künftig mitgeprüft werden, nicht nur die eine, die im Testlauf auffiel.

## Fehler 2: eigener Fehler in meiner Test-Hilfsfunktion
`test_delete_project_does_not_touch_other_projects_folder` legte zwei Projekte im selben Testlauf an, aber die verwendete Hilfsfunktion (`make_full_project`) hatte Projekt- und Angebotsnummer fest verdrahtet – der zweite Aufruf kollidierte mit dem ersten. Behoben, indem beide Nummern jetzt als optionale Parameter übergeben werden können (bestehender Standardwert bleibt für alle anderen, bereits funktionierenden Tests unverändert). Das ganze Projekt zusätzlich nach ähnlichen, bisher unbemerkten Fällen durchsucht – keine weiteren gefunden.

## Kein Migrations-Update nötig
Reine Code- und Testkorrektur, keine Modelländerung.

## Tests
Keine neuen Tests, ein bestehender erweitert. **Bitte `pytest` ausführen** – sollte weiterhin 564/564 zeigen, jetzt aber mit vollständigerer Prüfung.
