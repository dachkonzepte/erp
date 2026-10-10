import re

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .grunddaten import GrunddatenFehlen, einzelzeile
from .berlin_time import berlin_now
from .models import (
    CustomerProfile, GeneralSettings, Inquiry, NumberSequence, Project, Quote, Order,
)

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
    mapping = {
        "customer": CustomerProfile.customer_number,
        "inquiry": Inquiry.inquiry_number,
        "project": Project.project_number,
        "quote": Quote.quote_number,
        "order": Order.order_number,
    }
    return mapping.get(sequence_key)


def _pattern_regex(pattern: str, year: int) -> re.Pattern:
    token = re.search(r"\{N+\}", pattern)
    if not token:
        raise ValueError("Ungültiges Nummernformat.")
    before = pattern[:token.start()].replace("{YYYY}", str(year)).replace("{YY}", str(year)[-2:])
    after = pattern[token.end():].replace("{YYYY}", str(year)).replace("{YY}", str(year)[-2:])
    return re.compile(rf"^{re.escape(before)}(\d+){re.escape(after)}$")


def _sync_from_existing(db: Session, sequence: NumberSequence) -> None:
    column = _existing_column(sequence.sequence_key)
    if column is None:
        return
    year = berlin_now().year
    regex = _pattern_regex(sequence.format_pattern, year)
    highest = 0
    for value in db.scalars(select(column)).all():
        match = regex.fullmatch(value or "")
        if match:
            highest = max(highest, int(match.group(1)))
    if highest >= sequence.next_value:
        sequence.next_value = highest + 1


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


def _apply_year_reset(sequence: NumberSequence) -> None:
    year = berlin_now().year
    if sequence.reset_yearly and sequence.last_year is not None and sequence.last_year != year:
        sequence.next_value = sequence.start_value
    sequence.last_year = year


def preview_number(db: Session, sequence_key: str) -> str:
    """Nur zur Anzeige ("nächste Nummer" in Formularen und Einstellungen), ohne Sperre und ohne Hochzählen -- seit 1.8.73
    vergibt nichts mehr hierüber (tests/test_v376_nummernkreise.py prüft die Aufrufer)."""
    sequence = load_sequence(db, sequence_key)
    _apply_year_reset(sequence)
    _sync_from_existing(db, sequence)
    db.flush()
    return format_sequence_number(sequence.format_pattern, sequence.next_value)


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
    Aufrufer zurückgerollt, ist auch die Nummer nicht verbraucht."""
    sequence = _lock_sequence(db, sequence_key)
    _apply_year_reset(sequence)
    _sync_from_existing(db, sequence)
    value = format_sequence_number(sequence.format_pattern, sequence.next_value)
    sequence.next_value += 1
    db.flush()
    return value


def update_sequence(
    db: Session, sequence_key: str, *, format_pattern: str, start_value: int,
    next_value: int, reset_yearly: bool,
) -> NumberSequence:
    validate_number_pattern(format_pattern)
    if start_value < 0 or next_value < 0:
        raise ValueError("Start- und nächste Nummer müssen größer oder gleich 0 sein.")
    sequence = load_sequence(db, sequence_key)
    sequence.format_pattern = format_pattern.strip()
    sequence.start_value = start_value
    sequence.next_value = next_value
    sequence.reset_yearly = reset_yearly
    sequence.last_year = berlin_now().year
    db.commit()
    db.refresh(sequence)
    return sequence
