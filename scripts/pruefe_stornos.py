"""Prüfung: hebt jeder festgeschriebene Storno sein Original genau auf? (seit 1.9.119, Stufe 5, R1 Nachrunde, Punkt 1)

Bis 1.9.113 ließen sich die Positionen eines Storno-Entwurfs ändern, ergänzen und entfernen (Befund F8, seit 1.9.114 gesperrt) -- ein
vorher festgeschriebener Storno kann deshalb von seinem Original abweichen. Das Skript vergleicht je festgeschriebenem Storno Netto, USt
und Brutto (gerechnet mit app/invoices.py::compute_invoice_totals(), wie Rechnungsseite, PDF und Zahlungen) und jede Position (Menge,
Einzelpreis, Betrag) mit dem Original; Soll ist genau das Gegenteil des Originals. Ein pauschaler Abschlag ohne Position (vor 1.3.24) hat
als Soll die eine Position, die sein Storno seit 1.8.83 bekommt.

Aufruf auf dem Server, im Projektverzeichnis, mit geladener Umgebung und dem Python des Servers:

    cd /home/tobias/erp
    set -a; source .env; set +a
    .venv/bin/python scripts/pruefe_stornos.py

Nur lesen: die Sitzung ist schreibgeschützt (PostgreSQL: SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY, SQLite: PRAGMA
query_only), wird am Ende zurückgerollt und schreibt nichts -- auch keine Zeile im Änderungsprotokoll.

DATABASE_URL muss gesetzt sein, wie bei alembic und scripts/erstes_konto.py: ohne sie fiele app/database.py still auf eine SQLite-Datei
zurück, und das Skript prüfte die falsche Datenbank.

Ausgabe: je Treffer (ein Storno, der sein Original nicht genau umkehrt) der Storno, sein Original und jede Abweichung als Soll / Ist;
ohne Treffer „Alle n Stornos heben ihr Original genau auf.“ Rückgabe: 0 ohne Treffer, 1 mit Treffer, 2 Umgebung fehlt (DATABASE_URL,
Datenbank nicht lesbar).
"""

import argparse
import os
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, event, select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

# app.* erst nach der Prüfung von DATABASE_URL: app.database baut seine Engine beim ersten Import aus der Umgebung (fehlt sie, still
# SQLite).


@dataclass
class Treffer:
    storno: str
    original: str
    abweichungen: list[str] = field(default_factory=list)


def _zahl(wert: Decimal, stellen: int = 2) -> str:
    """Deutsch, mit Tausenderpunkt; mindestens `stellen` Nachkommastellen, mehr nur, wenn sie nicht null sind (ein ungerundeter
    Betrag vor 1.8.11 zeigt seine ganze Genauigkeit -- eine Abweichung um 0,004 € bleibt sichtbar)."""
    wert = Decimal(wert)
    exponent = wert.normalize().as_tuple().exponent
    nachkomma = max(stellen, -exponent if isinstance(exponent, int) and exponent < 0 else 0)
    text = f"{wert:,.{nachkomma}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".").replace("-", "−")


def _geld(wert: Decimal) -> str:
    return _zahl(wert) + " €"


def _menge(wert: Decimal) -> str:
    return _zahl(wert, 0)


def _bezeichnung(invoice) -> str:
    return f"{invoice.invoice_number or 'ohne Nummer'} (ID {invoice.id})"


def _positionen(invoice) -> list[dict]:
    """Die Positionen einer Rechnung, wie sie zählen: Menge, Einzelpreis, Betrag (invoice_line_total())."""
    from app.invoices import invoice_line_total

    return [{"schluessel": (item.sort_order, item.position_number or ""), "text": f"{item.gaeb_oz or item.position_number or ''} "
             f"{item.short_text or ''}".strip(), "menge": item.billed_quantity, "preis": item.unit_price,
             "betrag": invoice_line_total(invoice, item)} for item in sorted(invoice.items, key=lambda i: (i.sort_order, i.id))]


def _soll_positionen(original) -> list[dict]:
    """Die Positionen, die der Storno haben muss: jede des Originals mit umgekehrter Menge und umgekehrtem Betrag. Ein pauschaler
    Abschlag ohne Position (vor 1.3.24) -- eine Position 1 über den Pauschalbetrag (app/invoices.py::create_storno_draft())."""
    from app.invoices import INVOICE_ROUNDING_HALF_UP
    from app.rounding import round_money

    if original.invoice_type == "abschlag_pauschal" and not original.items:
        betrag = original.lump_sum_net if original.lump_sum_net is not None else Decimal("0")
        if original.rounding_rule == INVOICE_ROUNDING_HALF_UP:
            betrag = round_money(betrag)
        return [{"schluessel": (10, "1"), "text": f"1 {original.progress_description or ''}".strip(), "menge": Decimal("-1"),
                 "preis": original.lump_sum_net if original.lump_sum_net is not None else Decimal("0"), "betrag": -betrag}]
    return [{**p, "menge": -p["menge"], "betrag": -p["betrag"]} for p in _positionen(original)]


def _vergleiche_positionen(soll: list[dict], ist: list[dict]) -> list[str]:
    """Paart nach (Sortierung, Positionsnummer) -- eine ergänzte oder entfernte Position verschiebt die übrigen nicht."""
    abweichungen: list[str] = []
    offen = list(ist)
    for s in soll:
        partner = next((p for p in offen if p["schluessel"] == s["schluessel"]), None)
        if partner is None:
            abweichungen.append(f"Position {s['text']}: fehlt im Storno (Soll Menge {_menge(s['menge'])}, Betrag {_geld(s['betrag'])})")
            continue
        offen.remove(partner)
        teile = [f"{name} Soll {fmt(s[k])}, Ist {fmt(partner[k])}"
                 for k, name, fmt in (("menge", "Menge", _menge), ("preis", "Einzelpreis", _geld), ("betrag", "Betrag", _geld))
                 if Decimal(s[k]) != Decimal(partner[k])]
        if teile:
            abweichungen.append(f"Position {s['text']}: " + "; ".join(teile))
    for p in offen:
        abweichungen.append(f"Position {p['text']}: nur im Storno (Menge {_menge(p['menge'])}, Betrag {_geld(p['betrag'])})")
    return abweichungen


def pruefen(db) -> tuple[int, list[Treffer]]:
    """(Zahl der festgeschriebenen Stornos, Treffer) -- liest nur."""
    from app.invoices import EDITABLE_STATUS, compute_invoice_totals
    from app.models import Invoice

    stornos = db.scalars(select(Invoice).where(Invoice.invoice_type == "storno", Invoice.status != EDITABLE_STATUS)
                         .order_by(Invoice.id)).all()
    treffer: list[Treffer] = []
    for storno in stornos:
        original = db.get(Invoice, storno.storno_of_invoice_id) if storno.storno_of_invoice_id is not None else None
        if original is None:
            treffer.append(Treffer(_bezeichnung(storno), "—", ["das Original fehlt (storno_of_invoice_id leer oder unbekannt)"]))
            continue
        abweichungen = []
        ist, soll = compute_invoice_totals(storno), compute_invoice_totals(original)
        for schluessel, name in (("net_total", "Netto"), ("vat_total", "USt"), ("gross_total", "Brutto")):
            if ist[schluessel] != -soll[schluessel]:
                abweichungen.append(f"{name}: Soll {_geld(-soll[schluessel])}, Ist {_geld(ist[schluessel])}")
        abweichungen += _vergleiche_positionen(_soll_positionen(original), _positionen(storno))
        if abweichungen:
            treffer.append(Treffer(_bezeichnung(storno), _bezeichnung(original), abweichungen))
    return len(stornos), treffer


def nur_lesende_sitzung(url: str) -> Session:
    """Eine eigene Sitzung, die nicht schreiben kann -- jede Verbindung schreibgeschützt, bevor die erste Anfrage läuft."""
    engine = create_engine(url, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _schreibschutz(dbapi_verbindung, _eintrag):
        cursor = dbapi_verbindung.cursor()
        if engine.dialect.name == "postgresql":
            cursor.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
            dbapi_verbindung.commit()  # psycopg beginnt mit dem SET eine Transaktion; der Schreibschutz gilt für jede folgende
        elif engine.dialect.name == "sqlite":
            cursor.execute("PRAGMA query_only = ON")
        else:
            raise RuntimeError(f"Datenbank {engine.dialect.name} unbekannt -- kein Schreibschutz, keine Prüfung.")
        cursor.close()

    return Session(bind=engine, autoflush=False)


def ausgeben(anzahl: int, treffer: list[Treffer], ausgabe=print) -> None:
    if not anzahl:
        ausgabe("Kein festgeschriebener Storno -- nichts zu prüfen.")
        return
    if not treffer:
        ausgabe(f"Alle {anzahl} Stornos heben ihr Original genau auf.")
        return
    ausgabe(f"{len(treffer)} von {anzahl} Stornos heben ihr Original nicht genau auf:")
    for t in treffer:
        ausgabe(f"Storno {t.storno} zu {t.original}:")
        for zeile in t.abweichungen:
            ausgabe(f"  {zeile}")


def main(argv=None, *, sitzung=None, umgebung=None, ausgabe=print) -> int:
    """sitzung/umgebung/ausgabe nur für Tests; im Betrieb die nur lesende Sitzung aus DATABASE_URL, os.environ, print."""
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args(argv)
    umgebung = os.environ if umgebung is None else umgebung
    eigene = sitzung is None
    if eigene:
        url = (umgebung.get("DATABASE_URL") or "").strip()
        if not url:
            ausgabe("DATABASE_URL ist nicht gesetzt -- auf dem Server zuerst: set -a; source .env; set +a")
            return 2
        sitzung = nur_lesende_sitzung(url)
    try:
        anzahl, treffer = pruefen(sitzung)
    except SQLAlchemyError as fehler:
        ausgabe(f"Datenbank nicht lesbar: {type(fehler).__name__}")
        return 2
    finally:
        sitzung.rollback()
        if eigene:
            bind = sitzung.get_bind()
            sitzung.close()
            bind.dispose()
    ausgeben(anzahl, treffer, ausgabe)
    return 1 if treffer else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
