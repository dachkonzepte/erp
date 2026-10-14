"""Version 1.8.99 -- Zeitlimit beim Hochladen erst ab dem Ende der Übertragung (Vorgabe vom 14.10.2026, Vorweg 96-1).

Bis 1.8.98 lief das Zeitlimit des Bausteins (app/templates/_speichern.html, 60 s) für jedes Speichern ab dem Senden -- ein großes Foto
über eine langsame Verbindung (10 MB bei 1 Mbit/s rund 80 s) endete als "unklar", obwohl es noch übertragen wurde, und der Bereich nahm
bis zum Neuladen nichts mehr an (Nebenbefund 1 aus 1.8.96). Jetzt geht ein Hochladen (Body FormData, Blob/File oder Binärdaten) über
XMLHttpRequest: dessen upload-Ereignis loadend meldet das Ende der Übertragung, erst dann läuft die Uhr. Die Seite bekommt eine gewöhnliche
Response wie von fetch.

Hier der Baustein in node mit gestelltem XMLHttpRequest (node hat keins); scripts/klicktest_hochladen.py prüft dasselbe im echten Browser
mit gedrosseltem Netz."""

import pytest

from tests.test_v314_dashboard_month_berlin import NODE
from tests.test_v398_speichern_baustein import _ablauf

nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")

# Vor dem Baustein: ein gestelltes XMLHttpRequest. hochgeladen(n) meldet das Ende der Übertragung der n-ten Anfrage, antworteXhr(n,
# status, text) die Antwort, scheitereXhr(n) einen Netzfehler.
XHR = r"""
globalThis.XHRS=[];
globalThis.XMLHttpRequest=class{
  constructor(){XHRS.push(this);this.l={};this.upload={l:{},addEventListener(t,f){this.l[t]=f}};this.readyState=0;this.kopf={}}
  open(m,u){this.methode=m;this.url=u}
  setRequestHeader(k,v){this.kopf[k.toLowerCase()]=v}
  addEventListener(t,f){this.l[t]=f}
  send(body){this.body=body;log.push('xhr gesendet '+this.methode+' '+this.url)}
  abort(){log.push('xhr abgebrochen '+this.url);this.l.abort&&this.l.abort()}
  getAllResponseHeaders(){return 'content-type: application/json\r\nx-test: 1\r\n'}
};
globalThis.hochgeladen=async n=>{const x=XHRS[n];log.push('übertragen '+x.url);x.upload.l.loadend&&x.upload.l.loadend();await ruhe()};
globalThis.antworteXhr=async(n,status,text)=>{const x=XHRS[n];x.readyState=4;x.status=status;x.statusText='OK';
  x.response=new Blob([text]);x.l.readystatechange&&x.l.readystatechange();x.l.load();await ruhe()};
globalThis.scheitereXhr=async n=>{XHRS[n].l.error();await ruhe()};
"""


def _hochladen(name="/api/fotos", methode="POST"):
    return f"()=>fetch('{name}',{{method:'{methode}',body:(()=>{{const f=new FormData();f.append('datei',new Blob(['x']),'a.jpg');return f}})()}})"


@nur_mit_node
def test_the_time_limit_starts_after_the_transfer_ends():
    """Die Übertragung dauert länger als das Zeitlimit: kein Abbruch; erst danach läuft die Uhr, die Antwort kommt in der Zeit."""
    log = _ablauf(f"""
        const s=speichern('fotos',{_hochladen()}).then(async r=>'ergebnis '+r.status+' '+JSON.stringify(await r.json())+' '+r.headers.get('x-test'));
        await warte(750);                 // dreimal das Zeitlimit, noch in der Übertragung
        log.push('nach 750 ms '+(XHRS.length));
        await hochgeladen(0);
        await antworteXhr(0,200,'{{"id":7}}');
        log.push(await s);
    """, zeitlimit=250, vorspann=XHR)
    assert log == ["xhr gesendet POST /api/fotos", "nach 750 ms 1", "übertragen /api/fotos", 'ergebnis 200 {"id":7} 1']


@nur_mit_node
def test_after_the_transfer_the_usual_time_limit_applies():
    log = _ablauf(f"""
        const s=speichern('fotos',{_hochladen()}).then(()=>'kein',e=>e.dkBaustein);
        await warte(500); await hochgeladen(0); await warte(600);
        log.push('ergebnis '+(await s));
    """, zeitlimit=250, vorspann=XHR)
    assert log == ["xhr gesendet POST /api/fotos", "übertragen /api/fotos", "xhr abgebrochen /api/fotos", "ergebnis unklar"]


@nur_mit_node
def test_an_answer_header_also_ends_the_transfer():
    """Kommt der Antwortkopf, ist die Übertragung zu Ende, auch ohne upload-Ereignis (ein Browser ohne upload.loadend)."""
    log = _ablauf(f"""
        const s=speichern('fotos',{_hochladen()}).then(()=>'kein',e=>e.dkBaustein);
        await warte(500); XHRS[0].readyState=2; XHRS[0].l.readystatechange(); await warte(600);
        log.push('ergebnis '+(await s));
    """, zeitlimit=250, vorspann=XHR)
    assert log == ["xhr gesendet POST /api/fotos", "xhr abgebrochen /api/fotos", "ergebnis unklar"]


@nur_mit_node
def test_an_upload_is_sent_only_after_the_previous_save_and_counts_as_failed_on_a_network_error():
    log = _ablauf(f"""
        const a=speichern('fotos',anfrage('S1'));
        const b=speichern('fotos',{_hochladen('/api/fotos/2')}).then(()=>'kein',e=>e.constructor.name+' '+e.message);
        await ruhe(); log.push('-'); await antworte('S1'); await a;
        await scheitereXhr(0); log.push('ergebnis '+(await b));
        log.push('U1 '+await abschliessen('unterschrift',anfrage('U1')).then(()=>'kein',e=>e.dkBaustein));
    """, zeitlimit=1000, vorspann=XHR)
    assert log == ["gesendet S1", "-", "xhr gesendet POST /api/fotos/2", "ergebnis TypeError Failed to fetch", "U1 abschluss"]


@nur_mit_node
def test_an_error_status_of_an_upload_comes_back_as_a_response_and_counts_as_failed():
    log = _ablauf(f"""
        const r=speichern('fotos',{_hochladen()}); await ruhe(); await hochgeladen(0); await antworteXhr(0,413,'{{"detail":"zu groß"}}');
        const antwort=await r; log.push('ergebnis '+antwort.ok+' '+antwort.status+' '+(await antwort.json()).detail);
        log.push('U1 '+await abschliessen('unterschrift',anfrage('U1')).then(()=>'kein',e=>e.message));
    """, zeitlimit=1000, vorspann=XHR)
    assert log[:3] == ["xhr gesendet POST /api/fotos", "übertragen /api/fotos", "ergebnis false 413 zu groß"]
    assert log[3] == "U1 Nicht ausgeführt: ein Speichern auf der Seite ist gescheitert (Status 413). Bitte prüfen und erneut versuchen."


@nur_mit_node
def test_headers_and_method_go_with_the_upload_and_text_bodies_still_use_fetch():
    log = _ablauf("""
        const s=speichern('fotos',()=>fetch('/api/belege',{method:'put',headers:{'X-Dk':'1'},body:new Blob(['%PDF'])}));
        await ruhe(); log.push('kopf '+XHRS[0].kopf['x-dk']+' body '+(XHRS[0].body instanceof Blob));
        await hochgeladen(0); await antworteXhr(0,200,'{}'); await s;
        const t=speichern('text',()=>fetch('T1',{method:'POST',body:'{}'})); await ruhe(); await antworte('T1'); await t;
    """, zeitlimit=1000, vorspann=XHR)
    assert log == ["xhr gesendet PUT /api/belege", "kopf 1 body true", "übertragen /api/belege", "gesendet T1"]


@nur_mit_node
def test_without_xmlhttprequest_an_upload_falls_back_to_fetch():
    """Ohne XMLHttpRequest (node, alte Umgebung) bleibt es bei fetch -- das Zeitlimit läuft dann wie bis 1.8.98 ab dem Senden."""
    log = _ablauf(f"""
        const s=speichern('fotos',{_hochladen('F1')}).then(()=>'kein',e=>e.dkBaustein);
        await warte(250); log.push('ergebnis '+(await s));
    """, zeitlimit=100)
    assert log == ["gesendet F1", "abgebrochen F1", "ergebnis unklar"]
