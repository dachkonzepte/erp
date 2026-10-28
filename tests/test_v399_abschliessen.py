"""Version 1.8.96 -- Zeitlimit im Baustein und abschließende Aktionen (app/templates/_speichern.html; Vorgabe 1.8.96 Punkte 1 und 2).

Punkt 1: Kommt auf ein Speichern 60 s nach dem Senden keine Antwort, bricht der Baustein die Anfrage ab; der Bereich ist "unklar",
der Fehler sagt das und bittet um Neuladen und Prüfen (dazu ein Hinweis oben auf der Seite); wartende und neue Speichervorgänge des
Bereichs gehen nicht mehr hinaus; solange etwas läuft oder wartet, warnt die Seite beim Verlassen.

Punkt 2: Abschließende Aktionen (Unterschrift, Festschreiben, Versand, Buchung, Storno u. ä.) gehen über abschliessen(): erst wenn
jedes Speichern der Seite, das beim Klick lief oder wartete, zurück ist -- und gar nicht, wenn eines davon gescheitert ist. Die Liste
dieser Aufrufe steht unten (ABSCHLIESSEND); der Strukturtest prüft jede Vorlage dagegen.

Hier: der Baustein in node (Zeitlimit mit kurzem window.__dkZeitlimit), Warnung beim Verlassen und Hinweis mit gestelltem window/
document, abschliessen() samt zurückgehaltener Eingabe aus _debounce.html; der Strukturtest über die Liste."""

import re
from pathlib import Path

import pytest

from tests import vorlagen_js as vj
from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v398_speichern_baustein import _ablauf

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")

UNKLAR = "unklar, ob gespeichert wurde. Bitte die Seite neu laden und prüfen."
NICHT_GESENDET = "Nicht gesendet: ein Speichern davor blieb ohne Antwort"
GESCHEITERT = "Nicht ausgeführt: ein Speichern auf der Seite ist gescheitert (kaputt S1). Bitte prüfen und erneut versuchen."


def _debounce_js() -> str:
    return re.search(r"<script>(.*?)</script>", (TEMPLATES / "_debounce.html").read_text(encoding="utf-8"), flags=re.S).group(1)


# Gestelltes window.addEventListener und document für Warnung und Hinweis (vor dem Baustein).
SEITE = """
globalThis.__ereignisse=[];
globalThis.addEventListener=(typ,f)=>{globalThis.__ereignisse.push('lauscht '+typ);globalThis.__verlassen=f};
const __elemente={};
globalThis.document={
  body:{appendChild(el){__elemente[el.id]=el;globalThis.__ereignisse.push('hinweis')}},
  getElementById:id=>__elemente[id]||null,
  createElement:tag=>({tag,style:{},kinder:[],setAttribute(){},append(...k){this.kinder.push(...k)},
    querySelector(sel){return this.kinder.find(k=>k.className===sel.slice(1))||null}}),
};
globalThis.location={reload(){globalThis.__ereignisse.push('neu laden')}};
function verlassen(){const ev={preventDefault(){ev.verhindert=true}};const r=globalThis.__verlassen(ev);return !!ev.verhindert&&ev.returnValue===''&&r===''}
"""


# --- Punkt 1: Zeitlimit ----------------------------------------------------------------------------------------------------

@nur_mit_node
def test_a_save_without_answer_is_aborted_after_the_time_limit():
    log = _ablauf("""
        const s=speichern('form',anfrage('S1'),{anwenden:anwenden()}).then(()=>'kein',e=>e.message+' | '+e.dkBaustein);
        await warte(400);
        log.push('ergebnis '+(await s));
        await antworte('S1');  // kommt die Antwort danach doch noch, wird nichts angewandt
    """, zeitlimit=150)
    assert log[:2] == ["gesendet S1", "abgebrochen S1"]
    assert log[2].startswith("ergebnis Keine Antwort vom Server nach 0 Sekunden") and UNKLAR in log[2] and log[2].endswith("| unklar")
    assert len(log) == 3


@nur_mit_node
def test_a_late_answer_is_not_applied_even_if_the_request_ignores_the_abort():
    """Eine Anfrage, die das Abbruchsignal nicht weiterreicht, endet trotzdem mit dem Zeitlimit; ihre späte Antwort bleibt
    unangewandt."""
    log = _ablauf("""
        const roh=globalThis.fetch;globalThis.fetch=name=>roh(name);  // ohne init: kein Signal
        const s=speichern('form',anfrage('S1','spät'),{anwenden:anwenden()}).then(()=>'kein',e=>e.dkBaustein);
        await warte(300); log.push('ergebnis '+(await s));
        await antworte('S1'); await ruhe();
    """, zeitlimit=100)
    assert log == ["gesendet S1", "ergebnis unklar"]


@nur_mit_node
def test_an_answer_in_time_is_not_aborted():
    log = _ablauf("""
        const s=speichern('form',anfrage('S1'),{anwenden:anwenden()});
        await ruhe(); await antworte('S1'); await s; await warte(300);
    """, zeitlimit=100)
    assert log == ["gesendet S1", 'angewandt "S1"']


@nur_mit_node
def test_after_a_timeout_waiting_and_new_saves_of_the_area_are_not_sent():
    log = _ablauf("""
        const s1=speichern('form',anfrage('S1')).catch(e=>e.dkBaustein);
        const s2=speichern('form',anfrage('S2')).then(()=>'kein',e=>e.message);
        const t1=speichern('anders',anfrage('T1'));
        await ruhe(); await antworte('T1'); await t1;
        log.push('s1 '+(await s1)); log.push('s2 '+(await s2));
        const s3=await speichern('form',anfrage('S3')).then(()=>'kein',e=>e.dkBaustein);
        log.push('s3 '+s3);
        const t2=speichern('anders',anfrage('T2')); await ruhe(); await antworte('T2'); await t2;
        const l=lesen('form',anfrage('L1','frisch'),anwenden()); await ruhe(); await antworte('L1'); log.push('lesen '+(await l));
    """, zeitlimit=150)
    assert log[:4] == ["gesendet S1", "gesendet T1", "abgebrochen S1", "s1 unklar"]
    assert log[4].startswith("s2 " + NICHT_GESENDET) and log[4].endswith("Bitte die Seite neu laden und prüfen.")
    assert log[5:] == ["s3 nicht-gesendet", "gesendet T2", "gesendet L1", 'angewandt "frisch"', "lesen true"]
    assert "gesendet S2" not in log and "gesendet S3" not in log


@nur_mit_node
def test_the_page_shows_a_notice_with_reload_after_a_timeout():
    log = _ablauf("""
        await speichern('form',anfrage('S1')).catch(()=>{});
        const el=document.getElementById('dkSpeichernUnklar');
        log.push(el.kinder[0].textContent);
        el.kinder[1].onclick();
        log.push(JSON.stringify(globalThis.__ereignisse));
    """, zeitlimit=100, vorspann=SEITE)
    assert log[:2] == ["gesendet S1", "abgebrochen S1"]
    assert log[2].startswith("Keine Antwort vom Server") and UNKLAR in log[2]
    assert log[3] == '["lauscht beforeunload","hinweis","neu laden"]'


@nur_mit_node
def test_leaving_the_page_warns_while_a_save_runs_or_waits():
    log = _ablauf("""
        log.push('ruhig '+verlassen());
        const s1=speichern('form',anfrage('S1')),s2=speichern('form',anfrage('S2'));
        await ruhe(); log.push('läuft '+verlassen());
        await antworte('S1'); log.push('wartet '+verlassen());
        await antworte('S2'); await s1; await s2; log.push('fertig '+verlassen());
        const l=lesen('form',anfrage('L1')); await ruhe(); log.push('lesen '+verlassen()); await antworte('L1'); await l;
    """, vorspann=SEITE, baustein_zweimal=True)
    assert [x for x in log if not x.startswith("gesendet")] == [
        "ruhig false", "läuft true", "wartet true", "fertig false", "lesen false"]


@nur_mit_node
def test_the_leave_warning_is_registered_once_even_if_included_twice():
    log = _ablauf("log.push(JSON.stringify(globalThis.__ereignisse))", vorspann=SEITE, baustein_zweimal=True)
    assert log == ['["lauscht beforeunload"]']


# --- Punkt 2: abschliessen() -----------------------------------------------------------------------------------------------

@nur_mit_node
def test_a_final_action_waits_for_a_running_save_of_another_area():
    log = _ablauf("""
        const s=speichern('feld',anfrage('S1'));
        const a=abschliessen('unterschrift',anfrage('U1'),{anwenden:anwenden()});
        await ruhe(); log.push('-'); await antworte('S1'); await ruhe(); await antworte('U1'); await a;
    """)
    assert log == ["gesendet S1", "-", "gesendet U1", 'angewandt "U1"']


@nur_mit_node
def test_a_final_action_waits_for_a_waiting_save_too():
    log = _ablauf("""
        speichern('feld',anfrage('S1')); speichern('feld',anfrage('S2'));
        const a=abschliessen('unterschrift',anfrage('U1'));
        await ruhe(); await antworte('S1'); log.push('-'); await antworte('S2'); await ruhe(); await antworte('U1'); await a;
    """)
    assert log == ["gesendet S1", "gesendet S2", "-", "gesendet U1"]


@nur_mit_node
def test_a_final_action_does_not_run_if_a_running_save_fails():
    """Seit 1.8.99 (Festlegung 1.8.96 Nr. 7, korrigiert) sperrt das gescheiterte Speichern auch die nächste abschließende Aktion, bis ein
    Speichern im selben Bereich gelingt -- bis 1.8.98 ging U2 (nach dem Scheitern geklickt) hinaus."""
    log = _ablauf("""
        speichern('feld',anfrage('S1')).catch(()=>{});
        const a=abschliessen('unterschrift',anfrage('U1'),{anwenden:anwenden()}).then(()=>'kein',e=>e.message+' | '+e.dkBaustein);
        await ruhe(); await scheitere('S1'); log.push('ergebnis '+(await a));
        const b=await abschliessen('unterschrift',anfrage('U2')).then(()=>'kein',e=>e.dkBaustein); log.push('U2 '+b);
        const s=speichern('feld',anfrage('S2')); await ruhe(); await antworte('S2'); await s;
        const c=abschliessen('unterschrift',anfrage('U3')); await ruhe(); await antworte('U3'); await c;
    """)
    assert log == ["gesendet S1", "ergebnis " + GESCHEITERT + " | abschluss", "U2 abschluss", "gesendet S2", "gesendet U3"]


@nur_mit_node
def test_an_error_status_counts_as_failed():
    log = _ablauf("""
        speichern('feld',()=>fetch('S1'));
        const a=abschliessen('unterschrift',anfrage('U1')).then(()=>'kein',e=>e.message);
        await ruhe(); await antworte('S1',new Response('{}',{status:409})); log.push('ergebnis '+(await a));
    """)
    assert log == ["gesendet S1", "ergebnis Nicht ausgeführt: ein Speichern auf der Seite ist gescheitert (Status 409). "
                                  "Bitte prüfen und erneut versuchen."]


@nur_mit_node
def test_a_save_failed_before_the_click_blocks_until_a_later_save_of_the_same_area_succeeds():
    """Seit 1.8.99 (Festlegung 1.8.96 Nr. 7, korrigiert; vorher test_a_save_failed_before_the_click_does_not_block, Soll bis 1.8.98:
    U1 gesendet): ein gescheitertes Speichern ohne nachfolgendes erfolgreiches im selben Bereich sperrt abschließende Aktionen wie
    "unklar" -- auch wenn es vor dem Klick gescheitert ist. Ein erfolgreiches Speichern in einem anderen Bereich hebt das nicht auf, eins
    im selben Bereich schon."""
    log = _ablauf("""
        const s=speichern('feld',anfrage('S1')).catch(()=>{}); await ruhe(); await scheitere('S1'); await s;
        log.push('U1 '+await abschliessen('unterschrift',anfrage('U1')).then(()=>'kein',e=>e.message+' | '+e.dkBaustein));
        const t=speichern('anders',anfrage('T1')); await ruhe(); await antworte('T1'); await t;
        log.push('U2 '+await abschliessen('unterschrift',anfrage('U2')).then(()=>'kein',e=>e.dkBaustein));
        const s2=speichern('feld',anfrage('S2')); await ruhe(); await antworte('S2'); await s2;
        const a=abschliessen('unterschrift',anfrage('U3')); await ruhe(); await antworte('U3'); await a;
    """)
    assert log == ["gesendet S1", "U1 " + GESCHEITERT + " | abschluss", "gesendet T1", "U2 abschluss", "gesendet S2", "gesendet U3"]


@nur_mit_node
def test_an_error_status_before_the_click_blocks_too():
    log = _ablauf("""
        const s=speichern('feld',()=>fetch('S1')); await ruhe(); await antworte('S1',new Response('{}',{status:422})); await s;
        log.push('U1 '+await abschliessen('unterschrift',anfrage('U1')).then(()=>'kein',e=>e.message));
    """)
    assert log == ["gesendet S1", "U1 Nicht ausgeführt: ein Speichern auf der Seite ist gescheitert (Status 422). Bitte prüfen und "
                                  "erneut versuchen."]


@nur_mit_node
def test_a_final_action_refused_by_the_server_does_not_block_another():
    """Nur Speichern sperrt: eine abschließende Aktion, die der Server ablehnt (Fehlerstatus oder Fehler), hält die nächste nicht auf."""
    log = _ablauf("""
        const a=abschliessen('versand',()=>fetch('V1')); await ruhe(); await antworte('V1',new Response('{}',{status:409})); await a;
        const b=abschliessen('versand',anfrage('V2')).catch(e=>e.message); await ruhe(); await scheitere('V2'); await b;
        const c=abschliessen('unterschrift',anfrage('U1')); await ruhe(); await antworte('U1'); await c;
    """)
    assert log == ["gesendet V1", "gesendet V2", "gesendet U1"]


@nur_mit_node
def test_an_unclear_final_action_blocks_further_final_actions():
    """Eine abschließende Aktion ohne Antwort (Zeitlimit) macht ihren Bereich unklar -- danach geht keine weitere hinaus (Festlegung
    1.8.96 Nr. 9)."""
    log = _ablauf("""
        await abschliessen('versand',anfrage('V1')).catch(()=>{});
        log.push('U1 '+await abschliessen('unterschrift',anfrage('U1')).then(()=>'kein',e=>e.dkBaustein));
    """, zeitlimit=100)
    assert log == ["gesendet V1", "abgebrochen V1", "U1 abschluss"]


@nur_mit_node
def test_a_failed_read_does_not_block():
    log = _ablauf("""
        const l=lesen('feld',anfrage('L1'),anwenden()).catch(()=>{}); await ruhe(); await scheitere('L1'); await l;
        const a=abschliessen('unterschrift',anfrage('U1')); await ruhe(); await antworte('U1'); await a;
    """)
    assert log == ["gesendet L1", "gesendet U1"]


@nur_mit_node
def test_a_save_started_after_the_click_is_not_awaited():
    log = _ablauf("""
        const a=abschliessen('unterschrift',anfrage('U1')); const s=speichern('feld',anfrage('S2'));
        await ruhe(); log.push('-'); await antworte('U1'); await antworte('S2'); await a; await s;
    """)
    assert sorted(log[:2]) == ["gesendet S2", "gesendet U1"] and log[2:] == ["-"]


@nur_mit_node
def test_a_final_action_is_refused_while_an_area_is_unclear():
    log = _ablauf("""
        await speichern('feld',anfrage('S1')).catch(()=>{});
        const a=await abschliessen('unterschrift',anfrage('U1')).then(()=>'kein',e=>e.message+' | '+e.dkBaustein);
        log.push('ergebnis '+a);
    """, zeitlimit=100)
    assert log == ["gesendet S1", "abgebrochen S1",
                   "ergebnis Nicht ausgeführt: bei einem Speichern auf der Seite ist unklar, ob es gespeichert wurde. Bitte die Seite "
                   "neu laden und prüfen. | abschluss"]


@nur_mit_node
def test_a_held_back_input_is_saved_before_the_final_action():
    """Eine Eingabe, die _debounce.html noch zurückhält (Speichern erst 600 ms nach der letzten Taste), geht vor der Unterschrift
    hinaus -- und danach nicht noch einmal."""
    log = _ablauf(_debounce_js() + """
        const notiz=debounce(text=>speichern('feld',anfrage('E '+text)),60000);
        notiz('Dach'); notiz('Dach dicht');
        const a=abschliessen('unterschrift',anfrage('U1'));
        await ruhe(); log.push('-'); await antworte('E Dach dicht'); await ruhe(); await antworte('U1'); await a;
        log.push('wartend '+window.__dkEntprellt.size);
    """)
    assert log == ["gesendet E Dach dicht", "-", "gesendet U1", "wartend 0"]


@nur_mit_node
def test_a_final_action_in_the_same_area_queues_like_a_save():
    log = _ablauf("""
        const s=speichern('checkliste',anfrage('S1'),{anwenden:anwenden()});
        const a=abschliessen('checkliste',anfrage('U1','unterschrieben'),{anwenden:anwenden()});
        await ruhe(); log.push('-'); await antworte('S1'); await ruhe(); await antworte('U1'); await s; await a;
    """)
    assert log == ["gesendet S1", "-", 'angewandt "S1"', "gesendet U1", 'angewandt "unterschrieben"']


@nur_mit_node
def test_two_final_actions_after_a_failed_save_are_both_refused_naming_it():
    """Zwei abschließende Aktionen, beide nach dem Speichern geklickt: beide laufen nicht, die Meldung nennt das gescheiterte
    Speichern -- die zweite wegen dieses Speicherns, nicht wegen der ersten Aktion (eine abgelehnte abschließende Aktion sperrt keine
    weitere; bis 1.8.98 stand hier "die erste Aktion zählt für die zweite ebenfalls als gescheitert")."""
    log = _ablauf("""
        speichern('feld',anfrage('S1')).catch(()=>{});
        const a=abschliessen('versand',anfrage('V1')).catch(e=>e.dkBaustein);
        const b=abschliessen('unterschrift',anfrage('U1')).then(()=>'kein',e=>e.message);
        await ruhe(); await scheitere('S1'); log.push('a '+(await a)); log.push('b '+(await b));
    """)
    assert log[:2] == ["gesendet S1", "a abschluss"]
    assert log[2] == "b Nicht ausgeführt: ein Speichern auf der Seite ist gescheitert (kaputt S1). Bitte prüfen und erneut versuchen."
    assert len(log) == 3


def _versand_js() -> str:
    """Das erste Skript von _email_dispatch.html (Adressprüfung, Versandschlüssel, postEmailDispatch)."""
    return re.search(r"<script>(.*?)</script>", (TEMPLATES / "_email_dispatch.html").read_text(encoding="utf-8"),
                     flags=re.S).group(1)


@nur_mit_node
@pytest.mark.parametrize("fall, erwartet", [
    ("gescheitert", "Nicht ausgeführt: ein Speichern auf der Seite ist gescheitert (kaputt S1). Bitte prüfen und erneut versuchen."),
    ("zeitlimit", "Keine Antwort vom Server nach 0 Sekunden – ob die Mail hinausging, ist unklar. Bitte die Seite neu laden und im "
                  "Versandverlauf prüfen."),
    ("netz", "Keine Antwort vom Server – ob die Mail hinausging, ist unklar. Erneut klicken fragt mit demselben Versandauftrag nach "
             "und sendet nicht doppelt."),
])
def test_the_email_dispatch_names_why_it_did_not_send(fall, erwartet):
    """Der Versand (abschliessen) übersetzt einen Fehler bisher immer in "Keine Antwort vom Server … erneut klicken" -- seit 1.8.96
    reicht er "nicht ausgeführt" unverändert durch und sagt beim Zeitlimit, dass erst neu zu laden und zu prüfen ist (der Platz
    nimmt bis dahin nichts mehr an)."""
    schritte = {
        "gescheitert": "speichern('feld',anfrage('S1')).catch(()=>{});const v=postEmailDispatch('rechnung','V1',{to_email:'a@b.de'}).then(()=>'kein',e=>e.message);"
                       "await ruhe();await scheitere('S1');",
        "zeitlimit": "const v=postEmailDispatch('rechnung','V1',{to_email:'a@b.de'}).then(()=>'kein',e=>e.message);",
        "netz": "const v=postEmailDispatch('rechnung','V1',{to_email:'a@b.de'}).then(()=>'kein',e=>e.message);await ruhe();await scheitere('V1');",
    }[fall]
    log = _ablauf(_versand_js() + schritte + "log.push('meldung '+await v);",
                  zeitlimit=100 if fall == "zeitlimit" else None)
    assert log[-1] == "meldung " + erwartet
    assert ("gesendet V1" in log) == (fall != "gescheitert")


# --- Punkt 2: die Liste der abschließenden Aufrufe -----------------------------------------------------------------------

# (Vorlage, Funktion) -> was die Aktion abschließt. Die schreibende Anfrage in dieser Funktion geht über abschliessen(), jede andere
# über speichern(). Abschließend heißt: macht etwas unveränderlich oder gibt es hinaus -- Unterschrift, Festschreiben, Abschluss,
# Versand und Zustellung, Abnahme und Mangel (unveränderlich nach dem Speichern), Buchung, Storno, Verwerfen mit Begründung,
# Beauftragen und Abgleich mit dem Angebot (übernehmen den Stand der Seite).
ABSCHLIESSEND = {
    ("zeiten.html", "monatAbschliessen"): "Monat der Zeiterfassung abschließen",  # seit 1.9.97 (Seite „Zeiten“, Monat & Lohn)
    ("_abnahme.html", "saveAcceptance"): "Abnahme erfassen",
    ("_auftragsstatus.html", "statusDialogSenden"): "Status des Auftrags ändern (pausieren, fortsetzen, abschließen, stornieren)",  # 1.9.124
    ("_abnahme.html", "runProtocolAcceptance"): "Abnahme aus dem Protokoll anlegen",
    ("_abnahme.html", "discardAcceptance"): "Abnahme verwerfen",
    ("_email_dispatch.html", "postEmailDispatch"): "E-Mail-Versand (alle Dokumente)",
    ("_email_dispatch.html", "saveManualDelivery"): "Zustellung nachtragen",
    ("_email_dispatch.html", "saveDispatchOutcome"): "Empfang bestätigt / unzustellbar",
    ("_maengel.html", "saveDefect"): "Mangel erfassen",
    ("_maengel.html", "defSend"): "Mangel: Haltung, Status, Freigabe, Verwerfen",
    ("checklist.html", "uploadSignature"): "Unterschrift unter einer Checkliste",
    ("checklist.html", "completeChecklist"): "Checkliste abschließen",
    ("checklist.html", "voidChecklist"): "Anzeige als gegenstandslos abschließen",
    ("checklist.html", "discardSignature"): "Unterschrift verwerfen",
    ("checklist.html", "freezeNoticeLetter"): "Brief zur Anzeige erstellen (Fassung)",
    ("checklist.html", "runSummaryAcceptance"): "Abnahme aus dem Protokoll anlegen",
    ("checklist.html", "saveProtocolDefect"): "Mangel im Protokoll erfassen",
    ("checklist.html", "discardProtocolDefect"): "Mangel im Protokoll verwerfen",
    ("customer.html", "allocateRest"): "Rest einer Zahlung zuordnen",
    ("customer.html", "bookCustomerRefund"): "Erstattung buchen",
    ("customer.html", "reversePayment"): "Zahlung zurücknehmen",
    ("email_dispatches.html", "resolveDispatch"): "hängenden Versand klären",
    ("invoice_detail.html", "sendInvoice"): "Rechnung festschreiben und versenden",
    ("invoice_detail.html", "stornoInvoice"): "Storno",
    ("invoice_detail.html", "confirmPayment"): "Zahlung buchen",
    ("invoice_detail.html", "bookRefund"): "Erstattung buchen",
    ("invoice_detail.html", "reverseAllocation"): "Zuordnung gegenbuchen",
    ("invoice_detail.html", "sendReminderNow"): "Mahnung festschreiben",
    ("invoice_detail.html", "reverseCharge"): "Nebenforderung gegenbuchen",
    ("invoice_detail.html", "confirmStart"): "Verzugsbeginn bestätigen",
    ("invoice_detail.html", "discardStart"): "Verzugsbeginn verwerfen",
    ("mahnwesen.html", "sendReminder"): "Mahnung festschreiben",
    ("mobil_offen.html", "sendReport"): "Mangel als beseitigt melden",  # seit 1.9.49 auf „Heute / Offen“ (bis dahin mobil.html)
    ("order.html", "submitDeviceSignature"): "Vertrag auf dem Gerät unterschreiben",
    ("order.html", "submitPaperSignature"): "Vertrag als Papier-Scan unterschreiben",
    ("order.html", "freezeContract"): "Vertrag festschreiben",
    ("order.html", "syncSource"): "Abgleich mit dem Angebot",
    ("quote_editor.html", "createOrder"): "Beauftragen",
    ("quote_editor.html", "syncExistingOrder"): "Abgleich mit dem Auftrag",
    ("service_report.html", "berichtAbschliessen"): "Einsatzbericht unterschreiben",  # seit 1.9.67 (bis 1.9.66 confirmSignatureStep)
    # Seit 1.8.99 (Festlegung 1.8.96 Nr. 6, korrigiert: Zahlung, Gegenbuchung, Erstattung, Storno, Abnahme, Mangel und
    # Nebenforderung sind abschließend) -- alle übrigen dieser Arten standen schon hier.
    ("incoming_invoices.html", "markPaidNow"): "Eingangsrechnung als bezahlt markieren (Zahlung)",
}

# Adressen, die nach einer abschließenden Aktion klingen -- jede schreibende Anfrage, deren Adresse darauf passt, steht in
# ABSCHLIESSEND oder hier in NICHT_ABSCHLIESSEND (mit Grund). So fällt eine neue Unterschrift, ein neuer Versand o. ä. auf.
KLINGT_ABSCHLIESSEND = re.compile(
    r"/(sign|sign-paper|send|complete|freeze|storno|void|discard[\w-]*|reverse|refunds|allocations|payments|acceptances|"
    r"acceptance-from-protocol|defects|remedied|outcome|manual|resolve|convert-to-order|sync-source-quote|default-start|"
    r"notice-letters|charges)\b")  # charges seit 1.8.99 (Nebenforderung)
NICHT_ABSCHLIESSEND = {
    ("address_import.html", "discardPreview"): "Vorschau eines Imports verwerfen -- nichts ist festgeschrieben",
    ("address_import.html", "discardWorklistRow"): "Zeile der Arbeitsliste verwerfen -- Arbeitsschritt, kein Beleg",
    # Seit 1.8.99: Gebühr, Pauschale und Zinsen in den ENTWURF einer Mahnung übernehmen -- gebucht wird die Nebenforderung erst beim
    # Festschreiben der Mahnung (sendReminder/sendReminderNow, abschließend); der Server nimmt das nur an einem Entwurf an.
    ("invoice_detail.html", "saveReminderCharges"): "Nebenforderung in den Entwurf übernehmen -- gebucht beim Festschreiben",
    ("mahnwesen.html", "saveReminderCharges"): "Nebenforderung in den Entwurf übernehmen -- gebucht beim Festschreiben",
}


def _url_text(a: vj.Analyse, st: vj.Schreibstelle) -> str:
    """Die Adresse der schreibenden Anfrage als Text; eine Variable wird über ihre Zuweisung in derselben Funktion aufgelöst."""
    auf = a.eltern[a.eltern[st.index]]
    erstes = a.argumente(auf)[0]
    toks = a.t[erstes[0]:erstes[1] + 1]
    if len(toks) == 1 and toks[0].art == "name":
        name = toks[0].wert
        for k in range(erstes[0] - 1, -1, -1):
            if a.t[k].wert == name and a.t[k + 1].wert == "=" and a.t[k + 2].wert != "=":
                toks = a.t[k + 2:vj._ausdruck_ende(a, k + 2) + 1]  # die nächstliegende Zuweisung davor
                break
    return "".join(t.wert for t in toks)


def _schreibstellen_je_funktion(name: str):
    """(Funktion, Schreibstelle, Adresse) je schreibender Anfrage in den eigenen Skripten der Vorlage."""
    a = vj.analysieren(vj.eigene_skripte(name))
    rumpfe = [(s, e, n) for n, liste in a.funktionen.items() for s, e in liste]
    for st in vj.schreibstellen(a):
        umgebend = [(s, e, n) for s, e, n in rumpfe if s <= st.index <= e]
        fn = min(umgebend, key=lambda x: x[1] - x[0])[2] if umgebend else "<oben>"
        yield fn, st, a, _url_text(a, st)


VORLAGEN = vj.alle_vorlagen(TEMPLATES)  # seit 1.8.123 auch in Unterordnern


@pytest.mark.parametrize("name", VORLAGEN)
def test_final_actions_and_only_those_go_through_abschliessen(name):
    falsch = []
    for fn, st, a, url in _schreibstellen_je_funktion(name):
        if not st.ok:
            continue  # meldet tests/test_v398_speichern_baustein.py
        soll = "abschliessen" if (name, fn) in ABSCHLIESSEND else "speichern"
        if st.ruf != soll:
            falsch.append(f"{a.stelle(st.index)} in {fn}(): {st.ruf}() statt {soll}() ({url})")
    assert not falsch, ("Abschließende Aktionen (Liste ABSCHLIESSEND) gehen über abschliessen(), alles andere über speichern():\n"
                        + "\n".join(falsch))


@pytest.mark.parametrize("name", VORLAGEN)
def test_every_request_that_sounds_final_is_classified(name):
    offen = []
    for fn, st, a, url in _schreibstellen_je_funktion(name):
        if KLINGT_ABSCHLIESSEND.search(url) and (name, fn) not in ABSCHLIESSEND and (name, fn) not in NICHT_ABSCHLIESSEND:
            offen.append(f"{a.stelle(st.index)} in {fn}(): {url}")
    assert not offen, ("Klingt nach einer abschließenden Aktion -- in ABSCHLIESSEND eintragen (und über abschliessen() senden) "
                       "oder mit Grund in NICHT_ABSCHLIESSEND:\n" + "\n".join(offen))


def test_every_listed_call_exists():
    """Jeder Eintrag beider Listen trifft eine schreibende Anfrage (eine umbenannte Funktion fiele sonst still aus der Prüfung)."""
    vorhanden = {(name, fn) for name in VORLAGEN for fn, *_ in _schreibstellen_je_funktion(name)}
    assert set(ABSCHLIESSEND) - vorhanden == set()
    assert set(NICHT_ABSCHLIESSEND) - vorhanden == set()
    klingt = {(name, fn) for name in VORLAGEN for fn, st, a, url in _schreibstellen_je_funktion(name) if KLINGT_ABSCHLIESSEND.search(url)}
    assert set(NICHT_ABSCHLIESSEND) <= klingt, "NICHT_ABSCHLIESSEND nur für Adressen, die nach einer abschließenden Aktion klingen"


def test_the_checklist_signs_through_its_own_final_upload():
    """Foto und Unterschrift gehen an dieselbe Adresse -- die Unterschrift über uploadSignature() (abschliessen), das Foto über
    uploadFile() (speichern)."""
    text = (TEMPLATES / "checklist.html").read_text(encoding="utf-8")
    rumpf = text.split("async function saveSignature(", 1)[1].split("\nasync function ", 1)[0]
    assert "await uploadSignature(fieldId,blob,extra)" in rumpf and "uploadFile(" not in rumpf
