# Befund: Du statt Sie (Stufe „Grundlage“, Teil C, 19.10.2026)

Nur Befund, nichts geändert. Vorgabe (Auszug, vollständig in `docs/archiv/redesign.md`, „Stufe „Grundlage““): „C. Du statt Sie – nur
Befund, nichts ändern: Liste aller Sie-Anreden (Sie, Ihnen, Ihr/Ihre als Anrede, „Bitte … Sie“), die ein Nutzer sieht: Vorlagen, Skripte,
Server-Meldungen, PDFs, E-Mails. Je Stelle Datei, Text und Gruppe: „Oberfläche“ (wird Du), „an Kunden“ (Angebote, Rechnungen, Mahnungen,
E-Mails, PDFs – bleibt Sie) oder „unklar“. Zahlen je Gruppe. „sie“ als dritte Person nicht mitzählen. Dazu ein Vorschlag für einen
Wächter-Test, der Kundentexte beim Sie hält.“

Stand: Commit `31b85e8` (1.8.156).

Umgesetzt in der Runde „Du“ (`docs/archiv/redesign.md`): 1.8.158 die Oberfläche per Du, 1.8.159 eine Meldung „Dein Konto ist keinem
Mitarbeiter zugeordnet …“, 1.8.160 der Wächter nach dem Vorschlag unten (`tests/test_v440_runde_du.py`).

## Vorgehen

- **Gesucht** (Groß-/Kleinschreibung beachtet): `Sie`, `Ihnen`, `Ihr`, `Ihre`, `Ihren`, `Ihrem`, `Ihrer`, `Ihres` als ganzes Wort -- „sie“
  und „ihr“ klein sind dritte Person und nie Anrede. „Bitte … Sie“ ist darin enthalten.
- **Quellen**: alle Vorlagen unter `app/templates/` (Markup und eingebettete Skripte, ohne Jinja-, HTML- und JS-Kommentare), alle
  Zeichenketten unter `app/**/*.py` (Server-Meldungen, PDF-Texte, E-Mail-Vorlagen, Standardsätze) ohne Docstrings, ohne Kommentare und ohne
  Protokollaufrufe (`logger.*` -- sieht kein Nutzer), die Migrationen unter `alembic/versions/` (sie schreiben Texte in die Datenbank, die
  danach in der Oberfläche und in Dokumenten stehen), dazu die Betreiber-Skripte `scripts/erstes_konto.py` und `scripts/reset_admin_2fa.py`
  (keine Treffer). Tests nicht. Suchskript und Rohliste: 108 Treffer an 89 Stellen.
- **Gegenprobe der Suche**: jede Datei mit einem Kundentext-Muster („Sehr geehrte“, „anbei“) liegt unter den Treffern
  (`checklist_email.py`, `contract_versions.py`, `invoices.py`, `notice_letters.py`, `orders.py`, `projects.py`, `reminders.py`,
  `settings.html`).
- **Dritte Person** von Hand ausgesondert: neun Treffer, in denen „Sie“/„Ihr“ am Satzanfang einen Gegenstand meint (die Checkliste, die
  Rechnung, die Fassung …) -- Liste unten, nicht gezählt.
- **Gruppen**: „Oberfläche“ = alles, was ein Nutzer des ERP liest (Seiten, Hinweise und Meldungen in den Skripten, Meldungen des Servers);
  „an Kunden“ = Text, der beim Auftraggeber ankommt (PDFs, E-Mail-Vorlagen, Mahntexte, Briefe, Standardsätze von Angebot und Rechnung)
  -- auch ein Platzhalter in den Einstellungen, der einen solchen Text vormacht, gehört dazu (er muss beim Sie bleiben).

## Zahlen

| Gruppe | Stellen | Anreden |
|---|---|---|
| Oberfläche (wird Du) | 50 | 53 |
| an Kunden (bleibt Sie) | 30 | 46 |
| unklar | 0 | 0 |
| dritte Person (nicht gezählt) | 9 | 9 |

„Unklar“ blieb leer: jede Stelle ließ sich am Empfänger festmachen. Grenzfälle, ausdrücklich eingeordnet: die beiden Platzhalter in
`settings.html` (Beispiel für die Zahlungsbedingung und für die Mahn-E-Mail) -- im ERP sichtbar, aber Kundentext, also „an Kunden“; „Ihr
Angebot“ als Kopfangabe in Vertrag und Auftragsbestätigung -- „an Kunden“.

Auffällig: 20 der 50 Oberflächen-Stellen (in 15 Dateien) sind dieselbe Meldung „… keinem Mitarbeiter zugeordnet“ in neun Fassungen („Ihr
ERP-Benutzer …“ 10-mal, „Ihr ERP-Benutzerkonto …“ 4-mal, „Ihr Büro-Konto …“ 2-mal, je einmal „Ihr Benutzer … – Aufgaben …“, „Ihr Benutzer …
– Zeit buchen …“, „Ihr Konto … und hat keine eigenen Anträge“, „Ihr Konto ist mit keinem Mitarbeiter verknüpft“). Bei der Umstellung
lohnt eine gemeinsame Meldung (eine Stelle im Server, eine im Browser).

## Liste

### Oberfläche: 50 Stellen, 53 Anreden

| Datei:Zeile | Text (Ausschnitt) | Wohin / Art |
|---|---|---|
| `app/templates/access_denied.html:22` | <h1>Diese Seite ist für Ihre Rolle nicht verfügbar</h1> | Seite (Text, Hinweis oder Meldung im Skript) (Ihre) |
| `app/templates/access_denied.html:23` | <p>{{ message or "Bitte wenden Sie sich an eine Person mit den passenden Rechten, falls Sie diese Seite benötigen." }}</p> | Seite (Text, Hinweis oder Meldung im Skript) (Sie, Sie) |
| `app/templates/checklist_template.html:217` | ?`<div class="notice">Sie bearbeiten den <b>Entwurf (Fassung ${esc(version.version_no)})</b>. Monteure sehen ihn erst nach dem Veröffen | Seite (Text, Hinweis oder Meldung im Skript) (Sie) |
| `app/templates/checklist_template.html:218` | :`<div class="notice info">Sie sehen die <b>gültige Fassung ${esc(version.version_no)}</b> (nur lesen). Zum Ändern „Neuen Entwurf anlegen“.< | Seite (Text, Hinweis oder Meldung im Skript) (Sie) |
| `app/templates/dashboard.html:87` | if(!isAdmin&&!authStatus.user.employee_id){container.innerHTML='<div class="muted small">Ihr Benutzer ist keinem Mitarbeiter zugeordnet – Aufgaben können nicht  | Seite (Text, Hinweis oder Meldung im Skript) (Ihr) |
| `app/templates/field_timesheet.html:125` | showLoadWarning('Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. Bitte unter Einstellungen → Benutzer & Zugriff einen Mitarbei | Seite (Text, Hinweis oder Meldung im Skript) (Ihr) |
| `app/templates/mobil.html:151` | if(!groups.length){el.className='empty';el.textContent='Keine Wartungen an Ihren aktuellen Objekten.';return} | Seite (Text, Hinweis oder Meldung im Skript) (Ihren) |
| `app/templates/mobil.html:339` | document.getElementById('maintenanceList').textContent='Keine Wartungen an Ihren aktuellen Objekten.'; | Seite (Text, Hinweis oder Meldung im Skript) (Ihren) |
| `app/templates/roof_area.html:534` | ?`Ziehen Sie ein Rechteck auf der Skizze auf, um die Fläche von "${c?c.name:''}" zu markieren.` | Seite (Text, Hinweis oder Meldung im Skript) (Sie) |
| `app/templates/roof_area.html:535` | :`Klicken Sie auf die Skizze, um die Position von "${c?c.name:''}" zu setzen.`; | Seite (Text, Hinweis oder Meldung im Skript) (Sie) |
| `app/templates/service_reports.html:1377` | if(!employeeId&&nurFuerSichBuchen()){st.className='status err';st.textContent='Ihr Benutzer ist keinem Mitarbeiter zugeordnet – Zeit buchen ist nicht möglich.'; | Seite (Text, Hinweis oder Meldung im Skript) (Ihr) |
| `app/templates/tasks.html:80` | <div class="hint">Für jedes Büro-Konto sichtbar. „Übernehmen“ macht die Aufgabe zu Ihrer eigenen.</div> | Seite (Text, Hinweis oder Meldung im Skript) (Ihrer) |
| `app/templates/tasks.html:395` | if(ok){st.className='status ok';st.textContent='Übernommen – die Aufgabe steht jetzt bei Ihren Aufgaben.'} | Seite (Text, Hinweis oder Meldung im Skript) (Ihren) |
| `app/templates/time_backoffice.html:60` | Anträge – die Anträge anderer sieht und entscheidet ein Administrator.':'Hier stehen nur Ihre eigenen Anträge – die Anträge anderer sieht und entscheidet ein Ad | Seite (Text, Hinweis oder Meldung im Skript) (Ihr, Ihre) |
| `app/templates/time_tracking.html:55` | showLoadWarning(isUnlinked?'Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. Bitte unter Einstellungen → Benutzer & Zugriff einen Mitarbei | Seite (Text, Hinweis oder Meldung im Skript) (Ihr) |
| `app/templates/time_tracking_field.html:113` | <div class="muted small" style="margin-bottom:10px">Als Kolonnenführer buchen Sie hier für die ausgewählten Kollegen mit. Jede Buchung zeigt, dass Sie sie angel | Seite (Text, Hinweis oder Meldung im Skript) (Sie, Sie) |
| `app/templates/time_tracking_field.html:515` | showLoadWarning('Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. Bitte unter Einstellungen → Benutzer & Zugriff einen Mitarbei | Seite (Text, Hinweis oder Meldung im Skript) (Ihr) |
| `app/templates/time_tracking_field.html:534` | Warning('Keine eigenen Aufträge im Zeitraum gefunden. Ist ein Einsatz nicht dabei, wenden Sie sich an das Büro.'); | Seite (Text, Hinweis oder Meldung im Skript) (Sie) |
| `app/operational_assets.py:412` | in mindestens einem Einsatzbericht erfasst und kann nicht gelöscht werden -- archivieren Sie es stattdessen (Status auf Inaktiv). | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/operational_assets.py:420` | u diesem Betriebsmittel gibt es Checklisten -- es kann nicht gelöscht werden. Archivieren Sie es stattdessen (Status auf Inaktiv). | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/permissions.py:89` | Für Ihre Rolle nicht verfügbar. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihre) |
| `app/routers/absence_requests.py:37` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/routers/absence_requests.py:70` | Sie dürfen diesen Abwesenheitsantrag nicht zurückziehen. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/routers/checklists.py:83` | Von dieser Checkliste sind für Sie nur Titel, Datum und Ersteller sichtbar. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/routers/checklists.py:99` | Ihr Konto ist mit keinem Mitarbeiter verknüpft. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/routers/field_defects.py:42` | Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet -- bitte einen Administrator kontaktieren. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/routers/field_view.py:371` | Die Wartungshistorie zeigt die Monteursansicht nur für Objekte Ihrer Aufträge. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihrer) |
| `app/routers/field_view.py:121` | Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet -- bitte einen Administrator kontaktieren. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/routers/field_view.py:220` | Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/routers/maintenance_contracts.py:212` | Ihr ERP-Benutzerkonto ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/routers/maintenance_contracts.py:214` | Dieses Objekt ist Ihnen aktuell nicht zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihnen) |
| `app/routers/orders.py:41` | Dieser Auftrag ist Ihnen nicht zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihnen) |
| `app/routers/project_participants.py:70` | sind für Ihre Rolle nicht sichtbar. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihre) |
| `app/routers/service_reports.py:91` | Sie dürfen nur sich selbst als Mitarbeiter angeben. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/routers/tasks.py:59` | Diese Aufgabe ist für Sie nicht sichtbar. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/routers/time_tracking.py:169` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/routers/time_tracking.py:374` | Sie dürfen diese Zeiterfassung nicht ändern. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/routers/time_tracking.py:406` | Sie dürfen diese Zeitbuchung nicht ändern. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/routers/time_tracking.py:427` | Sie dürfen diese Zeitbuchung nicht löschen. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/routers/time_tracking.py:46` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/routers/time_tracking.py:48` | Sie dürfen nur eigene Zeiten erfassen. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/routers/time_tracking.py:187` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/routers/time_tracking.py:311` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/routers/work_preparation.py:44` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/tasks.py:197` | Ihr Büro-Konto ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/tasks.py:202` | Diese Aufgabe ist für Ihre Rolle nicht sichtbar. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihre) |
| `app/tasks.py:167` | Ihr Büro-Konto ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/time_tracking.py:412` | Ihr ERP-Benutzer ist keinem Mitarbeiter zugeordnet. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Ihr) |
| `app/time_tracking.py:419` | Sie gehören nicht zum ausgewählten Team. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |
| `app/time_tracking.py:422` | Sie dürfen nur für Kollegen des ausgewählten Teams mitbuchen. | Server-Meldung an die Oberfläche (detail einer 403/409/422) (Sie) |

### an Kunden: 30 Stellen, 46 Anreden

| Datei:Zeile | Text (Ausschnitt) | Wohin / Art |
|---|---|---|
| `app/templates/settings.html:290` | dardsatz)</span></label><textarea id="ptTextTemplate" placeholder="z. B. Bitte begleichen Sie den Betrag bis zum {faelligkeitsdatum}. Bei Zahlung bis {skontodat | Beispiel (Platzhalter) für den Text der Zahlungsbedingung auf Rechnungen (Sie) |
| `app/templates/settings.html:2026` | ="rl${x.id}EmailBody" rows="4" placeholder="Sehr geehrte Damen und Herren, anbei erhalten Sie unsere ${esc(x.level)}. Mahnung …">${esc(x.email_body_template\|\|'' | Beispiel (Platzhalter) für die E-Mail einer Mahnstufe (Sie) |
| `app/checklist_email.py:25` | anbei erhalten Sie die Checkliste „{checkliste}“ (Nr. {checklistennummer}, {bezug}). Alle Angaben entnehmen Sie bitte dem beigef | E-Mail: Checkliste an den Auftraggeber (Vorgabe) (Sie, Sie) |
| `app/contract_pdf.py:141` | Ihr Angebot | PDF Vertrag, Kopfangabe „Ihr Angebot“ (Ihr) |
| `app/contract_versions.py:62` | anbei erhalten Sie den Vertrag zu Auftrag {auftragsnummer} (Fassung {fassung}) mit unserem Angebot als Anlage. | E-Mail: Vertrag (Vorgabe) (Sie) |
| `app/invoices.py:1956` | anbei erhalten Sie unsere Rechnung {rechnungsnummer} vom {rechnungsdatum} über {gesamtbetrag}. Alle Einzelheiten entnehmen Sie b | E-Mail: Rechnung (Vorgabe) (Sie, Sie) |
| `app/invoices.py:810` | überweisen wir Ihnen. | PDF Rechnung: Satz bei Erstattungsbetrag (Ihnen) |
| `app/invoices.py:1971` | – den überweisen wir Ihnen. | Zahlungshinweis der Schlussrechnung (PDF und E-Mail-Platzhalter) bei Erstattung (Ihnen) |
| `app/notice_letters.py:161` | hiermit zeigen wir Ihnen an, dass wir bei der Ausführung unserer Leistungen zum oben genannten Auftrag behindert sind. Im Einzelnen: | Brief Behinderungsanzeige an den Auftraggeber (Ihnen) |
| `app/notice_letters.py:165` | hiermit melden wir Ihnen Bedenken zur Ausführung unserer Leistungen zum oben genannten Auftrag an und bitten um Ihre Entscheidung. Im | Brief Bedenkenanzeige an den Auftraggeber (Ihnen, Ihre) |
| `app/notice_letters.py:177` | anbei erhalten Sie das Protokoll der Abnahme zum Auftrag {auftragsnummer} (Bauvorhaben {bauvorhaben}). | E-Mail: Abnahmeprotokoll (Vorgabe) (Sie) |
| `app/notice_letters.py:179` | anbei erhalten Sie unsere Behinderungsanzeige zum Auftrag {auftragsnummer} (Bauvorhaben {bauvorhaben}). | E-Mail: Behinderungsanzeige (Vorgabe) (Sie) |
| `app/notice_letters.py:181` | anbei erhalten Sie unsere Anzeige der Wiederaufnahme der Arbeiten zum Auftrag {auftragsnummer} (Bauvorhaben {bauvorhaben}). | E-Mail: Anzeige der Wiederaufnahme (Vorgabe) (Sie) |
| `app/notice_letters.py:183` | anbei erhalten Sie unsere Bedenkenanzeige zum Auftrag {auftragsnummer} (Bauvorhaben {bauvorhaben}) mit der Bitte um Ihre Entsche | E-Mail: Bedenkenanzeige (Vorgabe) (Sie, Ihre) |
| `app/option_settings.py:46` | Vielen Dank für Ihre Anfrage. Gerne bieten wir Ihnen die nachfolgend beschriebenen Leistungen an. | Einleitungstext Angebot (Standardsatz der Auswahlliste) (Ihre, Ihnen) |
| `app/option_settings.py:70` | Bitte überweisen Sie den Rechnungsbetrag unter Angabe der Rechnungsnummer auf das unten genannte Konto. | Schlusstext Rechnung (Standardsatz) (Sie) |
| `app/option_settings.py:81` | Vielen Dank für Ihren Auftrag. Sollte sich Ihre Bankverbindung geändert haben, teilen Sie uns diese bitte für die Erstattung mit. | Schlusstext Rechnung bei Erstattung (Standardsatz) (Ihren, Ihre, Sie) |
| `app/order_pdf.py:79` | Ihr Angebot | PDF Auftragsbestätigung, Kopfangabe „Ihr Angebot“ (Ihr) |
| `app/orders.py:521` | anbei erhalten Sie unsere Auftragsbestätigung {auftragsnummer} über {gesamtbetrag}. Alle Einzelheiten entnehmen Sie bitte dem be | E-Mail: Auftragsbestätigung (Vorgabe) (Sie, Sie) |
| `app/projects.py:681` | anbei erhalten Sie unser Angebot {angebotsnummer} über {gesamtbetrag}. Alle Einzelheiten entnehmen Sie bitte dem beigefügten PDF | E-Mail: Angebot (Vorgabe) (Sie, Sie) |
| `app/reminders.py:839` | anbei erhalten Sie unsere {mahnstufe} zu Rechnung {rechnungsnummer}. Alle Einzelheiten entnehmen Sie bitte dem beigefügten PDF. | E-Mail: Mahnung (Vorgabe) (Sie, Sie) |
| `app/reminders.py:113` | seingang zu Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Bitte begleichen Sie den Betrag von {gesamtbetrag} (Aufstellung unten) bis zum {neue_fr | Mahntext 1. Stufe (Vorgabe) (Sie, Ihre, Sie) |
| `app/reminders.py:120` | ahlungseingang zu Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Wir bitten Sie letztmalig, den Betrag von {gesamtbetrag} (Aufstellung unten) bis  | Mahntext 2. Stufe (Vorgabe) (Sie) |
| `app/reminders.py:127` | Rechnung {rechnungsnummer} vom {rechnungsdatum} weiterhin nicht ausgeglichen. Wir bitten Sie letztmalig um Zahlung von {gesamtbetrag} (Aufstellung unten) bis zu | Mahntext 3. Stufe (Vorgabe) (Sie) |
| `alembic/versions/8e2f4b6d1c97_nebenforderungen_z2b.py:39` | seingang zu Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Bitte begleichen Sie den offenen Betrag von {offener_betrag} zuzüglich einer Mahngebühr | Mahntext einer Stufe (Migration schreibt ihn in die Datenbank) (Sie, Ihre, Sie) |
| `alembic/versions/8e2f4b6d1c97_nebenforderungen_z2b.py:44` | ahlungseingang zu Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Wir bitten Sie letztmalig, den offenen Betrag von {offener_betrag} zuzüglich eine | Mahntext einer Stufe (Migration schreibt ihn in die Datenbank) (Sie) |
| `alembic/versions/8e2f4b6d1c97_nebenforderungen_z2b.py:48` | Rechnung {rechnungsnummer} vom {rechnungsdatum} weiterhin nicht ausgeglichen. Wir bitten Sie letztmalig um Zahlung des offenen Betrags von {offener_betrag} zuzü | Mahntext einer Stufe (Migration schreibt ihn in die Datenbank) (Sie) |
| `alembic/versions/8e2f4b6d1c97_nebenforderungen_z2b.py:55` | seingang zu Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Bitte begleichen Sie den Betrag von {gesamtbetrag} (Aufstellung unten) bis zum {neue_fr | Mahntext einer Stufe (Migration schreibt ihn in die Datenbank) (Sie, Ihre, Sie) |
| `alembic/versions/8e2f4b6d1c97_nebenforderungen_z2b.py:59` | ahlungseingang zu Rechnung {rechnungsnummer} vom {rechnungsdatum} feststellen. Wir bitten Sie letztmalig, den Betrag von {gesamtbetrag} (Aufstellung unten) bis  | Mahntext einer Stufe (Migration schreibt ihn in die Datenbank) (Sie) |
| `alembic/versions/8e2f4b6d1c97_nebenforderungen_z2b.py:63` | Rechnung {rechnungsnummer} vom {rechnungsdatum} weiterhin nicht ausgeglichen. Wir bitten Sie letztmalig um Zahlung von {gesamtbetrag} (Aufstellung unten) bis zu | Mahntext einer Stufe (Migration schreibt ihn in die Datenbank) (Sie) |

### unklar: 0 Stellen, 0 Anreden

keine


### dritte Person (nicht gezählt): 9 Stellen, 9 Anreden

| Datei:Zeile | Text (Ausschnitt) | Bezug |
|---|---|---|
| `app/templates/address_import.html:211` | if (!confirm('Diese Adresse wirklich verwerfen? Sie erscheint dann nicht mehr in der Arbeitsliste.')) return; | die Adresse (Sie) |
| `app/templates/checklist.html:273` | Witterung'}), schließt das Büro sie hier mit Begründung ab – auch mit fehlenden Angaben. Sie bleibt als Beleg, verschwindet aus den offenen Listen, und die offe | die Checkliste (Sie) |
| `app/templates/checklist.html:281` | andslos abschließen?\n\nDanach ist sie nicht mehr änderbar und wird nicht mehr versendet. Sie bleibt mit der Begründung als Beleg erhalten.`))return; | die Checkliste (Sie) |
| `app/templates/invoice_detail.html:383` | async function stornoInvoice(){if(!confirm('Stornorechnung anlegen? Sie wird zunächst als Entwurf angelegt und muss anschließend selbst versendet werden.'))retu | die Stornorechnung (Sie) |
| `app/templates/work_preparation.html:20` | r Nachkalkulation</h3><div class="warn"><b>Planstunden werden nicht manuell gepflegt.</b> Sie entsprechen automatisch den kalkulierten Soll-Stunden des aktuelle | die Planstunden (Sie) |
| `app/checklists.py:1694` | Die Checkliste trägt verworfene Unterschriften. Sie bleiben samt ihren Fotos als Nachweis erhalten, die Checkliste kann deshalb nicht gelöscht werden. | die Unterschriften (Sie) |
| `app/contract_pdf.py:216` | Unterschrieben wurde genau diese Fassung. Ihr PDF in der Ablage hat die Prüfsumme (SHA-256): | die Fassung („Ihr PDF“ = das PDF der Fassung) (Ihr) |
| `app/invoices.py:315` | . Sie muss über 0 € liegen. | die Rechnung (Sie) |
| `app/invoices.py:313` | . Sie muss über 0 € liegen – Positionen mit Betrag eintragen oder den Entwurf löschen. | die Rechnung (Sie) |

## Vorschlag: Wächter-Test „Kundentexte bleiben beim Sie“

Ziel: bei der Umstellung der Oberfläche auf Du darf kein Kundentext mitgehen -- und ein neuer Kundentext darf nicht unbemerkt in einer
Datei entstehen, die niemand als Kundentext kennt.

1. **Verzeichnis der Kundentexte** im Test (`KUNDENTEXTE`, Muster wie `FESTE_WERTE` in `test_v364`): je Quelle Modul und Name --
   die Funktionen der E-Mail-Vorlagen (`projects.py`, `orders.py`, `invoices.py`, `reminders.py`, `contract_versions.py`,
   `checklist_email.py`, `notice_letters.py`), die Standardsätze in `option_settings.py` (Einleitung Angebot, Schlusstexte Rechnung),
   die Mahntexte (`reminders.py` und die Migration `8e2f4b6d1c97`), die PDF-Renderer (`*_pdf.py`, `notice_letters.py`) und die beiden
   Platzhalter in `settings.html` (über ihre `id`).
2. **Kundentexte bleiben beim Sie**: jede Zeichenkette aus dem Verzeichnis (per AST bzw. aus der Vorlage gelesen) enthält keine
   Du-Form (`du`, `dich`, `dir`, `dein…`, `euch`, `euer…` als ganzes Wort, groß oder klein); dazu je Dokumentart ein echtes PDF aus
   Testdaten (Angebot, Auftrag, Rechnung mit Erstattung, Mahnung, Vertrag, Behinderungs- und Bedenkenanzeige), Text wie in
   `tests/test_v213_inspection_items.py::_extract_pdf_text()` herausgelesen und ebenso geprüft. Eine Gegenprobe ersetzt in einem Mahntext
   „Sie“ durch „du“ -- rot.
3. **Kein Kundentext außerhalb des Verzeichnisses**: jede Zeichenkette unter `app/` mit einem Kundentext-Merkmal („Sehr geehrte“,
   „anbei erhalten“, „Mit freundlichen Grüßen“, „überweisen wir Ihnen“) steht im Verzeichnis -- sonst nennt der Test Datei und Zeile. So
   fällt ein neuer Brief oder eine neue E-Mail-Vorlage auf, bevor sie beim Umstellen versehentlich geduzt wird.
4. **Nach der Umstellung, als Gegenstück**: außerhalb des Verzeichnisses keine Sie-Anrede mehr (dieselbe Suche wie dieser Befund); die
   dritte Person am Satzanfang („Sie bleibt als Beleg …“) steht in einer Ausnahmeliste mit Bezug oder wird umformuliert -- die Liste darf
   nur kürzer werden.
