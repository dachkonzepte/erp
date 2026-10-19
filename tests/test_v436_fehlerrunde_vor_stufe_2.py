"""Fehlerrunde vor Stufe 2 des Redesigns (1.8.132 ff., Vorgabe vom 19.10.2026): je Punkt ein Test, der vor der Behebung scheiterte.

    1  Anfragen: „Projekt öffnen“ führt direkt in die Projektmappe, „Projekt + Angebot erzeugen“ direkt ins neue Angebot (1.8.132)
"""

import json

from tests.test_v334_auswahl_restfaelle import im_browser, nur_mit_node, seite


# ---------------------------------------------------------------------------
# 1. Anfragen: Projekt öffnen, Projekt + Angebot erzeugen
# ---------------------------------------------------------------------------

@nur_mit_node
def test_anfrage_projekt_oeffnen_fuehrt_in_die_projektmappe():
    """Bis 1.8.131 ging „Projekt öffnen“ auf /projects?project_id=7 -- die Projektliste wertet den Parameter nicht aus, man landete in der
    ganzen Liste."""
    lauf = im_browser(seite("inquiries.html", "init();\n"), """
      currentInquiry = {id: 3, project_id: 7};
      openLinkedProject();
      return location.href;""")
    assert lauf["ergebnis"] == "/projects/7"


@nur_mit_node
def test_nach_projekt_und_angebot_erzeugen_ins_neue_angebot():
    """Bis 1.8.131 blieb die Seite nach dem Umwandeln stehen (nur Statuszeile)."""
    antwort = {"inquiry": {"id": 3, "project_id": 7}, "project": {"id": 7, "project_number": "P-2026-0007"},
               "quote": {"id": 9, "quote_number": "A-2026-0009"}}
    lauf = im_browser(seite("inquiries.html", "init();\n"), f"""
      const echt = globalThis.fetch;
      globalThis.fetch = async (url, opt = {{}}) => {{
        if (opt.method !== 'POST' || url !== '/api/inquiries/3/convert') return echt(url, opt);
        AUFRUFE.push({{url, methode: 'POST'}});
        return {{ok: true, status: 200, statusText: 'OK', headers: {{get: () => 'application/json'}}, json: async () => ({json.dumps(antwort)})}};
      }};
      loadAll = async () => {{}};
      inquiries = [{{id: 3, project_id: null, title: 'Undichtes Flachdach'}}];
      currentInquiry = {{id: 3, project_id: null, title: 'Undichtes Flachdach'}};
      await convertInquiry();
      return location.href;""")
    assert lauf["ergebnis"] == "/quotes/9/edit"
    assert [a["url"] for a in lauf["aufrufe"] if a["methode"] == "POST"] == ["/api/inquiries/3/convert"]
