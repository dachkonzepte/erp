"""Version 1.11.1 (Stufe P1a, Nachtrag N1): Funktionen der Datenbank für Link und Sitzung des Kundenportals (app/portal/funktionen.py).

    Text          jede Funktion mit festem search_path, ohne dynamisches SQL, für alle nicht ausführbar; die SECURITY DEFINER sind genau die Rechte des
                  Portals (rechte.FUNKTIONEN); Zeit nur aus portal_jetzt(); jedes protokollierte Wort steht in app/portal/werte.py; Migration wörtlich
    Prüfwerte     app/portal/pruefwerte.py: Zweck vor dem Wert, Code an die Sitzung gebunden, Anschluss nur mit Schlüssel
    PostgreSQL    (Wegwerf-Schema, Aufrufe als Testrolle dkportal_test, Daten wie das ERP sie anlegt) -- Link öffnen (jeder Grund außen gleich, im Protokoll
                  unterschieden; unbestätigte Sitzung 15 Minuten; mit bestätigter Sitzung angemeldet; Bremse), Code anfordern (Auftrag, NOTIFY erst beim
                  Commit, 60 Sekunden, Grenzen je Zugang), Stand des Versands, Code prüfen (falsch mit Rest, 5 Versuche, abgelaufen, richtig: Sitzung
                  bestätigt mit neuem Wert, Code verbraucht; zwei gleichzeitig: einer), Sitzung prüfen und verlängern (höchstens einmal je Stunde),
                  abmelden (ein Gerät, alle Geräte nur bestätigt), Willkommen; Sperren, Portal aus, Archiv und Modul aus beenden jede Sitzung; die Rolle
                  liest keine Tabelle und keinen Helfer; Eingaben, die keine Prüfwerte sind, schreiben nichts; Migration hinauf und herab
"""

import os
import re
import threading
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from app.database import Base
from app.portal import funktionen, pruefwerte, rechte, unterlagen, werte
from tests.test_v380_nummern_eindeutig import _alembic, _ok

ROOT = Path(__file__).resolve().parent.parent
PG_URL = os.getenv("ERP_TEST_POSTGRES_URL")
TESTROLLE = "dkportal_test"
MIGRATION, VORHER = "b5d1e8a3c247", "4f8a2c6e1b97"
SCHLUESSEL = b"x" * 32
HIER = pruefwerte.anschluss("192.0.2.10", SCHLUESSEL)  # Dokumentationsadresse (RFC 5737)


# --- Text der Funktionen (ohne Datenbank) ------------------------------------------------------------------------------------------------------------

def _erzeugt(sql: str) -> str:
    return re.match(r"CREATE OR REPLACE FUNCTION (\w+)", sql).group(1)


def test_jede_funktion_fester_pfad_ohne_dynamisches_sql():
    erzeugen = [a for a in funktionen.ANWEISUNGEN if a.startswith("CREATE OR REPLACE FUNCTION")]
    assert len(erzeugen) == 14
    for sql in erzeugen:
        assert "SET search_path = pg_catalog, @SCHEMA@, pg_temp AS $$" in sql, _erzeugt(sql)
        rumpf = sql.split("$$", 1)[1]
        assert not re.search(r"\bEXECUTE\b", rumpf, re.I) and "format(" not in rumpf.lower(), _erzeugt(sql)
        assert "%" not in sql, _erzeugt(sql)  # exec_driver_sql ohne Parameter: kein Prozentzeichen im Text
        # Zeit nur aus portal_jetzt()
        if _erzeugt(sql) != "portal_jetzt":
            assert not re.search(r"\b(now|current_timestamp|clock_timestamp|localtimestamp|statement_timestamp)\b", rumpf, re.I), _erzeugt(sql)


def test_security_definer_genau_die_rechte_des_portals_und_keine_fuer_alle():
    definer = {_erzeugt(a) for a in funktionen.ANWEISUNGEN if a.startswith("CREATE OR REPLACE FUNCTION") and "SECURITY DEFINER" in a}
    assert definer == set(funktionen.FUER_DAS_PORTAL)
    # seit 1.11.31 (P2a) dazu die drei Funktionen der Unterlagen (app/portal/unterlagen.py, eigene Prüfung in tests/test_v821_portal_unterlagen.py)
    assert rechte.FUNKTIONEN == {**funktionen.FUER_DAS_PORTAL, **unterlagen.FUER_DAS_PORTAL}
    erzeugt = {_erzeugt(a) for a in funktionen.ANWEISUNGEN if a.startswith("CREATE OR REPLACE FUNCTION")}
    entzogen = {re.match(r"REVOKE ALL ON FUNCTION (\w+)\(", a).group(1) for a in funktionen.ANWEISUNGEN if a.startswith("REVOKE")}
    assert erzeugt == entzogen
    # alle Anweisungen erst anlegen, dann entziehen -- und jede Funktion genau einmal
    assert [a.startswith("REVOKE") for a in funktionen.ANWEISUNGEN] == sorted(a.startswith("REVOKE") for a in funktionen.ANWEISUNGEN)


def test_protokollierte_woerter_sind_feste_werte():
    text_ = "\n".join(funktionen.ANWEISUNGEN)
    for aktion, ergebnis in re.findall(r"portal_protokoll\([^,]+, [^,]+, '(\w+)', (?:'(\w+)'|v_grund)\)", text_):
        assert aktion in werte.AKTIONEN, aktion
        assert not ergebnis or ergebnis in werte.ERGEBNISSE, ergebnis
    grund = re.findall(r"THEN '(\w+)'", next(a for a in funktionen.ANWEISUNGEN if "portal_zugang_grund(p_zugang integer)" in a))
    assert set(grund) <= set(werte.ERGEBNISSE) and len(grund) == 6


def test_migration_traegt_die_anweisungen_woertlich():
    import importlib.util
    pfad = next((ROOT / "alembic" / "versions").glob(f"{MIGRATION}_*.py"))
    spec = importlib.util.spec_from_file_location("migration_portal_funktionen", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert modul.ANWEISUNGEN == funktionen.ANWEISUNGEN


def test_pruefwerte():
    assert pruefwerte.link("abc") == pruefwerte._sha256("dk-portal-link:abc") != pruefwerte.sitzung("abc")
    assert re.fullmatch(r"[0-9a-f]{64}", pruefwerte.sitzung(pruefwerte.neuer_wert()))
    s1, s2 = pruefwerte.sitzung("a"), pruefwerte.sitzung("b")
    assert pruefwerte.code(s1, "123456") != pruefwerte.code(s2, "123456")  # derselbe Code passt nur zu seiner Sitzung
    assert re.fullmatch(r"\d{6}", pruefwerte.neuer_code())
    assert pruefwerte.anschluss("192.0.2.1", SCHLUESSEL) != pruefwerte.anschluss("192.0.2.1", b"y" * 32)
    with pytest.raises(ValueError):
        pruefwerte.anschluss("192.0.2.1", b"kurz")
    with pytest.raises(ValueError):
        funktionen.anweisungen("public; DROP TABLE x")


# --- PostgreSQL ---------------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def pg():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_pfn_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        with engine.connect() as c:
            if c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": TESTROLLE}).first() is None:
                pytest.skip(f"Testrolle {TESTROLLE} fehlt (siehe tests/test_v799_portal_rechte.py)")
        Base.metadata.create_all(engine)  # legt die Funktionen an (app/database.py)
        with engine.begin() as c:
            c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            rechte.setzen(c, rolle=TESTROLLE, schema=schema)
            c.execute(text("INSERT INTO enabled_modules (module_key, enabled, updated_at) VALUES ('kundenportal', true, now())"))
        yield Welt(engine, schema)
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


class Welt:
    """Daten wie das ERP sie anlegt (als Benutzer des ERP) und Aufrufe wie das Portal (als Testrolle)."""

    def __init__(self, engine, schema):
        self.engine, self.schema, self._n = engine, schema, 0

    def erp(self, sql: str, **werte_):
        with self.engine.begin() as c:
            ergebnis = c.execute(text(sql), werte_)
            return ergebnis.fetchall() if ergebnis.returns_rows else None

    def kunde(self, *, portal=True, link="L", gueltig_tage=365, anrede="Herr", nachname="Muster"):
        """Kunde mit Zugang; gibt (kunde_id, zugang_id, Link-Wert) zurück."""
        self._n += 1
        link_wert = f"{link}{self._n}"
        kid = self.erp("INSERT INTO customers (name, salutation, last_name, first_name, created_at, portal_aktiv) VALUES "
                       "(:n, :a, :l, 'Max', now(), :p) RETURNING id", n=f"{anrede} Max {nachname}", a=anrede, l=nachname, p=portal)[0][0]
        zid = self.erp("INSERT INTO portal_zugaenge (customer_id, email, email_anzeige, link_sha256, link_erzeugt_am, gueltig_bis, angelegt_am) VALUES "
                       "(:k, 'max@example.invalid', 'm***@example.invalid', :l, now(), (now() AT TIME ZONE 'utc') + make_interval(days => :t), now()) "
                       "RETURNING id", k=kid, l=pruefwerte.link(link_wert), t=gueltig_tage)[0][0]
        return kid, zid, link_wert

    def als_portal(self, sql: str, **werte_):
        """Ein Aufruf als Testrolle in eigener Transaktion (committet) -- wie das Portal."""
        with self.engine.connect() as c:
            c.execute(text(f"SET ROLE {TESTROLLE}"))
            try:
                zeilen = c.execute(text(sql), werte_).fetchall()
                c.commit()
                return zeilen
            finally:
                c.rollback()
                c.execute(text("RESET ROLE"))
                c.commit()

    def oeffnen(self, link_wert, *, sitzung=None, neu=None, anschluss=HIER):
        neu = neu or pruefwerte.neuer_wert()
        zeile = self.als_portal("SELECT * FROM portal_link_oeffnen(:l, :a, :s, :n)", l=pruefwerte.link(link_wert), a=anschluss,
                                s=pruefwerte.sitzung(sitzung) if sitzung else None, n=pruefwerte.sitzung(neu))[0]
        return tuple(zeile), neu

    def anfordern(self, sitzung_wert, anschluss=HIER):
        return tuple(self.als_portal("SELECT * FROM portal_code_anfordern(:s, :a)", s=pruefwerte.sitzung(sitzung_wert), a=anschluss)[0])

    def code_anlegen(self, sitzung_wert, code="123456", minuten=10):
        """Wie der Postbote (P1c): Prüfwert des Codes an der unbestätigten Sitzung, frühere ersetzt."""
        s = pruefwerte.sitzung(sitzung_wert)
        sid = self.erp("SELECT id FROM portal_sitzungen WHERE wert_sha256 = :s", s=s)[0][0]
        self.erp("UPDATE portal_codes SET ersetzt_am = now() WHERE sitzung_id = :i AND verbraucht_am IS NULL AND ersetzt_am IS NULL", i=sid)
        self.erp("INSERT INTO portal_codes (sitzung_id, pruefwert, angelegt_am, gueltig_bis) VALUES (:i, :p, now() AT TIME ZONE 'utc', "
                 "(now() AT TIME ZONE 'utc') + make_interval(mins => :m))", i=sid, p=pruefwerte.code(s, code), m=minuten)
        return sid

    def pruefen(self, sitzung_wert, code, neu=None, anschluss=HIER):
        neu = neu or pruefwerte.neuer_wert()
        s = pruefwerte.sitzung(sitzung_wert)
        zeile = self.als_portal("SELECT * FROM portal_code_pruefen(:s, :p, :n, :a)", s=s, p=pruefwerte.code(s, code), n=pruefwerte.sitzung(neu), a=anschluss)[0]
        return tuple(zeile), neu

    def sitzung(self, wert):
        return self.als_portal("SELECT portal_sitzung(:s)", s=pruefwerte.sitzung(wert))[0][0]

    def angemeldet(self, link_wert):
        """Ein Gerät durch den ganzen Ablauf: Link, Code anfordern, Code anlegen (Postbote), Code richtig -- gibt den Wert des Cookies zurück."""
        (erg, _anzeige, _m), vorlaeufig = self.oeffnen(link_wert)
        assert erg == "code_noetig"
        assert self.anfordern(vorlaeufig) == ("angefordert", None)
        self.code_anlegen(vorlaeufig)
        (erg, _z), wert = self.pruefen(vorlaeufig, "123456")
        assert erg == "angemeldet"
        return wert

    def protokoll(self):
        return [tuple(r) for r in self.erp("SELECT aktion, ergebnis FROM portal_zugriffe ORDER BY id")]


def test_pg_link_oeffnen_legt_eine_unbestaetigte_sitzung_an(pg):
    _k, zid, link = pg.kunde()
    (erg, anzeige, minuten), neu = pg.oeffnen(link)
    assert (erg, anzeige, minuten) == ("code_noetig", "m***@example.invalid", None)
    angelegt, ab, bestaetigt = pg.erp("SELECT angelegt_am, laeuft_ab, bestaetigt_am FROM portal_sitzungen WHERE wert_sha256 = :s",
                                      s=pruefwerte.sitzung(neu))[0]
    assert ab - angelegt == timedelta(minutes=15) and bestaetigt is None  # Zeit der Datenbank
    assert pg.protokoll() == [("link_geoeffnet", "code_noetig")]
    assert pg.sitzung(neu) == "ungueltig"  # unbestätigt gilt nicht als Anmeldung


@pytest.mark.parametrize("grund", ["unbekannt", "gesperrt", "abgelaufen", "ohne_link", "portal_aus", "archiv", "modul_aus", "modul_ohne_zeile"])
def test_pg_jeder_grund_ist_aussen_gleich_und_im_protokoll_unterschieden(pg, grund):
    kid, zid, link = pg.kunde(portal=grund != "portal_aus", gueltig_tage=-1 if grund == "abgelaufen" else 365)
    if grund == "unbekannt":
        link = "gibt-es-nicht"
    elif grund == "gesperrt":
        pg.erp("UPDATE portal_zugaenge SET gesperrt_am = now(), gesperrt_grund = 'Test' WHERE id = :z", z=zid)
    elif grund == "ohne_link":
        pg.erp("UPDATE portal_zugaenge SET gueltig_bis = NULL WHERE id = :z", z=zid)
    elif grund == "archiv":
        pg.erp("UPDATE customers SET archiviert_am = now() WHERE id = :k", k=kid)
    elif grund == "modul_aus":
        pg.erp("UPDATE enabled_modules SET enabled = false WHERE module_key = 'kundenportal'")
    elif grund == "modul_ohne_zeile":
        pg.erp("DELETE FROM enabled_modules WHERE module_key = 'kundenportal'")
    (erg, anzeige, minuten), _ = pg.oeffnen(link)
    assert (erg, anzeige, minuten) == ("ungueltig", None, None)
    erwartet = {"ohne_link": "abgelaufen", "modul_ohne_zeile": "modul_aus"}.get(grund, grund)
    assert pg.protokoll() == [("link_geoeffnet", erwartet)]
    assert pg.erp("SELECT count(*) FROM portal_sitzungen")[0][0] == 0


def test_pg_mit_bestaetigter_sitzung_angemeldet_sonst_neue(pg):
    _k, _z, link = pg.kunde()
    _k2, _z2, link2 = pg.kunde()
    wert = pg.angemeldet(link)
    assert pg.sitzung(wert) == "gueltig"
    assert pg.oeffnen(link, sitzung=wert)[0] == ("angemeldet", None, None)
    assert pg.oeffnen(link2, sitzung=wert)[0][0] == "code_noetig"  # die Sitzung gehört zu einem anderen Zugang


def test_pg_bremse_link_je_anschluss(pg):
    _k, _z, link = pg.kunde()
    for _ in range(30):
        assert pg.oeffnen(link)[0][0] == "code_noetig"
    (erg, _a, minuten), _ = pg.oeffnen(link)
    assert erg == "bremse" and 1 <= minuten <= 60
    assert pg.oeffnen(link, anschluss=pruefwerte.anschluss("192.0.2.11", SCHLUESSEL))[0][0] == "code_noetig"  # ein anderer Anschluss nicht


def test_pg_code_anfordern_auftrag_und_notify_beim_commit(pg):
    _k, zid, link = pg.kunde()
    (_e, _a, _m), wert = pg.oeffnen(link)
    roh = pg.engine.raw_connection()
    try:
        roh.driver_connection.autocommit = True
        roh.driver_connection.execute("LISTEN portal_post")
        # Seit 1.11.18: NOTIFY gilt für die ganze Datenbank, nicht je Schema -- im parallelen Lauf fordern andere Testprozesse in ihren Wegwerf-Schemas
        # zugleich Codes an (test_v802, test_v805), ihre Weckrufe kommen hier mit an. Gezählt wird nur der Weckruf der Verbindung, die anfordert (pid);
        # ein fremder Weckruf steht zur Probe immer mit dabei.
        roh.driver_connection.execute("NOTIFY portal_post")
        assert pg.als_portal("SELECT portal_post_stand(:s)", s=pruefwerte.sitzung(wert))[0][0] == "keiner"
        with pg.engine.connect() as c:
            pid = c.execute(text("SELECT pg_backend_pid()")).scalar()
            c.execute(text(f"SET ROLE {TESTROLLE}"))
            ergebnis = tuple(c.execute(text("SELECT * FROM portal_code_anfordern(:s, :a)"), {"s": pruefwerte.sitzung(wert), "a": HIER}).fetchall()[0])
            c.commit()
            c.execute(text("RESET ROLE"))
            c.commit()
        assert ergebnis == ("angefordert", None)
        meldungen = list(roh.driver_connection.notifies(timeout=2))
        assert any(m.pid != pid for m in meldungen)  # der fremde Weckruf kam an
        assert [(m.channel, m.payload) for m in meldungen if m.pid == pid] == [("portal_post", "")]  # nur ein Weckruf, kein Inhalt
    finally:
        roh.close()
    assert pg.erp("SELECT art, zugang_id, status FROM portal_post") == [("code", zid, "wartet")]
    assert pg.als_portal("SELECT portal_post_stand(:s)", s=pruefwerte.sitzung(wert))[0][0] == "wartet"
    pg.erp("UPDATE portal_post SET status = 'gesendet'")
    assert pg.als_portal("SELECT portal_post_stand(:s)", s=pruefwerte.sitzung(wert))[0][0] == "gesendet"
    assert pg.anfordern(wert) == ("bremse", 1)  # ein neuer Code frühestens nach 60 Sekunden
    pg.erp("UPDATE portal_post SET angefordert_am = angefordert_am - interval '2 minutes'")
    assert pg.anfordern(wert) == ("angefordert", None)


def test_pg_code_anfordern_grenze_je_zugang(pg):
    _k, _z, link = pg.kunde()
    ergebnisse = [pg.anfordern(pg.oeffnen(link)[1])[0] for _ in range(4)]  # vier Geräte, je eine Sitzung
    assert ergebnisse == ["angefordert"] * 3 + ["bremse"]
    assert pg.erp("SELECT count(*) FROM portal_post")[0][0] == 3


def test_pg_code_nur_fuer_unbestaetigte_gueltige_sitzungen(pg):
    _k, _z, link = pg.kunde()
    wert = pg.angemeldet(link)
    assert pg.anfordern(wert) == ("ungueltig", None)  # bestätigt
    (_e, _a, _m), alt = pg.oeffnen(link)
    pg.erp("UPDATE portal_sitzungen SET laeuft_ab = now() AT TIME ZONE 'utc' - interval '1 minute' WHERE wert_sha256 = :s", s=pruefwerte.sitzung(alt))
    assert pg.anfordern(alt) == ("ungueltig", None)  # abgelaufen
    assert pg.anfordern(pruefwerte.neuer_wert()) == ("ungueltig", None)  # unbekannt


def test_pg_code_pruefen_falsch_versuche_richtig(pg):
    _k, zid, link = pg.kunde()
    (_e, _a, _m), wert = pg.oeffnen(link)
    pg.anfordern(wert)
    pg.code_anlegen(wert, "123456")
    assert [pg.pruefen(wert, "000000")[0] for _ in range(5)] == [("falsch", 4), ("falsch", 3), ("falsch", 2), ("falsch", 1), ("falsch", 0)]
    assert pg.pruefen(wert, "123456")[0] == ("neu_anfordern", None)  # nach 5 Versuchen gilt auch der richtige nicht mehr
    pg.code_anlegen(wert, "654321")
    (erg, _z), neu = pg.pruefen(wert, "654321")
    assert erg == "angemeldet"
    assert pg.sitzung(neu) == "gueltig" and pg.sitzung(wert) == "ungueltig"  # neuer Wert nach dem Code -- der alte nützt nichts
    bestaetigt, ab, zuletzt = pg.erp("SELECT bestaetigt_am, laeuft_ab, zuletzt_am FROM portal_sitzungen WHERE wert_sha256 = :s",
                                     s=pruefwerte.sitzung(neu))[0]
    assert ab - bestaetigt == timedelta(days=30) and zuletzt == bestaetigt
    assert pg.erp("SELECT count(*) FROM portal_codes WHERE verbraucht_am IS NOT NULL")[0][0] == 1
    assert pg.erp("SELECT zuletzt_genutzt_am IS NOT NULL FROM portal_zugaenge WHERE id = :z", z=zid)[0][0] is True
    assert pg.pruefen(wert, "654321")[0] == ("ungueltig", None)  # derselbe Code noch einmal: die Sitzung ist keine unbestätigte mehr
    assert ("angemeldet", "ok") in pg.protokoll() and pg.protokoll().count(("code_falsch", "ungueltig")) == 5


def test_pg_code_abgelaufen_und_fremde_sitzung(pg):
    _k, _z, link = pg.kunde()
    (_e, _a, _m), wert = pg.oeffnen(link)
    (_e, _a, _m), andere = pg.oeffnen(link)
    pg.code_anlegen(wert, "123456", minuten=-1)
    assert pg.pruefen(wert, "123456")[0] == ("neu_anfordern", None)
    pg.code_anlegen(wert, "123456")
    assert pg.pruefen(andere, "123456")[0] == ("neu_anfordern", None)  # der Code gehört zu einer anderen Sitzung
    assert pg.pruefen(wert, "123456")[0][0] == "angemeldet"


def _wartet_auf_sperre(pg, grenze: float = 20.0) -> bool:
    """Bis eine Verbindung dieses Schemas nachweislich auf eine Sperre wartet (pg_stat_activity) -- nie eine feste Zeit."""
    import time
    ende = time.monotonic() + grenze
    while time.monotonic() < ende:
        if pg.erp("SELECT count(*) FROM pg_stat_activity WHERE application_name = :n AND wait_event_type = 'Lock'", n=pg.schema)[0][0]:
            return True
        time.sleep(0.05)
    return False


def test_pg_zwei_richtige_codes_gleichzeitig_nur_einer(pg):
    """Die erste Eingabe hält ihre Sperren (noch nicht festgeschrieben), die zweite wartet nachweislich am Zugang; danach sieht sie die bestätigte Sitzung
    und ist „ungueltig“. Ohne die Sperre von Zugang und Sitzung käme sie bis zum Code und bekäme „neu_anfordern“ -- oder gewönne ebenfalls."""
    _k, _z, link = pg.kunde()
    (_e, _a, _m), wert = pg.oeffnen(link)
    pg.code_anlegen(wert, "123456")
    s = pruefwerte.sitzung(wert)
    zweite = {}
    with pg.engine.connect() as erste:
        erste.execute(text(f"SET ROLE {TESTROLLE}"))
        try:
            ergebnis = erste.execute(text("SELECT * FROM portal_code_pruefen(:s, :p, :n, :a)"),
                                     {"s": s, "p": pruefwerte.code(s, "123456"), "n": pruefwerte.sitzung(pruefwerte.neuer_wert()), "a": HIER}).one()
            # ein zweites Gerät an einem anderen Anschluss -- derselbe Anschluss reihte beide schon an der Zählerzeile der Bremse hintereinander
            anderer = pruefwerte.anschluss("192.0.2.20", SCHLUESSEL)
            faden = threading.Thread(target=lambda: zweite.setdefault("e", pg.pruefen(wert, "123456", anschluss=anderer)[0][0]))
            faden.start()
            assert _wartet_auf_sperre(pg), "die zweite Eingabe wartet nicht auf eine Sperre"
            erste.commit()
        finally:
            erste.rollback()
            erste.execute(text("RESET ROLE"))
            erste.commit()
    faden.join(30)
    assert (tuple(ergebnis), zweite.get("e")) == (("angemeldet", None), "ungueltig")
    assert pg.erp("SELECT count(*) FROM portal_sitzungen WHERE bestaetigt_am IS NOT NULL")[0][0] == 1


def test_pg_weiter_hoechstens_einmal_je_stunde(pg):
    _k, _z, link = pg.kunde()
    wert = pg.angemeldet(link)
    s = pruefwerte.sitzung(wert)
    assert pg.als_portal("SELECT portal_sitzung_weiter(:s)", s=s)[0][0] == "gueltig"
    pg.erp("UPDATE portal_sitzungen SET zuletzt_am = zuletzt_am - interval '2 hours', laeuft_ab = laeuft_ab - interval '2 hours' WHERE wert_sha256 = :s", s=s)
    assert pg.als_portal("SELECT portal_sitzung_weiter(:s)", s=s)[0][0] == "verlaengert"
    zuletzt, ab = pg.erp("SELECT zuletzt_am, laeuft_ab FROM portal_sitzungen WHERE wert_sha256 = :s", s=s)[0]
    assert ab - zuletzt == timedelta(days=30)
    assert ("verlaengert", "ok") in pg.protokoll()
    assert pg.als_portal("SELECT portal_sitzung_weiter(:s)", s=pruefwerte.sitzung("unbekannt"))[0][0] == "ungueltig"


def test_pg_abmelden_ein_geraet_und_alle(pg):
    _k, _z, link = pg.kunde()
    a, b = pg.angemeldet(link), pg.angemeldet(link)
    (_e, _x, _m), vorlaeufig = pg.oeffnen(link)
    assert pg.als_portal("SELECT portal_abmelden(:s, true)", s=pruefwerte.sitzung(vorlaeufig))[0][0] == "ungueltig"  # alle nur bestätigt
    assert pg.sitzung(a) == pg.sitzung(b) == "gueltig"
    assert pg.als_portal("SELECT portal_abmelden(:s, false)", s=pruefwerte.sitzung(a))[0][0] == "abgemeldet"
    assert (pg.sitzung(a), pg.sitzung(b)) == ("ungueltig", "gueltig")
    c = pg.angemeldet(link)
    assert pg.als_portal("SELECT portal_abmelden(:s, true)", s=pruefwerte.sitzung(c))[0][0] == "abgemeldet"
    assert (pg.sitzung(b), pg.sitzung(c)) == ("ungueltig", "ungueltig")
    gruende = [r[0] for r in pg.erp("SELECT beendet_grund FROM portal_sitzungen WHERE beendet_am IS NOT NULL ORDER BY id")]
    assert gruende.count("abgemeldet") == 1 and gruende.count("ueberall") == 3  # b, c und die unbestätigte


def test_pg_willkommen_nur_mit_bestaetigter_sitzung(pg):
    _k, _z, link = pg.kunde(anrede="Frau", nachname="Beispiel")
    wert = pg.angemeldet(link)
    assert [tuple(r) for r in pg.als_portal("SELECT * FROM portal_willkommen(:s)", s=pruefwerte.sitzung(wert))] == [
        ("Frau", None, "Max", "Beispiel", "Frau Max Beispiel")]
    assert pg.als_portal("SELECT * FROM portal_willkommen(:s)", s=pruefwerte.sitzung("unbekannt")) == []


@pytest.mark.parametrize("aenderung", ["gesperrt", "portal_aus", "archiv", "modul_aus", "abgelaufen"])
def test_pg_jede_sperre_beendet_die_sitzung_sofort(pg, aenderung):
    kid, zid, link = pg.kunde()
    wert = pg.angemeldet(link)
    sql = {"gesperrt": "UPDATE portal_zugaenge SET gesperrt_am = now() WHERE id = :z",
           "portal_aus": "UPDATE customers SET portal_aktiv = false WHERE id = (SELECT customer_id FROM portal_zugaenge WHERE id = :z)",
           "archiv": "UPDATE customers SET archiviert_am = now() WHERE id = (SELECT customer_id FROM portal_zugaenge WHERE id = :z)",
           "modul_aus": "UPDATE enabled_modules SET enabled = false WHERE :z > 0",
           "abgelaufen": "UPDATE portal_zugaenge SET gueltig_bis = now() AT TIME ZONE 'utc' - interval '1 minute' WHERE id = :z"}[aenderung]
    pg.erp(sql, z=zid)
    s = pruefwerte.sitzung(wert)
    assert pg.sitzung(wert) == "ungueltig"
    assert pg.als_portal("SELECT portal_sitzung_weiter(:s)", s=s)[0][0] == "ungueltig"
    assert pg.als_portal("SELECT * FROM portal_willkommen(:s)", s=s) == []


def test_pg_die_rolle_liest_keine_tabelle_und_keinen_helfer(pg):
    for sql in ("SELECT * FROM portal_sitzungen", "SELECT * FROM portal_zugaenge", "SELECT name FROM customers", "SELECT * FROM portal_codes",
                "SELECT portal_jetzt()", "SELECT portal_bremse('x', 1, interval '1 hour')", "SELECT portal_zugang_grund(1)",
                "SELECT portal_sitzung_id('x', true)", "SELECT portal_protokoll(NULL, NULL, 'abgemeldet', 'ok')"):
        with pytest.raises(ProgrammingError) as fehler:
            pg.als_portal(sql)
        assert fehler.value.orig.sqlstate == "42501", sql
    with pg.engine.connect() as c:
        assert rechte.pruefen(c, rolle=TESTROLLE, schema=pg.schema) == []


@pytest.mark.parametrize("eingabe", ["", "x", "'; DROP TABLE portal_sitzungen; --", "A" * 64, "0" * 63, "0" * 65, None])
def test_pg_eingaben_ohne_pruefwert_schreiben_nichts(pg, eingabe):
    _k, _z, link = pg.kunde()
    vorher = pg.erp("SELECT (SELECT count(*) FROM portal_sitzungen), (SELECT count(*) FROM portal_post), (SELECT count(*) FROM portal_bremsen)")
    gut = pruefwerte.sitzung("gut")
    assert pg.als_portal("SELECT ergebnis FROM portal_link_oeffnen(:l, :a, NULL, :n)", l=eingabe, a=HIER, n=gut)[0][0] == "ungueltig"
    assert pg.als_portal("SELECT ergebnis FROM portal_link_oeffnen(:l, :a, NULL, :n)", l=pruefwerte.link(link), a=eingabe, n=gut)[0][0] == "ungueltig"
    assert pg.als_portal("SELECT ergebnis FROM portal_code_anfordern(:s, :a)", s=eingabe, a=HIER)[0][0] == "ungueltig"
    assert pg.als_portal("SELECT ergebnis FROM portal_code_pruefen(:s, :p, :n, :a)", s=gut, p=eingabe, n=gut, a=HIER)[0][0] == "ungueltig"
    assert pg.als_portal("SELECT portal_sitzung(:s)", s=eingabe)[0][0] == "ungueltig"
    assert pg.als_portal("SELECT portal_abmelden(:s, true)", s=eingabe)[0][0] == "ungueltig"
    assert pg.erp("SELECT (SELECT count(*) FROM portal_sitzungen), (SELECT count(*) FROM portal_post), (SELECT count(*) FROM portal_bremsen)") == vorher
    assert pg.erp("SELECT to_regclass('portal_sitzungen') IS NOT NULL")[0][0] is True


def test_pg_create_all_legt_die_funktionen_an():
    """Testschemas und die lokale Entwicklung bekommen die Funktionen aus jedem create_all() (app/database.py), mit dem Schema im festen search_path."""
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_pfa_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    try:
        Base.metadata.create_all(engine)
        with engine.connect() as c:
            namen = [r[0] for r in c.execute(text(
                "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = :s AND p.proname LIKE 'portal!_%' "
                "ESCAPE '!' AND array_to_string(p.proconfig, ',') = :cfg ORDER BY 1"), {"s": schema, "cfg": f"search_path=pg_catalog, {schema}, pg_temp"})]
        # 14 aus P1, seit 1.11.31 dazu Helfer und Funktionen der Unterlagen (P2a)
        assert len(namen) == 14 + len(unterlagen._HELFER) + len(unterlagen._FUNKTIONEN) and set(rechte.FUNKTIONEN) <= set(namen)
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_pg_migration_hinauf_und_herab():
    if not PG_URL:
        pytest.skip("ERP_TEST_POSTGRES_URL nicht gesetzt -- PostgreSQL-Testlauf ist bewusst opt-in.")
    schema = f"pgtest_mig_pfn_{uuid.uuid4().hex[:8]}"
    admin = create_engine(PG_URL)
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = f"{PG_URL}{'&' if '?' in PG_URL else '?'}options=-csearch_path={schema}"
    engine = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}", "application_name": schema})
    abfrage = ("SELECT p.proname, array_to_string(p.proconfig, ',') FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
               "WHERE n.nspname = :s AND p.proname LIKE 'portal!_%' ESCAPE '!' ORDER BY 1")
    try:
        _ok(_alembic(url, "upgrade", VORHER))
        _ok(_alembic(url, "upgrade", MIGRATION))
        with engine.connect() as c:
            angelegt = c.execute(text(abfrage), {"s": schema}).all()
            offen = c.execute(text("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = :s "
                                   "AND p.proname LIKE 'portal!_%' ESCAPE '!' AND (p.proacl IS NULL OR p.proacl::text LIKE '{=X%' "
                                   "OR p.proacl::text LIKE '%,=X%')"), {"s": schema}).scalar()
        assert len(angelegt) == 14 and all(cfg == f"search_path=pg_catalog, {schema}, pg_temp" for _n, cfg in angelegt), angelegt
        assert offen == 0  # keine für alle ausführbar
        _ok(_alembic(url, "downgrade", VORHER))
        with engine.connect() as c:
            assert c.execute(text(abfrage), {"s": schema}).all() == []
        _ok(_alembic(url, "upgrade", "head"))
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :n"), {"n": schema})
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_migration_unter_sqlite_ohne_funktionen(tmp_path):
    url = f"sqlite:///{(tmp_path / 'pfn.db').as_posix()}"
    _ok(_alembic(url, "upgrade", MIGRATION))
    _ok(_alembic(url, "downgrade", VORHER))
