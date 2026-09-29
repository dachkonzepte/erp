"""checklisten_startvorlagen -- 13 Startvorlagen des Moduls "checklisten" (seit 1.8.5)

Daten-Migration, bewusst KEIN Self-Seeding (das würde vom Büro gelöschte Vorlagen beim nächsten
Zugriff wiederherstellen, siehe docs/archiv/modul-checklisten.md, "Startvorlagen"). Alle Vorlagen
landen als ENTWURF (Fassung 1, nicht veröffentlicht) -- Monteure sehen nichts, bis das Büro eine
Vorlage geprüft und veröffentlicht hat. Jede Vorlage beginnt mit dem Hinweisfeld "Vor
Veröffentlichung durch eine Fachkraft für Arbeitssicherheit prüfen." (derselbe Satz steht in der
Beschreibung).

upgrade(): legt jede Vorlage an, deren Bezeichnung es noch nicht gibt (eine gleichnamige, vom Büro
selbst angelegte Vorlage bleibt unangetastet, keine Dublette).
downgrade(): entfernt eine Startvorlage nur, solange sie nie veröffentlicht und nie verwendet
wurde (keine Checkliste) -- eine bereits veröffentlichte oder benutzte Vorlage ist inzwischen
Bestand des Betriebs und bleibt stehen. Ein unveröffentlichter, vom Büro bearbeiteter Entwurf
wird dabei mit entfernt (es gibt keine Spalte, die "unverändert" nachweisen könnte).

Die Daten stehen als Konstante STARTER_TEMPLATES auf Modulebene und das Einfügen/Entfernen in
eigenen Funktionen -- tests/test_v309_checklist_starter_templates.py lädt diese Datei direkt
(Muster CLAUDE.md "Eine Migrationsdatei selbst testen") und schickt jede Vorlage durch die echte
Veröffentlichungsprüfung. Rohes SQL ist hier bewusst vermieden (Booleans typisiert über sa.Table,
PostgreSQL-tauglich).

Revision ID: 349704eab07d
Revises: 144a46fc5a97
Create Date: 2026-09-29 11:45:23.382515

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '349704eab07d'
down_revision = '144a46fc5a97'
branch_labels = None
depends_on = None


FASI_SENTENCE = "Vor Veröffentlichung durch eine Fachkraft für Arbeitssicherheit prüfen."


def _fasi_hint() -> dict:
    return {"key": "hinweis_pruefung", "type": "hinweis", "label": FASI_SENTENCE,
            "help_text": "Diesen Hinweis nach der Prüfung löschen, dann veröffentlichen."}


def _f(key, field_type, label, **extra) -> dict:
    return {"key": key, "type": field_type, "label": label, **extra}


def _sig(key, signer_label, label="Unterschrift", **extra) -> dict:
    return _f(key, "unterschrift", label, signer_label=signer_label, **extra)


def _r(operator, title, field_key=None, operand=None, **extra) -> dict:
    return {"operator": operator, "title": title, "field_key": field_key, "operand": operand, **extra}


STARTER_TEMPLATES = [
    {
        "label": "Sicherheitscheck vor Arbeitsbeginn", "contexts": ["auftrag"],
        "fields": [
            _fasi_hint(),
            _f("absturz_gesichert", "ja_nein", "Absturzsicherung vorhanden und geprüft", required=True),
            _f("absturz_art", "auswahl", "Art der Absturzsicherung", required=True, multiple=True, options=[
                ("geruest", "Gerüst"), ("seitenschutz", "Seitenschutz"), ("fangnetz", "Fangnetz"),
                ("psaga", "PSAgA"), ("dachfanggeruest", "Dachfanggerüst")]),
            _f("durchtritt_gesichert", "ja_nein",
               "Nicht durchtrittsichere Bauteile gesichert (z. B. Lichtkuppeln, Lichtbänder, Faserzement)",
               required=True, allow_na=True),
            _f("anschlag_rettung", "ja_nein", "Anschlagpunkte geprüft und Rettung aus PSAgA geklärt", allow_na=True),
            _f("psa_vollstaendig", "ja_nein", "Persönliche Schutzausrüstung vollständig", required=True),
            _f("leitern_geruest", "ja_nein", "Leitern/Gerüst: Sichtprüfung in Ordnung"),
            _f("witterung", "ja_nein", "Witterung für die Arbeiten geeignet", required=True),
            _f("absperrung", "ja_nein", "Gefahrenbereich abgesperrt", allow_na=True),
            _f("freileitungen", "ja_nein", "Freileitungen im Arbeitsbereich"),
            _f("erste_hilfe", "ja_nein", "Erste Hilfe und Notruf geklärt"),
            _f("freigabe", "ja_nein", "Arbeitsbeginn freigegeben", required=True),
            _f("bemerkung", "text", "Bemerkung", multiline=True),
            _f("fotos", "foto", "Fotos", min_count=0, max_count=3),
            _sig("unterschrift_monteur", "Monteur", required=True),
        ],
        "rules": [_r("ist_nein", "Arbeitsbeginn nicht freigegeben: {kontext}", "freigabe", priority="hoch",
                     assignee="sachbearbeiter",
                     description="{ersteller} hat den Arbeitsbeginn nach dem Sicherheitscheck nicht freigegeben.")],
    },
    {
        "label": "Heißarbeiten mit Brandwache", "contexts": ["auftrag"],
        "fields": [
            _fasi_hint(),
            _f("freigabe_auftraggeber", "ja_nein", "Freigabe durch den Auftraggeber liegt vor", allow_na=True),
            _f("arbeitsbereich", "text", "Arbeitsbereich", required=True),
            _f("geraete_ok", "ja_nein", "Gasflasche, Schlauch und Brenner: Sichtprüfung in Ordnung", required=True),
            _f("brennbares", "ja_nein", "Brennbares entfernt oder abgedeckt", required=True),
            _f("loeschmittel", "auswahl", "Löschmittel bereitgestellt", required=True, multiple=True, options=[
                ("pulver", "Feuerlöscher (Pulver)"), ("schaum", "Feuerlöscher (Schaum)"),
                ("co2", "Feuerlöscher (CO2)"), ("loeschdecke", "Löschdecke"), ("wasser", "Wasser (Eimer/Schlauch)")]),
            _f("brandwache_name", "text", "Brandwache (Name)", required=True),
            _f("beginn", "datum_uhrzeit", "Beginn der Heißarbeiten", required=True, prefill_now=True),
            _f("ende", "datum_uhrzeit", "Ende der Heißarbeiten", required=True),
            _f("nachkontrolle_bis", "datum_uhrzeit", "Nachkontrolle bis", required=True,
               help_text="Die Mindestdauer der Nachkontrolle legt der Betrieb fest -- vor der Veröffentlichung hier eintragen."),
            _f("nachkontrolle_ohne_befund", "ja_nein", "Nachkontrolle ohne Befund", required=True),
            _f("fotos", "foto", "Fotos", min_count=0, max_count=5),
            _sig("unterschrift_ausfuehrender", "Ausführender", "Unterschrift Ausführender"),
            _sig("unterschrift_brandwache", "Brandwache", "Unterschrift Brandwache"),
        ],
        "rules": [_r("ist_nein", "Heißarbeiten: Befund bei der Nachkontrolle – {kontext}", "nachkontrolle_ohne_befund",
                     priority="hoch", assignee="sachbearbeiter")],
    },
    {
        "label": "Sicherheitsunterweisung", "contexts": ["betrieb", "auftrag"],
        "fields": [
            _fasi_hint(),
            _f("themen", "auswahl", "Themen", multiple=True, options=[
                ("absturz", "Absturz"), ("heissarbeiten", "Heißarbeiten"), ("gefahrstoffe", "Gefahrstoffe/Asbest"),
                ("leitern_gerueste", "Leitern/Gerüste"), ("witterung", "Witterung"), ("erste_hilfe", "Erste Hilfe"),
                ("sonstiges", "Sonstiges")]),
            _f("inhalt", "text", "Inhalt der Unterweisung", required=True, multiline=True),
            _f("unterweisender", "text", "Unterweisender", required=True),
            _f("zeitpunkt", "datum_uhrzeit", "Datum und Uhrzeit", required=True, prefill_now=True),
            _f("dauer", "zahl", "Dauer", unit="min", decimals=0, min_value=0),
            _sig("teilnehmer", "Teilnehmer", "Unterschriften der Teilnehmer", required=True, multiple=True,
                 min_count=1, max_count=20),
            _sig("unterschrift_unterweisender", "Unterweisender", "Unterschrift Unterweisender"),
        ],
        "rules": [],
    },
    {
        "label": "Gefahrstoff-Verdacht", "contexts": ["auftrag", "objekt"],
        "fields": [
            _fasi_hint(),
            _f("hinweis_einstellen", "hinweis", "Arbeiten im Bereich sofort einstellen",
               help_text="Verdächtiges Material nicht weiter bearbeiten, Bereich sichern, Büro informieren."),
            _f("verdacht", "auswahl", "Verdacht auf", required=True, multiple=True, options=[
                ("asbest", "Asbest/Faserzement"), ("kmf", "alte Mineralwolle (KMF)"),
                ("teer_pak", "teer-/PAK-haltige Abdichtung"), ("sonstiges", "Sonstiges")]),
            _f("fundort", "text", "Fundort/Bauteil", required=True),
            _f("flaeche", "zahl", "Geschätzte Fläche", unit="m²", decimals=1, min_value=0),
            _f("bearbeitet", "ja_nein", "Material wurde bereits bearbeitet", required=True),
            _f("eingestellt", "ja_nein", "Arbeiten eingestellt", required=True),
            _f("abgesperrt", "ja_nein", "Bereich abgesperrt"),
            _f("fotos", "foto", "Fotos", required=True, min_count=1, max_count=10),
            _f("bemerkung", "text", "Bemerkung", multiline=True),
            _sig("unterschrift_monteur", "Monteur", required=True),
        ],
        "rules": [_r("immer", "Gefahrstoff-Verdacht: {kontext}", priority="hoch",
                     description="Gemeldet von {ersteller}. Weiteres Vorgehen klären (Fachfirma, Kunde, Gefährdungsbeurteilung).")],
    },
    {
        "label": "Tagesbericht", "contexts": ["auftrag"],
        "fields": [
            _fasi_hint(),
            _f("datum", "datum", "Datum", required=True, prefill_now=True),
            _f("wetter", "auswahl", "Wetter", options=[
                ("sonnig", "Sonnig"), ("bewoelkt", "Bewölkt"), ("regen", "Regen"), ("schnee", "Schnee"),
                ("wind", "Sturm/Wind"), ("frost", "Frost")]),
            _f("temperatur", "zahl", "Temperatur", unit="°C", decimals=0),
            _f("anwesende", "text", "Anwesende", multiline=True),
            _f("arbeiten", "text", "Ausgeführte Arbeiten", required=True, multiline=True,
               help_text="Arbeitszeiten bitte in der Zeiterfassung buchen, nicht hier."),
            _f("materiallieferungen", "text", "Materiallieferungen", multiline=True),
            _f("anordnungen", "text", "Anordnungen durch Auftraggeber/Bauleitung", multiline=True),
            _f("vorkommnisse", "text", "Besondere Vorkommnisse", multiline=True),
            _f("behinderung", "ja_nein", "Behinderung aufgetreten", required=True),
            _f("fotos", "foto", "Fotos", min_count=0, max_count=10),
            _sig("unterschrift_monteur", "Monteur"),
        ],
        "rules": [
            _r("ist_ja", "Behinderung gemeldet: {kontext}", "behinderung", assignee="sachbearbeiter",
               description="Laut Tagesbericht von {ersteller} ist eine Behinderung aufgetreten. Behinderungsanzeige prüfen."),
            _r("ausgefuellt", "Anordnung auf der Baustelle: {kontext}", "anordnungen", assignee="sachbearbeiter",
               description="Im Tagesbericht von {ersteller} ist eine Anordnung durch Auftraggeber/Bauleitung vermerkt."),
        ],
    },
    {
        "label": "Pflichtfotos verdeckte Arbeiten", "contexts": ["auftrag"],
        "fields": [
            _fasi_hint(),
            _f("bereich", "text", "Bereich", required=True),
            _f("art", "auswahl", "Art", required=True, options=[
                ("dampfsperre", "Dampfsperre"), ("daemmung", "Dämmung"), ("unterdeckbahn", "Unterdeckbahn"),
                ("anschluesse", "Anschlüsse/Durchdringungen"), ("abdichtung_auflast", "Abdichtung unter Auflast"),
                ("befestigung", "Befestigung"), ("sonstiges", "Sonstiges")]),
            _f("fotos", "foto", "Fotos", required=True, min_count=2, max_count=10),
            _f("nach_vorgabe", "ja_nein", "Ausführung nach Vorgabe/Herstellerrichtlinie", required=True),
            _f("abweichung", "text", "Abweichung", multiline=True),
            _sig("unterschrift_monteur", "Monteur"),
        ],
        "rules": [_r("ist_nein", "Abweichung bei verdeckten Arbeiten: {kontext}", "nach_vorgabe",
                     assignee="sachbearbeiter")],
    },
    {
        "label": "Vorher/Nachher", "contexts": ["auftrag", "objekt"],
        "fields": [
            _fasi_hint(),
            _f("bereich", "text", "Bereich", required=True),
            _f("fotos_vorher", "foto", "Fotos vorher", required=True, min_count=1, max_count=10),
            _f("fotos_nachher", "foto", "Fotos nachher", required=True, min_count=1, max_count=10),
            _f("bemerkung", "text", "Bemerkung", multiline=True),
        ],
        "rules": [],
    },
    {
        "label": "Entsorgungsnachweis", "contexts": ["auftrag"],
        "fields": [
            _fasi_hint(),
            _f("abfallart", "auswahl", "Abfallart", required=True,
               help_text="AVV-Schlüssel vor der Veröffentlichung mit dem Entsorger abgleichen.", options=[
                   ("bitumen", "170302 Bitumengemische (ohne Kohlenteer)"),
                   ("teer", "170301* kohlenteerhaltige Bitumengemische"),
                   ("holz", "170201 Holz"), ("metall", "170407 gemischte Metalle"),
                   ("daemmung", "170604 Dämmmaterial (ohne gefährliche Stoffe)"),
                   ("kmf", "170603* Dämmmaterial mit gefährlichen Stoffen (z. B. alte KMF)"),
                   ("asbest", "170605* asbesthaltige Baustoffe"),
                   ("gemischt", "170904 gemischte Bau- und Abbruchabfälle"),
                   ("sonstiges", "Sonstiges (in der Bemerkung angeben)")]),
            _f("menge", "zahl", "Menge", required=True, decimals=2, min_value=0),
            _f("einheit", "auswahl", "Einheit", required=True, options=[
                ("t", "t"), ("m3", "m³"), ("big_bag", "Big Bag")]),
            _f("entsorger", "text", "Entsorger/Annahmestelle", required=True),
            _f("uebergabe", "datum_uhrzeit", "Übergabe", required=True, prefill_now=True),
            _f("beleg_nr", "text", "Wiege-/Lieferschein-Nr."),
            _f("beleg_foto", "foto", "Foto des Belegs", required=True, min_count=1, max_count=5),
            _f("bemerkung", "text", "Bemerkung", multiline=True),
            _sig("unterschrift_monteur", "Monteur"),
        ],
        "rules": [],
    },
    {
        "label": "Aufmaß einfach", "contexts": ["auftrag", "objekt"],
        "fields": [
            _fasi_hint(),
            _f("bereich", "text", "Bereich/Position", required=True,
               help_text="Ein Bereich je Checkliste -- für weitere Bereiche eine neue Checkliste anlegen."),
            _f("laenge", "zahl", "Länge", unit="m", decimals=2, min_value=0),
            _f("breite", "zahl", "Breite", unit="m", decimals=2, min_value=0),
            _f("flaeche", "zahl", "Fläche", unit="m²", decimals=2, min_value=0, help_text="Von Hand gerechnet."),
            _f("stueck", "zahl", "Stück", unit="Stk", decimals=0, min_value=0),
            _f("skizze", "foto", "Skizze/Foto", min_count=0, max_count=5),
            _f("bemerkung", "text", "Bemerkung", multiline=True),
        ],
        "rules": [],
    },
    {
        "label": "Geräte-Sichtprüfung", "contexts": ["betriebsmittel"], "field_readable": True,
        "description_extra": "Keine Prüfung nach DGUV/UVV -- die Prüffristen des Geräts bleiben unverändert.",
        "fields": [
            _fasi_hint(),
            _f("gehaeuse", "ja_nein", "Gehäuse/Rahmen unbeschädigt", required=True),
            _f("kabel_schlaeuche", "ja_nein", "Kabel, Stecker, Schläuche in Ordnung", required=True, allow_na=True),
            _f("schutzeinrichtungen", "ja_nein", "Schutzeinrichtungen funktionsfähig", allow_na=True),
            _f("pruefplakette", "ja_nein", "Prüfplakette gültig", allow_na=True),
            _f("funktionstest", "ja_nein", "Funktionstest in Ordnung", required=True),
            _f("betriebsstunden", "zahl", "Betriebsstunden", unit="h", decimals=1, min_value=0),
            _f("einsatzbereit", "ja_nein", "Gerät einsatzbereit", required=True),
            _f("bemerkung", "text", "Bemerkung", multiline=True),
            _f("fotos", "foto", "Foto", min_count=0, max_count=5),
            _sig("unterschrift_monteur", "Monteur"),
        ],
        "rules": [_r("ist_nein", "Gerät nicht einsatzbereit: {kontext}", "einsatzbereit",
                     description="Gemeldet von {ersteller} bei der Sichtprüfung.")],
    },
    {
        "label": "Schadensmeldung Gerät", "contexts": ["betriebsmittel"], "field_readable": True,
        "fields": [
            _fasi_hint(),
            _f("schadensart", "auswahl", "Schadensart", required=True, options=[
                ("mechanisch", "mechanisch"), ("elektrisch", "elektrisch"), ("verschleiss", "Verschleiß"),
                ("fehlt", "fehlt/verloren"), ("sonstiges", "Sonstiges")]),
            _f("beschreibung", "text", "Beschreibung", required=True, multiline=True),
            _f("festgestellt", "datum_uhrzeit", "Festgestellt am", required=True, prefill_now=True),
            _f("einsatzbereit", "ja_nein", "Gerät noch einsatzbereit", required=True),
            _f("gekennzeichnet", "ja_nein", "Außer Betrieb gekennzeichnet"),
            _f("fotos", "foto", "Fotos", required=True, min_count=1, max_count=10),
            _sig("unterschrift_monteur", "Monteur"),
        ],
        "rules": [
            _r("immer", "Geräteschaden gemeldet: {kontext}", description="Gemeldet von {ersteller}."),
            _r("ist_nein", "Gerät nicht einsatzbereit: {kontext}", "einsatzbereit", priority="hoch",
               description="Laut Schadensmeldung von {ersteller} nicht mehr einsatzbereit."),
        ],
    },
    {
        "label": "Abfahrtkontrolle", "contexts": ["betriebsmittel"],
        "fields": [
            _fasi_hint(),
            _f("kilometerstand", "zahl", "Kilometerstand", required=True, unit="km", decimals=0, min_value=0),
            _f("beleuchtung", "ja_nein", "Beleuchtung in Ordnung", required=True),
            _f("reifen", "ja_nein", "Reifen in Ordnung", required=True),
            _f("ladung", "ja_nein", "Ladung gesichert", required=True),
            _f("anhaenger", "ja_nein", "Anhänger gesichert", allow_na=True),
            _f("bordausstattung", "ja_nein", "Warnweste, Verbandkasten und Warndreieck an Bord"),
            _f("werkzeug", "ja_nein", "Werkzeug vollständig"),
            _f("schaeden", "ja_nein", "Schäden festgestellt", required=True),
            _f("fotos", "foto", "Foto", min_count=0, max_count=5),
            _sig("unterschrift_fahrer", "Fahrer"),
        ],
        "rules": [_r("ist_ja", "Schaden bei der Abfahrtkontrolle: {kontext}", "schaeden",
                     description="Gemeldet von {ersteller}.")],
    },
    {
        "label": "Nachtragsmeldung", "contexts": ["auftrag"],
        "fields": [
            _fasi_hint(),
            _f("hinweis_keine_zusage", "hinweis", "Keine Preis- oder Terminzusage an den Kunden",
               help_text="Nachträge bewertet und bestätigt ausschließlich das Büro."),
            _f("art", "auswahl", "Art", required=True, options=[
                ("zusatzleistung", "Zusatzleistung auf Kundenwunsch"), ("geaenderte_ausfuehrung", "Geänderte Ausführung"),
                ("befund", "Unvorhergesehener Befund"), ("mengenmehrung", "Mengenmehrung")]),
            _f("beschreibung", "text", "Beschreibung", required=True, multiline=True),
            _f("menge", "zahl", "Menge", decimals=2, min_value=0),
            _f("einheit", "text", "Einheit"),
            _f("zeitaufwand", "zahl", "Geschätzter Zeitaufwand", unit="h", decimals=1, min_value=0),
            _f("material", "text", "Material", multiline=True),
            _f("angeordnet_durch", "text", "Angeordnet durch"),
            _f("bereits_ausgefuehrt", "ja_nein", "Bereits ausgeführt", required=True),
            _f("fotos", "foto", "Fotos", required=True, min_count=1, max_count=10),
            _sig("unterschrift_kunde", "Kunde", "Unterschrift Kunde (optional)"),
        ],
        "rules": [_r("immer", "Nachtrag prüfen: {kontext}", assignee="sachbearbeiter",
                     description="{ersteller} hat einen möglichen Nachtrag gemeldet. Bewerten, ggf. Nachtragsangebot erstellen.")],
    },
]

_CONTEXT_COLUMNS = {"auftrag": "context_order", "objekt": "context_property",
                    "betriebsmittel": "context_asset", "betrieb": "context_company"}

# Eigene, von app.models unabhängige Tabellendefinitionen (eine Migration darf sich nie auf den
# jeweils aktuellen Modellstand verlassen); der Primärschlüssel ist angegeben, damit
# inserted_primary_key unter SQLite UND PostgreSQL die neue ID liefert.
_META = sa.MetaData()
templates_t = sa.Table(
    "checklist_templates", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("label", sa.String), sa.Column("description", sa.Text),
    sa.Column("purpose", sa.String), sa.Column("context_order", sa.Boolean), sa.Column("context_property", sa.Boolean),
    sa.Column("context_asset", sa.Boolean), sa.Column("context_company", sa.Boolean),
    sa.Column("field_readable", sa.Boolean), sa.Column("sort_order", sa.Integer), sa.Column("archived", sa.Boolean),
    sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime),
)
versions_t = sa.Table(
    "checklist_template_versions", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("template_id", sa.Integer), sa.Column("version_no", sa.Integer),
    sa.Column("status", sa.String), sa.Column("published_at", sa.DateTime),
    sa.Column("published_by_user_id", sa.Integer), sa.Column("created_at", sa.DateTime),
)
fields_t = sa.Table(
    "checklist_template_fields", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.Integer), sa.Column("field_key", sa.String),
    sa.Column("sort_order", sa.Integer), sa.Column("group_name", sa.String), sa.Column("field_type", sa.String),
    sa.Column("label", sa.String), sa.Column("help_text", sa.Text), sa.Column("required", sa.Boolean),
    sa.Column("allow_na", sa.Boolean), sa.Column("multiline", sa.Boolean), sa.Column("multiple", sa.Boolean),
    sa.Column("unit", sa.String), sa.Column("min_value", sa.Numeric(18, 4)), sa.Column("max_value", sa.Numeric(18, 4)),
    sa.Column("decimals", sa.Integer), sa.Column("min_count", sa.Integer), sa.Column("max_count", sa.Integer),
    sa.Column("prefill_now", sa.Boolean), sa.Column("signer_label", sa.String), sa.Column("is_system", sa.Boolean),
)
options_t = sa.Table(
    "checklist_template_field_options", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("field_id", sa.Integer), sa.Column("option_key", sa.String),
    sa.Column("label", sa.String), sa.Column("sort_order", sa.Integer),
)
rules_t = sa.Table(
    "checklist_template_rules", _META,
    sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.Integer), sa.Column("field_key", sa.String),
    sa.Column("operator", sa.String), sa.Column("operand", sa.String), sa.Column("task_title", sa.String),
    sa.Column("task_description", sa.Text), sa.Column("task_priority", sa.String), sa.Column("due_in_days", sa.Integer),
    sa.Column("assignee_mode", sa.String), sa.Column("min_visible_role", sa.String), sa.Column("sort_order", sa.Integer),
)
checklists_t = sa.Table("checklists", _META, sa.Column("id", sa.Integer, primary_key=True), sa.Column("template_id", sa.Integer))


def _description(spec: dict) -> str:
    return " ".join(x for x in (FASI_SENTENCE, "Startvorlage (Entwurf).", spec.get("description_extra")) if x)


def insert_starter_templates(bind, now: datetime | None = None) -> list[str]:
    """Legt jede Startvorlage an, deren Bezeichnung noch nicht existiert. Liefert die angelegten
    Bezeichnungen."""
    now = now or datetime.utcnow()
    existing = set(bind.execute(sa.select(templates_t.c.label)).scalars())
    created = []
    for position, spec in enumerate(STARTER_TEMPLATES, start=1):
        if spec["label"] in existing:
            continue
        contexts = set(spec["contexts"])
        template_id = bind.execute(templates_t.insert().values(
            label=spec["label"], description=_description(spec), purpose="allgemein",
            **{column: key in contexts for key, column in _CONTEXT_COLUMNS.items()},
            field_readable=bool(spec.get("field_readable")), sort_order=position * 10, archived=False,
            created_at=now, updated_at=now,
        )).inserted_primary_key[0]
        version_id = bind.execute(versions_t.insert().values(
            template_id=template_id, version_no=1, status="entwurf", published_at=None,
            published_by_user_id=None, created_at=now,
        )).inserted_primary_key[0]
        for index, field in enumerate(spec["fields"], start=1):
            field_type = field["type"]
            multiple = bool(field.get("multiple"))
            max_count = field.get("max_count")
            if field_type == "unterschrift" and not multiple:
                max_count = 1  # wie _normalize_field(): Einzelunterschrift
            field_id = bind.execute(fields_t.insert().values(
                version_id=version_id, field_key=field["key"], sort_order=index * 10, group_name=field.get("group"),
                field_type=field_type, label=field["label"], help_text=field.get("help_text"),
                required=bool(field.get("required")) and field_type != "hinweis",
                allow_na=bool(field.get("allow_na")), multiline=bool(field.get("multiline")), multiple=multiple,
                unit=field.get("unit"), min_value=field.get("min_value"), max_value=field.get("max_value"),
                decimals=field.get("decimals"), min_count=field.get("min_count"), max_count=max_count,
                prefill_now=bool(field.get("prefill_now")), signer_label=field.get("signer_label"), is_system=False,
            )).inserted_primary_key[0]
            for option_index, (option_key, option_label) in enumerate(field.get("options", []), start=1):
                bind.execute(options_t.insert().values(
                    field_id=field_id, option_key=option_key, label=option_label, sort_order=option_index * 10,
                ))
        for index, rule in enumerate(spec["rules"], start=1):
            bind.execute(rules_t.insert().values(
                version_id=version_id, field_key=rule["field_key"], operator=rule["operator"], operand=rule["operand"],
                task_title=rule["title"], task_description=rule.get("description"),
                task_priority=rule.get("priority", "normal"), due_in_days=rule.get("due_in_days"),
                assignee_mode=rule.get("assignee", "rolle"), min_visible_role=rule.get("role", "buero_auftrag"),
                sort_order=index * 10,
            ))
        created.append(spec["label"])
    return created


def remove_starter_templates(bind) -> list[str]:
    """Entfernt Startvorlagen, die nie veröffentlicht und nie verwendet wurden. Liefert die
    entfernten Bezeichnungen."""
    labels = [spec["label"] for spec in STARTER_TEMPLATES]
    removed = []
    for template_id, label in bind.execute(
        sa.select(templates_t.c.id, templates_t.c.label).where(templates_t.c.label.in_(labels))
    ).all():
        statuses = set(bind.execute(sa.select(versions_t.c.status).where(versions_t.c.template_id == template_id)).scalars())
        used = bind.execute(sa.select(checklists_t.c.id).where(checklists_t.c.template_id == template_id).limit(1)).first()
        if statuses != {"entwurf"} or used is not None:
            continue
        version_ids = list(bind.execute(sa.select(versions_t.c.id).where(versions_t.c.template_id == template_id)).scalars())
        field_ids = list(bind.execute(sa.select(fields_t.c.id).where(fields_t.c.version_id.in_(version_ids))).scalars())
        if field_ids:
            bind.execute(options_t.delete().where(options_t.c.field_id.in_(field_ids)))
        bind.execute(rules_t.delete().where(rules_t.c.version_id.in_(version_ids)))
        bind.execute(fields_t.delete().where(fields_t.c.version_id.in_(version_ids)))
        bind.execute(versions_t.delete().where(versions_t.c.template_id == template_id))
        bind.execute(templates_t.delete().where(templates_t.c.id == template_id))
        removed.append(label)
    return removed


def upgrade() -> None:
    insert_starter_templates(op.get_bind())


def downgrade() -> None:
    remove_starter_templates(op.get_bind())
