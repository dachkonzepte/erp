# Rechtekonzept (vier Rollen), Dateiablage je Objekt, Büro-Suche

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

## Rechtekonzept (seit 1.3.51, Etappe 1+2)

Vorbereitung dafür, dass die kommenden Monteurskonten UND die für Schritt 3 der Sidebar-
Suche geplante Rollenfilterung auf echtem Boden stehen, nicht auf einer einzelnen `admin`-
Prüfung. Vier Etappen (siehe unten "Etappenplan"), diese Version deckt 1+2 ab und wurde vor
Etappe 3 bewusst zur Zwischenbestätigung angehalten.

### Befund vor dem Bauen

- **`AppUser.role`** (`app/models.py`) war schon immer eine unbeschränkte `String(30)`-Spalte
  ohne Datenbank-Constraint -- die einzige Einschränkung auf zwei Werte saß ausschließlich in
  Pydantic (`app/schemas.py`, `pattern="^(admin|user)$"`).
- **Reale Datenbank**: genau zwei Konten, beide `role="admin"`, beide aktiv -- Tobias mit
  verknüpftem Mitarbeiter, "Admin" als reines Systemkonto ohne Mitarbeiterverknüpfung. **Kein
  einziges `role="user"`-Konto existierte** -- die Monteurskonten, für die dieses Konzept
  gebaut wird, gab es zum Zeitpunkt dieser Untersuchung noch nicht.
- **Admin-geprüfte Bereiche** (`require_admin()`, zwölf Dateien): Benutzerverwaltung
  (Schreibzugriffe, nicht `GET /api/users` selbst), Adressimport, Zeiterfassungs-Backoffice,
  Freigabe von Abwesenheitsanträgen, Wartungsfenster-/Aufgaben-Spalten-Verwaltung,
  Modul-Umschalter, E-Mail-Einstellungen, Monteursansicht-Konfiguration -- ausschließlich
  Konfiguration/Verwaltung, keine fachlichen Kerndaten.
- **Alles andere prüfte nichts** -- für jeden angemeldeten Benutzer erreichbar: Kunden,
  Projekte, Angebote, Aufträge, Rechnungen, Mahnungen, Leistungen/Materialien (inkl.
  Einkaufspreisen), Mitarbeiter (inkl. `EmployeeOut.hourly_wage`/`effective_hourly_wage`/
  `annual_gross_wage`), Objekte, Dachflächen, Einsatzberichte, Änderungshistorie, u. v. m. --
  praktisch der gesamte fachliche Kern der Anwendung. Damit war der reale Zustand nicht
  "Admin gegen eingeschränkter Rest", sondern "Admin gegen Rest", und "Rest" hieß praktisch
  alles.
- **Der Modulschalter (`OPTIONAL_MODULES`, `app/modules.py`) bleibt eine andere, unveränderte
  Achse**: eine Zeile je `module_key` für die GANZE Installation, keine Verknüpfung zu
  `AppUser`/`role` an irgendeiner Stelle -- er entscheidet "ist die Funktion in diesem Betrieb
  eingeschaltet", nicht "darf diese Person sie nutzen". Beide Mechanismen bestehen unverändert
  parallel, keine Überschneidung.
- **`/vor-ort` heute**: die Seite selbst prüft nur die allgemeine Anmeldepflicht, keine Rolle.
  Die eigentliche Voraussetzung sitzt ausschließlich in `GET /api/field-view/today` -- der
  angemeldete `AppUser` muss ein `employee_id` tragen (422 sonst), danach sieht er
  ausschließlich seine eigenen heutigen Plantafel-Zuordnungen. Sobald er von dort in einen
  Einsatzbericht wechselt (`/orders/{id}/service-reports`), greift dagegen **keine** Prüfung
  mehr -- rein technisch könnte er heute jeden beliebigen Auftrag über die URL ansteuern, nicht
  nur seine eigenen (siehe "Objekt-Filterung" unten, Etappe 3).

### Drei Rollen: `admin` / `office` / `field`

Bewusst nicht mehr als drei -- bei einem Betrieb mit einem Büro und mehreren Monteuren
bräuchte eine frei konfigurierbare Rollenmatrix mit Einzelrechten mehr Verwaltungsaufwand als
Nutzen. `admin` behält alle bisherigen, admin-gateten Verwaltungsbereiche zusätzlich zu allem,
was `office` sieht. `office` ist fachlich das, was `role="user"` schon immer bedeutet hat --
voller Zugriff außer den zwölf Verwaltungsbereichen. `field` ist neu und deutlich enger, siehe
"Objekt-Filterung" unten.

`app/permissions.py::require_role(*rollen, message=...)` verallgemeinert
`app/deps.py::require_admin()` auf drei statt zwei Rollen -- **`require_admin()` selbst bleibt
unverändert bestehen**, an den zwölf Dateien, die es nutzen, wurde nichts geändert (es deckt
sich exakt mit `require_role("admin")`, kein Grund, etwas Funktionierendes anzufassen).

**Migration `7a2b4e9f1c3d`** (reine Daten-Migration): bestehende `role="user"`-Zeilen werden zu
`role="office"` -- auf der echten, lokalen Datenbank betraf das 0 Zeilen (siehe Befund oben),
die Migration existiert trotzdem für jede andere Installation. `downgrade()` kann `field` nicht
verlustfrei zurückführen (dieser Wert existierte im Zwei-Rollen-Modell nicht) -- sowohl
`office` als auch `field` werden beim Zurückrollen zu `user`, der nächstliegenden, am wenigsten
überraschenden Entsprechung.

### Standardverweigerung statt Positivliste -- der wichtigste Teil dieses Entwurfs

Der reale Befund oben (praktisch alles ungated) ist kein Einzelfall, sondern das erwartbare
Ergebnis einer **Positivliste**: die Sidebar/das Menü zeigt einer Rolle nur, was für sie gedacht
ist (z. B. der frühere admin-gatete `/users`-Sidebarlink, siehe 1.3.28) -- das fühlt sich nach
einer Absicherung an, ist aber nur eine Anzeige-Entscheidung. Ob der darunterliegende Endpunkt
selbst geprüft ist, ist eine ZWEITE, unabhängige Frage -- vergisst man sie, funktioniert der
Endpunkt einfach für jeden, ohne Fehler, ohne Auffälligkeit. Niemand merkt es, bis jemand
gezielt mit einer fremden Rolle danach sucht (exakt das, was die Suche-Bestandsaufnahme dieser
Sitzung getan hat).

Die Umkehrung ist eine **Negativliste**: Standardverweigerung. Ein Endpunkt ohne ausdrückliche
Rollenangabe gilt nicht als "offen", sondern als **admin-only**. Der entscheidende Unterschied:
mit dieser Umkehrung fällt ein vergessener Endpunkt beim ERSTEN Aufruf durch eine andere Rolle
auf -- sie bekommt sofort ein sichtbares 403, keine stille Funktion. Damit das nicht erst durch
einen zufälligen Praxisfall auffällt, erzwingt `tests/test_v260_role_audit.py` das bereits beim
nächsten vollständigen Testlauf: er geht jede registrierte `/api/`-Route durch (importiert dafür
jedes Modul unter `app/routers/` einzeln über `pkgutil` -- bewusst NICHT `app.main`, das würde
`Base.metadata.create_all()` gegen die echte, lokale `DATABASE_URL` auslösen, siehe
"Migrations-Workflow" unten) und listet jede Route ohne erkennbare `_dk_roles`-Markierung
(gesetzt von `require_role()`/`require_admin()`) namentlich auf. **Diese Regel ist jetzt
Regel 11** (siehe oben) -- jeder neue `/api/`-Endpunkt braucht ab sofort eine ausdrückliche
Rollenangabe, sonst schlägt der nächste Testlauf mit seinem Namen fehl.

Eine kleine, einzeln begründete Ausnahmeliste (`ROLE_AUDIT_EXEMPT` in `app/permissions.py`)
deckt die Fälle ab, die aus einem strukturellen Grund keine Rollenprüfung tragen können (Login
selbst, Zwei-Faktor-Ersteinrichtung, das eigene Passwort ändern -- für jede Rolle gedacht,
`GET /api/field-view/today` -- prüft stattdessen `employee_id`, das PWA-Icon) -- jeder Eintrag
dort ist einzeln kommentiert, kein bequemer Sammelplatz für "kommt später".

**Der Test blieb bis 1.3.54 absichtlich rot** (`@pytest.mark.xfail(..., strict=False)`, damit er
den Testlauf nicht insgesamt als fehlgeschlagen zeigte) -- seine Fehlerliste war die konkrete
Checkliste der Etappen 2/3: 1.3.51 klassifizierte drei Dateien als Nachweis
(`customers.py`/`invoices.py`/`reminders.py`, 43 Endpunkte), 1.3.52 den riskanten Batch,
1.3.54 Teil A, 1.3.55 Teil B. **Seit 1.3.55 steht er bei null und ist ein harter Test** (die
`xfail`-Markierung ist entfernt): ein neuer `/api/`-Endpunkt ohne Rollenangabe färbt den
nächsten vollständigen Testlauf rot -- genau die gewollte Standardverweigerung. Die neun
`ROLE_AUDIT_EXEMPT`-Einträge sind die einzigen rollenlosen Endpunkte, jeder einzeln begründet.

### Objekt-Filterung -- warum Rollen allein für `field` nicht reichen (Etappe 3, API-Seite seit 1.3.55 fertig)

Eine Rolle beantwortet "darf diese Person Finanzen/Kalkulation/Mitarbeiterdaten sehen" --
binär, für einen ganzen Funktionsbereich. Sie beantwortet NICHT "darf ein Monteur DIESEN
Auftrag/Bericht öffnen, nicht nur irgendeinen". Bis 1.3.54 prüften
`service_reports.py`/`findings.py`/`orders.py` genau das nicht -- ein `field`-Konto hätte jeden
beliebigen Auftrag über die URL erreichen können, nicht nur die eigenen.

**Die eine Definition (seit 1.3.55): `app/orders.py::field_may_access_order(db, employee_id,
order_id)`.** Vorgegeben war der Planungsbezug (Plantafel-Team-Besetzung, direkte Zuweisung an
der Arbeitsvorbereitung) mit der Auflage, zu prüfen, ob das vollständig ist -- war es nicht;
seit der Betreiber-Rückmeldung (1.3.56) lautet die Festlegung: **zwei Wege, Planungsbezug ODER
ein selbst angelegter Bericht, kein dritter, keine Vertrauensbasis** (Auftragsnummern sind
fortlaufend -- wer eine kennt, kennt alle; eine Zuordnung, die jeder umgehen kann, wäre
Dekoration). Zwei Funde, die sich aus dem Code ergaben, nicht aus der Vorgabe:

1a. **Team-Besetzung an der AV** (`WorkPreparationTeamAssignment` → Besetzungs-Schnappschuss
   `WorkPreparationTeamEmployee`) -- der Weg der Plantafel, denn jeder `PlanningSlot` hängt an
   genau so einer Zuweisung; geprüft wird aber an der AV, nicht am Slot, und OHNE den
   Datumsfilter von `list_todays_assignments_for_employee()`: ein vor Tagen begonnener
   Entwurfsbericht muss weiter bearbeitbar bleiben, ein für nächste Woche geplanter schon
   vorbereitet werden können. Die Tagesliste ist die datumsgefilterte Sicht auf dieselben
   Tabellen, keine dritte Quelle. **Bewusst an der Arbeitsvorbereitung geprüft, nicht am
   `PlanningSlot` selbst** (auf Nachfrage bestätigt, nicht verschärfen): ein Team, das einer AV
   bereits zugewiesen ist, aber noch keinen Termin im Kalender hat (`WorkPreparationTeamAssignment`
   existiert, aber kein `PlanningSlot` referenziert sie), soll den Auftrag schon sehen -- die
   Terminierung ist ein reiner Planungsschritt, keine Zugriffsentscheidung. Eine Prüfung, die
   zusätzlich einen `PlanningSlot` verlangt, würde genau den Fall verschärfen, der bei der
   1a./1b.-Herleitung bewusst ausgeschlossen wurde: die Tagesliste braucht den Slot nur für das
   Datum "heute", nicht für die Zugriffsfrage selbst.
1b. **Einzelzuweisung an der AV** (`WorkPreparationEmployee`) -- bewusst OHNE einen
   `PlanningSlot` vorauszusetzen: die Tagesliste braucht den Slot nur für das Datum, die
   Zuordnung selbst hängt an der AV. **Fund 1**: genau diese beiden Wege trug
   `app/time_tracking.py::employee_assigned_order_ids()` schon seit jeher als EIGENE, zweite
   Definition (Auftragsauswahl eines Nicht-Admins in der Zeiterfassung) -- seit 1.3.55 eine
   reine Weiterleitung auf `app/orders.py::_assigned_order_id_queries()`, damit Zeitbuchung
   und Berichtszugriff nie auseinanderlaufen (lokaler Import wegen Regel 3: `orders.py`
   erreicht über `invoices`/`projects` transitiv `work_preparation.py`, das `time_tracking.py`
   importiert).
2. **Eigener Bericht** (`ServiceReport.created_by_employee_id`) -- **Fund 2**: `/mobil` (damals
   `/vor-ort`) findet seine "offenen Entwurfsberichte" seit 1.3.0 über genau dieses Feld
   (`list_draft_reports_for_employee()`), unabhängig von jeder Planung. Ohne diesen zweiten Weg
   verlöre ein Monteur den Zugriff auf einen begonnenen Bericht, sobald das Büro ihn umplant
   oder aus dem Team nimmt -- die Monteursansicht zeigte den Entwurf noch, die Berichtsseite antwortete
   403 (exakt die Divergenz "Tagesliste ja, Bericht nein", die vermieden werden sollte).
   Bootstrappt nur über einen selbst angelegten Bericht: den ersten Bericht zu einem
   GEPLANTEN Auftrag legt an, wer über 1a./1b. zugeordnet ist; eine UNGEPLANTE Wartung startet
   ein Monteur vor Ort über "Wartung durchführen" (siehe unten, seit 1.3.56) -- der so erzeugte
   Bericht trägt ihn als Ersteller, das ist dann sein Zugriffsweg auf den neuen Auftrag.

Kein dritter Weg (geprüft): Monteure legen selbst keine Aufträge an (`quick_service_orders.py`
ist seit Teil A Büro/Admin; der Schnellauftrag hinter "Wartung durchführen" läuft in-process),
Zeitbuchungen setzen 1a./1b. bereits voraus, jede andere Verbindung Mitarbeiter ↔ Auftrag läuft
über eine der drei Tabellen oben.

**"Wartung durchführen" für Monteure (seit 1.3.56, Betreibervorgabe)**:
`POST /api/maintenance-contracts/{id}/perform-maintenance` war seit Teil A Büro/Admin -- ein
Monteur, der vor Ort eine ungeplante Wartung startet, hätte den Weg nicht gehabt. Jetzt
`require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD)`; `create_maintenance_visit()` bekommt
`created_by_employee_id` und setzt den Anfragenden als Ersteller des vorbereiteten Berichts
(dieselbe `_employee_for_request()`-Regel wie `POST /api/orders/{id}/service-reports`:
Nicht-Admin = eigene Mitarbeiterverknüpfung, Admin = keine). Ein `field`-Konto ohne
Mitarbeiterverknüpfung wird mit 403 abgelehnt -- der Bericht wäre sonst für niemanden
erreichbar, der ihn ausfüllen soll. Alle übrigen Endpunkte der Datei (Vertragsliste, Detail,
Bearbeitung, Historie, Einstellungen) bleiben Büro/Admin. **Korrigiert seit 1.3.59** (siehe
Abschnitt "Vertragsfinder auf /mobil" → "Fund: fremde Wartung per geratener Vertrags-ID"
unten): dieser Endpunkt prüfte bis dahin keine Zuordnung Monteur ↔ Vertrag, jeder Monteur konnte
den Vorgang für JEDEN Vertrag auslösen. Die ursprüngliche Einstufung dazu -- "legt einen Auftrag
an, Datenintegrität, kein Datenleck, so akzeptiert" -- ist überholt: ein Sicherheitstest hat
gezeigt, dass sich darüber echte Auftrags-/Projektdatensätze unter fremden Kunden anlegen
lassen, über fortlaufende, leicht erratbare IDs. Das ist Manipulation von Geschäftsdaten, keine
zu tolerierende Nebenwirkung -- `field_may_perform_maintenance()` schließt die Lücke, siehe dort.

**`sign_report()` unter dem neuen Konzept geprüft (1.3.56)**: die Unterschriftsroutine erzeugt
danach die "Rechnung erstellen"-Aufgabe (`create_task()`) und schreibt in Vertragsdaten
(`MaintenanceContract.next_due_date`) -- beides reine In-Process-Aufrufe; Rollen-Gates sitzen in
diesem Projekt ausschließlich als `Depends(...)` an Routern, nie in der Geschäftslogik. Ein
Monteur kann daran also nicht scheitern. Als Ende-zu-Ende-Test festgehalten
(`test_field_can_start_an_unplanned_maintenance_visit_and_sign_it`): Monteur startet die
ungeplante Wartung, unterschreibt über die echte Route, die Aufgabe entsteht, die Fälligkeit
rückt um `interval_months`.

**Anwendung**: `app/routers/orders.py::require_field_order_access(db, role, order_id)` ist die
eine Router-Stelle, die die Entscheidung in ein 403 übersetzt (Büro/Admin passieren ungeprüft,
ein `field`-Konto ohne Mitarbeiterverknüpfung wird immer abgelehnt) -- `service_reports.py` und
`findings.py` importieren sie. Endpunkte, die nicht über `order_id` laufen, lösen zuerst
`report_id`/`item_id`/`photo_id`/`material_id`/`finding_id` über `service_report_id` auf den
Auftrag auf (`_order_id_for_report()`/`_order_id_for_report_child()` in
`routers/service_reports.py`). `properties.py`/`roof_areas.py` brauchen keine Ableitung: seit
Teil A Büro/Admin, der Monteur liest Objekt und Dachflächen ausschließlich auftragsbezogen
(`GET /api/orders/{id}/property` bzw. `.../roof-areas`). Fremde und nicht existierende Aufträge
antworten für `field` gleichermaßen 403 (kein URL-Raten von Auftragsnummern); bei den
berichtsbezogenen Endpunkten kommt für eine nicht existierende `report_id` weiterhin das 404,
das der Endpunkt ohnehin gegeben hätte.

**Preisfreies Auftragsschema**: `GET /api/orders/{id}` liefert `field` ein `OrderFieldAccessOut`
(`app/schemas.py`) -- `id`/`order_number`/`customer_name`/`items[id, position_number, gaeb_oz,
short_text, unit]`, exakt was `service_reports.html` (Kopfzeile, LV-Auswahl für die Zeitbuchung)
und `time_tracking.html` (`ensureOrderItems()`) lesen; `order_to_dict()` hätte sonst
`unit_price`/`line_total`/Summen/Vertragstexte mitgeliefert. Ohne `customer_id` wird der
Kundenname in der Berichtsseite automatisch Text statt Link auf `/customers/{id}` -- der seit
1.3.51 vorgemerkte Punkt, ohne Rollenlogik im Template gelöst. Büro/Admin bekommen unverändert
das volle `OrderOut` (Union-Response-Model, Muster `list[EmployeeOut] | list[EmployeeNameOut]`).

**Wartungshistorie** (`GET /api/orders/{id}/property-service-reports`): ein Monteur sieht dort
gewollt frühere, unterschriebene Berichte ANDERER Aufträge desselben Objekts -- geprüft wird nur
die Zuordnung zum aktuellen Auftrag. **Seit 1.3.56 ein reduziertes Modell für `field`**
(`ServiceReportHistoryOut`, `list_property_history_for_field()`, Betreibervorgabe): Datum,
Berichtstyp, Monteur, Prüfergebnisse (Prüfpunkte mit Ergebnis/Zustand/Messwert/Bemerkung, je
Dachfläche), Mängel mit Status -- kein Beschreibungstext, kein Material, keine Unterschrifts-/
Vertrags-/Kundenfelder, keine Erledigungs-Verweise der Mängel (Folgeauftrag/Aufgabe sind
Büro-Vorgänge). Die Prüfpunkt-Bemerkung (`InspectionItem.notes`) zählt zum Prüfergebnis und
steht auf dem Kunden-PDF -- keine interne Bemerkung, deshalb enthalten. Das PDF eines fremden
Berichts bleibt für `field` über `require_field_order_access()` gesperrt (es trägt u. a. die
Zeitbuchungen der Kollegen), `service_reports.html::historyCard()` zeigt einem Monteur deshalb
Prüfergebnisse und Mängel inline statt des PDF-Links -- erkennbar an der Anwesenheit von
`inspection_items` in der Antwort, keine Rollenlogik im Template. Büro/Admin bekommen
unverändert das volle `ServiceReportOut` samt PDF-Link (Union-Response-Model wie bei
`GET /api/orders/{id}`). Per Test belegt (`test_maintenance_history_carries_no_prices_
purchase_values_or_customer_notes`): exakte Schlüsselmenge des reduzierten Modells, rekursiv
kein Preis-/Einkaufs-/Vergütungs-/Notiz-Schlüssel, Büro weiterhin mit Beschreibungstext.

**Zeiterfassung**: `?order_id=` in `GET /api/time-entries` liefert einem Monteur NICHT die
Buchungen der Kollegen -- `get_time_entries()` setzt für `ROLE_FIELD` `employee_id` auf die
eigene Person, `list_entries()` verknüpft beide Filter mit UND (geprüft, kein Fund, als Test
festgehalten); `_time_entry_can_edit()`/`_time_entry_employee_for_request()` verhindern
Ändern/Löschen fremder Zeilen und Buchen unter fremdem Namen. **Seit 1.3.56 gilt die
Lese-Eingrenzung nur noch für `field`** (vorher jeder Nicht-Admin, ein Vorher-Zustand aus der
Zeit vor dem Rechtekonzept): das Büro sieht die Buchungen aller, auch ohne eigene
Mitarbeiterverknüpfung -- es rechnet sie ab, `order.html`/`project_folder.html` lesen darüber
"alle Buchungen des Auftrags/Projekts" für "Rechnung aus Aufwand" und die Kennzahlen
(Betreiberentscheidung: "Die Summe über alle sieht das Büro"). Alle 13 Endpunkte tragen
`require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD)`, der Backoffice-Bereich
(`time_backoffice.py`) bleibt admin-only.

**Büro/Admin-only innerhalb der Teil-B-Dateien**: `GET /api/orders` (Liste), jede
Auftragsbearbeitung (`PUT`, Steuerschlüssel, Positionen, Abschnitte, Sync mit dem Quellangebot),
Revisionen, Auftrags-PDF und -Versand, `GET /api/orders/{id}/materials` (Rechnungsentscheidung
für `order.html`), `GET /api/findings` (auftragsübergreifende Mängelliste, `findings.html`),
`GET /api/roof-components/{id}/findings` (Bauteil-Mängelhistorie), die gesamte
Prüfvorlagen-Verwaltung inkl. Einzelansicht und Dachtyp-Standardzuordnung -- nur
`GET /api/inspection-templates` (Vorlagenliste) bleibt für `field` lesbar, `service_reports.html`
lädt sie für die Vorlagenauswahl.

### Vertragsfinder auf /mobil (seit 1.3.58 -- bis 1.3.60 /vor-ort): "Wartungen an meinen Objekten"

Zuletzt offener Punkt aus der Seiten-Klassifizierung (1.3.57): einem Monteur fehlte auf
`/vor-ort` (heute `/mobil`, siehe "Monteursansicht: Umbenennung zu /mobil", 1.3.61) der Weg,
einen Wartungsvertrag zu finden, um eine ungeplante Wartung zu starten --
"Wartung durchführen" (`create_maintenance_visit()`, seit 1.3.56 für Monteure erreichbar) sitzt
auf der Büro-Vertragsseite (`/maintenance-contracts/{id}`), die für `field` gesperrt ist. Ein
Monteur soll dabei NICHT die volle Vertragsliste durchsuchen können, aber die Objekte erreichen,
an denen er heute oder in Kürze zu tun hat -- Betreibervorgabe, vor dem Bauen als Vorschlag
vorgelegt und mit zwei Korrekturen bestätigt.

**Erst geprüft, wie verlangt: ist `WorkPreparation.status` zuverlässig genug, um "offene AV ODER
Zeitfenster" zu kombinieren?** Zwei Befunde, gegenläufig:
- Statisch UND tatsächlich beschreibbar: `PUT /api/orders/{order_id}/work-preparation`
  (`work_preparation.html`s `saveHeader()`, Büro/Admin) kann den Status jederzeit auf einen der
  fünf Werte setzen -- das Feld ist kein toter Code, anders als zunächst vermutet.
- Aber die reale, lokale Datenbank enthält für diese Prüfung nur **eine einzige**
  `WorkPreparation`-Zeile insgesamt (`status="offen"`) -- zu dünn, um "wird das im Alltag
  verlässlich gepflegt" empirisch zu beurteilen.
- Entscheidend gegen die Kombination: "offen ODER Zeitfenster" hätte das Risiko, das das
  Zeitfenster gerade vermeiden soll, an anderer Stelle wieder eingeführt -- eine AV, die
  tatsächlich fertig ist, aber nie manuell auf "abgeschlossen" gesetzt wurde (leicht zu
  vergessen, reines Büro-Freitextfeld ohne Zwang), bliebe dann unabhängig vom Datum sichtbar,
  exakt die Altlast, die vermieden werden sollte. **Ergebnis: Zeitfenster allein**, wie vom
  Nutzer selbst als Rückfall vorgegeben -- `WorkPreparation.status` fließt in
  `list_field_relevant_property_ids()` nirgends ein.

**`app/planning.py::list_field_relevant_property_ids(db, employee_id, window_days=14)`** -- die
eine Definition, welche Objekte relevant sind:
- Zuordnung an der AV (Team oder Einzeln) über die bereits bestehende
  `employee_assigned_order_ids()` (`app/orders.py`) -- dieselben Aufträge, über die auch die
  Zeiterfassung und `field_may_access_order()` entscheiden, keine dritte Definition.
- Datum: JEDER `PlanningSlot` dieser AV (`preparation_id`, unabhängig davon, über welchen der
  beiden Wege der Mitarbeiter zugeordnet ist -- ein Slot trägt keine `employee_id`) innerhalb
  ±14 Tage um heute. Fehlt jede Terminierung, `WorkPreparation.planned_start`/`planned_end` als
  Rückfall. Fehlt auch das, bleibt die AV unberücksichtigt -- kein Anhaltspunkt, kein Raten.
- Objekt-Auflösung: `order.project.property` geht vor, ohne verknüpftes Objekt die
  Hauptadresse-`Property` des Kunden (`is_primary_address`) -- damit ein Wartungsvertrag mit
  `property_id IS NULL` (bedeutet "Hauptadresse", `contract_to_dict()`) über denselben Abgleich
  gefunden wird.

**`app/maintenance_contracts.py::list_relevant_contracts_for_employee()`** -- gruppiert nach
Objekt, zeigt ALLE (nicht archivierten) Verträge des Objekts, `is_due` je Vertrag hervorgehoben
(zweite Nutzerkorrektur: "alle zeigen, fällige hervorheben", nicht nur die fälligen). Ein Vertrag
mit aktiven "Zu wartenden Dachflächen" unter `MaintenanceSettings.use_roof_area_items` wird
übersprungen -- `create_maintenance_visit()` lehnt "Wartung durchführen" dafür grundsätzlich ab
(reine Vertragsebene, siehe dort), ein Button, der zuverlässig mit einer Fehlermeldung endet,
wäre schlechter als gar keiner.

**Reduziertes Schema** (`FieldMaintenancePropertyGroupOut`/`FieldMaintenanceContractOut`,
`app/schemas.py`) -- erste Nutzerkorrektur: `property_name`/`customer_name` nur so weit, wie das
Objekt erkennbar wird. `customer_name` steht deshalb dabei (ohne ihn wäre "Hauptadresse" allein
niemandem zuzuordnen), aber weder Kundennummer noch Straße/PLZ -- nur `city` ("der Ort").

**`GET /api/field-view/maintenance-contracts`** (`app/routers/field_view.py`, `_any_role_dep` wie
`.../today`) -- löst den Mitarbeiter ausschließlich über `request.state.erp_user` auf. Fehlt die
Mitarbeiterverknüpfung oder ist das Modul "wartungen" aus, bewusst eine **leere Liste, kein
Fehler** -- dritte Nutzerkorrektur: die Karte "Wartungen an meinen Objekten" darf leer bleiben,
ohne zu stören. `mobil.html` zeigt bei leerer Antwort einen ruhigen Hinweistext (dasselbe
Muster wie die beiden bestehenden Karten bei "keine Einsätze"/"keine Entwürfe"), nie eine leere
Fläche. Klick auf "Wartung durchführen" ruft `POST /api/maintenance-contracts/{id}/perform-
maintenance` (seit 1.3.56 für Monteure offen) und navigiert direkt zu
`/orders/{order_id}/service-reports?report={report_id}` (Muster `maintenance_contract.html`).

### Fund: fremde Wartung per geratener Vertrags-ID (behoben seit 1.3.59)

Ein Sicherheitstest gegen eine isolierte Testinstanz (eigene, temporäre Datenbank, nie gegen die
echte `dachkonzepte_erp.db`) hat gezeigt: `POST /api/maintenance-contracts/{id}/perform-
maintenance` prüfte für `field` seit 1.3.56 zwar die Mitarbeiterverknüpfung, aber KEINE Zuordnung
zwischen Monteur und Vertrag. Ein Monteur konnte damit für JEDEN Vertrag -- fortlaufende,
leicht erratbare ID -- einen echten Auftrag samt Projekt und vorbereitetem Bericht unter einem
ihm völlig fremden Kunden anlegen. Die ursprüngliche Einstufung dieser Lücke ("legt einen
Auftrag an, kein Datenleck, so akzeptiert") ist damit überholt: das ist keine Frage vertraulicher
Daten, sondern eine Manipulation der Geschäftsdaten, über eine triviale ID-Iteration auslösbar --
genau der Angriff, den die Standardverweigerung des ganzen Rechtekonzepts verhindern soll.

**`app/maintenance_contracts.py::field_may_perform_maintenance(db, employee_id, contract_id)`**
zieht dieselbe Grenze wie der Vertragsfinder selbst: ein Monteur darf eine Wartung nur an einem
Objekt starten, das über `list_field_relevant_property_ids()` erreichbar ist -- also an einem
Objekt, an dem er über die Arbeitsvorbereitung tatsächlich aktuell oder in Kürze zu tun hat.
`contract_effective_property_id()` löst dafür denselben Hauptadresse-Rückfall auf wie
`contract_to_dict()` (ein Vertrag mit `property_id IS NULL` zählt über die Hauptadresse-`Property`
des Kunden). Der Router (`post_perform_maintenance()`) prüft das zusätzlich zur bestehenden
Mitarbeiterverknüpfung-Prüfung, ausschließlich für `field` -- Büro/Admin bleiben unbeschränkt.
Geprüft und mit einem zweiten Durchlauf desselben Angriffstests bestätigt: 0 "durchgelassen".

### Berichts-Eigentümerschaft: fremde Berichte auf einem gemeinsamen Auftrag (behoben seit 1.3.59)

Derselbe Sicherheitstest fand einen zweiten, schwerwiegenderen Fund: `require_field_order_access()`
prüft nur "gehört der AUFTRAG zu mir" -- auf einem Mehrpersonen-Auftrag (mehrere Monteure über
Team-Besetzung an der AV zugeordnet) reichte das für einen EINZELNEN Bericht nicht. Ein Monteur
mit legitimem Auftragszugriff konnte jeden Bericht eines Kollegen auf demselben Auftrag lesen
(volles Schema inkl. Freitext), ändern, löschen und sogar signieren -- dieselbe, ungeprüfte
Auftragsebene stand vor PUT/DELETE/sign UND vor Prüfpunkten, Fotos, Material und Mängeln.

**Trennung nach Zugriffsart** (Betreibervorgabe):
- **Lesen der Berichtsliste** (`GET /api/orders/{order_id}/service-reports`): bleibt für jeden
  mit Auftragszugriff erlaubt -- aber pro Bericht, nicht pro Auftrag. Der eigene Bericht
  (`created_by_employee_id` == der angemeldete Monteur) zeigt weiterhin das volle
  `ServiceReportOut` -- ohne das könnte ein Monteur seinen eigenen, noch nicht unterschriebenen
  Bericht nicht mehr bearbeiten, `service_reports.html` liest den Beschreibungstext zum
  Bearbeiten direkt aus dieser Liste, kein separater Einzelabruf davor. Jeder Bericht eines
  ANDEREN Erstellers kommt im reduzierten Schema der Wartungshistorie (`ServiceReportHistoryOut`,
  über `app/service_reports.py::list_reports_for_field()`, die dieselbe Konvertierungsfunktion
  wie `list_property_history_for_field()` wiederverwendet) -- keine vertraulichen Notizen, kein
  voller Freitext, keine Zeitbuchungen der Kollegen. Bewusst **kein** `response_model=list[A] |
  list[B]` auf der Route -- beide Schemata überlappen sich strukturell zu weit (dieselbe
  `roof_areas`-Liste, überwiegend optionale Zusatzfelder), um sich verlässlich auf Pydantics
  automatische Unterscheidung innerhalb EINER Liste zu verlassen; der Router wählt stattdessen
  je Zeile explizit das passende Schema und validiert einzeln.
- **Schreiben und Detailzugriff auf einen konkreten Bericht** (PUT/DELETE/sign, Prüfpunkte,
  Fotos, Material, Mängel, PDF): nur der Ersteller. Neue Funktion
  `app/routers/orders.py::require_field_report_ownership(db, role, report_id)` -- prüft zuerst
  wie bisher `require_field_order_access()` (derselbe Auftragsbezug), danach zusätzlich
  `report.created_by_employee_id == role.employee_id`. Büro/Admin bleiben unbeschränkt.

**Bewusste betriebliche Festlegung, keine technische Annahme** (auf Rückfrage, ob "nur der
Ersteller" zu eng ist -- könnten zwei Monteure legitim an einem Bericht arbeiten, einer beginnt,
der andere schließt ab?): in diesem Betrieb schreibt jeder Monteur seinen eigenen Bericht nach
getaner Arbeit, keine Fortführung durch einen Kollegen (Betreiberantwort). Ändert sich dieser
Ablauf, ist `require_field_report_ownership()` die Stelle, die dann von "Ersteller" auf "alle dem
Auftrag zugeordneten Monteure" (`employee_assigned_order_ids()`) erweitert werden muss -- nicht
der Auftragsbezug selbst, der bleibt richtig.

Betrifft `app/routers/service_reports.py` (PUT/DELETE/sign-Bericht, PDF, Prüfpunkte inkl.
regenerate/sync, Fotos, Material -- je Endpunkt einzeln mit einem Test belegt, der den Zugriff
eines Nicht-Erstellers ablehnt) und `app/routers/findings.py` (Mängel eines Berichts lesen/
anlegen, Nachverfolgung ändern -- Eigentümerschaft hängt am PARENT-Bericht, nicht an
`Finding.created_by_employee_id` selbst, da `InspectionItem` gar kein eigenes Ersteller-Feld
trägt und die Regel für alle Kind-Objekte eines Berichts einheitlich gelten soll). Mit einem
zweiten Durchlauf desselben Angriffstests bestätigt: 0 "durchgelassen", inklusive PUT/DELETE/
sign auf einem fremden Bericht.

### Zeiterfassung für Monteure (seit 1.3.60)

Bis dahin führte "Zeiterfassung" auf `/vor-ort` nur als Link auf die volle, sidebar-getragene
`time_tracking.html` -- für `field` seit der Seiten-Klassifizierung (1.3.57) zwar erreichbar
(eine der vier freigegebenen Seiten), aber mit der kompletten Büro-Oberfläche samt
Mitarbeiter-Umschalter-Optik und Gruppenbuchung, nicht der schmalen, handschuhtauglichen
Bedienung des restlichen `/vor-ort`. Befund vor dem Bauen (siehe eigener Befund-Austausch): die
API-Endpunkte in `app/routers/time_tracking.py`/`absence_requests.py` waren bereits vollständig
self-scoped (Rechtekonzept Teil B, 1.3.55/56) -- die Reduktion ist eine reine Darstellungsfrage,
keine Zugriffsfrage; `time_backoffice.html` (admin-only) bleibt die einzige echte Büro-Funktion
in diesem Bereich.

**Drei Betreiberentscheidungen, umgesetzt:**

1. **Manuelle Buchung/Nachtrag bleibt, aber abgespeckt.** Ein Monteur braucht sie ("merkt abends,
   dass er eine Stunde vergessen hat, oder korrigiert eine falsche"), aber nur für die eigenen
   Buchungen -- das leistete `_time_entry_employee_for_request()`/`_time_entry_can_edit()`
   bereits vorher, unverändert wiederverwendet. Feldliste in der neuen Maske: Auftrag (aus den
   eigenen Einsätzen), Datum, Von-Bis **oder** Dauer (Umschalter, Stunden werden clientseitig aus
   der Uhrzeitspanne berechnet -- `POST /api/time-entries` kennt in seinem Schema
   (`TimeEntryManualCreate`) gar kein `started_at`/`ended_at`, nur `hours`, anders als
   `create_manual_entry()` selbst, das beides könnte), Zeitart, Notiz. Kein Mitarbeiterfeld (immer
   die eigene Person -- `employee_id` wird trotzdem im Request mitgeschickt, da das Schema es
   verlangt, nur eben ohne sichtbares Feld, siehe Code-Kommentar in `time_tracking_field.html`),
   keine LV-Position, keine Pause-Minuten (nutzt `TimeTrackingSettings.default_break_minutes`
   still im Hintergrund, sofern konfiguriert). **Bekannter, bewusst nicht behobener Randfall**: ist
   `require_order_item`/`require_activity` im Backoffice aktiviert, verlangt der Server ein Feld,
   das die reduzierte Maske gar nicht anbietet -- die Anfrage schlägt dann mit einer klaren,
   bereits vorhandenen deutschen Fehlermeldung fehl (kein Absturz), aber ohne Weg, sie in dieser
   Maske zu beheben. Für diese Installation nicht relevant (beide Schalter stehen auf Default
   `False`), nicht eigens abgefangen.

2. **Auftragsauswahl: dasselbe ±14-Tage-Fenster wie der 1.3.58-Wartungsfinder, plus ein dabei
   gefundener echter Fund.** Neue Funktion `app/planning.py::list_field_bookable_order_ids()`
   nutzt exakt dieselbe, jetzt in `_relevant_preparation_ids_for_employee()` ausgelagerte
   Zeitfenster-Logik wie `list_field_relevant_property_ids()` (1.3.58) -- "was dort als 'meine
   Objekte' gilt, gilt hier als 'meine Aufträge'". Vor dem Bauen geprüft (Betreibervorgabe: "das
   Fenster muss den laufenden Einsatz sicher erfassen"): ein erst gestern zugewiesener, heute
   bearbeiteter Auftrag fällt zuverlässig ins Fenster, SOFERN die Arbeitsvorbereitung überhaupt
   ein Datum trägt (echter `PlanningSlot` oder `planned_start`/`-end`) -- für einen für heute
   terminierten Einsatz ist das bei jeder sinnvollen Fenstergröße der Fall, das war nie das
   eigentliche Risiko.

   Das eigentliche, von der Fenstergröße UNABHÄNGIGE Risiko: ein per "Wartung durchführen"
   (`create_maintenance_visit()`, seit 1.3.56 auch für Monteure) gestarteter, ungeplanter Auftrag
   hat GAR KEINE `WorkPreparation` -- `create_quick_service_order()` legt bewusst keine an (kein
   Plantafel-Bezug). Ein solcher Auftrag taucht in `employee_assigned_order_ids()` und damit in
   keinem Zeitfenster jemals auf, unabhängig von dessen Größe -- ein zu enges Fenster hätte das
   nicht gelöst, ein beliebig großes auch nicht. `list_field_bookable_order_ids()` ergänzt deshalb
   UNGEFENSTERT jeden Auftrag, zu dem der Monteur bereits selbst einen `ServiceReport` angelegt
   hat (`created_by_employee_id`) -- exakt der zweite der beiden Wege, über die
   `field_may_access_order()` (`app/orders.py`) ohnehin schon Zugriff gewährt. Ohne diese Ergänzung
   hätte ein Monteur nach "Wartung durchführen" zwar seinen Bericht öffnen, aber nie Zeit auf den
   dafür entstandenen Auftrag buchen können -- exakt die Divergenz, die `field_may_access_order()`
   an anderer Stelle bereits ausdrücklich vermeidet.

   `GET /api/field-view/time-tracking/orders` (`app/routers/field_view.py`) liefert die
   aufgelöste Liste (id/order_number/customer_name/property_address, dieselben Felder wie
   `time_tracking_context()` für die volle Seite) -- löst den Mitarbeiter ausschließlich über
   `request.state.erp_user` auf, kein `employee_id`-Parameter, bewusst eine leere Liste statt
   eines Fehlers ohne Mitarbeiterverknüpfung (Muster `GET /api/field-view/maintenance-contracts`).

3. **Gruppenbuchung komplett entfernt, Abwesenheitsantrag bleibt.** Ein Monteur bucht nur für
   sich -- die neue `time_tracking_field.html` enthält keinerlei Gruppenbuchungs-Markup, keinen
   Aufruf von `/api/time-entry-groups*`. **Offener Punkt, hier bewusst festgehalten (Betreiber-
   vorgabe):** in der Praxis bucht eine Kolonne trotzdem oft gemeinsam -- dafür bleibt vorerst nur
   der Weg über die volle `time_tracking.html` (Büro/Admin). Ob und wie ein Kolonnenführer künftig
   selbst gruppenbuchen darf (z. B. eine vierte Rollenausprägung oder ein Team-Attribut
   "Kolonnenführer"), ist eine eigene, spätere Entscheidung -- nicht Teil dieser Version.
   Abwesenheitsanträge dagegen sind unverändert self-service (siehe `absence_requests.py`, bereits
   seit dem Rechtekonzept korrekt eingegrenzt) und stehen in der reduzierten Ansicht wie in der
   vollen.

**Die Weiche hängt an der Rolle, nicht am Weg.** Auf ausdrückliche Vorgabe geprüft: es gibt DREI
unabhängige Linkquellen zu `/time-tracking` (`_sidebar.html`, `_mobile_header.html`,
`service_reports.html`s `#timeLink` mit `?order_id=`) -- eine Lösung über eine zweite Route (z. B.
`/vor-ort/zeit`) hätte alle drei einzeln anpassen müssen und wäre bei jeder künftigen, neuen
Verlinkung erneut anfällig. Stattdessen bleibt die URL `/time-tracking` für jede Rolle identisch --
`app/routers/pages.py::time_tracking_page()` entscheidet servereitig anhand der AKTUELLEN
Sitzungsrolle (`_role.role`, das `AppUser`-Objekt aus `require_role()`), welche Vorlage gerendert
wird: `time_tracking_field.html` für `field`, unverändert `time_tracking.html` sonst. Damit gilt
automatisch, ohne dass ein einziger Link geändert werden musste: ein Büro-Konto, das testweise als
`field` unterwegs ist (oder umgekehrt), sieht bei JEDEM Aufruf -- Sidebar-Link, altes Lesezeichen,
eingetippte Adresse, `?order_id=`-Link -- exakt das, was die aktuelle Rolle vorsieht, nie einen
Zwischenstand aus einer früheren Rolle. Da es dieselbe, bereits `_dk_roles`-markierte
`require_role(ROLE_ADMIN, ROLE_OFFICE, ROLE_FIELD)`-Dependency wie zuvor bleibt (nur die
Template-Wahl im Funktionskörper ist neu), bleibt `/time-tracking` unverändert eine der vier für
`field` freigegebenen Seiten -- der Audit-Test (`test_v260_role_audit.py`) prüft davon unberührt
weiter.

**Punkt 4 der Anfrage, ausdrücklich geprüft: die volle Seite ist für `field` jetzt strukturell
unerreichbar, nicht nur standardmäßig anders.** Es gibt keine zweite URL, unter der
`time_tracking.html` unabhängig von der Rolle gerendert würde -- `time_tracking_page()` ist die
EINZIGE Stelle im Code, die diese Vorlage lädt. Ein Monteur, der `/time-tracking` über die
Adresszeile eintippt oder ein altes Lesezeichen (aus der Zeit vor 1.3.60) öffnet, bekommt
serverseitig immer `time_tracking_field.html` -- der im vorherigen Screenshot gezeigte Zustand
(volle Sidebar) ist danach für `field` nicht mehr erreichbar, unabhängig vom Weg dorthin.

**Nachtrag (seit 1.7.9): Auftragsauswahl war nur in der Oberfläche eingeschränkt.** Befund bei der
Kolonnenführer-Planung: `POST /api/time-entries`, `/start`, `PUT /api/time-entries/{id}` und beide
Gruppen-Endpunkte nahmen für `field` jede existierende Auftrags-ID an -- die reduzierte Maske bot
zwar nur `list_field_bookable_order_ids()` an, ein direkter Aufruf konnte aber beliebige Aufträge
bebuchen, und die Antwort (`TimeEntryOut`) lieferte Auftragsnummer, Titel und Projektname zurück
(Auftragsnummern sind fortlaufend, also durchprobierbar). Geschlossen über die bereits bestehende
`require_field_order_access()` (`app/routers/orders.py`, 403 statt 404) --
`field_may_access_order()` als Maßstab, bewusst OHNE das ±14-Tage-Fenster der Auswahlliste, damit
ein Nachtrag für einen älteren Einsatz weiter möglich bleibt. Büro/Admin unverändert.
`tests/test_v299_time_booking_order_scope.py`.

**Nachtrag (seit 1.7.12): Kolonnenführer -- löst den offenen Punkt aus Punkt 3 oben.** Befund
vorab: die Gruppenbuchung war für `field` seit 1.3.60 nur in der Oberfläche entfernt, die vier
`/api/time-entry-groups*`-Endpunkte standen serverseitig jedem Monteur offen
(`require_min_role(ROLE_FIELD)`, `validate_group_members()` prüfte nur Teamzugehörigkeit) --
jeder Monteur konnte per direktem Aufruf für seine Teamkollegen buchen. Betreiberentscheidungen:

- **Keine fünfte Rolle, sondern ein Kennzeichen an der Teamzuordnung:**
  `TeamEmployee.is_crew_leader` (Boolean, `server_default='0'`, Migration `2f5de21f11b8`). Das
  vorhandene `TeamEmployee.role` taugt dafür NICHT: Freitext ("Rolle im Team, z. B.
  Vorarbeiter"), als Anzeige-Schnappschuss in die Arbeitsvorbereitung kopiert -- eine
  Rechteentscheidung hinge an Schreibweisen. Bestehende "Vorarbeiter"-Texte werden bewusst NICHT
  automatisch zum Kennzeichen; das Büro setzt es nach dem Einspielen selbst. Mehrere je Team
  erlaubt (Vertretung). Gesetzt in der Team-Maske (`master_data_form.html`) von wem Teams pflegt
  (`buero_auftrag`+). **Fallstrick:** `_apply_team_payload()` legt alle Mitgliedszeilen bei jedem
  Speichern neu an -- ein Client, der `is_crew_leader` nicht mitschickt, setzt es zurück.
- **Gate:** `_require_crew_leader()` (`app/routers/time_tracking.py`) -- ein Monteur gruppenbucht
  (manuell oder Timer) nur für ein aktives Team, in dem er Kolonnenführer ist. Bestehende Regeln
  gelten weiter: er selbst muss dabei sein, alle Gebuchten müssen Mitglieder sein, der Auftrag
  muss ihm zugeordnet sein (1.7.9), der Zeitraum offen (1.7.10). Büro/Admin unverändert.
- **Korrektur:** neu `PUT`/`DELETE /api/time-entry-groups/{id}` (`update_group()`/
  `delete_group()`) -- Admin, oder wer die Gruppe angelegt hat; ein Monteur zusätzlich nur,
  solange er im Team der Buchung noch Kolonnenführer ist; nur bis zum Abschluss. Die Korrektur
  gilt für alle Mitgliedsbuchungen gleich und überschreibt eine zwischenzeitliche Einzeländerung
  eines Mitglieds. Die Besetzung ist nicht änderbar (löschen und neu buchen). Einzelbuchungen der
  Kollegen bleiben für ihn unerreichbar (`_time_entry_can_edit()` unverändert).
- **Keine Sicht auf fremde Zeiten:** Gruppenantworten enthalten für `field` je Mitglied nur Name,
  Stunden, Status (`_group_out()`); `GET /api/time-entry-groups/mine` (eigene Gruppenbuchungen,
  14 Tage) ebenso nur Namen. `GET /api/time-entries` bleibt self-scoped.
- **Nachvollziehbar:** `TimeEntryOut.booked_by_name`/`booked_by_employee_id` (aus
  `TimeEntry.created_by_user_id`, neue Relationship `TimeEntry.created_by`, keine Migration);
  Mitglied und Backoffice sehen "gebucht von …". Die Gruppe selbst trägt
  `initiated_by_employee_id`, die Änderungshistorie schreibt Zeitbuchungen und Teamänderungen
  mit.
- **Oberfläche:** Abschnitt "Kolonne" in `time_tracking_field.html`, nur sichtbar, wenn
  `GET /api/time-tracking/crews` etwas liefert. Eine laufende Kolonnenzeit ist zugleich die eigene
  laufende Zeit -- deren "Zeit stoppen" beendet die Gruppe für alle (bestehende Initiator-Regel),
  bewusst kein zweiter Stopp-Knopf.
- **Nebenbefund, eigene Version 1.7.11:** `delete_entry()` scheiterte unter PostgreSQL an der
  Gruppen-Verknüpfung (Fremdschlüssel ohne Kaskade).

`tests/test_v302_crew_leader.py` (14 Tests, inkl. Angriffstest; Gegenprobe mit abgeschaltetem Gate
rot), Klicktest per CDP gegen eine isolierte Instanz (Start/Stopp/Nachtrag/Ändern/Löschen als
Kolonnenführerin, "gebucht von" beim Mitglied, Team-Maske, Abschluss-Karte).

### Fünf weitere Anpassungen an der Monteursansicht (seit 1.3.61)

Fünf rollenbezogene Punkte, alle ohne neues Datenmodell außer Punkt 4 (siehe dort -- am Ende doch
keine neue Tabelle, nur ein neuer, bereits bestehender Mechanismus zweitverwendet).

**Punkt 1 -- Umbenennung und neue URL: `/vor-ort` → `/mobil`.** `/vor-ort` entfällt ersatzlos
(keine Weiterleitung -- der Nutzer hatte ausdrücklich bestätigt, dass es keine Lesezeichen darauf
gibt), `app/routers/pages.py::field_view_page()` ist jetzt unter `/mobil` registriert und rendert
`app/templates/mobil.html` (umbenannt und erweitert aus `vor_ort.html`, das gelöscht wurde,
Titel "DACHKONZEPTE GmbH - Mobil"). Geprüft, wie verlangt, ob im Code irgendwo `/vor-ort`
VERLINKT ist (nicht nur in Prosa erwähnt) -- alle drei tatsächlichen Linkquellen aus 1.3.60
gefunden und mitgezogen:
1. `app/mobile_manifest.py::build_manifest()` -- `start_url` jetzt `/mobil`.
2. `app/templates/login.html` -- der clientseitige Rückfall ohne `next`
   (`d.role==='field'?'/mobil':'/projects'`).
3. `app/permissions.py::default_home_page_for_role()` -- die eine, gemeinsame Quelle für
   `login_page()`, den 403-Exception-Handler UND (neu, siehe Punkt 2) `dashboard_page()`.

`app/templates/_mobile_header.html` verlinkte selbst nicht auf `/vor-ort` als Ziel (die Einträge
sind bereits relativ zur aktuellen Seite, `path == '/mobil'` statt eines hartkodierten Strings),
musste also nur den Vergleichswert mitziehen. Reine Docstring-/Kommentar-Erwähnungen in rund
einem Dutzend weiterer Dateien (`app/service_reports.py`, `app/models.py`, `app/orders.py`,
`app/mobile_settings.py`, `app/schemas.py`, `app/routers/quotes.py` u. a.) wurden für
Stellen korrigiert, die LAUFENDES Verhalten beschreiben (z. B. "GET /mobil prüft die
Feierabend-Grenze NICHT") -- rein historische "Neu seit 1.3.X"-Einträge weiter oben in dieser
Datei bleiben unverändert bei `/vor-ort`, da sie beschreiben, was zu jenem Zeitpunkt tatsächlich
gebaut wurde (Regel 8/etablierte Konvention dieser Datei), siehe z. B. "Neu seit 1.3.57"/
"Neu seit 1.3.58" oben. Der Abschnitt "Vertragsfinder auf /vor-ort" (1.3.58) heißt seither
"Vertragsfinder auf /mobil" -- er ist ein aktiver Querverweis aus mehreren Code-Kommentaren
(`app/maintenance_contracts.py`, `app/routers/maintenance_contracts.py`), keine reine
Versionshistorie, deshalb umbenannt statt unverändert gelassen.

**Punkt 2 -- Startseite für Monteure.** `app/routers/pages.py::dashboard_page()` (`GET /`) trug
bisher `_role_dep` (Büro/Admin, 403 für `field`) -- jetzt `_any_role_dep`, mit einer Weiche im
Funktionskörper: `if _role.role == ROLE_FIELD: return RedirectResponse(default_home_page_for_role(...))`,
sonst unverändert das Dashboard. Deckt beide vom Nutzer genannten Fälle in einer einzigen
Prüfung ab -- nach dem Anmelden (über `login_page()`s bereits bestehende Weiche) UND ein von
Hand eingetipptes `/` (über `dashboard_page()`s neue Weiche), da beide dieselbe
`default_home_page_for_role()`-Funktion nutzen. Kein drittes Verhalten neben "gesperrt"/"offen"
-- die Rolle entscheidet das Ziel, nicht der Weg (exakt die vom Nutzer vorgegebene Formulierung).
`tests/test_v260_role_audit.py::test_field_reaches_only_the_five_pages_it_needs` prüft seither
für `/` einen 302 auf `/mobil` statt eines 403.

**Punkt 3 -- Tätigkeit im Nachtrag, PRÄMISSE KORRIGIERT.** Der Nutzer nannte als Ausgangspunkt
"der Schnellstart hat schon ein Tätigkeitsfeld, der Nachtrag noch nicht" -- beim Nachsehen im
tatsächlichen `time_tracking_field.html` (Stand 1.3.60) stimmte das nicht: WEDER Schnellstart
NOCH Nachtrag hatten ein Tätigkeitsfeld, nur die "Zeitart"-Kacheln (Baustelle/Fahrzeit/Werkstatt/
Sonstige) existierten -- "Tätigkeit" ist ein davon unabhängiges Konzept
(`time_entry_activities`-Optionsgruppe, z. B. "Dacheindeckung", "Reparatur"), das bei der
1.3.60-Reduktion bewusst aus BEIDEN Abschnitten weggelassen worden war. Diese Diskrepanz wurde
vor der Umsetzung transparent gemacht, nicht stillschweigend nach der einen oder anderen Seite
aufgelöst. Umgesetzt wie vom Nutzer für den Korrekturfall verlangt ("ergänze es, mit denselben
Werten wie im Schnellstart"): ein neues, optionales `<select id="quickActivity">` UND
`<select id="manualActivity">`, beide befüllt aus derselben `time_entry_activities`-Optionsgruppe
wie die volle `time_tracking.html` (`safeOptionGroup('time_entry_activities', ...)`, Werte/Label
identisch zum Vorbild). Kein Backend-Fund nötig -- `TimeTimerStart`/`TimeEntryManualCreate`
(`app/schemas.py`) kannten `activity: str | None` schon immer, `_time_entry_*`-Endpunkte
verarbeiteten es bereits korrekt, nur die reduzierte Maske hatte kein Feld dafür.

**Punkt 4 -- Stundenzettel.** Neue Seite `/mobil/stundenzettel` (`field_timesheet_page()`, eigene
Seite statt eines weiteren Kartenabschnitts auf `/mobil` -- Monatswahl/Liste/PDF-Knopf passen
strukturell nicht zum einfachen Karten-Muster der übrigen Abschnitte dort). Vor dem Bauen
geprüft, wie verlangt: der bestehende Büro-Stundenzettel (`app/time_backoffice.py::
build_timesheet_pdf()`, admin-only, `GET /api/time-backoffice/timesheet.pdf`) ist ein
ALTER, eigener `SimpleDocTemplate`/`landscape(A4)`-Renderer, der den gemeinsamen PDF-Rahmen aus
dem 1.3.1–1.3.20-Umbau NIE genutzt hat (vor oder unabhängig davon entstanden) -- er konnte also
nur als inhaltliche Vorlage dienen (Spaltenauswahl Datum/Auftrag/Zeitart/Tätigkeit/Stunden,
Tagessummen-/Gesamtsummenzeilen, Gruppierung je Mitarbeiter), nicht als Code-Vorbild für den vom
Nutzer ausdrücklich geforderten "gemeinsamen Rahmen ... mit Briefkopf".

Neuer, dedizierter Renderer `app/field_timesheet_pdf.py::build_field_timesheet_pdf(db,
employee_id, year, month) -> bytes` -- nutzt `render_framed_pdf()` mit einem KOMPLETT NEUEN
`document_type="field_timesheet"` (erstmals seit `service_report` in 1.3.11 wieder ein Typ ohne
jede Vorgeschichte), eingetragen in `DOCUMENT_TYPES` (`app/document_layout.py`) UND
`RENDERERS_USING_SHARED_FRAME` (`app/document_frame.py`) -- ohne beide Einträge wirft
`render_framed_pdf()`/`ensure_default_layout()` einen `ValueError` (Muster exakt wie 1.3.11
dokumentiert). Fällt ohne eigene Zeile automatisch auf den geteilten `"default"`-Briefpapier-/
Rand-/Bausteinsatz zurück (`resolve_shared_document_type()`) -- **kein neues Datenmodell, keine
Migration**, entgegen der ursprünglichen Erwartung "Punkt 4 könnte eine Ausnahme brauchen": der
bereits bestehende Rückfallmechanismus aus 1.3.6 reicht vollständig aus. Portrait statt Landscape
(anders als der Büro-Stundenzettel), fünf Spalten (Datum/Auftrag/Zeitart/Tätigkeit/Stunden statt
neun), `build_din5008_header_block()` mit dem Mitarbeiternamen als "Empfänger" (DIN-5008-korrekt
für ein personenbezogenes Dokument) und der Personalnummer als zusätzlicher Meta-Zeile, sofern
gesetzt. Zeitart-Beschriftungen kommen server-seitig aus `get_option_group(db,
"time_entry_types")` (dieselbe Optionsgruppe, dieselbe Auflösung wie clientseitig in
`time_tracking_field.html`), keine hartkodierte Fallback-Tabelle im PDF selbst.

Kein neuer JSON-Endpunkt für die Bildschirmansicht -- bewusste Entscheidung: `field_timesheet.html`
ruft direkt das bereits bestehende, für `field` self-scoped `GET /api/time-entries?start_date=&
end_date=` auf (seit 1.3.56 self-scoped, siehe "Objekt-Filterung" oben) und gruppiert client-seitig
nach Tag. Nur die PDF-Erzeugung braucht zwangsläufig einen serverseitigen Weg: neuer Endpunkt
`GET /api/field-view/timesheet.pdf?year=&month=` (`app/routers/field_view.py`, `_any_role_dep`),
löst den Mitarbeiter ausschließlich über `request.state.erp_user` auf (kein Client-Parameter --
ein Monteur kann so nie den Stundenzettel eines Kollegen abrufen), Standard ist der laufende
Monat, 422 statt 500 ohne Mitarbeiterverknüpfung (anders als die übrigen, bewusst leer statt
fehlerhaft antwortenden Listen-Endpunkte dieser Datei -- ein Stundenzettel-PDF ohne Mitarbeiter
ergibt keinen Sinn, eine leere Liste dagegen schon).

**Punkt 5 -- Eigene Plantafel-Einträge ("Meine kommenden Termine").** Neuer Kartenabschnitt
direkt auf `/mobil` (bewusst KEIN eigener Reiter/keine eigene Seite wie bei Punkt 4 -- eine
einfache, datumssortierte Liste passt strukturell zu den drei bestehenden Kartenabschnitten
"Heutige Einsätze"/"Offene Berichte"/"Wartungen an meinen Objekten", anders als Punkt 4s
Monatswahl+PDF-Knopf). Neue Funktion `app/planning.py::list_upcoming_assignments_for_employee(db,
employee_id, *, today=None, days_ahead=30)` -- dieselbe Zuordnung wie die bereits bestehende
Tagesliste (`_employee_assignment_slot_condition()`, seit 1.3.61 aus
`list_todays_assignments_for_employee()` in eine gemeinsame, jetzt zweitverwendete Hilfsfunktion
ausgelagert, ebenso `_slot_query_with_order_options()`/`_slot_to_assignment_dict()`), aber über
ein Zeitfenster (±30 Tage voraus) statt eines einzelnen Tages. Bewusst `PlanningSlot.end_date >=
today` (nicht `start_date >= today`) -- ein bereits laufender, mehrtägiger Einsatz bleibt
sichtbar, auch wenn sein Slot vor dem Fensterbeginn angefangen hat; dieselbe Überlegung, die
schon bei der Tagesliste selbst gilt. Neuer Endpunkt `GET /api/field-view/upcoming`
(`app/routers/field_view.py`, `_any_role_dep`) -- löst den Mitarbeiter ausschließlich über
`request.state.erp_user` auf, bewusst eine leere Liste statt eines Fehlers ohne
Mitarbeiterverknüpfung (Muster `GET /api/field-view/maintenance-contracts`, da diese Karte kein
Kernbestandteil der Seite ist wie die Tagesliste). `mobil.html` rendert die Zeilen als reine,
NICHT anklickbare Karten (`<div>` statt `<a>`, anders als "Heutige Einsätze") -- bewusste, kleine
Abgrenzung, die die vom Nutzer betonte "reine Leseansicht, kein Zugriff auf die Plantafel selbst"
optisch unterstreicht, auch wenn ein Klick technisch ohnehin nirgends hinführen würde.

Geprüft, dass die volle Plantafel für Monteure gesperrt bleibt: `GET /planning`
(`app/routers/pages.py`) trägt weiterhin `_role_dep` (Büro/Admin, unverändert seit der
1.3.57-Seiten-Klassifizierung), `GET /api/planning` und die übrigen Endpunkte in
`app/routers/planning.py` tragen weiterhin `_role_dep` = `require_role(ROLE_ADMIN, ROLE_OFFICE)`
(unverändert seit Rest-Etappe Teil A, 1.3.54) -- keiner der fünf Punkte dieser Runde berührt
diese Datei.

**Der vom Nutzer verlangte, wiederholte Angriffstest** (`tests/test_v265_mobile_rename_and_extras.py::
TestVollePlantafelBleibtGesperrt`, gegen eine isolierte Testinstanz, nie gegen die echte
Datenbank): volle Plantafel-Seite (`/planning`) UND volle Plantafel-API (`GET /api/planning`,
`GET /api/planning/settings`) liefern für `field` weiterhin 403; ein `field`-Konto, das
`?employee_id=<Kollege>` an `GET /api/time-entries` anhängt, bekommt trotzdem nur die eigenen
Stunden zurück (die bestehende, seit 1.3.56 geltende Überschreibung greift unverändert); ein
`field`-Konto sieht über `GET /api/field-view/upcoming` nie die kommenden Plantafel-Einträge
eines Kollegen. Alle vier Fälle mit einem zweiten Testdurchlauf bestätigt: null "durchgelassen".
1267/1267 Tests grün.

### Kundendaten für einen Monteur: ausschließlich über den Bericht, nicht über eine Kundenseite

Enger gefasst als eine reine Rollen-Sperre auf `/customers/*`: ein Monteur soll Kundendaten nie
über eine eigene Seite oder eine Adresse mit Kunden-ID sehen, sondern ausschließlich das, was
im Einsatzbericht selbst steht. Geprüft, ob das inhaltlich schon vollständig ist -- war es
NICHT: `Order`/`ServiceReport` trugen Objektname/Anschrift (als Schnappschuss), aber weder
einen "Zugang" (Schlüssel, Codes, Hunde, Parken) noch einen vom Kunden-Hauptansprechpartner
unabhängigen "Ansprechpartner vor Ort" (Hausverwaltung vs. tatsächlich anzutreffende Person).

Ergänzt: `Property.access_notes`/`site_contact_name`/`site_contact_phone` (Migration
`1ccb91b19e8a`, alle nullable, bewusst NICHT das bestehende `notes`-Feld umgewidmet, um dort
bereits erfasste Freitexte nicht umzudeuten) -- gepflegt auf der Objektseite (`property.html`),
gelesen über einen neuen, auftragsbezogenen Weg **ohne** `/api/properties/{id}`:
`GET /api/orders/{order_id}/property` (`app/routers/service_reports.py`, Geschäftslogik
`get_property_context_for_order()` in `app/service_reports.py`, löst wie
`list_roof_areas_for_order()` über `order.project.property_id` auf) -- LIVE gelesen, kein
Schnappschuss, da sich ein Torcode/eine Kontaktperson ändern kann, ohne dass deshalb ein neuer
Auftrag entsteht. `service_reports.html` zeigt das in einer neuen Karte "Objekt & Zugang"
oberhalb des Berichts-Editors, sichtbar für jeden, der die Seite heute schon erreicht (Etappe 3
schränkt erst ein, WER die Seite erreicht -- die Anzeige selbst ist unabhängig davon richtig).

**Seit 1.3.55 gelöst, ohne Template-Änderung**: der Kundenname-Link in derselben Seite
(`document.getElementById('breadcrumb')`, `o.customer_id ? <a href="/customers/{id}"> : Text`)
wird für einen Monteur zu reinem Text, weil `OrderFieldAccessOut` (die Antwort von
`GET /api/orders/{id}` für `field`) bewusst kein `customer_id` trägt -- dieselbe Entscheidung wie
bei `PropertyAccessOut`, und keine Rollenlogik im Template nötig (Anmerkung "ausblenden, nicht
ausgrauen"). Der "Auftrag"-Link daneben (`/orders/{id}`, eine Büro-Seite) führt seit 1.3.57 für
einen Monteur auf `access_denied.html` (die Seite ist jetzt gesperrt, siehe "Seiten-
Klassifizierung" unten) -- kein Datenleck (die API dahinter war es ohnehin nie), aber ein
unnötiger Zwischenstopp; bewusst nicht mitgefixt, siehe „Bekannte, bewusst offene Punkte".

### Seiten-Klassifizierung (seit 1.3.57): dieselbe Standardverweigerung wie bei der API

Bis hierhin war ausschließlich die API rollengeprüft -- jede der (damals) 31 Seiten-Routen in
`app/routers/pages.py` rendierte ihr Gerüst für JEDE angemeldete Rolle, unabhängig davon, ob
die API-Aufrufe dahinter für diese Rolle überhaupt etwas lieferten. Für einen Monteur bedeutete
das: er konnte `/customers/{id}`, `/finanzen`, `/maintenance-contracts` usw. öffnen und sah eine
leere oder fehlerhafte Seite (die API-Aufrufe scheiterten längst mit 403) -- kein Datenleck, aber
auch keine echte Sperre, nur eine im Sidebar-Menü versteckte Tür, die trotzdem offen war. Auf
ausdrückliche Vorgabe geschlossen: **eine Seite, die eine Rolle nicht öffnen darf, muss
serverseitig sperren, nicht nur im Menü fehlen.**

- **Mechanismus, wiederverwendet statt neu erfunden**: `app/permissions.py::require_role()`
  trägt bereits die `_dk_roles`-Markierung (für den Audit-Test) und braucht für seine Prüfung
  nur `request.state.erp_user` -- exakt das, was auch eine Seiten-Route hat, keine
  Sonderfassung nötig. Jede Seiten-Route in `app/routers/pages.py` bekam deshalb schlicht
  `_role: AppUser = _role_dep` (Büro/Admin) bzw. `_any_role_dep` (jede Rolle) als zusätzlichen
  Parameter -- dieselben zwei Konstanten wie an jeder API-Datei dieser Etappe.
- **Fünf Seiten für `field`, jede andere Büro/Admin** (bei Einführung 1.3.57 waren es vier --
  `/mobil/stundenzettel` kam erst mit 1.3.61 dazu, `/vor-ort` heißt seit derselben Version
  `/mobil`, siehe "Monteursansicht: Umbenennung zu /mobil"): `/account`, `/mobil`,
  `/mobil/stundenzettel`, `/time-tracking`, `/orders/{order_id}/service-reports` -- exakt die
  Seiten, die ein Monteur tatsächlich braucht (Selbstbedienung, seine Einstiegsseite, sein
  eigener Stundenzettel, seine Zeitbuchung, sein Bericht). Jede andere
  Seite (Kunden, Objekte, Dachflächen, Projekte, Angebote/Aufträge/Rechnungen/Mahnungen,
  Stammdaten, Einstellungen, Aufgaben, Wartungsverträge, Prüfvorlagen, Mängelliste, Änderungs-
  historie, Adressimport, Zeiterfassungs-Backoffice) ist Büro/Admin -- gespiegelt an der bereits
  bestehenden API-Klassifizierung der jeweiligen Fachdomäne, keine neue Entscheidung.
  `/time-backoffice` und `/address-import` trugen bereits vorher `Depends(require_admin(...))`
  (admin-only) und blieben unverändert -- `require_admin()` markiert `_dk_roles` schon lange.
- **`/users` ist die einzige Seite mit einer bespoken Dependency statt `require_role(...)`**
  (`_require_users_page_access()`, `app/routers/pages.py`): exakt derselbe Bootstrap-Fall wie
  `POST /api/users` -- vor dem allerersten ERP-Benutzer gibt es niemanden, der eine Rollenprüfung
  erfüllen könnte, danach Büro/Admin wie die Benutzerliste selbst. Trägt deshalb keine
  `_dk_roles`-Markierung und steht einzeln begründet in der neuen `PAGE_AUDIT_EXEMPT`
  (`app/permissions.py`) -- zusammen mit `/login`, `/health`, `/manifest.json` (dieselben drei
  strukturellen Ausnahmen wie bei der API, jetzt für Seiten).
- **403 zeigt `access_denied.html`, nicht rohes JSON**: ein neuer Exception-Handler in
  `app/main.py` (`_role_check_403_shows_access_denied_page()`, registriert für `HTTPException`)
  fängt jeden 403 ab und rendert für Nicht-`/api/`-Pfade das bereits in Etappe 1 vorbereitete,
  aber nie verdrahtete `access_denied.html` -- jeder andere Statuscode und jeder `/api/`-Pfad
  läuft unverändert über FastAPIs eigenen Standard-Handler (`http_exception_handler`, daran
  delegiert, keine Kopie). "Zur Startseite" zeigt auf `app/permissions.py::
  default_home_page_for_role(role)` -- `/mobil` (bis 1.3.60 `/vor-ort`) für `field`, sonst `/` --,
  außer der Aufruf war anonym (nur im Bootstrap-Fall möglich, `_page_requires_login()` leitet
  sonst schon vorher auf `/login` um): dann auf `/users`, die einzige in diesem Zustand
  erreichbare Seite.
- **Login-Landing für `field` korrigiert, an zwei Stellen**: `default_home_page_for_role()`
  wird auch von `login_page()` genutzt (bereits angemeldeter Aufruf von `/login`, vorher
  hartkodiert `"/"`) -- ohne diese Korrektur hätte ein Monteur nach dem zweiten Login-Versuch
  auf einer jetzt gesperrten Seite gelandet. `login.html`s eigener, client-seitiger Rückfall
  ohne `next` (`"/projects"`, JS, kein gemeinsames Modul mit Python) bekam denselben Zweig
  separat dupliziert (`d.role==='field' ? '/vor-ort' : '/projects'`) -- die beiden
  unterschiedlichen Nicht-Feld-Rückfälle (`/` server-seitig, `/projects` client-seitig) sind
  ein bereits bestehender, dokumentierter Unterschied (siehe 1.3.47/1.3.48) und wurden nicht
  vereinheitlicht, nur jeweils um den `field`-Zweig ergänzt.
- **Ein vorher unbemerkter Test-Fund**: `tests/test_v256_login_wall_for_pages.py::make_user()`
  erzeugte Konten mit `role="user"` (der Rollenname vor dem Rechtekonzept) -- harmlos, solange
  keine Seite eine Rolle prüfte. Zwei Tests dieser Datei (bereits angemeldeter Nutzer erreicht
  `/`/`/tasks` direkt) schlugen mit der neuen Sperre entsprechend fehl, bis der Standard auf
  `role="office"` (den direkten Nachfolger von `"user"`) korrigiert wurde -- kein Fund an der
  neuen Logik selbst, ein veralteter Testfixture-Wert.
- **Audit-Test deckt jetzt beide Ebenen ab**: `tests/test_v260_role_audit.py::
  test_all_page_routes_have_an_explicit_role_check()` (Muster der API-Variante, dieselbe
  `_iter_role_marked_dependants()`-Hilfsfunktion, jetzt parametrisiert auf `/api/`- vs.
  Seiten-Routen) steht bei null unklassifizierten Seiten-Routen, direkt als harter Test (kein
  `xfail`-Zwischenschritt wie bei der API-Fassung, da hier von Anfang an vollständig gebaut).
  Eine zweite Testgruppe (`TestPageRouteClassification`) belegt stichprobenhaft, dass die
  Rollen dabei auch tatsächlich richtig zugeordnet sind (der Audit-Test allein sieht nur "trägt
  eine Markierung", nicht "die richtige") -- inkl. eines isolierten Tests für den neuen
  Exception-Handler selbst (HTML für Seiten, unverändert JSON für `/api/`, korrekter
  `home_url`-Wert für `field`/anonym).

### Aufgaben: heute gesperrt, nicht angefasst, dokumentierter Grund

Geprüft, bevor entschieden wurde: existiert heute überhaupt eine Aufgabe, die sinnvoll einem
Monteur statt dem Büro zugewiesen würde? Die echte Datenbank zeigt: **alle** aktuell
zugewiesenen Aufgaben (`Task.assigned_employee_id`) gehen an Employee-ID 1 -- Tobias, den
Geschäftsführer, verknüpft über `AppUser`-Konto "Tobias". Keine einzige Aufgabe ist an einen
der acht Dachdecker-Mitarbeiter (Vorarbeiter/Geselle/Auszubildende) oder die beiden
Büro-Mitarbeiterinnen adressiert. Automatisch erzeugte Aufgaben (Wartungs-Erinnerungen,
"buero_pruefen"-Mängelmaßnahme) landen laut Code ohnehin beim konfigurierten
Sachbearbeiter/Standard-Verantwortlichen -- fachlich eine Büro-Rolle, kein Monteurs-Vorgang.

**Entscheidung**: Aufgaben (`/tasks`, `/api/tasks*`, `/api/task-columns*`, `/api/task-settings`,
dazu die beiden `/api/tasks/{task_id}/finding`- und `.../create-follow-up-project`-Endpunkte, die
aus historischen Gründen in `app/routers/findings.py` statt `tasks.py` liegen)
bleiben für `field` vorerst vollständig gesperrt (umgesetzt in 1.3.52, Büro+Admin wie die übrige
Verwaltung) statt einer eigenen "nur eigene Aufgaben"-Filterung. Sollte sich der Betriebsablauf
ändern (eine Aufgabe wird künftig gezielt einem Monteur zugewiesen), ist das ein bewusster,
späterer Schritt -- keine stillschweigend mitgebaute Funktion ohne heutigen Anwendungsfall.

**Was dafür fehlen würde, festgehalten für den nächsten Durchgang** (nicht gebaut, nur
dokumentiert, wie verlangt) -- geprüft direkt am Code, nicht nur vermutet:

1. **Ein "eigene Aufgaben"-Filter existiert teilweise schon, aber lückenhaft.**
   `GET /api/tasks` (`app/routers/tasks.py::get_tasks()`) schränkt für jeden Nicht-Admin
   bereits heute auf `employee_id == request.state.erp_user.employee_id` ein, und
   `_require_task_access()` tut dasselbe für die Checklisten-Endpunkte
   (`POST/PUT/DELETE .../checklist-items*`). **Aber**: `PUT /api/tasks/{id}` (Titel/Status/
   Priorität/Zuweisung ändern), `DELETE /api/tasks/{id}` und die beiden
   Archivieren/Reaktivieren-Endpunkte prüfen GAR KEINE Eigentümerschaft -- ein Nicht-Admin
   könnte darüber heute schon jede beliebige Aufgabe ändern, nicht nur seine eigene, wenn er
   diese Endpunkte erreicht. Das ist eine bereits im Code bestehende Lücke, unabhängig vom
   Rechtekonzept -- fiele beim Öffnen von Aufgaben für `field` sofort auf, weil dann zum ersten
   Mal jemand mit einer wirklich anderen Interessenlage als "Büro" darauf träfe. Vor einer
   Öffnung für `field` müsste dieselbe `_require_task_access()`-Prüfung auch auf diese drei/vier
   Endpunkte ausgedehnt werden.
2. **Eine belastbare Zuweisung an den AppUser, nicht nur an den Employee.** Der bestehende
   Filter (Punkt 1) funktioniert nur, weil er `request.state.erp_user.employee_id` gegen
   `Task.assigned_employee_id` vergleicht -- verlässt sich also auf eine verlässliche
   Employee↔AppUser-Zuordnung. `AppUser.employee_id` ist aber nullable UND ohne
   Unique-Constraint (zwei AppUser-Konten könnten theoretisch dieselbe `employee_id` tragen,
   oder eine Aufgabe könnte einem Employee zugewiesen sein, der gar kein Login hat). Heute
   folgenlos (ein einziges Admin-Konto mit Employee-Verknüpfung), würde aber bei mehreren
   echten Monteurskonten zur tatsächlichen Fehlerquelle, sollte diese Zuordnung je nicht
   eindeutig sein.

### Sichtbarkeit in der Oberfläche: ausblenden, nicht ausgrauen (Fundament gelegt, noch nicht verdrahtet)

Ein Monteur soll nicht einmal sehen, DASS es Finanzen/Kalkulation/Stammdaten gibt -- kein
ausgegrauter, unklickbarer Menüpunkt. `_sidebar.html` bekommt dafür `is_office`/`is_field`
(neben dem bestehenden `is_admin`), nach demselben Muster berechnet -- in dieser Version noch
ungenutzt (keine Navigationseinträge wurden bereits umgestellt, das ist Teil der Etappe-2/3-
Umsetzung an den einzelnen Seiten).

**Ausnahme, wie gefordert**: wer eine Adresse von Hand eintippt (kein Menüpunkt führt dorthin,
also kein Ausblenden möglich), bekommt eine verständliche Meldung statt einer rohen
403-JSON-Antwort. Neues, eigenständiges Template `app/templates/access_denied.html` (Muster
`login.html` -- eigenständige Seite, kein `_sidebar.html`-Include, da eine Person ohne Zugriff
auf eine Seite meist auch nicht die volle Navigation sehen soll) mit einem Link zurück zur
jeweiligen Startseite. Noch nicht in die Middleware verdrahtet -- das braucht die
Seiten-Klassifizierung aus Etappe 2/3 (welche der 31 Seiten ist für wen gedacht), nicht nur die
API-Klassifizierung.

### Bestandsschutz und sichere Voreinstellung beim Anlegen (`users.html`)

Tobias und "Admin" bleiben unverändert `role="admin"` -- keine ihrer Zeilen wurde durch die
Migration berührt (0 betroffene Zeilen, siehe oben). Für NEUE Konten:
`AppUserCreate`/`AppUserUpdate` (`app/schemas.py`) haben jetzt `default="field"` statt
`default="user"` -- die am wenigsten privilegierte Rolle, nicht mehr eine, die praktisch schon
immer vollen Zugriff bedeutete. Das Auswahlfeld in `users.html` listet "Monteur" absichtlich
zuerst (Browser wählen ohne Interaktion die erste `<option>`). **Zusätzlich, wie verlangt, eine
Warnung**: legt jemand ein NEUES Konto an, ohne das Rollenfeld ausdrücklich zu ändern
(`roleTouched`-Flag, per `onchange` gesetzt), erscheint vor dem Speichern eine
`confirm()`-Bestätigung mit der Rolle, die tatsächlich vergeben würde -- verhindert, dass eine
Rolle "einfach passiert", unabhängig von der (bereits sicheren) Voreinstellung selbst. Gilt
bewusst nur beim Anlegen, nicht beim Bearbeiten eines bestehenden Kontos (dessen aktuelle Rolle
ist in der Liste ohnehin sichtbar, keine verdeckte Änderung möglich).

### Etappenplan

1. **Fundament** (diese Version): dritte Rollenstufe, `require_role()`, Migration,
   Standardverweigerungs-Mechanismus samt Audit-Test. -- **fertig**.
2. **Rollen-Gate nachziehen**: `require_role(...)` an alle heute ungeschützten Finanz-/
   Kalkulations-/Mitarbeiter-/Stammdaten-/Verwaltungs-Endpunkte hängen, entlang der vom
   Audit-Test namentlich gelisteten Routen. -- **fertig (1.3.51-1.3.55)**: der riskante Batch
   (Finanzen/Kalkulation/Mitarbeiter/Einstellungen/Benutzer/Historie/Aufgaben, 1.3.52), Teil A
   des Rests (alle Dateien ohne Monteur-Bezug, 1.3.54) und Teil B (die 65 aktiv von Monteuren
   genutzten Endpunkte in `orders.py`/`service_reports.py`/`findings.py`/`inspection_templates.py`/
   `time_tracking.py`, 1.3.55 -- erst NACH Etappe 3, weil ein blankes Büro+Admin-Gate dort den
   Einsatzbericht-Ablauf gebrochen hätte, genau der Fehler von `GET /api/employees` in 1.3.53).
   Der Audit-Test steht bei null und ist seit 1.3.55 ein harter Test (`xfail` entfernt).
3. **Objekt-Filterung für `field`** -- **fertig (1.3.55-1.3.59)**: `field_may_access_order()`
   (`app/orders.py`, zwei Wege, siehe "Objekt-Filterung" oben) und `require_field_order_access()`
   (`app/routers/orders.py`) sind auf `orders.py`/`service_reports.py`/`findings.py` angewendet;
   `properties.py`/`roof_areas.py` brauchten sie nicht (seit Teil A Büro/Admin, der Monteur liest
   Objekt und Dachflächen ausschließlich auftragsbezogen über `service_reports.py`). Nachtrag
   1.3.56 nach Betreiber-Rückmeldung: "Wartung durchführen" für Monteure, reduzierte Historie,
   Büro sieht alle Zeitbuchungen, `sign_report()` geprüft. **Seit 1.3.57 zusätzlich die
   Seiten-Klassifizierung**: dieselbe Standardverweigerung gilt jetzt auch für die
   Seiten-Routen selbst (`app/routers/pages.py`, `Depends(require_role(...))` je Route,
   `PAGE_AUDIT_EXEMPT` für die vier strukturellen Ausnahmen), ein 403 zeigt `access_denied.html`
   statt einer rohen JSON-Antwort (`app/main.py`s Exception-Handler), der Audit-Test deckt beide
   Ebenen ab -- siehe "Seiten-Klassifizierung" unten für die volle Herleitung. **Seit 1.3.58
   zusätzlich der `/mobil`-Vertragsfinder** (damals noch unter `/vor-ort`)**: die Karte "Wartungen
   an meinen Objekten" (siehe eigener Abschnitt "Objekt-Filterung" → "Vertragsfinder auf /mobil"
   unten) schließt die
   zuletzt offene Lücke -- ein Monteur konnte bisher nur eine bereits geplante Wartung
   durchführen, keine ungeplante an einem Objekt starten, an dem er gerade arbeitet. **Seit
   1.3.59 ein Sicherheitstest gegen eine isolierte Testinstanz** (nie gegen die echte
   `dachkonzepte_erp.db`) mit zwei echten Funden, beide behoben: fremde Berichte auf einem
   gemeinsamen Auftrag lesen/ändern/löschen/signieren (siehe "Berichts-Eigentümerschaft" oben)
   und eine Wartung auf einem fremden Vertrag per geratener ID auslösen (siehe "Fund: fremde
   Wartung per geratener Vertrags-ID" oben) -- ein zweiter Durchlauf desselben Angriffstests
   bestätigt beide als geschlossen. **Seit 1.3.60 zusätzlich die reduzierte Zeiterfassung**
   (siehe "Zeiterfassung für Monteure" oben) -- die volle, sidebar-getragene `time_tracking.html`
   war zuvor die letzte für `field` erreichbare Seite ohne eine eigens dafür gebaute, schmale
   Ansicht. **Noch offen**: der "Auftrag"-Link in `service_reports.html`, der auf eine jetzt
   gesperrte Büro-Seite zeigt, und die Kolonnenführer-Rolle für Gruppenbuchungen (beide siehe
   "Bekannte, bewusst offene Punkte").
4. Erstes echtes `field`-Testkonto anlegen, vollständigen Monteurs-Ablauf im Browser
   durchklicken. -- offen.

### Vier Rollen (seit 1.4.7/1.4.8, Etappe 1: Rollen-Erweiterung, Etappe 2: die Verengungen)

Vom Betreiber beauftragter Umbau auf dem obigen Fundament -- Vorgehen wie bei den größeren
Umbauten dieses Projekts üblich: erst ein reiner Befund + Vorschlag (keine Codeänderung,
separat berichtet), dann nach Bestätigung der Bau, in zwei ausdrücklich angeforderten Etappen.
**1.4.7 war Etappe 1 -- die reine Rollen-Erweiterung** (bis dahin sah `buero_auftrag` überall
exakt dasselbe wie `buero_finanzen`). **1.4.8 ist Etappe 2 -- die Verengungen selbst**, siehe
eigener Unterabschnitt unten: ab jetzt unterscheiden sich beide Rollen tatsächlich.

**Anlass**: die bisherige Rolle `office` bündelte zu viel unter einem Dach -- ein Sachbearbeiter,
der Angebote schreibt, sah damit automatisch auch die Kostenstruktur des Betriebs
(Kalkulationsgrundlagen, künftig Betriebskosten) und die Vergütung der Kollegen. Der Betreiber
wollte das trennen, ohne die seit "Rechtekonzept" etablierte Standardverweigerung/den
Audit-Mechanismus neu zu erfinden.

**Vier Rollen** (`app/permissions.py`): `admin` bleibt alles inklusive Systemverwaltung.
`buero_finanzen` = alles Fachliche/Kaufmännische PLUS Betriebskosten-Übersicht (künftig)/
Kalkulationsgrundlagen/Stundenverrechnungssatz-Herleitung/Mitarbeitervergütung -- Schnittstelle
zum Steuerberater, keine Systemverwaltung. `buero_auftrag` = derselbe fachliche/kaufmännische
Kern (Projekte, Angebote MIT voller Kalkulation/Marge/Einkaufspreisen -- das bleibt bewusst
unverengt, siehe unten --, Aufträge, Rechnungen, Mahnwesen, Planung, Wartung, Anfragen, Aufgaben,
Betriebsmittel-Bestand) OHNE die vier finanzspezifischen Bereiche oben. `field` unverändert.

**Die Hierarchie -- die zentrale, vom Betreiber selbst gestellte Frage** ("kann buero_finanzen
alles, was buero_auftrag kann, plus mehr? Prüfe, ob has_role() das als Hierarchie abbilden
kann"): ja, über eine neue, parallele Prüfart. `ROLE_RANK` (`app/permissions.py`) ist eine reine
Ganzzahl-Kette -- `field=0 < buero_auftrag=1 < buero_finanzen=2 < admin=3` --, `has_min_role(user,
min_role)` prüft `ROLE_RANK[user.role] >= ROLE_RANK[min_role]`, `require_min_role(min_role, *,
message=...)` ist die dazugehörige FastAPI-Dependency-Fabrik (Muster `require_role()`, trägt
ebenso eine `_dk_roles`-Markierung -- hier die vollständige, aus `ROLE_RANK` abgeleitete Menge
aller Rollen ab diesem Rang, damit `tests/test_v260_role_audit.py` ohne jede Sonderbehandlung
weiterläuft). `has_role()`/`require_role()` (die FLACHE Mengenprüfung) bleiben unverändert
bestehen -- für `require_admin()`-äquivalente Fälle und echte "für jede Rolle offen"-Stellen,
keine Ablösung, eine zweite, weiterhin gültige Prüfart daneben.

**Warum das die Migration deutlich weniger invasiv macht, als zunächst befürchtet**: eine
exhaustive Durchsuchung aller `require_role(...)`-Aufrufe im Projekt (vor dem Bauen, nicht
danach) ergab, dass im GESAMTEN Projekt nur genau ZWEI Rollenkombinationen je vorkamen --
`require_role(ROLE_ADMIN, ROLE_OFFICE)` in ~40 Dateien und `require_role(ROLE_ADMIN, ROLE_OFFICE,
ROLE_FIELD)` in ~15 Dateien, keine dritte. Beide übersetzen sich verlustfrei und OHNE
Einzelentscheidung in `require_min_role(ROLE_OFFICE_AUFTRAG)` bzw. `require_min_role(ROLE_FIELD)`
-- ein Skript hat diese reine Textersetzung über ~55 Endpunkt-Dependencies in ~45 `app/routers/`-
Dateien vorgenommen, gefolgt von einer automatischen Importzeilen-Bereinigung (ungenutzte Symbole
entfernt, `require_min_role` ergänzt) und einer echten Modul-für-Modul-Importprobe (jedes
`app.routers.*`-Modul einzeln importiert -- fängt einen falschen/fehlenden Import sofort als
`ImportError`, nicht erst als Testfehler). Zwei App-Kernmodule brauchten dieselbe Umstellung
manuell: `app/tasks.py::list_tasks_for_user()` (`has_role(user, ROLE_ADMIN, ROLE_OFFICE)` ->
`has_min_role(user, ROLE_OFFICE_AUFTRAG)`) und `app/search.py::OFFICE_ROLES` (die EINE, von allen
18 Büro-Suchquellen referenzierte Konstante, erweitert auf `{ROLE_ADMIN, ROLE_OFFICE_FINANZEN,
ROLE_OFFICE_AUFTRAG}` -- bestätigt exakt die in der vorangegangenen Bestandsaufnahme getroffene
Vorhersage, dass die Suche nur EINE Konstantenänderung braucht, keine 18 Einzelentscheidungen).
Ein einziger, vom Skript naturgemäß nicht erfasster manueller Rollenvergleich
(`app/routers/pages.py::_require_users_page_access()`, `user.role not in (ROLE_ADMIN,
ROLE_OFFICE)`, kein `require_role(...)`-Aufruf, sondern eine Inline-Bedingung im Bootstrap-Pfad)
wurde beim Import-Check als `ImportError` sichtbar und auf `has_min_role(user,
ROLE_OFFICE_AUFTRAG)` umgestellt. Drei literale `can(current_user, 'admin', 'office')`-Aufrufe in
`_sidebar.html`/`_topbar.html` (Jinja-Templates kennen keine Rollenkonstanten, nur String-Literale,
`can()` selbst ist eine FLACHE Mengenprüfung ohne Hierarchie -- siehe `app/routers/pages.py::_can()`)
wurden auf `can(current_user, 'admin', 'buero_finanzen', 'buero_auftrag')` erweitert.
`require_admin()` (`app/deps.py`) bleibt in dieser Etappe unverändert -- die Verschiebung von
`time_backoffice.py`/`address-import` auf `buero_auftrag` ist Teil von Etappe 2.

**Migration `7677d9d878ba`** (reine Daten-Migration, kein Schema-Umbau -- `app_users.role` war
immer schon eine unbeschränkte `String(30)`-Spalte ohne Constraint, siehe oben): ein bestehendes
`role="office"`-Konto wird `buero_finanzen` -- die umfassendere der beiden neuen Rollen, exakt
wie vom Betreiber vorgegeben (Bestandsschutz: ein bereits eingerichtetes Büro-Konto darf durch
den Split nie Zugriff verlieren, umgekehrt zur "sicherste Rolle zuerst"-Regel bei NEUEN Konten
unten). **Vor der Migration geprüft, nicht geraten, wie ausdrücklich verlangt** ("ich will
wissen, wer welche Rolle bekommt, bevor sie vergeben wird"): die echte, lokale
`dachkonzepte_erp.db` trägt genau zwei Konten -- Tobias (mit Mitarbeiterverknüpfung) und Admin
(reines Systemkonto) --, BEIDE bereits `admin`. **0 Zeilen betroffen.** Migration trotzdem
angewendet (Kettenanschluss für jede andere Installation), Bestand danach erneut verifiziert:
beide Konten unverändert `admin`. `downgrade()` bildet beide neuen Werte gleich auf `office`
zurück (kann die Aufteilung nicht verlustfrei rückgängig machen, dieselbe Konvention wie die
vorangegangene Rollen-Migration `7a2b4e9f1c3d`).

**Neue Konten, sicherer Vorgabewert** (`app/schemas.py::AppUserCreate`/`AppUserUpdate`): Pattern
erweitert auf alle vier Rollen, der SCHEMA-Vorgabewert (greift nur, wenn ein Aufruf `role` ganz
weglässt -- `users.html` schickt immer einen ausdrücklich gewählten Wert) geändert von `"field"`
auf `"buero_auftrag"` -- die restriktivere der beiden Bürorollen, damit niemand allein durch
Weglassen des Feldes Zugriff auf Kalkulationsgrundlagen/Mitarbeitervergütung erbt. Die
Sidebar-Voreinstellung in `users.html` bleibt davon bewusst UNABHÄNGIG weiterhin `field`
(Monteur) -- die am wenigsten privilegierte Rolle über alle vier Stufen hinweg, unverändert seit
1.3.51 (Begründung: die beiden Vorgaben beantworten unterschiedliche Fragen -- "welche der zwei
Bürorollen, falls office unspezifisch bliebe" vs. "welche Rolle soll ein Administrator beim
Anlegen eines neuen Kontos ohne bewusste Wahl voreingestellt sehen", und für Letzteres bleibt die
niedrigste Stufe insgesamt die sicherste Antwort). Rollen-Dropdown zeigt jetzt vier Optionen
("Monteur"/"Büro – Auftrag"/"Büro – Finanzen"/"Administrator", in dieser Rangfolge), die
bestehende Bestätigungsabfrage beim Anlegen ohne ausdrücklich gewählte Rolle bleibt unverändert.

**Testfolgen**: ~140 Vorkommen von `role="office"`/`ROLE_OFFICE` über ~35 Testdateien einzeln
durchgesehen und eingeordnet -- der weit überwiegende Teil sind reine Testaufbau-Stellen,
mechanisch auf `buero_auftrag` umbenannt (Wahl als Repräsentant, nicht willkürlich: es ist die
untere der beiden Bürorollen-Schwellen, ein damit erfolgreicher Test beweist bei einer
`>=`-Rang-Prüfung automatisch, dass auch `buero_finanzen`/`admin` bestehen würden). Eine kleine
Zahl von Stellen, die ausdrücklich "office UND admin dürfen beide" belegen sollten, wurde auf
alle drei nicht-Monteur-Rollen erweitert statt nur umbenannt -- stärkerer Nachweis der Hierarchie
an genau den Stellen, die das schon vorher zeigen wollten (u. a.
`TestRoleGateOnCustomersInvoicesReminders`, die Aufgaben-/Seiten-Klassifizierungstests in
`test_v260_role_audit.py`, die Büro-Suche in `test_v270_office_search.py`).
`tests/test_v261_permissions_foundation.py`s Migrationstest für die HISTORISCHE Migration
`7a2b4e9f1c3d` (role='user' -> 'office') blieb bewusst unverändert -- der testet eine bereits
abgeschlossene, andere Migration. Neue, dedizierte Datei `tests/test_v281_role_hierarchy.py` --
end-to-end-Nachweis der Hierarchie über eine echte FastAPI-Testroute (nicht nur die Funktion
isoliert): `require_min_role(ROLE_OFFICE_AUFTRAG)` lässt `buero_auftrag`, `buero_finanzen` UND
`admin` durch, ohne dass Letztere in der Dependency-Definition einzeln genannt wurden; ein liegen
gebliebener Altwert (`"office"`) fällt an JEDER Schwelle sicher durch (Standardverweigerung, kein
stiller Rückfall). Volle Suite: 1514 Tests grün.

**Etappe 2 (seit 1.4.8) -- die Verengungen, umgesetzt.** Drei der vier ursprünglich angekündigten
Punkte wurden gebaut, der zweite (Betriebskosten-Übersicht) bleibt ein reiner Vormerkposten, da
er im Code noch nicht existiert:

1. **Kalkulationsgrundlagen/Stundenverrechnungssatz-Herleitung -> `buero_finanzen`.** Wie beim
   Nachschärfen vorab geklärt (siehe Herleitung oben, unverändert gültig): `GET/PUT
   /api/calculation-settings` (`app/routers/settings.py`) und alle 4 Endpunkte in
   `app/routers/labor_rate.py` (ein einziger Modul-`_role_dep`) sind auf
   `require_min_role(ROLE_OFFICE_FINANZEN)` verengt -- das ist genau die Stelle, an der die
   Bestandteile GEPFLEGT werden. Der fertige Satz bleibt für `buero_auftrag` dort sichtbar, wo er
   ANGEWENDET wird (Angebotskalkulation/Leistungskatalog), ohne einen eigenen, neuen Endpunkt --
   diese Trennung ergab sich bereits aus der bestehenden Architektur, keine Endpunkt-Aufteilung
   nötig.
2. **Betriebskosten-Übersicht** -> `buero_finanzen` (existiert im Code weiterhin nicht, bleibt
   reiner Vormerkposten für ein künftiges Feature).
3. **Mitarbeitervergütung -> `buero_finanzen`, der Bestand bleibt `buero_auftrag`.** Neues
   `EmployeeRosterOut`-Schema (`app/schemas.py`) -- Name, Funktion, Kontakt, Planung,
   Kosten-Zuordnung (eine Kategorie, kein Betrag), OHNE `compensation_type`/`hourly_wage`/
   `monthly_salary`/`effective_hourly_wage`/`annual_gross_wage`. `app/routers/employees.py::
   _employee_out_for_role()` wählt je Rolle zwischen `EmployeeOut` (buero_finanzen/admin),
   `EmployeeRosterOut` (buero_auftrag) und `EmployeeNameOut` (field, unverändert seit 1.3.53) --
   angewendet auf Liste/Sachbearbeiter/Einzelabruf. **Anlegen/Bearbeiten komplett auf
   `buero_finanzen`**, nicht nur die Lohnfelder -- `master_data_form.html::employeeForm()` ist
   EIN kombiniertes Formular mit den Lohnfeldern direkt darin (Regel 10), eine Rechte-Aufteilung
   hätte ein zweites Formular gebraucht und das Risiko eingeführt, dass ein für `buero_auftrag`
   unsichtbares Lohnfeld beim Speichern den Wert eines Kollegen stillschweigend auf 0/`None`
   überschreibt -- bewusste, transparent gemeldete Erweiterung über die wörtliche Anfrage
   hinaus. `_require_finanzen_for_employees()` (`app/routers/pages.py`) sperrt zusätzlich die
   beiden Formular-SEITEN selbst, `master_data.html` blendet Vergütungsspalte/"Gewichteter
   Mittellohn"/"+ Hinzufügen"/"Bearbeiten" für `buero_auftrag` aus (ausblenden, nicht ausgrauen).
   **Eigener, bei der Umsetzung gefundener Zusatzpunkt, in der ursprünglichen Anfrage nicht
   benannt**: die Änderungshistorie (`GET /api/audit-logs`) zeigt Vorher-/Nachher-Werte und
   angelegt/gelöscht-Schnappschüsse über ALLE Entitäten -- auch eine `hourly_wage`-Änderung im
   Klartext. `app/audit.py::WAGE_FIELD_NAMES`/`redact_wage_snapshot()` entfernen für
   `buero_auftrag` betroffene "geändert"-Zeilen vollständig und bereinigen "angelegt"/
   "gelöscht"-Schnappschüsse um die drei Lohnschlüssel, ohne die `AuditLog`-Zeile selbst zu
   mutieren; `buero_finanzen`/`admin` sehen die Historie unverändert vollständig, andere
   Entitäten bleiben für `buero_auftrag` unangetastet sichtbar.
4. **Zeiterfassungs-Backoffice** (`app/routers/time_backoffice.py`, `/time-backoffice`, 15
   Endpunkte) -> von `require_admin()` auf `require_min_role(ROLE_OFFICE_AUFTRAG)` angehoben.
   Vor der Anhebung wie verlangt geprüft, ob dabei Vergütung mitsichtbar wird -- kein Fund
   (`EmployeePayrollSettingsOut` trägt nur eine DATEV-Personalnummer-Zuordnung, `backoffice_summary()`/
   `build_timesheet_pdf()`/`build_time_csv()` zeigen ausschließlich Stunden, `build_datev_export()`s
   "Lohnart" ist eine Buchungskategorie, kein €-Betrag) -- die gesamte Datei hebt sich deshalb
   einheitlich an, ohne interne Verengung. **`/address-import` bleibt bewusst UNVERÄNDERT
   admin-only** -- die Betreiberanfrage nannte ausdrücklich nur "das Zeiterfassungs-Backoffice",
   `require_admin()` bleibt in `app/routers/pages.py` deshalb weiterhin importiert und für diese
   eine Seite in Gebrauch.

**Beim Bauen gefundener Jinja-Fehler, behoben**: die neuen `{% if can(current_user, 'admin',
'buero_finanzen') %}`-Bedingungen in `settings.html`/`master_data.html` verließen sich auf ein
`{% set current_user = ... %}` aus dem eingebundenen `_sidebar.html` -- ein `{% set %}`
innerhalb eines `{% include %}` wirkt in Jinja aber NICHT in der einbindenden Vorlage nach,
unabhängig von der Rolle. Beide Dateien setzen `current_user` seither selbst, direkt nach
`<body>`. Ohne diesen Fund hätte `/settings` und `/master-data` für JEDE Rolle mit
`UndefinedError` abgebrochen -- durch den bereits bestehenden `test_v218_template_rendering.py`
gefangen, nicht durch manuelles Ausprobieren.

**Angriffstest zum Abschluss, wie vom Betreiber verlangt** (`tests/test_v282_role_narrowing_etappe2.py`,
18 Tests, je ein Testkonto pro Rolle): `buero_auftrag` bekommt 403 auf Kalkulationsgrundlagen/
Stundenverrechnungssatz-Herleitung/Mitarbeiter-Schreiben, kein Lohnfeld in irgendeiner Antwort
(rekursiver Schlüssel-Scan, auch durch als JSON-String codierte `AuditLogOut.details`-Werte
hindurch); `buero_auftrag` erreicht das Zeiterfassungs-Backoffice (erlaubt), aber ohne
Lohndaten; `buero_finanzen` sieht alles davon (erlaubt); `field` bleibt überall gesperrt, wie
zuvor. Null durchgelassen. Volle Suite: 1532 Tests grün.

## Dateiablage je Objekt ("Runde 2" der Monteurs-Erweiterung, seit 1.3.62)

Ziel (Betreibervorgabe): jeder Mitarbeiter -- auch Monteure -- kann Bilder und Dokumente zu einem
Objekt hochladen und ansehen, mit einer admin-gesteuerten Freigabe für Monteure UND einer
kategorieabhängigen Sperre für sensible Dokumente. Vorgehen ausdrücklich in Etappen: zuerst
Befund+Vorschlag (kein Code), dann diese Version -- **nur das Fundament** (Kategorie-Stammdaten,
Migration, feste Code-Sperrliste) --, danach erst die mobile Objektansicht und die geteilte Suche,
jeweils erst nach Bestätigung des vorherigen Schritts.

### Befund vor dem Bauen (Runde-2-Vorlauf, keine Codeänderung)

Vier bestehende Upload-Wege, unterschiedlich objekt-/projekt-/kundenbezogen: `roof_area_sketches`
(an `RoofArea`, damit indirekt an `Property`), `project_files`/`ProjectDocument` (an `Project`,
nicht direkt an `Property`), `customer_documents`/`CustomerDocument` (an `Customer`, nicht an
`Property`), `service_report_photos` (an `Finding`/`InspectionItem` über den Einsatzbericht).
**Keiner der vier hängt heute direkt an einem `Property`** -- eine Dateiablage je Objekt bräuchte
entweder eine neue, objektbezogene Ablage oder eine Zusammenführung der bereits projekt-/
kundenbezogenen Dokumente über die Objektzuordnung. Alle vier folgen demselben Speichermuster:
`ERP_DATA_DIR`/`data_dir()` (siehe "Geheimnisse für den Serverbetrieb" oben) plus einem
dedizierten, rollen-geprüften Auslieferungsendpunkt -- kein `StaticFiles`-Mount irgendwo im
Projekt. `resize_and_store_photo()` (`app/service_report_photos.py`, 1.2.17) verkleinert Fotos mit
Pillow (`exif_transpose()` + `thumbnail()` auf 1600px + JPEG q82) -- dabei ein echter,
architektonischer Fund: der Aufrufer (`post_service_report_photo`, eine `async def`-Route) ruft
diese synchrone, CPU-gebundene Funktion direkt auf, ohne `run_in_threadpool()`/
`asyncio.to_thread()` -- blockiert damit einen der beiden gunicorn-Arbeitsprozesse des
4-GB-Produktivservers (siehe "Produktivbetrieb" oben, `-w 2`) für die Dauer jeder Verkleinerung,
die Hälfte der Gesamtkapazität. Für eine künftige, neue Foto-Upload-Route in der Objektablage
NICHT verbatim kopieren -- entweder eine gewöhnliche `def`-Route (Starlette threadpoolt synchrone
Routen automatisch) oder ein expliziter `run_in_threadpool()`-Aufruf.

Als Vorbild für den künftigen Objektzugriff eines Monteurs vorgeschlagen (noch nicht gebaut,
Entscheidung steht noch aus): dasselbe Zwei-Wege-Muster wie `field_may_access_order()`
(`app/orders.py`, siehe "Rechtekonzept" → "Objekt-Filterung" oben) -- Planungsbezug (aktuell/nah
zugeordnet) ODER ein eigener, bereits angelegter Bezug (z. B. ein selbst hochgeladenes Dokument),
damit ein Monteur nach einer Umplanung nicht den Zugriff auf bereits Hochgeladenes verliert.

### Entscheidungen des Betreibers für diese und die folgenden Etappen (bereits getroffen, noch nicht alle umgesetzt)

1. **Objekt statt Projekt als Leitkonzept.** In der künftigen mobilen Ansicht öffnet ein Monteur
   ein Objekt und sieht die Dokumente ALLER nicht archivierten Projekte dieses Objekts,
   zusammengeführt, nach Kategorie gruppiert -- "die Pläne von der Baustelle Musterstraße", nicht
   "die Pläne aus Projekt P-2026-0012". Eigene Uploads eines Monteurs binden sich an das OBJEKT,
   nicht an ein bestimmtes Projekt (ein spontaner Einsatz hat oft gar kein Projekt) -- ob das eine
   eigene, objektbezogene Ablage-Tabelle braucht oder einem Sammelprojekt des Objekts zugeordnet
   wird, ist noch offen; der Betreiber neigt zur eigenen, objektbezogenen Ablage. **Noch nicht
   gebaut** -- gehört zur nächsten Etappe.
2. **Kategorie-Stammdaten mit `is_sensitive`/`is_field_visible`** -- diese Version, siehe unten.
3. **Feste Code-Sperrliste zusätzlich zur Einstellung** -- diese Version, siehe unten
   (`HARD_LOCKED_CATEGORY_KEYS`).
4. **Geteilte Suche mit serverseitiger Feldbegrenzung.** Eine gemeinsame Kernfunktion mit
   unterschiedlicher Feld-/Ergebnisbegrenzung statt zweier getrennter Implementierungen (Muster:
   genau das, was bei `build_customer_and_meta_block()` mit drei divergierenden Varianten zum
   Problem wurde, siehe "Kopfbereich" oben). Die Begrenzung für Monteure muss dabei SERVERSEITIG
   sitzen, nicht nur in der Aufrufweise -- ein Monteur, der den Büro-Suchendpunkt direkt aufruft,
   muss dieselbe Begrenzung bekommen, nicht die vollen Ergebnisse. **Noch nicht gebaut** -- gehört
   zur übernächsten Etappe (nach der mobilen Objektansicht).

### Diese Version: Kategorie-Stammdaten (`DocumentCategory`), Migration, zwei unabhängige Schlösser

Siehe `app/document_categories.py` für die vollständige, im Moduldocstring festgehaltene
Begründung -- hier nur die Zusammenfassung. Echte Stammdatentabelle statt einer weiteren
Optionsgruppe (dieselbe Hochstufung wie `RoofComponentType`/`RoofLayerType`, 1.2.19/1.2.18): eine
reine Auswahlliste kann `is_sensitive`/`is_field_visible` nicht tragen. `key` bleibt bewusst
textidentisch zu den bisherigen Optionswerten der abgelösten Gruppe `project_document_categories`
(`app/option_settings.py`) -- die bestehenden, unveränderten Freitext-Spalten
`CustomerDocument.category`/`ProjectDocument.category` matchen dadurch unverändert weiter.

**Acht Kategorien** (`DEFAULT_CATEGORIES`, wortgleich aus der abgelösten Optionsgruppe): Pläne,
Bilder / Fotos, Lieferscheine, Aufmaß (alle vier `is_field_visible=True`), Schriftverkehr (weder
sensibel noch sichtbar), Verträge / Freigaben und Rechnungen / Belege (beide `is_sensitive=True`),
Sonstiges (Rückfallkategorie, weder sensibel noch sichtbar).

**Zwei unabhängige Schlösser, wie ausdrücklich vom Betreiber verlangt ("zwei unabhängige
Schlösser, kein gemeinsamer Schlüssel")**:
1. `is_sensitive`/`is_field_visible` in `DocumentCategory` selbst -- `create_category()`/
   `update_category()` (`app/document_categories.py`) lehnen die Kombination
   `is_sensitive=True` + `is_field_visible=True` grundsätzlich ab, unabhängig vom Key. Zusätzlich
   ist `is_sensitive` **einmal gesetzt unveränderlich** -- `update_category()` verweigert jeden
   Versuch, eine bereits sensible Kategorie wieder auf `is_sensitive=False` zu setzen (weder über
   die Oberfläche noch über die API, da beide denselben Endpunkt nutzen).
2. `HARD_LOCKED_CATEGORY_KEYS` (`frozenset({"Rechnungen / Belege", "Verträge / Freigaben"})`) --
   eine feste, im Code verankerte Sperrliste, die `field_may_see_category()` UNABHÄNGIG von den
   beiden Datenbankfeldern prüft. Selbst wenn jemand die `document_categories`-Tabelle direkt
   manipuliert (rohes SQL, ein Bug in einer künftigen Änderung), bleibt `field_may_see_category()`
   für diese beiden Kategorien hart auf `False` -- kein gemeinsamer Prüfpfad mit Schloss 1. Per
   Test belegt (`tests/test_v266_document_categories.py::
   test_field_may_see_category_blocks_hard_locked_keys_even_with_tampered_flags`): ein
   `DocumentCategory`-Objekt wird dort DIREKT konstruiert, unter vollständiger Umgehung von
   `create_category()`/`update_category()`, mit `is_field_visible=True` für einen gesperrten Key
   -- `field_may_see_category()` liefert trotzdem `False`.

`create_category()`/`update_category()` sind noch UNGENUTZT von jedem Anzeigepfad in dieser
Version (kein Monteur sieht heute schon eine Kategorie -- die mobile Objektansicht kommt erst in
der nächsten Etappe) -- die Validierung ist bereits vollständig, damit die kommende Etappe darauf
aufbauen kann, ohne die Schloss-Logik selbst nachzuziehen.

**Migration/Backfill der bestehenden Freitext-Kategorien** (`category_id`, neue, zusätzliche
FK-Spalte -- `category`, der Freitext, bleibt unverändert stehen und ist weiterhin das einzige
Feld, das das bestehende Upload-/Bearbeiten-Formular direkt beschreibt). Migration `9137945e8785`
folgt Regel 1 (server_default bei NOT-NULL-Spalten auf bestehenden Tabellen): `category_id` wird
zunächst NULLABLE angelegt (ein `server_default` auf eine konkrete ID wäre fragil, da der
Fremdschlüssel auf eine erst in DERSELBEN Migration befüllte Tabelle zeigt), aus dem Bestand
befüllt (`_resolve_category_id()`, standalone und eigenständig testbar direkt in der
Migrationsdatei, Muster aus 1.2.19/1.3.12/1.3.22), erst danach auf NOT NULL gesetzt.
Zuordnungsregel: exakte Übereinstimmung des Freitexts gegen `key`, sonst Rückfall auf
"Sonstiges" -- NIE auf eine sichtbare oder sensible Kategorie, im Zweifel gesperrt statt offen.

**Vor dem Schreiben gegen die echte, lokale Datenbank geprüft, wie verlangt** ("berichte mir,
welche Strings du vorfindest"): `customer_documents` war zum Zeitpunkt der Migration LEER (0
Zeilen) -- kein Backfill nötig. `project_documents` hatte GENAU EINE Zeile, `category='Pläne'` --
ein exakter Treffer auf den gleichnamigen Kategorie-Key, kein einziger unklassifizierbarer String
im gesamten Bestand. Nach dem Lauf verifiziert: alle 8 Kategorien korrekt gesät, die eine reale
Zeile trägt `category_id` mit dem korrekten Bezug auf "Pläne".

**Vier bestehende Endpunkte mussten für ein funktionsfähiges Gesamtbild mit angefasst werden**
(nicht Teil der ursprünglichen "nur Stammdaten"-Anfrage im engeren Sinne, aber ohne sie hätte die
neue NOT-NULL-Spalte ab dem Moment der Migration jeden neuen Upload/jede Aktualisierung brechen
lassen -- ein unvollständiger Zustand wäre schlechter gewesen als die kleine, surgical
Erweiterung): `upload_customer_document()`/`upload_project_document()`
(`app/routers/customers.py`/`projects.py`) und `update_customer_document()`/
`update_project_document()` (`app/routers/customer_documents.py`/`project_documents.py`) befüllen
`category_id` jetzt über die neue `resolve_category_id()` zusätzlich zum unveränderten
`category`-Freitext.

**Echter Fund über diese vier Endpunkte hinaus, beim Testlauf entdeckt und sofort behoben**: der
Lieferschein-Upload `upload_work_preparation_delivery_note()`
(`app/routers/work_preparation.py`) legt ebenfalls eine `ProjectDocument`-Zeile
(`category="Lieferscheine"`) an -- ohne dieselbe Korrektur hätte dieser Endpunkt in Produktion mit
einem `IntegrityError: NOT NULL constraint failed` fehlgeschlagen, sobald die Migration gelaufen
wäre. Zwei bestehende Tests (`tests/test_v066_audit_history.py`,
`tests/test_v083_material_bulk_assignment.py`) konstruierten `ProjectDocument` ebenfalls direkt
ohne `category_id` (Regel 7: Modell-Konstruktoren gegen `app/models.py` prüfen, hier: eine neue
NOT-NULL-Spalte trifft auch bestehende Test-Fixtures) -- beide nachgezogen.

**Router und Oberfläche** (`app/routers/document_categories.py`, Muster
`app/routers/roof_areas.py`s Bauteilarten-Endpunkte): `GET/POST/PUT` + `activate`/`deactivate`,
Büro/Admin (`require_role(ROLE_ADMIN, ROLE_OFFICE)`) -- bewusst KEIN DELETE-Endpunkt in dieser
Runde (die beiden fest gesperrten Kategorien dürfen ohnehin nie verschwinden, ob ein
"Löschen blockiert bei Verwendung"-Mechanismus wie bei `RoofComponentType` gebraucht wird,
entscheidet sich erst, wenn echte Dokumente `category_id` in nennenswerter Zahl tragen).
Einstellungen → Dokumente → "Dokumentkategorien" (neuer Abschnitt, `settings.html`): Liste +
Bearbeiten-Panel, spiegelt beide Schlösser in der Oberfläche selbst (das "Sensibel"-Kontrollkästchen
lässt sich nach dem Setzen nicht mehr entfernen, "Für Monteure sichtbar" ist deaktiviert, sobald
sensibel oder fest gesperrt) -- rein kosmetisch, die eigentliche Durchsetzung sitzt serverseitig
in `create_category()`/`update_category()`.

**20 neue Tests** (`tests/test_v266_document_categories.py`): Selbst-Seeding (inkl. "rührt eine
bereits gesäte Zeile nie wieder an"), beide Schlösser einzeln (inkl. der
DB-Manipulations-Simulation für Schloss 2), Router-Rollenprüfung (`field` bekommt 403 auf jeden
Endpunkt), die Freitext-Zuordnung `resolve_category_id()` (Treffer/Rückfall), die vier
Regressions-Endpunkte (Upload/Update setzt `category_id` tatsächlich), und die Migration isoliert
(`_resolve_category_id()`/`_seed_default_categories()`/`_backfill_table_category_ids()` direkt
gegen eine eigene, leichte Connection aufgerufen -- kein `batch_alter_table()`-Aufruf getestet,
siehe CLAUDE.md "Testen" für die Begründung, warum nur die Befüll-Logik, nicht der Schema-Umbau
selbst geprüft wird).

**Bewusst NICHT Teil dieser Version** (nächste, noch zu bestätigende Etappen): die mobile
Objektansicht (Punkt 1 oben, inkl. der noch offenen Frage "eigene objektbezogene Ablage oder
Sammelprojekt je Objekt für eigene Monteur-Uploads"), die geteilte, feldbegrenzte Suche (Punkt 4
oben), und ein tatsächlicher Upload-Weg für Objektdateien selbst -- diese Version legt
ausschließlich das Fundament, mit dem eine künftige Datei ihre Kategorie zuordnen und ein Monteur
später geprüft werden kann, ob er sie sehen darf.

### Schritt 2 (seit 1.3.63): die mobile Objektansicht

Baut auf dem Kategorie-Fundament aus 1.3.62 auf. Erst die Ansicht selbst, die geteilte Suche
(Punkt 4 aus der ursprünglichen Betreiber-Entscheidung, siehe oben) kam als eigener, späterer
Schritt -- in dieser Version war `/mobil/objekt/{property_id}` deshalb nur über eine bekannte
Objekt-ID erreichbar, nicht aus `/mobil` heraus verlinkt. **Seit 1.3.64 verlinkt, siehe "Schritt 3"
unten.**

**Punkt 2 der Anfrage (Objekt- statt Sammelprojekt-Ablage), entschieden**: neue Tabelle
`PropertyDocument` (`app/models.py`), direkt an `Property` gebunden -- die vom Betreiber
favorisierte Variante. Begründung, wie angefragt geprüft: ein Sammelprojekt je Objekt hätte in
JEDER projektbezogenen Auswertung (Projektliste, Kennzahlen, Rechnungslauf-Kandidaten) als
scheinbar echter Vorgang mitgezählt, ohne einer zu sein -- eine eigene Tabelle vermeidet das
vollständig, kostet dafür eine zusätzliche, aber sehr schlanke Tabelle (nur `property_id`,
`category_id`, Datei-Metadaten, `uploaded_by_employee_id`). Anders als `CustomerDocument`/
`ProjectDocument` trägt sie bewusst NUR `category_id`, keinen zusätzlichen freien
`category`-String -- der Freitext existiert dort ausschließlich wegen Altbestands-Kompatibilität
(1.3.62 musste bestehende Freitext-Werte weiter matchen lassen), eine brandneue Tabelle ohne
Altbestand hat diesen Zwang nicht. **Auffindbarkeit fürs Büro geprüft, wie verlangt**: ein neuer
Abschnitt "Objektdateien" auf `property.html` zeigt dieselbe zusammengeführte Liste
(`list_merged_documents_for_property()`, `app/property_documents.py`) ungefiltert -- ein
Monteur-Upload landet dort sofort sichtbar, mit Upload-/Löschmöglichkeit auch fürs Büro selbst.

**Zwei Dokumentquellen, eine Funktion**: `list_merged_documents_for_property(db, property_id, *,
field_visible_only=False)` führt `PropertyDocument` (eigene Objekt-Uploads) UND `ProjectDocument`
aus ALLEN NICHT ARCHIVIERTEN Projekten des Objekts (`Project.property_id`) zusammen, sortiert
nach Kategorie-Reihenfolge -- wie vom Betreiber vorgegeben ("ein Dachdecker denkt in Objekten,
nicht in Projektnummern"). `CustomerDocument` bleibt bewusst AUSSEN VOR -- Kundenebene, nicht
Objektebene, gehört fachlich nicht zu "den Dokumenten dieses Objekts". Dieselbe Funktion bedient
Büro (`field_visible_only=False`, voller Bestand) UND Monteursansicht
(`field_visible_only=True`) -- kein zweiter, divergierender Weg (Muster: genau die Lehre aus
`build_customer_and_meta_block()`, siehe "Kopfbereich" oben).

**Bildverkleinerung wie 1.2.17, aber keine Wiederverwendung von `resize_and_store_photo()`**: die
bestehende Funktion (`app/service_report_photos.py`) ist fest an ihr eigenes `PHOTO_ROOT`
gebunden, nicht parametrisierbar -- `app/property_documents.py` trägt deshalb eine eigene,
strukturell identische Kopie (`_store_uploaded_file()`) mit eigenem `PROPERTY_ROOT`
(`DACHKONZEPTE_PROPERTY_FILE_ROOT`, neunte Env-Var dieser Art, siehe "Geheimnisse für den
Serverbetrieb" oben). Bilder werden verkleinert (1600px, JPEG q82), Dokumente (PDF u. Ä.) bleiben
im Original -- dieselbe Unterscheidung wie ursprünglich verlangt.

### Punkt 3 (Rechte) -- die eine bewusste Ausnahme im ganzen Rechtekonzept

Ab der mobilen Objektansicht gilt eine ANDERE Zugriffsregel als überall sonst im Rechtekonzept
(siehe eigener Abschnitt oben): **ein Monteur erreicht JEDES Objekt über seine ID, nicht nur die
eigenen** -- die sonst übliche Zuordnungsprüfung (`list_field_relevant_property_ids()`,
Planungsbezug) wird hier ausdrücklich NICHT angewendet, wie vom Betreiber vorgegeben ("die alte
Grenze 'nur zugeordnete Objekte' ist für diese Ansicht aufgehoben"). Die Grenze sitzt
stattdessen ausschließlich im INHALT:

- **Objektfelder**: `PropertyAccessOut` (bereits bestehendes Schema aus dem Rechtekonzept, seit
  1.3.51, dort für `GET /api/orders/{order_id}/property`) -- `id`/`name`/`street`/`postal_code`/
  `city`/`access_notes`/`site_contact_name`/`site_contact_phone`, bewusst OHNE `notes`,
  `customer_id`, `is_primary_address`. `GET /api/field-view/properties/{property_id}`
  (`app/routers/field_view.py`) liefert es unverändert bei jeder existierenden `property_id` --
  kein zweites, neues Schema nötig, das bestehende war bereits exakt die richtige Teilmenge.
- **Dokumente**: `field_may_see_category()` (beide Schlösser aus 1.3.62) filtert JEDE Anzeige --
  bei der Auflistung (`GET .../properties/{id}/documents`) UND ERNEUT, unabhängig davon, am
  Datei-Ausliefer-Endpunkt (`GET .../documents/{source}/{document_id}/view|download`). Eine über
  die Liste nie gezeigte, aber per geratener `{source}/{document_id}` angefragte Datei aus einer
  gesperrten Kategorie liefert denselben 404 wie eine tatsächlich nicht existierende Datei --
  ununterscheidbar, damit eine Anfrage nicht einmal bestätigt, dass die Datei existiert. Der
  Ausliefer-Endpunkt prüft zusätzlich, dass das Dokument tatsächlich zu der in der URL
  angegebenen `property_id` gehört (bei `source=project` zusätzlich: das Projekt ist nicht
  archiviert) -- eine Korrektheitsmaßnahme, kein Rechte-Schutz im engeren Sinn (jedes Objekt ist
  ohnehin erreichbar), aber sie verhindert, dass eine Objekt-URL fremde Dokument-IDs "durchreicht".
- **Eigene Uploads**: `POST .../properties/{property_id}/documents` prüft `category_id`
  serverseitig gegen `field_may_see_category()` -- unabhängig davon, was
  `GET .../document-categories` (die Kategorie-Auswahl der Oberfläche, selbst bereits nur
  freigegebene Kategorien listend) anbietet. Ein direkter API-Aufruf mit einer gesperrten
  Kategorie schlägt mit 422 fehl, exakt wie über die Oberfläche.
- **Wartungshistorie**: `list_maintenance_history_for_property_field()` (`app/service_reports.py`,
  neu aus der bereits bestehenden `_property_history_reports()`-Abfrage herausgelöst in eine
  property_id-first-Variante `_property_history_reports_for_property_id()`) liefert dasselbe,
  bereits etablierte reduzierte `ServiceReportHistoryOut`-Schema wie
  `list_property_history_for_field()` (Rechtekonzept → "Berichts-Eigentümerschaft") --
  objektbezogen statt auftragsbezogen, deshalb ohne den dortigen Ausschluss "nicht der eigene
  Auftrag" (hier gibt es keinen "eigenen" Auftrag, von dem aus die Ansicht geöffnet wurde).

**Angriffstest (`tests/test_v267_property_field_documents.py`, 15 Tests), wie verlangt**:
fremdes Objekt über die ID öffnen -- erlaubt, aber nur die harmlosen Felder (per
`set(body) == {...}`-Vergleich belegt, kein `notes`/`customer_id`); Datei aus gesperrter
Kategorie über geratene ID -- 404, inklusive einer direkten Datenbank-Manipulationssimulation
(dieselbe Technik wie 1.3.62: `DocumentCategory.is_field_visible` direkt auf `True` gesetzt,
`field_may_see_category()` bleibt trotzdem bei `False`, da `HARD_LOCKED_CATEGORY_KEYS`
unabhängig geprüft wird); Datei eines ANDEREN Objekts über die URL -- 404, obwohl dieselbe Datei
über die korrekte `property_id` abrufbar ist; archivierte Projekte vollständig ausgeschlossen
(Liste UND Datei-Abruf); Upload in eine nicht freigegebene bzw. fest gesperrte Kategorie --
422, server- nicht nur oberflächenseitig; kein Endpunkt dieser Runde liefert ein Preis-/Kosten-/
internes Feld (rekursiver Schlüssel-Scan über alle vier neuen Endpunkte, Fehlerklasse
`purchase_price` aus 1.3.53); Büro sieht einen Monteur-Upload sofort in der eigenen Liste. Ein
zweiter Punkt (Upload ohne Mitarbeiterverknüpfung -- 422) rundet das ab. Null "durchgelassen".

### Schritt 3 (seit 1.3.64): die geteilte Suche als Einstieg

Letzter, ursprünglich zweimal zurückgestellter Punkt (Punkt 4 der Betreiber-Entscheidung, siehe
oben) -- ein Monteur bekommt einen Weg, ein Objekt zu FINDEN, statt seine ID zu kennen. Mit
dieser Version gilt: "Damit ist die Monteursansicht vollständig" (Betreibervorgabe).

**Geteilte Kernfunktion statt zwei divergierender Implementierungen** (`app/search.py`, neu) --
die Büro-Suche existiert weiterhin nicht (nur Befund, nie gebaut), diese Datei ist trotzdem
bereits als geteilter KERN angelegt: eine künftige Büro-Suche ERWEITERT ihn um weitere
Datensatzarten (Kunden, Aufträge, ...), ersetzt ihn nicht. Zwei bewusst getrennte Schichten:

1. `search_properties(db, query, *, limit=10)` -- reine Datenbeschaffung, KEINE Rollenprüfung.
   Sucht `Property` nach Name/Straße/PLZ/Ort UND dem Namen des zugehörigen Kunden (Join), gibt
   volle `Property`-ORM-Objekte zurück. Eine zu kurze Anfrage (< `MIN_QUERY_LENGTH=2`) liefert
   bewusst `[]` statt der ersten N Objekte -- eine Vorschlagsliste ohne brauchbaren Suchbegriff
   wäre irreführend, und ein Ein-Zeichen-Muster (`ILIKE('%e%')`) würde einen unnötig breiten
   Treffer über nahezu den ganzen Bestand erzeugen.
2. `field_safe_property_search_results()`/`search_properties_for_field()` -- reduziert JEDES
   Ergebnis auf `id`/`name`/`city` (Punkt 3 der Anfrage: nur so viel wie zur Identifikation
   nötig, kein Kunde, keine volle Adresse, keine Kundennummer).

**Die Feldbegrenzung sitzt serverseitig, an der Rolle, nicht an der URL** (wie ausdrücklich
verlangt): `GET /api/field-view/properties/search` (`app/routers/field_view.py`, registriert VOR
`GET .../properties/{property_id}` -- sonst die bereits mehrfach dokumentierte
Literal-vs-Platzhalter-Kollision, "search" scheitert am `int`-Platzhalter mit 422) ruft
UNABHÄNGIG vom Aufrufer immer `search_properties_for_field()` auf -- dieser Endpunkt IST die
Monteurs-Suche, kein gemeinsamer, rollenabhängig antwortender Endpunkt. Eine künftige,
reichhaltigere Büro-Suche bekommt einen EIGENEN Endpunkt auf `search_properties()` -- der
Moduldocstring von `app/search.py` hält als verbindliche Regel fest, dass JEDER künftige, auch
für `field` erreichbare Endpunkt (auch ein gemeinsamer Büro+Monteur-Endpunkt) bei `role==
ROLE_FIELD` zwingend `search_properties_for_field()` aufrufen muss, nie die volle Kernfunktion
direkt zurückgeben darf. `response_model=list[PropertySearchHitOut]` (`app/schemas.py`) kappt
zusätzlich strukturell auf genau drei Felder (seit 1.3.65: vier, siehe Nachtrag unten) -- eine
zweite, unabhängige Sperre, falls die Funktion selbst je einen Fehler hätte. `q` ist der einzige
Client-Parameter; `limit` ist bewusst
NICHT client-steuerbar (fest auf `SEARCH_RESULT_LIMIT=10`), ein `?limit=99999` kann nie mehr als
zehn Treffer erzwingen, unbekannte Parameter (`?type=customer` u. Ä.) ignoriert FastAPI ohnehin.

**Index-Frage geprüft, nicht nur angenommen** (wie ausdrücklich verlangt): empirisch gegen die
echte, lokale `dachkonzepte_erp.db` mit `EXPLAIN QUERY PLAN` belegt -- `customers.name` trägt
bereits einen B-Baum-Index (`ix_customers_name`), trotzdem zeigt `SELECT * FROM customers WHERE
name LIKE '%test%'` `SCAN customers` (voller Tabellenscan, Index vollständig ignoriert). Ein
gewöhnlicher B-Baum-Index unterstützt nur Präfix-Suchen (`LIKE 'term%'`), keine Substring-Suchen
mit führendem Platzhalter -- ein neuer Index auf `Property.name`/`street`/`postal_code`/`city`
wäre für dieses Abfragemuster ebenso wirkungslos. Bei der aktuellen Datenmenge (163 Objekte, 162
Kunden) ist ein voller Tabellenscan je Suchanfrage ohnehin irrelevant (< 1ms) -- deshalb **keine
neue Migration für Indizes**. Die tatsächlich wirksamen Hebel gegen zu teure Anfragen sind
`MIN_QUERY_LENGTH` (verhindert eine sehr breite Anfrage bei nur einem Zeichen) und der
client-seitige Debounce (siehe unten) -- beide bereits eingebaut. Sollte die Datenmenge um
Größenordnungen wachsen, wäre der richtige nächste Schritt PostgreSQL `pg_trgm`/SQLite `FTS5`,
kein gewöhnlicher B-Baum-Index -- als Hinweis für später festgehalten, nicht gebaut.

**Oberfläche** (ursprünglich `app/templates/mobil.html`, seit 1.3.65 in `_mobile_header.html`
umgezogen, siehe Nachtrag unten): ein Suchfeld, `{% include "_debounce.html" %}` (derselbe,
bereits bestehende, generische `debounce(fn, ms)`-Helfer wie bei `roof_area.html`/
`service_reports.html`, hier zum ersten Mal für eine Suche statt eines Autosave verwendet -- der
Helfer selbst ist dafür bereits geeignet, siehe CLAUDE.md-Fußnote zu `_debounce.html`) mit 300ms
Verzögerung nach dem letzten Tastendruck. Eine Vorschlagsliste zeigt Objektname und Ort je
Treffer, ein Klick führt direkt zu `/mobil/objekt/{id}`. Bei genau zehn Treffern (dem Limit) ein
Hinweistext "Weitere Treffer möglich -- Suche verfeinern" -- ohne einen zusätzlichen
Zähl-Request: der Server liefert keine Gesamtzahl, das Erreichen des Limits ist die naheliegende
Annahme, dass mehr existieren könnten. Eine Anfrage unter zwei Zeichen löst client-seitig gar
keinen Request aus (spart den Roundtrip, den `MIN_QUERY_LENGTH` serverseitig ohnehin verwerfen
würde). Keine Ergebnisseite mit Filtern (wie bei einer künftigen Büro-Suche) -- die
Vorschlagsliste genügt, wie ausdrücklich vorgegeben.

**Angriffstest (`tests/test_v268_property_search.py`, 12 Tests), wie verlangt**: findet ein
Monteur über die Suche etwas anderes als Objekte -- nein, jede Antwort des tatsächlichen
Router-Endpunkts enthält ausschließlich `id`/`name`/`city` (seit 1.3.65 zusätzlich
`customer_name`, siehe Nachtrag -- rekursiver Schlüssel-Scan, Fehlerklasse `purchase_price`);
liefert die Vorschlagsantwort ein gesperrtes Feld mit (Kundennummer, interne Notiz) -- nein, auch
bei einem Treffer über den Kundennamen bleibt die Antwort auf die drei harmlosen Objektfelder
beschränkt (Stand 1.3.64 -- seit 1.3.65 ist der Kundenname selbst ein viertes, bewusst erlaubtes
Feld, alles andere über den Kunden bleibt weiterhin gesperrt); kommt ein Monteur, der den
Such-Endpunkt mit anderen Parametern aufruft (`type=customer`, `full=true`, `fields=all`,
`limit=99999`), an mehr als Objekte -- nein, unverändert höchstens zehn Treffer, unverändert nur
die (seit 1.3.65: vier) erlaubten Felder. Zusätzlich: Literal-vs-Platzhalter-Kollisionscheck
(`.../search` scheitert nicht am `{property_id}`-Platzhalter), `MIN_QUERY_LENGTH`-Grenze,
Limit-Kappung bei 15 tatsächlich angelegten Treffern. Null "durchgelassen". Damit ist die
Monteursansicht laut Betreibervorgabe vollständig.

### Nachtrag (seit 1.3.65): Kundenname in den Vorschlägen, Suche in die Kopfzeile

Zwei vom Betreiber nach dem ersten Einsatz gemeldete Anpassungen an der 1.3.64-Suche.

**Punkt 1 -- Kundenname in den Vorschlägen.** Nur Objektname und Ort reichten zur Identifikation
nicht: ein Objekt ist ohne Kundenname schwer einzuordnen, besonders wenn ein Kunde mehrere
Objekte hat. `PropertySearchHitOut` (`app/schemas.py`) bekommt ein viertes Feld `customer_name`
-- bewusst NICHT sensibel (ein Monteur, der zum Objekt fährt, kennt den Kunden ohnehin), im
Unterschied zu Kundennummer/interner Notiz/voller Adresse/allem Finanziellen, die weiterhin
gesperrt bleiben. Die reine Kernfunktion `search_properties()` (Schicht 1, siehe oben) bleibt
unverändert rollenlos -- nur `field_safe_property_search_results()` (Schicht 2) wurde erweitert,
mit `selectinload(Property.customer)` in `search_properties()` bereits vorgeladen, damit der
Zugriff auf `p.customer.name` keine zusätzliche Abfrage je Treffer auslöst. Der Angriffstest aus
1.3.64 wurde angepasst statt neu geschrieben: die Erwartung "nur id/name/city" wird überall zu
"id/name/city/customer_name", ein eigener Test belegt zusätzlich, dass ein Treffer über den
Kundennamen (`Customer.name` als Suchkriterium) den Namen zwar jetzt zeigen darf, aber sonst
nichts Weiteres über den Kunden durchlässt (12 Tests weiterhin in
`tests/test_v268_property_search.py`, teils erweitert, teils umbenannt).

**Punkt 2 -- Suche in die Kopfzeile.** Das Suchfeld saß bisher nur auf `mobil.html` ("Einsätze"),
unerreichbar von den drei anderen Monteursseiten aus. Umgezogen in `_mobile_header.html` -- die
gemeinsame, schlanke Kopfzeile, die `mobil.html`/`mobil_objekt.html`/`field_timesheet.html`/
`time_tracking_field.html` ohnehin schon alle einbinden -- damit ist die Suche automatisch von
jeder dieser vier Seiten aus erreichbar, ohne dass jede sie einzeln nachbauen müsste. Der
Debounce-Helfer (`_debounce.html`) zog mit um -- genau einmal eingebunden (in
`_mobile_header.html` selbst), keines der vier Templates bindet ihn zusätzlich eigenständig ein,
sonst wäre `debounce()` doppelt definiert.

**Bei der Gelegenheit die alte, seit 1.3.45 bestehende Stapel-Architektur der Kopfzeile
abgelöst.** Kopf (`.mobile-header`) und Reiter (`.mobile-nav`) waren bisher zwei EINZELN sticky
positionierte Elemente, die sich über einen hart codierten `top:45px`-Wert am Reiter aufeinander
stapelten (der Kopf-Höhe geschätzt, nie exakt vermessen -- funktionierte bisher nur, weil sich
zwischen beiden nichts einschob). Eine neue Zeile dazwischen hätte diesen Wert neu vermessen
müssen, UND hätte bei jeder künftigen Änderung der Kopf-Höhe (z. B. ein längerer Mitarbeitername)
erneut brechen können -- ein fragiles Muster für exakt das, was jetzt gebraucht wurde. Ersetzt
durch EINEN gemeinsamen sticky-Wrapper (`.mobile-header-wrap`), der Kopf/Suchfeld/Reiter als
normale, nie überlappende Blockzeilen enthält -- kein Pixelwert mehr zu pflegen, unabhängig von
der tatsächlichen Höhe jeder Zeile. Das beantwortet zugleich die geforderte Prüfung für beide
Bildschirmgrößen: auf einem schmalen Smartphone-Hochformat können normale Blockzeilen sich
strukturell nicht überlappen, unabhängig von der Fensterbreite -- kein Sonderfall nötig.

**Die Vorschlagsliste überlagert die Reiter bewusst NICHT.** Naiv direkt unter dem Eingabefeld
geöffnet, hätte sie visuell über den darunterliegenden Reitern gelegen (Suchfeld steht jetzt ÜBER
den Reitern, eine aufklappende Liste reicht überall dorthin herab) -- ein Tipp auf einen Reiter
bei offener Liste hätte dann zuerst die Liste getroffen (und nur geschlossen), nicht den Reiter
selbst; ein zweiter Tipp wäre nötig gewesen, genau das vom Betreiber benannte Risiko ("ein
offener Vorschlag ... darf nicht stehenbleiben"). Behoben durch die Positionierung: die
Vorschlagsliste ist ein Kind des GANZEN sticky-Wrappers (nicht nur des Suchfelds), mit
`top:100%` relativ zu dessen Unterkante -- sie öffnet sich dadurch strukturell erst UNTERHALB der
Reiter, kann sie also nie überdecken. Die Reiter bleiben damit bei offener Liste jederzeit mit
einem einzigen Tipp erreichbar. Dass eine offene Liste beim tatsächlichen Wechsel der Seite
verschwindet, ergibt sich zusätzlich schon aus der Architektur dieses Projekts (klassische
Mehrseiten-Navigation, kein SPA, siehe CLAUDE.md "Stack & Struktur") -- ein Tipp auf einen Reiter
lädt ohnehin die komplette Seite neu.

**Maximalbreite fürs Tablet.** Suchfeld UND Vorschlagsliste bekommen `max-width:640px` mit
zentrierenden Rändern (`margin:auto`) -- auf einem Tablet wirkt das Feld dadurch nicht unnötig
breit, auf einem Smartphone (immer schmaler als 640px) ändert die Regel nichts, das Feld bleibt
dort ohnehin voll breit.

**Kein echter Browser-Screenshot möglich** (dieselbe, wiederholt dokumentierte
Werkzeug-Einschränkung dieser Umgebung) -- die Layout-/Überlappungsfreiheit ist ausschließlich
strukturell an den Template-Quellen nachgewiesen (`tests/test_v269_mobile_header_search.py`, 8
Tests: Suchfeld/-liste liegen in `_mobile_header.html`, nicht mehr in `mobil.html`; der
Debounce-Helfer ist genau einmal eingebunden; alle vier Seiten binden die Kopfzeile ein; die
Vorschlagsliste steht strukturell nach `<nav>`; Kopf/Reiter tragen kein `position:sticky` mehr
einzeln; die Maximalbreite ist gesetzt), nicht an einem gerenderten Bild. Sollte bei Gelegenheit
im Browser gegengeprüft werden, insbesondere das Verhalten bei offener Vorschlagsliste auf einem
echten Touchscreen.

### Wartungsbericht-Detailansicht (seit 1.3.69)

Anlass: ein Monteur führt dieselbe Wartung erneut durch und will nachvollziehen, was beim
letzten Einsatz gemacht wurde -- auch von einem inzwischen ausgeschiedenen Kollegen. Die mobile
Objektansicht zeigte dafür bisher nur das reduzierte Wartungshistorie-Schema
(`ServiceReportHistoryOut`, seit 1.3.56/1.3.63) -- Datum, Berichtstyp, Monteur, Prüfergebnisse,
Mängel mit Status, aber keinen Weg, den einzelnen Bericht im Detail (samt Fotos) oder als PDF zu
öffnen. Vorab ein reiner Befund, dann auf Bestätigung gebaut.

**Befund, der die ursprüngliche Annahme korrigiert.** Die Anfrage ging von einem "PDF ohne
Preise" aus -- tatsächlich enthält das Bericht-PDF an KEINER Stelle einen Preis:
`ServiceReportMaterial` trägt strukturell keine Preisspalte (der Monteur erfasst nur, WAS
verbraucht wurde, siehe Klassendocstring in `app/models.py`), `TimeEntry` hat kein Preis-/
Stundensatzfeld. Der einzige Abschnitt, der für einen Monteur gesperrt bleiben muss, ist
"Erfasste Zeiten" (`app/service_report_pdf.py`) -- wegen der FREMDEN PERSONENDATEN (wer hat wann
wie viele Stunden gebucht), nicht wegen eines Preises. Ebenso geprüft und mit KEINEM FUND
bestätigt: ein vermutetes `internal_note`-Feld existiert an keiner Stelle im reduzierten Schema
oder den zugrunde liegenden Modellen (`ServiceReport`/`Finding`/`InspectionItem`) -- ein
rekursiver Schlüssel-Scan (Muster `test_maintenance_history_carries_no_prices_purchase_values_
or_customer_notes`, `tests/test_v260_role_audit.py`, hier um zusätzliche Suchbegriffe erweitert)
bestätigt das, nichts wurde entfernt.

**Ein Schalter statt eines eigenen Renderers.** Weil der einzige zu entfernende Abschnitt schon
vorher isoliert war (eine einzige `if entries:`-Tabelle am Ende der Story), reicht ein neuer,
optionaler Parameter: `build_service_report_pdf(db, report, include_time_entries=False)` lässt
"Erfasste Zeiten" komplett weg -- `list_entries()` wird dabei GAR NICHT ERST aufgerufen, nicht
nur die Tabelle ausgeblendet (per Test mit einem Aufruf-Wächter belegt, der eine Ausnahme wirft,
falls die Funktion doch aufgerufen würde). Alles andere bleibt exakt wie im Kundendokument,
inklusive des "Monteur"-Meta-Felds (`created_by_employee_name`) -- das bleibt ausdrücklich
sichtbar (Vorgabe: "damaliger Monteur" ist erlaubt), nur ein ZWEITER, fremder Zeitbucher
verschwindet. `build_service_report_pdf_for_field()` ist die dünne, dokumentierende
Wrapper-Funktion für genau diesen Aufruf -- kein zweiter, paralleler Renderer nach dem Muster
des Angebots-Umbaus (1.3.13): der wäre für "eine von zehn Abschnitten weglassen" unverhältnismäßig
gewesen.

**Zugang ausschließlich über das Objekt.** Neuer Endpunkt `GET /api/field-view/properties/
{property_id}/maintenance-history/{report_id}/pdf` (`app/routers/field_view.py`) --
`resolve_property_history_report_for_field()` (`app/service_reports.py`) verifiziert am
Abrufzeitpunkt ERNEUT, dass der Bericht tatsächlich zu GENAU diesem Objekt gehört und bereits
unterschrieben ist (`status=="unterschrieben"`, dieselbe Grenze wie die Historie selbst) -- Muster
`resolve_property_document_for_field()` (`app/property_documents.py`, seit 1.3.63): sonst `None`,
der Router liefert dafür 404, ununterscheidbar von "existiert nicht", NIE ein 403 (kein
Bestätigen per URL-Raten, dass irgendein Bericht mit dieser ID existiert). Bewusst OHNE die
Ersteller-Prüfung von `require_field_report_ownership()` (`app/routers/orders.py`, Rechtekonzept
-> "Berichts-Eigentümerschaft") -- die Wartungshistorie zeigt einem Monteur schon immer fremde
Berichte desselben Objekts (`list_maintenance_history_for_property_field()`, seit 1.3.56/1.3.63),
diese Version ist nur die Detail-Variante derselben, bereits etablierten Ausnahme: Objekt- statt
Ersteller-Zugehörigkeit, nur lesend, als vollständiges Dokument statt der reduzierten Liste.
`require_field_report_ownership()`s Docstring trägt seither eine ausdrückliche Notiz zu dieser
Ausnahme, damit die Behauptung dort ("nur die reduzierte Zusammenfassung, nicht mehr") nicht
stillschweigend falsch wird.

**Nur Lesen.** Unter diesem Pfad existiert kein PUT/DELETE/sign (405 bei einem Versuch, da nur
GET registriert ist) -- die bestehenden Berichts-Endpunkte (`PUT`/`DELETE`/`.../sign`) bleiben
unverändert über `require_field_report_ownership()` auf den eigenen Bericht beschränkt, komplett
unberührt von dieser Änderung (per Test belegt: derselbe Monteur, der über das Objekt lesen darf,
bekommt über den klassischen Weg weiterhin 403 für PUT/DELETE/sign an einem fremden Bericht).

`app/templates/mobil_objekt.html`s `renderHistory()` bekommt dafür einen "Als PDF ansehen"-Link
je Historieneintrag (Muster der bereits bestehenden `.doc-actions`-Knöpfe). 9 neue Tests
(`tests/test_v273_maintenance_report_field_detail.py`): geratene `report_id` ohne echten
Objektweg, ein Bericht, der zu einem ANDEREN Objekt gehört, ein noch nicht unterschriebener
Entwurf, interne/preisähnliche Schlüssel (rekursiver Scan), die fremde Zeitbuchung im PDF-Text,
und ein Schreibversuch über den alten UND den neuen Weg -- null "durchgelassen".

## Büro-Suche (seit 1.3.66, Etappe 1)

Der ursprüngliche Wunsch aus der Suche-Bestandsaufnahme (siehe "Dateiablage je Objekt" ->
"Schritt 3", 1.3.64): Vorschläge beim Tippen, Ergebnisseite mit Filtern bei Bestätigung, für die
volle "Gruppe A" (17 Datensatzarten) statt nur Objekte. Baut direkt auf zwei bereits bestehenden
Fundamenten auf, ändert an keinem der beiden etwas: dem geteilten Suchkern aus 1.3.64
(`search_properties()` bleibt UNVERÄNDERT die eine Objektsuche, die "properties"-Quelle unten
ruft sie direkt auf -- der 1.3.64-Moduldocstring-Versprecher "eine künftige Büro-Suche erweitert
den Kern, ersetzt ihn nicht" ist damit eingelöst) und dem Rechtekonzept (`require_role()`,
Standardverweigerung). Vor dem Bauen ein reiner Befund-Durchgang (keine Codeänderung), danach vom
Nutzer vier Entscheidungen -- siehe unten, jede einzeln umgesetzt. Zwei Etappen, wie verlangt:
Etappe 1 (diese Version) -- Registry, Kernstruktur, Rollensicherheit; Etappe 2 (Oberfläche:
Suchfeld in der Topbar, Ergebnisseite) folgt erst nach Rückmeldung zu dieser Etappe.

### Registry-Muster (`app/search.py`)

`SearchSource` (frozen dataclass) -- analog im Geist zu `require_role()`s "keine impliziten
Defaults"-Philosophie: `key`/`label`/`allowed_roles`/`query_fn`/`row_fn` sind Pflichtfelder, nur
`module_key` hat einen Default (`None`, siehe unten). `OFFICE_SEARCH_SOURCES` ist ein Tupel aus
17 solchen Quellen -- **Registry und Vollständigkeitstest wurden ZUSAMMEN gebaut, nicht
danach** (ausdrückliche Vorgabe): `tests/test_v270_office_search.py::
EXPECTED_OFFICE_SEARCH_KEYS` vergleicht die tatsächlich registrierten Schlüssel gegen die 17
erwarteten und prüft zusätzlich, dass jede `allowed_roles`-Menge nicht-leer und eine Teilmenge
von `{admin, office}` ist (ROLE_FIELD darf NIE enthalten sein) und jeder `module_key` entweder
`None` oder einer der beiden bekannten Modul-Schlüssel ist -- Muster: dieselbe mechanische
Absicherung wie beim Rollen-Audit-Test (Regel 11), eine Registry ohne erzwungene
Vollständigkeit ist nur ein Vorschlag, keine Absicherung.

`search_office(db, role, query, *, limit_per_type=20, types=None)` ist der EINE Dispatcher --
geht die Registry durch und filtert **dreifach**: Rolle (`source.allowed_roles`), optionaler
`types`-Filter (welche Datensatzarten überhaupt durchsucht werden sollen), Modul-Zustand (dritte,
unabhängige Achse, siehe unten). Prüft `MIN_QUERY_LENGTH` (aus der Monteurs-Suche
wiederverwendet, `=2`) EINMAL zentral, bevor irgendeine der 17 Quellfunktionen aufgerufen wird --
keine der 17 prüft es erneut, das ist beabsichtigt. `_count_and_fetch(db, stmt, order_by, limit,
*, options=())` ist der gemeinsame Helfer fast jeder Quelle: EIN gefilterter Basis-`stmt`, zwei
Verwendungen (eine echte `COUNT(*)`-Abfrage für die reale Trefferzahl, eine gekappte, geordnete
Liste für die Anzeige) -- kann nie auseinanderlaufen, im Unterschied zu
`build_customer_and_meta_block()`s historischer Divergenz in drei Varianten (siehe
"Kopfbereich"), die hier von Anfang an vermieden wird.

**Der Fund beim Customer-Suchen (Regel 7, vor dem Schreiben geprüft, nicht aus dem Gedächtnis
geraten)**: `Customer.customer_number` ist ein Python-`@property` (`self.profile.customer_number
if self.profile else None`), KEINE gemappte Spalte -- `Customer.customer_number.ilike(...)` in
einer Query würde mit einem `AttributeError` scheitern (ein Property-Descriptor kennt kein
`.ilike()`). Die "customers"-Quelle joint deshalb `CustomerProfile` (`outerjoin`, ein Kunde ohne
Profil-Zeile bleibt trotzdem über `Customer.name` allein auffindbar) und filtert auf
`CustomerProfile.customer_number` -- die tatsächliche, gemappte Spalte. Zum Vergleich geprüft:
`Order.customer_number`/`Invoice.customer_number`/`Supplier.supplier_number`/
`Employee.employee_number` sind alle echte, gemappte Spalten -- nur bei `Customer` ist es dieser
eine Sonderfall.

### Die vier Entscheidungen -- jede einzeln umgesetzt

**1. Rechnungen für Büro sichtbar, nichts in der Registry admin-only.** Die Grenze verläuft
zwischen Büro und Monteur, nicht zwischen Admin und Büro -- JEDE der 17 Quellen trägt
`allowed_roles={ROLE_ADMIN, ROLE_OFFICE}`, keine Ausnahme. Geprüfte Rückfrage (Auftrag: "prüfe,
ob es innerhalb der Finanzdaten etwas gibt, das nur Admin sehen soll"): **nein, nichts** --
Kalkulationsgrundlagen sind gar keine Gruppe-A-Entität (eine einzelne Singleton-Settings-Zeile,
nicht durchsuchbar), Einkaufspreise (`Material.purchase_price`) und Vergütung
(`Employee.hourly_wage`/`effective_hourly_wage`/`annual_gross_wage`) sind seit dem
Rechtekonzept (1.3.52) bereits über die normalen Material-/Mitarbeiter-Stammdatenseiten
Büro+Admin-sichtbar -- eine Einschränkung nur am Sucheinstieg wäre inkonsistent mit dem Rest der
Anwendung und würde nichts schützen (Büro sieht dieselben Daten ohnehin auf der jeweiligen
Stammdatenseite). Der tatsächliche, ausreichende Schutz ist unabhängig von der Rolle: JEDE
`row_fn` liefert strukturell ausschließlich `{id, title, subtitle, url}` -- eine reine
Trefferkurzform, nie ein Preis-/Lohn-/Einkaufsfeld, unabhängig davon, welche Rolle sucht.
`OfficeSearchHitOut` (Pydantic, `app/schemas.py`) kappt das zusätzlich strukturell, als zweite,
unabhängige Sperre.

**2. ILIKE statt Volltextsuche.** Empirisch geprüft (nicht angenommen), gegen die echte,
lokale `dachkonzepte_erp.db`: 472 Zeilen über alle 17 Tabellen zusammen (customers=162,
properties=163, roof_areas=4, projects=8, quotes=10, orders=6, invoices=6, reminders=2,
inquiries=0, tasks=7, employees=12, service_reports=4, findings=4, maintenance_contracts=2,
services=24, materials=56, suppliers=2). `EXPLAIN QUERY PLAN` + Zeitmessung an vier
repräsentativen, gejointen ILIKE-Abfragen (Angebot→Projekt→Kunde, Mahnung→Rechnung,
Aufgabe→Projekt, Wartungsvertrag→Kunde): alle ≈0.03ms. Bei dieser Größenordnung ist "ein Query
je Datensatzart" (17 einzelne, kleine Abfragen statt einer UNION-Abfrage über alle Tabellen)
sowohl einfacher zu warten als auch schnell genug -- eine UNION-Query über 17 strukturell
verschiedene Tabellen (unterschiedliche Spalten, unterschiedliche Joins) wäre erheblich
komplexer geworden, ohne einen messbaren Vorteil bei dieser Datenmenge.

**Schwelle für einen künftigen Wechsel, wie ausdrücklich verlangt festgehalten** (damit ein
späterer Durchgang das nicht neu herleiten muss): Volltextsuche (PostgreSQL `pg_trgm`/`tsvector`
bzw. SQLite `FTS5`) wird erst relevant, wenn EINE der beiden folgenden Schwellen überschritten
wird -- (a) die Gesamtzahl der Zeilen über alle 17 Tabellen wächst in den fünfstelligen Bereich
(grobe Faustregel: ab ~50.000-100.000 Zeilen wird ein voller Tabellenscan pro Suchanfrage auf
gewöhnlicher Server-Hardware spürbar, nicht mehr nur theoretisch), ODER (b) eine einzelne Quelle
(am ehesten "properties"/"customers"/"orders", die am schnellsten wachsen) allein bereits
mehrere tausend Zeilen trägt UND die Suche dabei spürbar (>100ms) langsam wird. Beides ist bei
472 Zeilen und ~0.03ms je Abfrage um mehrere Größenordnungen entfernt -- ein neuer Index wäre
hier ebenso wirkungslos wie bei der Monteurs-Suche (siehe "Suche als Einstieg": ein B-Baum-Index
hilft einem präfixlosen `ILIKE('%term%')` weder unter SQLite noch unter PostgreSQL, `EXPLAIN
QUERY PLAN` zeigt `SCAN` selbst bei einem bereits indizierten Feld).

**3. Snapshot UND live-Name durchsucht, unabhängig voneinander.** Der Fund, der sonst zur
stillen Lücke geworden wäre: "orders" und "invoices" durchsuchen IMMER beide Felder --
die eingefrorene Schnappschuss-Spalte (`Order.customer_name`/`Invoice.customer_name`, seit
1.3.31/1.3.32 bereits als für die Suche nutzbar verifiziert, siehe dort) UND die live
`Customer.name` über den Projekt-Join. Wer nach der alten Schreibweise sucht, findet die alte
Rechnung mit dem eingefrorenen Namen; wer nach der heutigen sucht, findet den aktuellen Kunden
UND -- über den JOIN zum heutigen Kunden, nicht über den eigenen unveränderten Schnappschuss --
auch die Rechnung, da sie ja weiterhin zu diesem Kunden gehört. Beide Suchwege bleiben dabei
unabhängig: würde nur die live `Customer.name` gejoint (die Schnappschuss-Spalte selbst nie
geprüft), verlöre eine Suche nach der ALTEN Schreibweise jede Rechnung, deren Kunde inzwischen
umbenannt/umformatiert wurde -- exakt die stille Lücke. Belegt in
`tests/test_v270_office_search.py::test_invoice_found_via_frozen_snapshot_and_customer_found_via_live_name`:
ein Kunde ("Wolfgang Rödchen"), dessen Schreibweise nach einer Rechnung auf "Wolfgang Roedchen"
korrigiert wird -- die Suche nach der alten Schreibweise findet weiterhin die alte Rechnung
(über deren unverändertes `customer_name`-Feld), die Suche nach der neuen findet den
aktualisierten Kunden. "Reminders" durchsucht dagegen nur `Invoice.customer_name` (den
Schnappschuss der zugehörigen Rechnung) -- bei nur zwei Mahnungen im echten Bestand kein
Bedarf für denselben, aufwendigeren Doppel-Join wie bei Aufträgen/Rechnungen.

**4. Ergebnisseite-Begrenzung.** `search_office()` liefert je Datensatzart die REALE Trefferzahl
(`total`, aus `_count_and_fetch()`s unabhängiger `COUNT(*)`-Abfrage) UND eine auf
`limit_per_type` (Standard 20, `OFFICE_SEARCH_RESULT_LIMIT`) gekappte Liste (`hits`) -- die
Oberfläche (Etappe 2) zeigt daraus je Datensatzart die Trefferzahl und "weitere anzeigen" statt
Seitenzahlen, konsistent mit dem Rest des Projekts (siehe CLAUDE.md: nirgends im Projekt gibt es
eine nummerierte Seitenpaginierung).

### Dritte, unabhängige Achse: der Modul-Umschalter

Nicht ausdrücklich vom Nutzer angefragt, aber Konsequenz der bereits bestehenden Regel
("API-Endpunkte müssen den Modul-Zustand selbst prüfen, sonst bleibt die Funktion über die API
erreichbar, obwohl die Oberfläche sie versteckt", siehe "Modul-Umschalter" oben): vier Quellen
hängen an einem abschaltbaren Modul -- `tasks` (Modul `"aufgabenmanagement"`),
`service_reports`/`findings`/`maintenance_contracts` (Modul `"wartungen"`).
`SearchSource.module_key` trägt dafür den jeweiligen Schlüssel (`None` für die übrigen 13),
`search_office()` prüft `is_module_enabled(db, module_key)` für jede Quelle mit gesetztem
`module_key` zusätzlich zur Rolle -- unabhängig davon, ob der Suchende Büro oder Admin ist. Bei
deaktiviertem Modul verschwinden die betroffenen Quellen komplett aus dem Ergebnis, auch wenn
die zugrunde liegenden Daten weiterhin passend wären (per Test belegt).

### Separate-Endpunkt-Prinzip (seit 1.3.64 etabliert, hier bestätigt) und Router

`GET /api/search` (`app/routers/search.py`, neu) ist ein VÖLLIG EIGENSTÄNDIGER Endpunkt --
niemals ein gemeinsamer, rollenverzweigender Endpunkt mit der Monteurs-Suche
(`GET /api/field-view/properties/search`). Das macht `Depends(require_role(ROLE_ADMIN,
ROLE_OFFICE, message=...))` (ROLE_FIELD ausdrücklich NICHT dabei) zur PRIMÄREN Sicherung: ein
Monteur bekommt 403, BEVOR `search_office()` auch nur eine Zeile liest -- die rolleninterne
Filterung in `search_office()` selbst (jede Quelle prüft `role` gegen `source.allowed_roles`)
ist eine zweite, unabhängige Absicherung, kein Ersatz dafür. Automatisch durch den bestehenden
Rollen-Audit-Test (`tests/test_v260_role_audit.py`) erfasst, da `require_role()` die dafür
nötige `_dk_roles`-Markierung trägt -- keine Änderung an jenem Test nötig.

`q` (Suchbegriff), `types` (optionale, kommagetrennte Liste von `SearchSource`-Schlüsseln, um
gezielt nur bestimmte Datensatzarten zu durchsuchen -- Etappe 2 nutzt das für Filter auf der
Ergebnisseite), `limit` (geklammert auf `[1, 100]`, bevor er als `limit_per_type` an
`search_office()` geht -- ein Client kann damit nie mehr als 100 Treffer je Datensatzart
erzwingen, unabhängig vom übergebenen Wert).

### Der verlangte Angriffstest -- null durchgelassen

Mirror des Monteurs-Suche-Angriffstests (1.3.64/1.3.65), gegen eine isolierte Testinstanz (nie
gegen die echte `dachkonzepte_erp.db`): ein Monteur, der `GET /api/search` aufruft -- **plain
UND mit manipulierten Parametern** (`types=invoices,customers,employees`, `limit=999999`) --
bekommt in BEIDEN Fällen **403**, identisch, nie irgendeine Zeile, geschweige denn eine Rechnung
oder ein Preisfeld. Büro/Admin bekommen dagegen 200 mit korrekt gruppierten Ergebnissen
INKLUSIVE einer `invoices`-Gruppe (belegt Entscheidung 1 über den tatsächlichen Router-Weg, nicht
nur die Kernfunktion direkt). Ein rekursiver Schlüssel-Scan über JEDE zurückgegebene Zeile (über
alle 17 Gruppen, mit absichtlich gesetztem `Employee.hourly_wage`/`Material.purchase_price`/
`Service.sale_price` in den Testdaten) findet in keiner Rolle ein Preis-/Lohn-/Einkaufsfeld --
strukturell garantiert, da jede Zeile ausschließlich `{id, title, subtitle, url}` trägt.
`tests/test_v270_office_search.py`, 11 neue Tests, alle grün.

### Bewusst NICHT Teil dieser Etappe

Die Oberfläche (Suchfeld im reservierten `.app-topbar-search-slot`, siehe "Umgestaltung der
Sidebar" -> "Schritt 2", die Ergebnisseite mit Filtern/"weitere anzeigen") -- wartet auf
Rückmeldung zu dieser Etappe, wie ausdrücklich vom Nutzer verlangt ("Nach Etappe 1 ... berichte
mir, bevor die Oberfläche kommt").

### Etappe 2 (seit 1.3.67): die Oberfläche

Nach Rückmeldung zu Etappe 1 gebaut -- Suchfeld in der Topbar, Ergebnisseite. Baut ausschließlich
auf bereits bestehenden Bausteinen auf: dem seit 1.3.45 reservierten `.app-topbar-search-slot`,
`GET /api/search` aus Etappe 1, und `require_role()`/`_role_dep` aus dem Rechtekonzept.

**Suchfeld in der Topbar** (`app/templates/_topbar.html`): rendert nur, wenn
`current_user.role in ("admin", "office")` -- für `field` fehlt das Eingabefeld strukturell im
Markup, kein nie funktionierendes Feld (kleine, opportunistische Vorwegnahme des in "Rechtekonzept"
-> "Sichtbarkeit in der Oberfläche" bereits als künftiges Ziel festgehaltenen "ausblenden statt
ausgrauen" -- ohne den dort beschriebenen größeren Umbau der übrigen Navigation vorzuziehen).
Vorschläge beim Tippen: 300ms Debounce, Mindestlänge 2 Zeichen -- dieselben Werte wie die
Monteurs-Suche, absichtlich NICHT über den geteilten `_debounce.html`-Helfer eingebunden, sondern
ein eigener, winziger Timer direkt in der bestehenden IIFE der Datei: `_topbar.html` wird auf
allen 31 Büro-Seiten eingebunden, von denen mindestens zwei (`roof_area.html`,
`service_reports.html`) `_debounce.html` bereits selbst einbinden -- ein zusätzliches Include hier
hätte die Funktion global doppelt definiert, exakt das Muster, das seit 1.3.65 für die
Monteurs-Kopfzeile bewusst vermieden wird. Ruft ausschließlich `GET /api/search` auf, niemals den
Monteurs-Suchendpunkt (Separate-Endpunkt-Prinzip, siehe oben) -- ein Vorschlag zeigt Gruppen-Label/
Titel/Untertitel, ein Klick führt direkt auf die `url` des Treffers. Bestätigen (Enter) öffnet
`/suche?q=...`. Schließt bei Klick daneben und bei Escape.

**Kleiner, transparent gemeldeter Fund dabei**: die Anfrage ging davon aus, dass Escape die
Monteurs-Suche bereits schließt ("wie in der Monteurs-Suche") -- tatsächlich hatte
`_mobile_header.html` bisher NUR den Klick-daneben-Schluss, keine Escape-Behandlung. Für beide
nachgezogen, nicht nur für die neue Büro-Suche, statt die Prämisse stillschweigend nur für eine
Seite aufzulösen (Muster: dieselbe Transparenz wie bei der 1.3.61-Prämisse-Korrektur zur
Tätigkeit im Nachtrag/Schnellstart).

**Ergebnisseite** (`GET /suche`, `app/routers/pages.py::office_search_page()`,
`app/templates/search_results.html`) -- trägt **dieselbe `_role_dep`-Absicherung wie jede andere
Büro-Seite**, nicht nur der API-Endpunkt dahinter: ein Monteur, der `/suche` über die Adresse
aufruft, bekommt 403 -> `access_denied.html`, bevor überhaupt etwas rendert. Automatisch vom
bestehenden Seiten-Audit-Test erfasst (`_dk_roles`-Markierung über `require_role()`), keine neue
`PAGE_AUDIT_EXEMPT`-Zeile nötig. Zusätzlich per echtem Ende-zu-Ende-Test gegen eine isolierte,
tatsächlich laufende Serverinstanz bestätigt (nicht nur `router_test_client`): ein frisch
angelegtes `field`-Konto bekommt sowohl auf `GET /suche` als auch auf `GET /api/search` über
echtes HTTP 403 -- null durchgelassen.

Die Seite selbst rendert nur das Gerüst, `q`/`types` werden client-seitig aus `location.search`
gelesen (Muster: jede andere Seite in diesem Projekt lädt ihre Daten per `fetch()` nach). Zeigt je
zurückgegebener Gruppe die reale Trefferzahl (`total`) und die auf `limit=20` gekappte Liste
(`hits`) -- "weitere anzeigen" fragt gezielt NUR diese eine Gruppe erneut ab (`types=<key>` +
erhöhtes `limit`), nicht die gesamte Suche neu. Filter nach Datensatzart: 17 Umschalt-Knöpfe
("Alle" setzt zurück), mehrere gleichzeitig wählbar -- die Schlüssel/Beschriftungen sind
client-seitig hartcodiert (`TYPE_LABELS`, kein Endpunkt liefert diese Liste, sie ändert sich nur,
wenn ohnehin die Registry selbst geändert wird), ein Regressionstest gleicht sie gegen
`OFFICE_SEARCH_SOURCES` ab (Schlüssel UND Reihenfolge), damit ein künftiges Auseinanderlaufen
auffällt.

**Tests**: `tests/test_v271_office_search_ui.py` (10 neue Tests -- Seiten-Absicherung,
Typenlisten-Abgleich, Topbar-Verdrahtung), dazu `tests/test_v254_topbar.py::
test_search_slot_is_present_and_empty` in zwei Tests umgeschrieben (die 1.3.45-Erwartung "Suchslot
bleibt leer" ist jetzt bewusst überholt -- ein Test für admin/office, ein Test für field). Volle
Suite weiterhin grün (1344/1344).

### Nachtrag (seit 1.4.4): Aufgaben-Sichtbarkeit in der Büro-Suche

Gemeldete Lücke aus 1.4.3 (siehe Abschnitt "Aufgabe" -> "Sichtbarkeit für Büro-Konten" oben):
`_search_tasks()` (die "tasks"-Quelle) hatte -- anders als jede andere Quelle -- keine
Mitarbeiter-Filterung. Ein Büro-Konto fand über `/suche` auch die persönlich zugewiesene Aufgabe
eines Kollegen, genau die Grenze, die `list_tasks_for_user()` (`GET /api/tasks`, Dashboard) seit
1.4.3 zieht -- zwei Stellen, eine Regel, aber nur an einer gepflegt.

**Behoben durch tatsächliche Wiederverwendung, keine zweite Kopie der Regel** -- ausdrückliche
Vorgabe des Betreibers ("Nutze wenn möglich dieselbe Filterfunktion, nicht eine zweite, die
dieselbe Regel nachbaut -- sonst laufen Liste und Suche beim nächsten Mal wieder auseinander").
`app/tasks.py::list_tasks()`/`list_tasks_for_user()` bekommen einen neuen, optionalen
`search: str | None`-Parameter (Titel-ILIKE, unverändert an `list_tasks()` durchgereicht).
`_search_tasks()` (`app/search.py`) ruft `list_tasks_for_user()` seither **zweimal** auf --
einmal ohne `unassigned_only` ("eigene"), einmal mit ("empfängerlose") -- und vereinigt beide
Ergebnislisten (Duplikate über die `id` entfernt): `list_tasks_for_user()` liefert für die
getrennten Board-Tabs bewusst ENTWEDER eigene ODER empfängerlose Aufgaben (ein
Entweder-Oder-Schalter, richtig so für "Meine Aufgaben"/"Offene Büro-Aufgaben" als zwei getrennte
Ansichten) -- die Suche braucht dagegen beide KOMBINIERT in einer Trefferliste, deshalb zwei
Aufrufe statt einem dritten, neuen Query-Modus. Ein Büro-Konto ohne Mitarbeiterverknüpfung kann
"eigene" nicht bestimmen (`ValueError`) -- das wird abgefangen, damit wenigstens die
empfängerlosen weiterhin gefunden werden (dieselbe Großzügigkeit wie beim direkten Sehen des
gemeinsamen Eingangs), statt die Suche für dieses Konto komplett leer zu lassen.

**Transportmechanismus**: `search_office()` bekommt einen neuen, optionalen
`employee_id: int | None = None`-Parameter (nur für "tasks" relevant, jede andere Quelle
ignoriert ihn -- kein bestehender Aufrufer musste sich ändern, da der Default `None` das
bisherige Verhalten für Admin unverändert lässt). Ein transientes, nie persistiertes
`AppUser(role=role, employee_id=employee_id)`-Objekt trägt beide Werte in
`list_tasks_for_user()` hinein -- dieselbe Technik wie `router_test_client()`s Test-Identität,
kein neuer Mechanismus. **Bewusst kein einheitlicher 4-Parameter-`query_fn` für alle 18
Quellen** (das hätte 17 unbeteiligte Funktionssignaturen um einen ungenutzten Parameter
erweitert) -- `search_office()`s Dispatch-Schleife behandelt "tasks" stattdessen als einzigen,
klar kommentierten Sonderfall (`if source.key == "tasks": ...`), der zusätzlich `role`/
`employee_id` an `source.query_fn` übergibt. `_task_row()` liest seither ein Dict
(`task_to_dict()`-Schema, geliefert von `list_tasks_for_user()`) statt eines ORM-`Task`-Objekts --
Feldnamen entsprechend angepasst (`project_name` statt `t.project.name`).

**Der verlangte Angriffstest** (`tests/test_v270_office_search.py`, vier neue Tests): ein
Büro-Konto findet über die Suche die eigenen UND die empfängerlosen Aufgaben, nie die eines
Kollegen (Kernfunktions- UND echter Router-Test); ein Büro-Konto ohne Mitarbeiterverknüpfung
findet weiterhin die empfängerlosen; Admin findet alle. Ein Monteur findet über die Büro-Suche
gar nichts -- unverändert bereits durch `allowed_roles`/den Router-`require_role()`-Gate
abgedeckt (`test_field_role_gets_nothing_from_any_source_pure_function`/
`test_office_search_router_field_role_always_gets_403`), keine neue Prüfung dafür nötig. Volle
Suite grün (1466/1466).
