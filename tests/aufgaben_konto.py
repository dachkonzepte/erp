"""Seit 1.9.371 (Nachrunde Urlaub, Punkt 2): eine Aufgabe bekommt nur, wer sie sieht -- ein aktives Büro-Konto (app/tasks.py::zuweisung_grund(), auch ohne
Mindestrolle). Testdaten, die einer Person eine Aufgabe zuweisen (von Hand oder über ein Modul), geben ihr hierüber ein Konto; ohne Konto käme die Aufgabe
eines Moduls in den Büro-Eingang, die Zuweisung von Hand wäre 422."""

from app.models import AppUser


def buero_konto(db, employee, role: str = "buero_auftrag") -> AppUser:
    """Ein aktives Konto der Person mit der Rolle (Vorgabe Büro – Auftrag); Benutzername „konto-<ID der Person>“. Schreibt mit flush, nicht commit."""
    if employee.id is None:
        db.flush()
    konto = AppUser(username=f"konto-{employee.id}", display_name=f"Konto {employee.id}", role=role, employee_id=employee.id, active=True,
                    password_hash="-")
    db.add(konto)
    db.flush()
    return konto
