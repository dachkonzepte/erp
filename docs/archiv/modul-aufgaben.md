# Aufgabe (Task)

Ausgelagert aus CLAUDE.md am 2026-09-28 im Zuge der Aufteilung in eine schlanke
CLAUDE.md plus themensortiertes Archiv (siehe CLAUDE.md, Abschnitt "Modulübersicht",
und `docs/archiv/regel-abgleich.md` für die vollständige Zuordnung). Der Inhalt ist
wortgetreu (per Skript, zeilenweise) aus der vorherigen CLAUDE.md übernommen, keine
Umformulierung. Versionsangaben ("seit 1.x.y") beziehen sich auf den Stand zum
jeweiligen Zeitpunkt der ursprünglichen Aufzeichnung.

---

- **Aufgabe** (`Task`, seit 1.1.0, erstes Modul `aufgabenmanagement`): freie, eigenständige Aufgabe
  mit Status und Priorität, optional einem Mitarbeiter und/oder einem `Project` zugeordnet –
  unabhängig von den älteren, bereichsgebundenen `WorkPreparationTask`-Einträgen der
  Arbeitsvorbereitung. **Sichtbarkeit, zentral über EINE Stelle entschieden (seit 1.4.3, siehe
  Unterabschnitt "Sichtbarkeit für Büro-Konten" unten)**: `app/tasks.py::list_tasks_for_user()`
  ist der ausschließliche Einstiegspunkt -- eigene zugewiesene Aufgaben für ein Büro-Konto
  (serverseitig erzwungen, Kollegen-Aufgaben bleiben unsichtbar), Admin frei wählbar,
  empfängerlose Aufgaben zusätzlich für JEDES Büro-/Admin-Konto sichtbar. Drei
  freie Felder `source_module`/`source_label`/`source_url` sind die **Automatisierungs-
  Anschlussstelle**: ein künftiges Modul (z. B. digitale Wartungsberichte) ruft `create_task()` in
  `app/tasks.py` direkt in-process auf, um automatisiert eine Aufgabe zu erzeugen, ohne dass
  `tasks` dafür etwas über das aufrufende Modul wissen muss; Idempotenz (kein doppeltes Anlegen)
  ist Sache des aufrufenden Moduls.
  - **Spalten** (`TaskColumn`, seit 1.1.1): `Task.status` ist kein fester Enum mehr, sondern
    referenziert `TaskColumn.key` – ein Admin verwaltet die Spalten (umbenennen, sortieren,
    hinzufügen, löschen sobald ungenutzt) unter Einstellungen → Aufgaben frei, angelehnt an den
    mehrstufigen Ablauf einer Kundenanfrage. Jede Spalte trägt `is_done`; `completed_at` auf
    `Task` richtet sich nach diesem Flag, nicht mehr nach dem Literal `"erledigt"`. Fehlt jede
    Spalte (z. B. eine per `Base.metadata.create_all()` erzeugte Testdatenbank ohne die Migration),
    seedet `app/task_columns.py::ensure_default_columns()` beim ersten Zugriff selbstständig die
    drei ursprünglichen Spalten nach – dieselben drei, die die Migration `6ed174efcf4a` für echte
    Installationen bereits per Daten-Seed anlegt.
  - **Checkliste** (`TaskChecklistItem`, seit 1.1.2): abhakbare Unterpunkte einer Aufgabe. Anders
    als die migrationsarmen Zusatztabellen zu bestehenden Kern-Tabellen (Quote, QuoteItem, siehe
    Regel 6) bekommt sie eine echte ORM-Relationship mit `cascade="all, delete-orphan"` auf
    `Task`, da `Task` selbst schon unser eigenes, neues Modul ist – kein manuelles Aufräumen beim
    Löschen einer Aufgabe nötig.
  - **Zuweisungs-E-Mail** (seit 1.1.3): `notify_task_assignment()` in `app/tasks.py` verschickt bei
    neuer/geänderter `assigned_employee_id` eine Benachrichtigung an `EmployeeProfile.email` (kann
    fehlen) über die neue anhangslose `send_plain_email()` in `app/email_sending.py`. Schalter dazu
    in `TaskSettings.notify_on_assignment` (Singleton wie `LaborRateSettings`). Ein Versandfehler
    wird innerhalb der Funktion abgefangen – darf das bereits erfolgte Speichern der Aufgabe nicht
    rückwirkend als Fehler erscheinen lassen.
  - **Archivieren** (`set_task_archived()`, seit 1.2.11, gleiches Muster wie
    `Project.archived`): blendet eine Aufgabe aus dem Standard-Board aus, ohne sie wie
    `delete_task()` unwiderruflich zu löschen – unabhängig von Spalte/`is_done`. `list_tasks()`
    nimmt dafür `include_archived` (Default `False`).
  - **"Vorgang erstellen" aus der Aufgabe heraus** (seit 1.2.21, für Aufgaben mit
    `source_module="wartungsbericht"`, siehe **Mängel und Fotos** oben): der eigentliche
    Folgeauftrag (Projekt + Auftrag über `create_quick_service_order()`) entsteht nicht mehr
    automatisch beim Anlegen des Mangels, sondern erst durch einen bewussten Klick auf dieser
    Aufgabe. Rückrichtung von der Aufgabe zum Mangel läuft über die bereits bestehende Spalte
    `Finding.follow_up_task_id` (`get_finding_for_task()` in `app/findings.py`, eine gezielte
    `select`-Abfrage) – bewusst KEINE neue Spalte an `Task`, um für einen einzelnen Anzeigefall
    keine neue Relationship einzuführen (gleiche Zurückhaltung wie bei
    `list_contracts_for_property()`). `create_follow_up_project_for_task()` lehnt ab, wenn kein
    zugehöriger Mangel existiert oder bereits ein Vorgang erzeugt wurde (`follow_up_order_id`
    gesetzt). Zwei neue, modulgegatete Endpunkte `GET/POST /api/tasks/{id}/finding` bzw.
    `/create-follow-up-project` – URL-Präfix richtet sich nach dem Task-Kontext, Business-Logik
    bleibt in `app/findings.py` (Muster wie `GET /api/orders/{order_id}/roof-areas`). Navigiert
    nach Erfolg **sofort** zum neuen Vorgang (anders als die 1.2.20-Ausnahme bei "Vorgang
    erstellen" auf der Wartungsvertrags-Seite) – hier sitzt der Sachbearbeiter am Schreibtisch
    und bearbeitet die Aufgabe gezielt, nicht mitten in einer Felderfassung.
  - **Sichtbarkeit für Büro-Konten, "Übernehmen"/"Zurück in den Büro-Eingang" (seit 1.4.3)**:
    Anlass war der in 1.4.2 gemeldete Fund, dass eine unassigned Aufgabe für ein Büro-Konto ohne
    Admin-Rolle nach dem damaligen Filter unsichtbar blieb -- erst Befund (der Filter sitzt
    exakt an einer Stelle: `list_tasks()`, aufgerufen ausschließlich von `GET /api/tasks`),
    dann bestätigter Bauauftrag. `app/tasks.py::list_tasks_for_user(db, user, *, unassigned_only
    ..., employee_id=...)` ist seither die EINE Stelle für jede Task-Sichtbarkeitsentscheidung
    (Liste, Dashboard-Widget, jede Zählung) -- nutzt `has_role()` (`app/permissions.py`, neu die
    zentrale Rollenquelle für `require_role()` UND den Jinja-Global `can()`, statt eines
    zweiten, eigenen Wegs zur Rollenbestimmung -- genau das Muster, das bei
    `build_din5008_header_block()` bereits einmal zu drei divergierenden Varianten geführt hat,
    siehe "Kopfbereich"). `list_tasks()` bekommt dafür einen neuen, vorrangigen
    `unassigned_only: bool`-Parameter (`Task.assigned_employee_id.is_(None)`). Admin bleibt frei
    wählbar; ein Büro-Konto ist ohne `unassigned_only` weiterhin zwingend auf die eigene
    `employee_id` festgelegt (Kollegen-Aufgaben bleiben unsichtbar, unverändert); mit
    `unassigned_only=True` sieht JEDES Büro-/Admin-Konto den gemeinsamen Eingang, unabhängig von
    der eigenen `employee_id` -- das reine SEHEN braucht dafür keine Mitarbeiter-Verknüpfung
    (nur das Übernehmen selbst, siehe unten). Ein Monteur bekommt von `list_tasks_for_user()`
    stets eine leere Liste (die primäre Absicherung bleibt aber `require_role()` am Router --
    ein Monteur erreicht `GET /api/tasks` gar nicht, unverändert seit "Rechtekonzept").

    **"Übernehmen" weist fest zu, kein dritter Zustand**: `claim_task(db, task_id, user)`
    (`POST /api/tasks/{id}/claim`) setzt `assigned_employee_id` auf die eigene, verknüpfte
    `employee_id` -- exakt dasselbe Feld wie jede andere Zuweisung, keine zweite Zuweisungsart.
    Fehlt die Mitarbeiter-Verknüpfung, eine klare 400-Meldung, kein stiller Fehler -- derselbe
    Fall wie beim Monteur ohne `employee_id` an anderer Stelle. Eine bereits vergebene Aufgabe
    lässt sich nicht "übernehmen" (400) -- eine neue, bewusste Sperre gegen versehentliches
    Stehlen einer Kollegen-Aufgabe, die die bestehende PUT-Zuweisung nicht kennt. "Zurück in den
    Büro-Eingang" (`release_task()`, `POST /api/tasks/{id}/release`) setzt `assigned_employee_id`
    zurück auf `NULL`, bewusst OHNE Eigentümerschafts-Prüfung -- konsistent mit der bereits
    bestehenden, dokumentierten Lücke bei PUT/DELETE/archive/unarchive (kein Eigentümer-Check,
    siehe oben), keine isolierte Verschärfung nur hier.

    **Oberfläche**: neues, opt-in Dashboard-Widget "Offene Büro-Aufgaben" (`open_office_tasks`,
    `app/templates/dashboard.html`, Muster `due_maintenance`/`due_assets` -- NICHT im
    `DEFAULT_LAYOUT`) zeigt `GET /api/tasks?unassigned_only=true` mit einem
    "Übernehmen"-Button je Zeile, der nach Erfolg gezielt nur den eigenen Widget-Container neu
    rendert. "Meine Aufgaben" bleibt unverändert (ausschließlich eigene zugewiesene Aufgaben,
    nie unassigned). `/tasks` bekommt einen neuen Button "Zurück in den Büro-Eingang" im Editor,
    sichtbar nur bei bereits zugewiesener Aufgabe -- der Board-Fetch selbst (`loadTasks()`)
    bleibt für Nicht-Admin unverändert "nur eigene Aufgaben"; ein Monteur sieht dort weiterhin
    nichts (gesamte `/api/tasks*`-Familie bleibt Büro/Admin-only).

    **Angriffstest bestätigt** (`tests/test_v279_task_visibility.py`, 21 Tests): ein Monteur
    bekommt über `GET /api/tasks?unassigned_only=true` UND über die Claim/Release-Endpunkte --
    auch mit einer geratenen, nicht existierenden Aufgaben-ID -- durchgängig 403, bevor
    irgendeine Geschäftslogik läuft. Ein Büro-Konto sieht die empfängerlosen, aber nicht die
    persönlich zugewiesene Aufgabe eines Kollegen, auch nicht mit manipuliertem
    `employee_id`-Parameter. Die dabei transparent gemeldete, unabhängige Lücke in der
    Büro-Suche (`app/search.py::_search_tasks()` ohne Mitarbeiter-Filterung) ist seit 1.4.4
    behoben -- siehe Abschnitt "Büro-Suche" -> "Nachtrag (seit 1.4.4)" unten.

  - **Ziel-Mindestrolle für empfängerlose Aufgaben, `min_visible_role` (seit 1.5.0)**: allgemeine
    Erweiterung des obigen claim/release-Modells, nicht nur für die Betriebskosten-Übersicht
    gedacht -- Anlass war deren Kündigungsfrist-Erinnerung ("geht nur buero_finanzen etwas an,
    nicht die Auftragsbearbeitung"), aber das Feld liegt direkt auf `Task` und ist für jedes
    künftige Modul nutzbar. Neue, nullable Spalte `Task.min_visible_role: String(30)` -- `NULL`
    bedeutet unverändert "an jedes Büro-/Admin-Konto" (wie oben), ein gesetzter Rollenwert (z. B.
    `buero_finanzen`) grenzt eine empfängerlose Aufgabe zusätzlich auf diese Rolle UND alles
    Darüberliegende ein, geprüft über die bereits bestehende `has_min_role()`-Hierarchie
    (`app/permissions.py`, `ROLE_RANK`) -- **kein zweiter, eigener Rollenvergleich**, exakt die
    Vorgabe, das sauber ins bestehende Modell einzupassen statt eine Parallelstruktur zu bauen.
    `app/tasks.py::list_tasks_for_user()` filtert dafür JEDE zurückgegebene Zeile zusätzlich
    (`row.min_visible_role is None or has_min_role(user, row.min_visible_role)`) -- unbedingt,
    nicht nur im `unassigned_only`-Zweig, für Konsistenz (praktisch relevant wird es aber nur
    dort, da eine bereits einem Mitarbeiter zugewiesene Aufgabe ohnehin nur für diesen selbst
    oder Admin sichtbar ist). `create_task()`/`update_task()` validieren den Wert gegen `ROLES`
    (`app/permissions.py`), ein unbekannter String wirft `ValueError`.

    **`claim_task()` bekommt dafür ein zweites, eigenes Exception-Muster**: trägt die Aufgabe ein
    `min_visible_role`, das die übernehmende Person nicht erfüllt, wirft die Funktion
    `PermissionError` (NICHT `ValueError`) -- geprüft VOR der "bereits vergeben"-Prüfung, damit
    eine geratene Aufgaben-ID einer fremden Rolle immer dasselbe 403 liefert, unabhängig vom
    Zuweisungszustand. `app/routers/tasks.py::claim_task_endpoint()` fängt `PermissionError`
    separat ab und mappt es auf 403 -- getrennt von der bestehenden `ValueError` -> 400-Zuordnung
    für Geschäftsregeln (fehlende `employee_id`, bereits vergeben). `release_task()` bleibt
    bewusst UNVERÄNDERT ohne jede Rollenprüfung -- konsistent mit der bereits dokumentierten,
    akzeptierten Lücke bei PUT/DELETE/archive/unarchive oben, keine isolierte Verschärfung nur
    für dieses neue Feld.

    Erster echter Nutzer: `app/recurring_costs.py::check_due_cancellations_and_create_reminders()`
    setzt `min_visible_role=ROLE_OFFICE_FINANZEN` -- siehe Abschnitt "Betriebskosten-Übersicht"
    unten. Angriffstest dort: ein `buero_auftrag`-Konto sieht eine finanz-adressierte Aufgabe an
    keiner Stelle (weder in der Liste noch im gemeinsamen Eingang) und kann sie auch mit
    bekannter ID nicht übernehmen (403) -- `field` bleibt ohnehin über `require_role()` am
    Router vollständig ausgeschlossen, unverändert.
