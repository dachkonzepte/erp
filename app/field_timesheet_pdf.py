"""Eigener Stundenzettel für Monteure (seit 1.3.61, siehe CLAUDE.md "Zeiterfassung für Monteure"
-> "Stundenzettel"). Anders als der bestehende, admin-only Büro-Stundenzettel
(app/time_backoffice.py::build_timesheet_pdf(), landscape, mehrere Mitarbeiter je Lauf, eigener
SimpleDocTemplate -- NICHT auf dem gemeinsamen Rahmen) nutzt dieser Renderer ausdrücklich
render_framed_pdf() (app/document_frame.py) wie Mahnung/Rechnung/Auftrag/Einsatzbericht/Angebot --
"mit Briefkopf" (Betreibervorgabe). Der Büro-Stundenzettel diente nur als inhaltliche Vorlage
(Spaltenauswahl, Tages-/Summenzeilen), nicht als Code-Vorbild für den Rahmen.

Neuer Dokumenttyp "field_timesheet" -- eingetragen in DOCUMENT_TYPES (app/document_layout.py) und
RENDERERS_USING_SHARED_FRAME (app/document_frame.py), sonst wirft render_framed_pdf() einen
ValueError (Muster aus 1.3.11, als "service_report" zum ersten Mal ein komplett neuer Typ wurde).
Fällt ohne eigene Zeile automatisch auf den geteilten "default"-Satz zurück
(resolve_shared_document_type(), app/document_type_fallback.py) -- dasselbe Briefpapier/dieselben
Ränder/Bausteine wie jeder andere Dokumenttyp außer dem Angebot, keine eigene Migration nötig."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from html import escape

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from .document_frame import frame_content_width, render_framed_pdf
from .document_page_margins import get_margins
from .document_pdf import build_din5008_header_block, build_styles
from .models import Employee
from .option_settings import get_option_group, option_group_to_dict
from .settings import get_or_create_general_settings
from .time_tracking import entry_to_dict, list_entries

MONTH_NAMES_DE = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}

# Feste Spaltenbreiten -- "Auftrag" und "Tätigkeit" teilen sich den variablen Rest, Muster
# ITEMS_COL_WIDTHS_MM in invoice_pdf.py (dort eine einzige variable Spalte statt zwei; hier zwei,
# weil beide Textspalten unterschiedlich lang werden können und keine davon eindeutig die
# "Hauptspalte" ist).
FIXED_COL_WIDTHS_MM = {"datum": 22, "zeitart": 26, "stunden": 22}
_VARIABLE_SPLIT = (0.55, 0.45)  # Auftrag : Tätigkeit


def _fmt_h(value) -> str:
    return f"{Decimal(value or 0):.2f}".replace(".", ",")


def month_date_range(year: int, month: int) -> tuple[date, date]:
    """Erster und letzter Kalendertag eines Monats -- reine Datumsarithmetik, kein Aufrufer
    außerhalb dieses Moduls (der Bildschirm-Stundenzettel berechnet dieselbe Spanne clientseitig
    aus dem <input type="month">, siehe field_timesheet.html)."""
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    from datetime import timedelta
    return start, end - timedelta(days=1)


def build_field_timesheet_pdf(db: Session, employee_id: int, year: int, month: int) -> bytes:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise ValueError("Mitarbeiter wurde nicht gefunden.")
    start, end = month_date_range(year, month)
    rows = list_entries(db, employee_id=employee_id, start_date=start, end_date=end, limit=2000)
    general = get_or_create_general_settings(db)
    styles = build_styles()
    body, h1 = styles["body"], styles["h1"]
    content_width = frame_content_width(get_margins(db, "field_timesheet", "first"))

    type_group = get_option_group(db, "time_entry_types")
    type_labels = {o["value"]: o["label"] for o in option_group_to_dict(type_group)["options"]} if type_group else {}

    sender_parts = [general.company_name, general.street, " ".join(x for x in [general.postal_code, general.city] if x)]
    sender_line = " - ".join(x for x in sender_parts if x)
    employee_name = f"{employee.first_name} {employee.last_name}".strip()
    month_label = f"{MONTH_NAMES_DE.get(month, month)} {year}"

    by_day: dict[date, list] = defaultdict(list)
    for r in rows:
        by_day[r.work_date].append(r)

    def build_story(total_pages: int | None) -> list:
        page_value = f"1 / {total_pages}" if total_pages is not None else "1 / …"
        meta_rows = []
        if employee.employee_number:
            meta_rows.append(("Personalnummer", employee.employee_number))
        meta_rows += [("Zeitraum", month_label), ("Seite", page_value)]
        story = list(build_din5008_header_block(sender_line, [employee_name], meta_rows, styles, content_width=content_width))
        story.append(Paragraph(f"Stundenzettel {month_label}", h1))
        story.append(Spacer(1, 4 * mm))

        fixed_width = sum(FIXED_COL_WIDTHS_MM.values()) * mm
        remaining = content_width - fixed_width
        col_widths = [
            FIXED_COL_WIDTHS_MM["datum"] * mm, remaining * _VARIABLE_SPLIT[0],
            FIXED_COL_WIDTHS_MM["zeitart"] * mm, remaining * _VARIABLE_SPLIT[1],
            FIXED_COL_WIDTHS_MM["stunden"] * mm,
        ]

        if not by_day:
            story.append(Paragraph("Keine Zeitbuchungen in diesem Zeitraum.", body))
            return story

        table_rows = [["Datum", "Auftrag", "Zeitart", "Tätigkeit", "Stunden"]]
        summary_row_indices: list[int] = []
        month_total = Decimal("0")
        for day in sorted(by_day):
            day_total = Decimal("0")
            for r in sorted(by_day[day], key=lambda x: (x.started_at or x.created_at, x.id)):
                d = entry_to_dict(r)
                hours = Decimal(r.hours or 0)
                day_total += hours
                table_rows.append([
                    day.strftime("%d.%m.%Y"),
                    escape(d.get("order_number") or ""),
                    type_labels.get(r.entry_type, r.entry_type),
                    escape(r.activity or ""),
                    _fmt_h(hours),
                ])
            table_rows.append(["", "", "", f"Tagessumme {day.strftime('%d.%m.')}", _fmt_h(day_total)])
            summary_row_indices.append(len(table_rows) - 1)
            month_total += day_total
        table_rows.append(["", "", "", "Monatssumme", _fmt_h(month_total)])
        summary_row_indices.append(len(table_rows) - 1)

        style_commands = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 8.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("FONTSIZE", (0, 1), (-1, -1), 8.5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), .25, colors.HexColor("#cccccc")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
        ]
        for ridx in summary_row_indices:
            style_commands.append(("FONTNAME", (0, ridx), (-1, ridx), "Helvetica-Bold"))
            style_commands.append(("LINEABOVE", (0, ridx), (-1, ridx), .6, colors.black))

        t = Table(table_rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle(style_commands))
        story.append(t)
        return story

    return render_framed_pdf(
        db, document_type="field_timesheet", title=f"Stundenzettel {month_label} -- {employee_name}",
        content_story=build_story,
    )
