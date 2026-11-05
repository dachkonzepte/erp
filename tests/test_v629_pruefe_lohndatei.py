"""Version 1.9.227 (Lohn L1b, Punkt 4): scripts/pruefe_lohndatei.py -- die Lohndatei des ERP gegen die Datei aus Time 4, je Person und Tag.

Kleinstdateien, erfunden (Berater und Mandant wie in den Mustern). Erklärt: die erwarteten Abweichungen des L1b-Befunds (Abschnitt 3) und die
Rundung; alles andere zu klären. Rückgabe 0 nur Erklärtes, 1 zu klären, 2 Formfehler oder nicht lesbar. Liegen die Muster (bildgrundlage/lohn,
nicht in Git) vor, ergibt jedes gegen sich selbst keine Abweichung.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("pruefe_lohndatei", WURZEL / "scripts" / "pruefe_lohndatei.py")
pl = importlib.util.module_from_spec(_spec)
sys.modules["pruefe_lohndatei"] = pl  # Dataclasses brauchen das Modul in sys.modules
_spec.loader.exec_module(pl)
MUSTER = WURZEL / "bildgrundlage" / "lohn"


def datei(tmp_path, name, zeilen, kopf="1234567;12345;12/2026"):
    p = tmp_path / name
    p.write_bytes(("\r\n".join([kopf, *zeilen]) + "\r\n").encode("ascii"))
    return p


def lauf(tmp_path, capsys, erp, t4, *args, kopf_erp="1234567;12345;12/2026", kopf_t4="1234567;12345;12/2026"):
    rc = pl.main([str(datei(tmp_path, "erp.txt", erp, kopf_erp)), str(datei(tmp_path, "t4.txt", t4, kopf_t4)), *args])
    return rc, capsys.readouterr().out


def zeilen_mit(out, wort):
    return [z.strip() for z in out.splitlines() if z.strip().startswith(wort)]


# --- Form -----------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("roh, fund", [
    (b"1234567;12345;12/2026\r\n00101;7;1;1000;8,00;;;;;;", "Zeilenende"),
    (b"1234567;12345;12/2026\n00101;7;1;1000;8,00;;;;;;\n", "Zeilenende"),
    (b"1234567;12345;2026-12\r\n", "Kopf"),
    (b"1234567;12345;12/2026\r\n00101;7;1;1000;8,00;;;;;\r\n", "10 statt 11 Felder"),
    (b"1234567;12345;12/2026\r\n00101;32;1;1000;8,00;;;;;;\r\n", "nicht im Monat"),
    (b"1234567;12345;12/2026\r\n00101;07;1;1000;8,00;;;;;;\r\n", "Tageszeile"),
    (b"1234567;12345;12/2026\r\n00101;7;1;1000;8.00;;;;;;\r\n", "Tageszeile"),
    (b"1234567;12345;12/2026\r\n00101;7;\xc4;1000;8,00;;;;;;\r\n", "kein ASCII"),
    (b"1234567;12345;12/2026\r\n00101;;;8110;;;15,0;;;;\r\n", "Monatszeile"),
])
def test_formfehler_rot(tmp_path, capsys, roh, fund):
    (tmp_path / "erp.txt").write_bytes(roh)
    t4 = datei(tmp_path, "t4.txt", [])
    assert pl.main([str(tmp_path / "erp.txt"), str(t4)]) == 2
    assert fund in capsys.readouterr().out


def test_gegen_sich_selbst_keine_abweichung(tmp_path, capsys):
    z = ["00101;7;1;1000;8,00;;;;;;", "00101;8;U;8000;7,50;;;;;;", "00101;31;UU;;7,50;;;;;;", "00101;;;8110;;;15,00;;;;"]
    rc, out = lauf(tmp_path, capsys, z, z)
    assert rc == 0 and out.strip().endswith("Keine Abweichung.")


@pytest.mark.skipif(not MUSTER.exists(), reason="Muster liegen nur lokal vor (bildgrundlage/lohn, nicht in Git)")
def test_muster_gegen_sich_selbst(capsys):
    for p in sorted(MUSTER.glob("time4_muster_*.txt")):
        assert pl.main([str(p), str(p)]) == 0, p.name
        assert capsys.readouterr().out.strip().endswith("Keine Abweichung."), p.name


# --- erklärt ----------------------------------------------------------------------------------------------------------------------------

def test_rundung_und_pause_erklaert(tmp_path, capsys):
    """Rundung (9,13 -> 9,25); Samstag ohne Pause in Time 4 (8,50 -> 8,00); Winter über 9 h (Time 4 30 min: 9,50 -> 9,25); unter 6 h über die
    Mittagspause (4,50 -> 5,00); Lücke über der festen Pause (Time 4 zog 10 min ab: 7,75 -> 7,50)."""
    t4 = ["00101;1;1;1000;9,13;;;;;;", "00101;5;1;1000;8,50;;;;;;", "00101;7;1;1000;9,50;;;;;;", "00101;8;1;1000;4,50;;;;;;", "00101;9;1;1000;7,75;;;;;;"]
    erp = ["00101;1;1;1000;9,25;;;;;;", "00101;5;1;1000;8,00;;;;;;", "00101;7;1;1000;9,25;;;;;;", "00101;8;1;1000;5,00;;;;;;", "00101;9;1;1000;7,50;;;;;;"]
    rc, out = lauf(tmp_path, capsys, erp, t4)
    erklaert = zeilen_mit(out, "erklärt")
    assert rc == 0 and len(erklaert) == 5, out
    assert "Rundung" in erklaert[0] and "ohne Pause" in erklaert[1] and "30 min feste Pause" in erklaert[2] and "30 min feste Pause" in erklaert[3]
    assert "zum Teil überdeckt" in erklaert[4]


def test_schlechtwetter_heiligabend_silvester_berufsschule_mehrarbeit_nummer(tmp_path, capsys):
    t4 = ["9005;;;8110;;;15,00;;;;", "9005;24;1;1000;7,50;;;;;;", "9005;31;U;8000;7,50;;;;;;", "00201;7;1;1000;9,00;;;;;;"]
    erp = ["09005;9;WA;8195;7,50;;;;;;", "09005;10;WA;8195;7,50;;;;;;", "09005;24;FR;1080;7,00;;;;;;", "09005;31;UU;;7,50;;;;;;",
           "00201;7;1;1000;7,50;;;;;;", "00201;7;AA;1900;1,50;;;;;;", "00201;8;FE;;7,50;;;;;;"]
    rc, out = lauf(tmp_path, capsys, erp, t4)
    assert rc == 0, out
    text = "\n".join(zeilen_mit(out, "erklärt"))
    for wort in ("5 Stellen", "Monatszeile 8110 (Time 4) 15,00 h, im ERP WA je Tag 15,00 h an 2 Tagen", "Schlechtwetter je Tag", "Heiligabend",
                 "Silvester (UU), in Time 4 Urlaub", "Silvester: das ERP UU", "Berufsschule (FE)", "Mehrarbeit Azubi (AA / 1900), zusammen"):
        assert wort in text, wort


def test_azubi_nur_im_erp(tmp_path, capsys):
    erp, t4 = ["00201;7;1;1000;8,00;;;;;;", "00201;25;F;1012;7,50;;;;;;"], ["00201;2;U;8000;7,50;;;;;;"]
    assert lauf(tmp_path, capsys, erp + t4, t4)[0] == 1  # ohne --azubis zu klären
    rc, out = lauf(tmp_path, capsys, erp + t4, t4, "--azubis", "00201")
    assert rc == 0 and len(zeilen_mit(out, "erklärt")) == 2 and "Azubi: Time 4 gab nur U und K aus" in out


def test_nummernwechsel(tmp_path, capsys):
    rc, out = lauf(tmp_path, capsys, ["91016;7;1;1000;8,00;;;;;;"], ["91008;7;1;1000;8,00;;;;;;"], "--gleich", "91008=91016")
    assert rc == 0 and "Nummernwechsel" in out


# --- zu klären --------------------------------------------------------------------------------------------------------------------------

def test_zu_klaeren(tmp_path, capsys):
    """Anderes Kennzeichen (U hier, K dort), andere Lohnart, eine Stunde mehr ohne Erklärung, Monatszeile mit anderer Summe (dann ist auch die
    Tageszeile WA nicht erklärt), Kopf (Mandant)."""
    t4 = ["00101;2;K;1650;7,50;;;;;;", "00101;3;U;8000;7,50;;;;;;", "00101;4;1;1000;8,00;;;;;;", "00102;;;8110;;;15,00;;;;"]
    erp = ["00101;2;U;8000;7,50;;;;;;", "00101;3;U;8001;7,50;;;;;;", "00101;4;1;1000;9,00;;;;;;", "00102;9;WA;8195;7,50;;;;;;"]
    rc, out = lauf(tmp_path, capsys, erp, t4, kopf_erp="1234567;12346;12/2026")
    offen = zeilen_mit(out, "zu klären")
    assert rc == 1 and len(offen) == 7, out
    for wort in ("Kopf: Mandant ERP 12346, Time 4 12345", "U / 8000 7,50 nur im ERP", "K / 1650 7,50 nur in Time 4", "U: Lohnart ERP 8001, Time 4 8000",
                 "1: ERP 9,00, Time 4 8,00", "Summe abweichend", "WA / 8195 7,50 nur im ERP"):
        assert any(wort in z for z in offen), wort
    assert "7 Abweichungen, davon 7 zu klären." in out


def test_summen_je_person(tmp_path, capsys):
    rc, out = lauf(tmp_path, capsys, ["00101;7;1;1000;8,00;;;;;;", "00101;8;1;1000;8,00;;;;;;"], ["00101;7;1;1000;8,00;;;;;;", "00101;8;1;1000;8,25;;;;;;"])
    assert "00101  1 16,00/16,25" in out and rc == 0  # 8,25 -> 8,00: Pause (Time 4 ohne, 8:15 h -> 15 min)
