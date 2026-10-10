import logging
import re

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .grunddaten import GrunddatenFehlen, einzelzeile
from .berlin_time import berlin_now
from .models import (
    CustomerProfile, GeneralSettings, Inquiry, Invoice, NumberSequence, Project, Quote, Order, Reminder,
)

logger = logging.getLogger(__name__)

DEFAULT_SEQUENCES = {
    "customer": {"label": "Kundennummer", "format": "K-{YYYY}-{NNNN}", "start": 1, "reset_yearly": True},
    "inquiry": {"label": "Anfragenummer", "format": "ANF-{YYYY}-{NNNN}", "start": 1, "reset_yearly": True},
    "project": {"label": "Projektnummer", "format": "P-{YYYY}-{NNNN}", "start": 1, "reset_yearly": True},
    "quote": {"label": "Angebotsnummer", "format": "A-{YYYY}-{NNNN}", "start": 1, "reset_yearly": True},
    "invoice": {"label": "Rechnungsnummer", "format": "R-{YYYY}-{NNNN}", "start": 1, "reset_yearly": True},
    "reminder": {"label": "Mahnungsnummer", "format": "M-{YYYY}-{NNNN}", "start": 1, "reset_yearly": True},
    "order": {"label": "Auftragsnummer", "format": "AUF-{YYYY}-{NNNN}", "start": 1, "reset_yearly": True},
}


def load_general_settings(db: Session) -> GeneralSettings:
    """Nur lesen -- die Zeile legt app.grunddaten.anlegen() beim Start an (seit 1.8.42)."""
    return einzelzeile(db, GeneralSettings)


def get_accent_color(db: Session) -> str:
    return load_general_settings(db).accent_color


def set_accent_color(db: Session, accent_color: str) -> str:
    general = load_general_settings(db)
    general.accent_color = accent_color
    db.commit()
    return general.accent_color


def validate_number_pattern(pattern: str) -> None:
    if not pattern or not re.search(r"\{N+\}", pattern):
        raise ValueError("Das Nummernformat muss einen Platzhalter wie {NNNN} enthalten.")
    if len(re.findall(r"\{N+\}", pattern)) != 1:
        raise ValueError("Das Nummernformat darf genau einen laufenden Nummern-Platzhalter enthalten.")


def format_sequence_number(pattern: str, value: int, year: int | None = None) -> str:
    validate_number_pattern(pattern)
    year = year or berlin_now().year
    result = pattern.replace("{YYYY}", str(year)).replace("{YY}", str(year)[-2:])
    match = re.search(r"\{(N+)\}", result)
    width = len(match.group(1)) if match else 1
    return re.sub(r"\{N+\}", str(value).zfill(width), result, count=1)


def _existing_column(sequence_key: str):
    """Spalte mit den vergebenen Nummern je Nummernkreis -- seit 1.8.74 auch Rechnung und Mahnung (vorher fehlten sie: wer
    "nächste Nummer" zurücksetzte, bekam dort eine schon vergebene Nummer)."""
    mapping = {
        "customer": CustomerProfile.customer_number,
        "inquiry": Inquiry.inquiry_number,
        "project": Project.project_number,
        "quote": Quote.quote_number,
        "order": Order.order_number,
        "invoice": Invoice.invoice_number,
        "reminder": Reminder.reminder_number,
    }
    return mapping.get(sequence_key)


class SequenceConflict(ValueError):
    """Speichern eines Nummernkreises abgelehnt -- der Router antwortet 409 mit dem Text (seit 1.8.76 gemeinsame Oberklasse)."""


class NumberBelowExisting(SequenceConflict):
    """Die nächste Nummer läge auf oder unter einer vergebenen desselben Formats und Jahres (seit 1.8.74) -- der Router
    antwortet 409 mit der höchsten vergebenen."""


class YearlyResetWithoutYear(SequenceConflict):
    """Format ohne Jahr mit "Jahreswechsel: auf Startnummer zurück" (seit 1.8.76) -- die Nummern des neuen Jahres wären die des
    alten; die Vergabe spränge danach über die vergebenen (mit Warnung im Log, issue_number())."""


def has_year(format_pattern: str) -> bool:
    return "{YYYY}" in format_pattern or "{YY}" in format_pattern


def highest_existing(db: Session, sequence_key: str, format_pattern: str) -> tuple[int, str] | None:
    """(laufende Nummer, Nummer) der höchsten vergebenen Nummer desselben Formats im laufenden Jahr (Berlin) -- ein Format
    ohne Jahr vergleicht mit allen Nummern dieses Formats. None, wenn es keine gibt."""
    column = _existing_column(sequence_key)
    if column is None:
        return None
    regex = _pattern_regex(format_pattern, berlin_now().year)
    best = None
    for value in db.scalars(select(column).where(column.is_not(None))):
        match = regex.fullmatch(value)
        if match and (best is None or int(match.group(1)) > best[0]):
            best = (int(match.group(1)), value)
    return best


def _pattern_regex(pattern: str, year: int) -> re.Pattern:
    token = re.search(r"\{N+\}", pattern)
    if not token:
        raise ValueError("Ungültiges Nummernformat.")
    before = pattern[:token.start()].replace("{YYYY}", str(year)).replace("{YY}", str(year)[-2:])
    after = pattern[token.end():].replace("{YYYY}", str(year)).replace("{YY}", str(year)[-2:])
    return re.compile(rf"^{re.escape(before)}(\d+){re.escape(after)}$")


def _sync_from_existing(db: Session, sequence: NumberSequence) -> None:
    """Nur noch beim Anlegen eines Nummernkreises (_create_sequence()): die nächste Nummer über die höchste vergebene. Die
    Vergabe rechnet seit 1.8.76 selbst (issue_number(), mit Warnung beim Überspringen), die Vorschau nur lesend; die
    Einstellungen lehnen eine nächste Nummer auf oder unter einer vergebenen ab (update_sequence(), seit 1.8.74)."""
    best = highest_existing(db, sequence.sequence_key, sequence.format_pattern)
    if best is not None and best[0] >= sequence.next_value:
        sequence.next_value = best[0] + 1


def load_sequence(db: Session, sequence_key: str) -> NumberSequence:
    """Nur lesen -- die Nummernkreise legt app.grunddaten.anlegen() beim Start an (seit 1.8.42)."""
    if sequence_key not in DEFAULT_SEQUENCES:
        raise KeyError(f"Unbekannter Nummernkreis: {sequence_key}")
    sequence = db.scalar(select(NumberSequence).where(NumberSequence.sequence_key == sequence_key))
    if sequence is None:
        raise GrunddatenFehlen(f"number_sequences: Nummernkreis {sequence_key} fehlt -- app.grunddaten.anlegen() "
                               "ist beim Start nicht gelaufen oder gescheitert (siehe Log).")
    return sequence


def load_sequences(db: Session) -> list[NumberSequence]:
    return [load_sequence(db, key) for key in DEFAULT_SEQUENCES]


def _create_sequence(db: Session, sequence_key: str) -> None:
    """Gegen einen gleichzeitigen ersten Zugriff abgesichert (siehe CLAUDE.md "Self-Seeding
    gegen gleichzeitigen Zugriff absichern"): der Anlegeversuch läuft in einem SAVEPOINT --
    kollidiert er mit der UNIQUE-Verletzung auf sequence_key (ein anderer Prozess war
    zwischen dem obigen SELECT und hier schneller), gilt das als "schon angelegt".
    Ein neuer Nummernkreis übernimmt die höchste schon vergebene Nummer (_sync_from_existing())."""
    if db.scalar(select(NumberSequence.id).where(NumberSequence.sequence_key == sequence_key)) is not None:
        return
    default = DEFAULT_SEQUENCES[sequence_key]
    year = berlin_now().year
    try:
        with db.begin_nested():
            sequence = NumberSequence(
                sequence_key=sequence_key,
                label=default["label"],
                format_pattern=default["format"],
                start_value=default["start"],
                next_value=default["start"],
                reset_yearly=default["reset_yearly"],
                last_year=year,
            )
            db.add(sequence)
            db.flush()
    except IntegrityError:
        return
    _sync_from_existing(db, sequence)
    db.flush()


def ensure_default_sequences(db: Session) -> None:
    """Anlegeschritt von app.grunddaten.anlegen() (seit 1.8.42): flush, kein commit -- ein Commit gäbe dort
    die Sperre frei. Lesepfade rufen das nicht mehr auf."""
    for key in DEFAULT_SEQUENCES:
        _create_sequence(db, key)


def _planned_value(sequence: NumberSequence, year: int) -> int:
    """Nächste Nummer laut Nummernkreis -- nach dem Jahreswechsel die Startnummer (reset_yearly)."""
    if sequence.reset_yearly and sequence.last_year is not None and sequence.last_year != year:
        return sequence.start_value
    return sequence.next_value


def _free_value(db: Session, sequence: NumberSequence, planned: int) -> int:
    """planned, oder -- liegt es auf oder unter einer vergebenen Nummer desselben Formats und Jahres -- die nächste darüber."""
    best = highest_existing(db, sequence.sequence_key, sequence.format_pattern)
    return best[0] + 1 if best is not None and best[0] >= planned else planned


def preview_number(db: Session, sequence_key: str) -> str:
    """Nur zur Anzeige ("nächste Nummer" in Formularen und Einstellungen), ohne Sperre und ohne Hochzählen -- seit 1.8.73
    vergibt nichts mehr hierüber (tests/test_v376_nummernkreise.py prüft die Aufrufer). Seit 1.8.76 schreibt sie auch nichts:
    Jahreswechsel und Abgleich mit den vergebenen Nummern werden nur ausgerechnet. Vorher setzte sie beides am Nummernkreis,
    ohne Sperre, und die GET-Routen der Einstellungen committeten es -- mit einem veralteten Stand konnte das die nächste
    Nummer unter eine gelöschte zurücksetzen (tests/test_v379_nummern_anzeige.py)."""
    sequence = load_sequence(db, sequence_key)
    return format_sequence_number(sequence.format_pattern, effective_next_value(db, sequence))


def effective_next_value(db: Session, sequence: NumberSequence) -> int:
    """Die laufende Nummer, die die nächste Vergabe zöge -- Jahreswechsel und Abgleich ausgerechnet, nichts geschrieben (seit
    1.8.76). Die Einstellungen zeigen sie als "Nächste Nr.": der gespeicherte Wert stammt nach dem Jahreswechsel bis zur ersten
    Vergabe noch aus dem alten Jahr -- wer die Zeile dann unverändert speicherte, hätte den Jahreswechsel überschrieben."""
    return _free_value(db, sequence, _planned_value(sequence, berlin_now().year))


def _lock_sequence(db: Session, sequence_key: str) -> NumberSequence:
    """Sperrt die Zeile des Nummernkreises bis zum Commit und lädt sie danach frisch (seit 1.8.73, Nebenbefund 1 aus
    1.8.72: zwei gleichzeitig festgeschriebene Rechnungen verschiedener Aufträge bekamen dieselbe Nummer -- beide lasen
    next_value, bevor die erste committet hatte). Gesperrt wird mit einem UPDATE ohne Änderung statt SELECT ... FOR UPDATE:
    unter PostgreSQL hält es die Zeilensperre, unter SQLite die Schreibsperre der Datenbank -- auch dort wartet der zweite,
    bis der erste committet hat. populate_existing: ein vorher geladener Nummernkreis bliebe sonst auf dem alten Stand."""
    if sequence_key not in DEFAULT_SEQUENCES:
        raise KeyError(f"Unbekannter Nummernkreis: {sequence_key}")
    db.execute(
        update(NumberSequence).where(NumberSequence.sequence_key == sequence_key)
        .values(next_value=NumberSequence.next_value).execution_options(synchronize_session=False)
    )
    sequence = db.scalar(select(NumberSequence).where(NumberSequence.sequence_key == sequence_key)
                         .execution_options(populate_existing=True))
    return sequence if sequence is not None else load_sequence(db, sequence_key)  # fehlt: GrunddatenFehlen


def issue_number(db: Session, sequence_key: str) -> str:
    """Vergibt die nächste Nummer des Nummernkreises -- seit 1.8.73 unter der Sperre seiner Zeile (_lock_sequence()) bis
    zum Commit des Aufrufers: Jahreswechsel, Abgleich mit den vorhandenen Nummern und Hochzählen laufen für jeden
    Nummernkreis nacheinander. Alle sieben Nummernkreise vergeben hierüber (Kunde, Anfrage, Projekt und Angebot bis 1.8.72
    über preview_number() ohne Hochzählen -- gleichzeitig angelegt, scheiterte der zweite an der Eindeutigkeit). Wird der
    Aufrufer zurückgerollt, ist auch die Nummer nicht verbraucht.

    Liegt die nächste Nummer auf oder unter einer vergebenen (Nummer von Hand, Import, Datenbank, Format ohne Jahr mit
    Jahreswechsel), springt die Vergabe darüber -- seit 1.8.76 nicht still: logger.warning mit Nummernkreis und übersprungenen
    Nummern (Festlegung 1.8.74 Nr. 2, geändert; nur Nummern, Regel 18)."""
    sequence = _lock_sequence(db, sequence_key)
    year = berlin_now().year
    planned = _planned_value(sequence, year)
    value = _free_value(db, sequence, planned)

    def number(v: int) -> str:
        return format_sequence_number(sequence.format_pattern, v, year)

    if value > planned:
        skipped = number(planned) if value - 1 == planned else f"{number(planned)} bis {number(value - 1)}"
        logger.warning("Nummernkreis %s: nächste Nummer %s lag auf oder unter einer vergebenen -- übersprungen: %s, "
                       "vergeben wird %s.", sequence_key, number(planned), skipped, number(value))
    sequence.last_year = year
    sequence.next_value = value + 1
    db.flush()
    return number(value)


def update_sequence(
    db: Session, sequence_key: str, *, format_pattern: str, start_value: int,
    next_value: int, reset_yearly: bool,
) -> NumberSequence:
    validate_number_pattern(format_pattern)
    if start_value < 0 or next_value < 0:
        raise ValueError("Start- und nächste Nummer müssen größer oder gleich 0 sein.")
    # Seit 1.8.76: ohne Jahr im Format kein Zurücksetzen zum Jahreswechsel -- die Nummern des neuen Jahres wären die des alten.
    if reset_yearly and not has_year(format_pattern):
        raise YearlyResetWithoutYear(
            "Ein Format ohne Jahr ({YYYY} oder {YY}) kann zum Jahreswechsel nicht auf die Startnummer zurückgehen -- die Nummern "
            "des neuen Jahres wären dieselben wie die des alten. Bitte das Jahr ins Format aufnehmen oder „fortlaufend“ wählen.")
    sequence = load_sequence(db, sequence_key)
    # Seit 1.8.74: nicht auf oder unter eine vergebene Nummer desselben Formats und Jahres -- ablehnen mit der höchsten
    # vergebenen, statt (wie bis 1.8.73 die Vorschau danach) still darüber zu springen; bei Rechnung und Mahnung entstand
    # vorher sogar eine Dublette.
    best = highest_existing(db, sequence_key, format_pattern.strip())
    if best is not None and next_value <= best[0]:
        raise NumberBelowExisting(f"Die nächste Nummer darf nicht auf oder unter einer vergebenen liegen: höchste vergebene "
                                  f"Nummer in diesem Format ist {best[1]} -- nächste Nummer mindestens {best[0] + 1}.")
    sequence.format_pattern = format_pattern.strip()
    sequence.start_value = start_value
    sequence.next_value = next_value
    sequence.reset_yearly = reset_yearly
    sequence.last_year = berlin_now().year
    db.commit()
    db.refresh(sequence)
    return sequence
