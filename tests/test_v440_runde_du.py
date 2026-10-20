"""Runde „Du“ (1.8.157 ff., Vorgabe vom 20.10.2026).

    3  „… keinem Mitarbeiter zugeordnet“: eine gemeinsame Meldung (app/meldungen.py::KEIN_MITARBEITER) statt neun Fassungen (1.8.159)
    4  Kundentexte bleiben beim Sie (Verzeichnis KUNDENTEXTE, auch in echten PDFs), ein Kundentext-Merkmal nur im Verzeichnis,
       außerhalb keine Sie-Anrede -- das hält auch Punkt 2 (Oberfläche per Du, 1.8.158) fest (1.8.160)
"""

import ast
import re
from pathlib import Path

import pytest

from tests.test_v305_checklist_filling import world  # noqa: F401 -- Fixture
from tests.test_v341_behinderungsanzeige import bworld  # noqa: F401 -- Fixture
from tests.test_v343_behinderungsanzeige_versand import nworld  # noqa: F401 -- Fixture
from tests.test_v346_bedenkenanzeige import kworld  # noqa: F401 -- Fixture
from tests.test_v347_bedenkenanzeige_versand import mworld  # noqa: F401 -- Fixture

ROOT = Path(__file__).resolve().parents[1]
MELDUNG_MUSTER = re.compile(r"(keinem|mit keinem) Mitarbeiter (zugeordnet|verknüpft)")


# ---------------------------------------------------------------------------
# 3. Eine Meldung „… keinem Mitarbeiter zugeordnet“
# ---------------------------------------------------------------------------

def _zeichenketten(pfad: Path):
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    docstrings = {id(k.body[0].value) for k in ast.walk(baum)
                  if isinstance(k, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and k.body
                  and isinstance(k.body[0], ast.Expr) and isinstance(k.body[0].value, ast.Constant)}
    for k in ast.walk(baum):
        if isinstance(k, ast.Constant) and isinstance(k.value, str) and id(k) not in docstrings:
            yield k.lineno, k.value


def test_keine_eigene_fassung_der_meldung():
    """Bis 1.8.158 stand die Meldung in neun Fassungen an 20 Stellen (14 im Server, 6 in Vorlagen). Seit 1.8.159 nur noch als
    KEIN_MITARBEITER in app/meldungen.py; die Vorlagen nehmen den Jinja-Global kein_mitarbeiter."""
    from app.meldungen import KEIN_MITARBEITER
    from tests.test_v334_auswahl_restfaelle import TEMPLATES
    from tests.vorlagen_js import alle_vorlagen

    funde = [f"{p.relative_to(ROOT)}:{nr}" for p in sorted((ROOT / "app").rglob("*.py")) if p.name != "meldungen.py"
             for nr, s in _zeichenketten(p) if MELDUNG_MUSTER.search(s)]
    for name in alle_vorlagen():
        text = re.sub(r"\{#.*?#\}", "", (TEMPLATES / name).read_text(encoding="utf-8"), flags=re.S)
        funde += [f"app/templates/{name}" for _ in MELDUNG_MUSTER.finditer(text)]
    assert funde == []
    assert KEIN_MITARBEITER == ("Dein Konto ist keinem Mitarbeiter zugeordnet. Ein Administrator kann das unter Einstellungen → "
                                "Benutzer und Zugriff ändern.")
    nutzer = {name for name in alle_vorlagen() if "{{ kein_mitarbeiter|tojson }}" in (TEMPLATES / name).read_text(encoding="utf-8")}
    assert nutzer == {"dashboard.html", "field_timesheet.html", "service_reports.html", "time_backoffice.html", "time_tracking.html",
                      "time_tracking_field.html"}


@pytest.mark.parametrize("adresse,rolle", [("/time-tracking", "buero_finanzen"), ("/time-tracking", "field"), ("/", "buero_auftrag"),
                                           ("/mobil/stundenzettel", "field"), ("/time-backoffice", "buero_finanzen")])
def test_seiten_zeigen_die_gemeinsame_meldung(threaded_db_session, router_test_client, adresse, rolle):
    """Die gezeichnete Seite trägt genau die Meldung aus app/meldungen.py (als JSON-Zeichenkette im Skript)."""
    from jinja2.utils import htmlsafe_json_dumps

    from app.meldungen import KEIN_MITARBEITER
    from app.routers.pages import router as pages_router

    antwort = router_test_client(threaded_db_session, pages_router, role=rolle).get(adresse, follow_redirects=False)
    assert antwort.status_code == 200, (adresse, antwort.status_code)
    assert str(htmlsafe_json_dumps(KEIN_MITARBEITER)) in antwort.text


def test_server_meldet_die_gemeinsame_meldung(threaded_db_session, router_test_client, feste_uhr):
    """Ein Konto ohne Mitarbeiter bekommt aus Zeiterfassung und Monteursansicht dieselbe Meldung (feste Uhr: /today meldet ab dem
    Feierabend 401)."""
    from app.meldungen import KEIN_MITARBEITER
    from app.routers.field_view import router as field_router
    from app.routers.time_tracking import router as time_router

    db = threaded_db_session
    monteur = router_test_client(db, time_router, field_router, role="field")
    for antwort in (monteur.post("/api/time-entries", json={"employee_id": 1, "order_id": 1, "work_date": "2026-10-20", "hours": "1"}),
                    monteur.get("/api/time-entries/active"),
                    monteur.get("/api/field-view/today"),
                    monteur.get("/api/field-view/timesheet.pdf")):
        assert antwort.status_code in (403, 422), antwort.text
        assert antwort.json()["detail"] == KEIN_MITARBEITER


# ---------------------------------------------------------------------------
# 4. Kundentexte bleiben beim Sie, die Oberfläche beim Du (Vorschlag aus docs/archiv/befund-du-statt-sie.md)
# ---------------------------------------------------------------------------

# Verzeichnis der Kundentexte: was an Kunden geht (Angebot, Auftrag, Rechnung, Mahnung, Vertrag, Briefe, ihre E-Mails und PDFs)
# bleibt beim Sie. Je Datei die Namen auf oberster Ebene (Funktion, Klasse, Zuweisung), deren Zeichenketten Kundentexte sind;
# None = die ganze Datei (PDF-Renderer an Kunden). Ein neuer Kundentext kommt hier hinein -- ein Kundentext-Merkmal außerhalb des
# Verzeichnisses lässt test_kundentext_merkmal_nur_im_verzeichnis scheitern.
KUNDENTEXTE = {
    "app/checklist_email.py": {"DEFAULT_CHECKLIST_EMAIL_BODY"},
    "app/contract_versions.py": {"DEFAULT_CONTRACT_EMAIL_BODY"},
    "app/invoices.py": {"DEFAULT_INVOICE_EMAIL_BODY", "refund_sentence", "payment_note_sentence"},
    "app/notice_letters.py": {"INTRO", "DEFAULT_EMAIL_BODY", "salutation_line", "build_letter_content"},
    "app/option_settings.py": {"DEFAULT_OPTION_GROUPS"},  # Vortexte, Zahlungsbedingungen, Schlusstexte
    "app/orders.py": {"DEFAULT_ORDER_EMAIL_BODY"},
    "app/projects.py": {"DEFAULT_QUOTE_EMAIL_BODY"},
    "app/reminders.py": {"DEFAULT_REMINDER_EMAIL_BODY", "DEFAULT_REMINDER_LEVELS"},
    "alembic/versions/8e2f4b6d1c97_nebenforderungen_z2b.py": {"OLD_TEXTS", "NEW_TEXTS"},  # Mahntexte in der Datenbank
    "app/checklist_pdf.py": None, "app/contract_pdf.py": None, "app/document_pdf.py": None, "app/invoice_pdf.py": None,
    "app/notice_letter_pdf.py": None, "app/order_pdf.py": None, "app/quote_framed_pdf.py": None, "app/reminder_pdf.py": None,
    "app/service_report_pdf.py": None,
}
# Platzhalter in Vorlagen (Beispieltext eines Kundentexts), über die id des Felds
KUNDENTEXTE_PLATZHALTER = {"settings.html": ("ptTextTemplate", "rl${x.id}EmailBody")}
KUNDENTEXT_MERKMAL = re.compile(r"Sehr geehrte|anbei erhalten|Mit freundlichen Grüßen|überweisen wir Ihnen")
DU_FORM = re.compile(r"\b(du|dich|dir|dein\w*|euch|euer\w*|eure\w*)\b", re.I)
SIE_ANREDE = re.compile(r"\b(Sie|Ihnen|Ihr|Ihre|Ihren|Ihrem|Ihrer|Ihres)\b")
# „Sie“ als dritte Person am Satzanfang außerhalb der Kundentexte: (Datei, Text ab dem Treffer) -> Bezug. Darf nur kürzer werden.
DRITTE_PERSON = {
    ("app/templates/address_import.html", "Sie erscheint dann nicht mehr"): "die Adresse",
    ("app/templates/checklist.html", "Sie bleibt als Beleg"): "die Anzeige",
    ("app/templates/checklist.html", "Sie bleibt mit der Begründung"): "die Anzeige",
    ("app/templates/invoice_detail.html", "Sie wird zunächst als Entwurf angelegt"): "die Stornorechnung",
    ("app/templates/work_preparation.html", "Sie entsprechen automatisch"): "die Planstunden",
    ("app/checklists.py", "Sie bleiben samt ihren Fotos"): "die verworfenen Unterschriften",
    ("app/invoices.py", "Sie muss über 0 € liegen"): "die Rechnung (zwei Stellen in amount_block_reason)",
}
PROTOKOLL = {"debug", "info", "warning", "error", "exception", "critical", "log"}


def _oberste_name(knoten) -> str | None:
    if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return knoten.name
    if isinstance(knoten, ast.Assign) and len(knoten.targets) == 1 and isinstance(knoten.targets[0], ast.Name):
        return knoten.targets[0].id
    if isinstance(knoten, ast.AnnAssign) and isinstance(knoten.target, ast.Name):
        return knoten.target.id
    return None


def _zeichenketten_je_name(pfad: Path):
    """(Name auf oberster Ebene oder None, Zeile, Text) jeder Zeichenkette -- ohne Docstrings, freistehende Zeichenketten und
    Protokollaufrufe (die sieht kein Nutzer)."""
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    aus = set()
    for k in ast.walk(baum):
        if isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str):
            aus.add(id(k.value))
        if isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute) and k.func.attr in PROTOKOLL \
                and isinstance(k.func.value, ast.Name) and k.func.value.id in ("logger", "log", "logging"):
            aus.update(id(x) for x in ast.walk(k))
    for oben in baum.body:
        name = _oberste_name(oben)
        for k in ast.walk(oben):
            if isinstance(k, ast.Constant) and isinstance(k.value, str) and id(k) not in aus:
                yield name, k.lineno, k.value


def _im_verzeichnis(rel: str, name: str | None) -> bool:
    return rel in KUNDENTEXTE and (KUNDENTEXTE[rel] is None or name in KUNDENTEXTE[rel])


def _py_dateien() -> list[Path]:
    """Was ein Nutzer zu sehen bekommen kann: app/, die Texte der Migrationen, die Ausgaben der Betreiber-Skripte."""
    return (sorted((ROOT / "app").rglob("*.py")) + sorted((ROOT / "alembic" / "versions").glob("*.py"))
            + [ROOT / "scripts" / "erstes_konto.py", ROOT / "scripts" / "reset_admin_2fa.py"])


def _rel(pfad: Path) -> str:
    return pfad.relative_to(ROOT).as_posix()


def _leer(m) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def _platzhalter(name: str, feld_id: str) -> re.Match:
    from tests.test_v334_auswahl_restfaelle import TEMPLATES

    treffer = list(re.finditer(r'id="' + re.escape(feld_id) + r'"[^>]*?placeholder="([^"]*)"',
                               (TEMPLATES / name).read_text(encoding="utf-8")))
    assert len(treffer) == 1, (name, feld_id, len(treffer))
    return treffer[0]


def _vorlage_ohne_kundentexte(name: str) -> str:
    """Vorlage ohne Kommentare (Jinja, HTML, JS) und ohne die Platzhalter aus dem Verzeichnis -- Zeilen bleiben, wo sie sind."""
    from tests.test_v334_auswahl_restfaelle import TEMPLATES

    text = (TEMPLATES / name).read_text(encoding="utf-8")
    for feld_id in KUNDENTEXTE_PLATZHALTER.get(name, ()):
        m = _platzhalter(name, feld_id)
        text = text[:m.start(1)] + re.sub(r"[^\n]", " ", m.group(1)) + text[m.end(1):]
    text = re.sub(r"\{#.*?#\}", _leer, text, flags=re.S)
    text = re.sub(r"<!--.*?-->", _leer, text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", _leer, text, flags=re.S)
    # // nur am Zeilenanfang oder nach ; { } ) -- nicht in https://
    return re.sub(r"(^|[;{})]\s*)//[^\n]*", lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), text, flags=re.M)


def _kundentexte():
    """(Fundstelle, Text) jedes Kundentexts aus dem Verzeichnis."""
    for rel in KUNDENTEXTE:
        for name, nr, s in _zeichenketten_je_name(ROOT / rel):
            if _im_verzeichnis(rel, name):
                yield f"{rel}:{nr}", s
    for name, ids in KUNDENTEXTE_PLATZHALTER.items():
        for feld_id in ids:
            yield f"app/templates/{name}#{feld_id}", _platzhalter(name, feld_id).group(1)


def test_verzeichnis_der_kundentexte_ist_aktuell():
    """Jede Datei und jeder Name im Verzeichnis gibt es noch, und jeder Name trägt Text -- ein umbenannter Kundentext fiele sonst
    still aus der Prüfung."""
    for rel, namen in KUNDENTEXTE.items():
        assert (ROOT / rel).exists(), rel
        if namen is None:
            continue
        mit_text = {name for name, _nr, s in _zeichenketten_je_name(ROOT / rel) if name in namen and re.search(r"[a-zäöü]{3}", s)}
        assert mit_text == namen, (rel, sorted(namen - mit_text))
    assert len(list(_kundentexte())) > 100


def test_kundentexte_ohne_du():
    """Kein Kundentext aus dem Verzeichnis enthält eine Du-Form."""
    funde = [f"{ort}: {m.group(0)!r}" for ort, s in _kundentexte() for m in DU_FORM.finditer(s)]
    assert funde == []


def test_kundentext_merkmal_nur_im_verzeichnis():
    """Jede Zeichenkette mit einem Kundentext-Merkmal („Sehr geehrte“, „anbei erhalten“, „Mit freundlichen Grüßen“, „überweisen wir
    Ihnen“) steht im Verzeichnis -- ein neuer Brief oder eine neue E-Mail-Vorlage fällt auf, bevor sie geduzt wird."""
    from tests.vorlagen_js import alle_vorlagen

    funde = [f"{_rel(p)}:{nr}" for p in _py_dateien()
             for name, nr, s in _zeichenketten_je_name(p) if KUNDENTEXT_MERKMAL.search(s) and not _im_verzeichnis(_rel(p), name)]
    for name in alle_vorlagen():
        text = _vorlage_ohne_kundentexte(name)
        funde += [f"app/templates/{name}:{text[:m.start()].count(chr(10)) + 1}" for m in KUNDENTEXT_MERKMAL.finditer(text)]
    assert funde == []


def test_ausserhalb_der_kundentexte_keine_sie_anrede():
    """Außerhalb des Verzeichnisses (Oberfläche, Meldungen des Servers, Ausgaben der Skripte) keine Sie-Anrede -- seit 1.8.158 per Du.
    „Sie“ als dritte Person steht in DRITTE_PERSON mit Bezug; ein Eintrag, den nichts mehr braucht, muss heraus."""
    from tests.vorlagen_js import alle_vorlagen

    def erlaubt(rel, rest):
        for (datei, anfang) in DRITTE_PERSON:
            if datei == rel and rest.startswith(anfang):
                gebraucht.add((datei, anfang))
                return True
        return False

    gebraucht, funde = set(), []
    for p in _py_dateien():
        for name, nr, s in _zeichenketten_je_name(p):
            if _im_verzeichnis(_rel(p), name):
                continue
            funde += [f"{_rel(p)}:{nr}: {s[max(0, m.start() - 40):m.end() + 40]!r}" for m in SIE_ANREDE.finditer(s)
                      if not erlaubt(_rel(p), s[m.start():])]
    for name in alle_vorlagen():
        text, rel = _vorlage_ohne_kundentexte(name), f"app/templates/{name}"
        funde += [f"{rel}:{text[:m.start()].count(chr(10)) + 1}: {text[max(0, m.start() - 40):m.end() + 40]!r}"
                  for m in SIE_ANREDE.finditer(text) if not erlaubt(rel, text[m.start():])]
    assert funde == []
    assert sorted(set(DRITTE_PERSON) - gebraucht) == [], "nicht mehr gebraucht -- aus DRITTE_PERSON streichen"
    assert len(DRITTE_PERSON) <= 7  # darf nur kürzer werden


def _pdf_text(pdf: bytes) -> str:
    from tests.test_v325_contract_basis import pdf_text

    return " ".join(pdf_text(pdf).split())


def _du_formen(text: str) -> list[str]:
    return sorted({m.group(0) for m in DU_FORM.finditer(text)})


def test_pdfs_an_kunden_ohne_du():
    """Je Dokumentart ein echtes PDF aus Testdaten -- Angebot mit dem Standard-Vortext, Auftrag, Vertrag, Rechnung mit Erstattung,
    Mahnung: keine Du-Form, und der Kundentext per Sie steht darin (sonst prüfte der Test nichts)."""
    from app.invoice_pdf import build_invoice_pdf
    from app.option_settings import DEFAULT_OPTION_GROUPS
    from app.order_pdf import build_order_pdf
    from app.projects import load_quote
    from app.quote_framed_pdf import build_quote_framed_pdf
    from app.reminder_pdf import build_reminder_pdf
    from app.reminders import create_reminder, ensure_default_reminder_levels, finalize_and_send_reminder
    from tests.test_v153_mahnwesen import db_session, make_sent_overdue_invoice
    from tests.test_v325_contract_basis import make_quote
    from tests.test_v335_vertragsvorlagen import beauftragen, contract_pdf, save
    from tests.test_v393_ueberzahlung import _ueberzahlt

    vortext = next(o[2] for o in DEFAULT_OPTION_GROUPS["quote_intro_texts"]["options"] if o[3])
    db = db_session()
    save(db)  # Vertragsvorlage: Beauftragen legt den Vertragsentwurf an
    quote = make_quote(db)
    quote.intro_text = vortext
    db.commit()
    quote = load_quote(db, quote.id)
    order = beauftragen(db, quote)
    pdfs = {"Angebot": (build_quote_framed_pdf(db, quote), "Vielen Dank für Ihre Anfrage"),
            "Auftrag": (build_order_pdf(db, order), "Ihr Angebot"),
            "Vertrag": (contract_pdf(db, order), "Ihr Angebot")}

    db = db_session()
    _auftrag, _abschlag, schluss = _ueberzahlt(db)
    pdfs["Rechnung mit Erstattung"] = (build_invoice_pdf(db, schluss), "überweisen wir Ihnen")

    db = db_session()
    ensure_default_reminder_levels(db)
    mahnung = create_reminder(db, make_sent_overdue_invoice(db), 1)
    finalize_and_send_reminder(db, mahnung)
    pdfs["Mahnung"] = (build_reminder_pdf(db, mahnung), "Bitte begleichen Sie")

    for art, (pdf, kundentext) in pdfs.items():
        text = _pdf_text(pdf)
        assert _du_formen(text) == [], art
        assert kundentext in text, art


def test_behinderungsanzeige_als_brief_ohne_du(nworld, router_test_client):
    """Die Behinderungsanzeige als Brief an den Auftraggeber (echte Fassung in der Ablage): keine Du-Form, Einleitung per Sie."""
    from app.notice_letters import ensure_letter
    from tests.test_v343_behinderungsanzeige_versand import NOTICE, _archive_bytes
    from tests.test_v343_behinderungsanzeige_versand import _signed as unterschrieben

    c = unterschrieben(nworld, router_test_client)
    text = _pdf_text(_archive_bytes(ensure_letter(nworld["db"], c["id"], NOTICE).sent_document))
    assert _du_formen(text) == []
    assert "Sehr geehrter Herr Dr. Muster, hiermit zeigen wir Ihnen an" in text


def test_bedenkenanzeige_als_brief_ohne_du(mworld, router_test_client):
    """Die Bedenkenanzeige als Brief an den Auftraggeber (echte Fassung in der Ablage): keine Du-Form, Einleitung per Sie."""
    from app.notice_letters import ensure_letter
    from tests.test_v347_bedenkenanzeige_versand import KIND, _archive_bytes
    from tests.test_v347_bedenkenanzeige_versand import _signed as unterschrieben

    c = unterschrieben(mworld, router_test_client)
    text = _pdf_text(_archive_bytes(ensure_letter(mworld["db"], c["id"], KIND).sent_document))
    assert _du_formen(text) == []
    assert "Sehr geehrte Frau Bauherrin, hiermit melden wir Ihnen Bedenken" in text
