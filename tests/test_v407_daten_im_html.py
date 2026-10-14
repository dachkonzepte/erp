"""Version 1.8.102 -- Daten im HTML (Vorgabe vom 14.10.2026 Punkt 2; Befund 1.8.100 Nr. 5–8).

Strukturtests über das JavaScript aller Vorlagen (Scanner tests/vorlagen_html.py, Regeln dort im Kopf):
1. kein Wert ohne esc() in HTML (innerHTML, insertAdjacentHTML, outerHTML, document.write; Template-Literale und Verkettungen mit
   Markup) -- Ausnahmeliste AUSNAHMEN_UNGESCHUETZT;
2. keine on…-Attribute mit eingesetzten Werten, sondern data-Attribute und Aktionen (_aktionen.html) -- Ausnahmeliste
   AUSNAHMEN_HANDLER (heute nur Zahlen und IDs); dazu Jinja-Werte in on…-Attributen des Markups (keine);
3. jedes href/src/Navigation aus Daten nur http(s), mailto, tel oder lokal -- über sichererLink()/sichereBildquelle() (_links.html)
   oder mit festem erlaubtem Anfang; ohne Ausnahmen.
Die Ausnahmelisten dürfen nur kürzer werden: eine neue Stelle ist rot, eine behobene, die noch in der Liste steht, auch ("bitte
streichen").

Dazu: der Scanner selbst an Beispielen (was er findet, was er durchlässt), jede esc-Funktion der Vorlagen in node, die Datumsfunktionen,
die als sicher gelten, sichererLink()/sichereBildquelle() an einer Tabelle von Angriffen, der Baustein _aktionen.html, und dass jedes
Feld "id"/"…_id" mit Text in TEXT_IDS steht. Angriffe auf die vier Befund-Stellen: tests/test_v405_befund_seiten.py; im Browser:
scripts/klicktest_daten_im_html.py. Gegenproben: docs/archiv/befund-vor-echtbetrieb.md, "Umsetzung 1.8.102"."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from tests.test_v314_dashboard_month_berlin import NODE, _node
from tests.vorlagen_html import (DATUM_FUNKTIONEN, TEXT_IDS, Pruefer, alle_funde, alle_vorlagen, jinja_handler,
                                 zusammenhaenge)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
nur_mit_node = pytest.mark.skipif(NODE is None, reason="node nicht installiert")

# Ein Wert, der ohne esc() in HTML geht -- mit Grund. Darf nur kürzer werden.
AUSNAHMEN_UNGESCHUETZT = {
    # HTML aus CHANGELOG.md im Repository; der Server maskiert den Text, bevor er `code` und **fett** setzt (app/changelog.py::
    # _inline_format()) -- kein Wert von außen.
    "changelog.html | load | e.html": 1,
}

# on…-Attribute mit eingesetzten Werten, die noch nicht auf data-Attribute umgebaut sind (Stand 1.8.102: nur Zahlen und IDs --
# jeder Text-Wert ist umgebaut). Schlüssel "Datei | Funktion | Attribut: Ausdruck", Wert: Anzahl. Darf nur kürzer werden.
AUSNAHMEN_HANDLER = {
    '_abnahme.html | acceptanceHtml | onclick: a.id': 4,
    '_abnahme.html | rowsHtml | onclick: r.checklist_id': 1,
    '_maengel.html | defOpen | onchange: id': 4,
    '_maengel.html | defOpen | onclick: id': 7,
    'address_import.html | loadRuns | onclick: r.id': 1,
    'address_import.html | renderWorklist | onclick: r.id': 3,
    'calendar.html | eventChipHtml | onclick: click': 2,
    'calendar.html | renderMonth | onclick: d.getDate()': 1,
    'calendar.html | renderMonth | onclick: d.getFullYear()': 1,
    'calendar.html | renderMonth | onclick: d.getMonth()': 1,
    'checklist.html | fieldBody | onblur: f.id': 3,
    'checklist.html | fieldBody | onchange: f.id': 5,
    'checklist.html | fieldBody | onclick: a.id': 3,
    'checklist.html | fieldBody | onclick: f.id': 4,
    'checklist.html | fieldBody | oninput: f.id': 3,
    'checklist.html | protocolDefectHtml | onclick: d.id': 1,
    'checklist.html | protocolDefectHtml | onclick: f.id': 1,
    'checklist.html | renderVersions | onclick: d.id': 1,
    'checklist.html | renderVersions | onclick: v.id': 1,
    'checklist.html | signerInput | onchange: f.id': 2,
    'checklist_template.html | fieldBody | onchange: f.id': 1,
    'checklist_template.html | fieldBody | onchange: o.id': 1,
    'checklist_template.html | fieldBody | onclick: f.id': 3,
    'checklist_template.html | fieldBody | onclick: o.id': 1,
    'checklist_template.html | fieldBody | onkeydown: f.id': 1,
    'checklist_template.html | renderFields | onclick: f.id': 1,
    'checklist_template.html | renderFields | onclick: i': 2,
    'checklist_template.html | renderRules | onclick: r.id': 3,
    'checklist_template.html | renderVersions | onclick: v.id': 1,
    "checklist_template.html | ruleForm | onchange: r.id??'null'": 2,
    'customer.html | paymentCardHtml | onchange: p.id': 1,
    'customer.html | paymentCardHtml | onclick: p.id': 3,
    'customer.html | renderCustomerDocuments | onclick: d.id': 2,
    'customer.html | renderExtras | onclick: i.id': 2,
    'customer.html | renderProperties | onclick: p.id': 4,
    'dashboard.html | loadAndRenderOpenOfficeTasks | onclick: t.id': 1,
    'email_dispatches.html | fileButtons | onclick: a.id': 2,
    'email_dispatches.html | statusCell | onclick: d.id': 2,
    'incoming_invoices.html | row | onclick: inv.id': 3,
    'incoming_invoices.html | skontoRow | onclick: inv.id': 1,
    'index.html | renderServices | onclick: s.id': 2,
    'inquiries.html | card | onclick: i.id': 1,
    'inspection_template.html | itemRow | onblur: item.id': 7,
    'inspection_template.html | itemRow | onchange: item.id': 4,
    'inspection_template.html | itemRow | onclick: item.id': 1,
    'inspection_templates.html | row | onclick: !t.archived': 1,
    'inspection_templates.html | row | onclick: t.id': 1,
    'invoice_detail.html | allocationHtml | onclick: a.id': 2,
    'invoice_detail.html | chargeHtml | onclick: c.id': 2,
    'invoice_detail.html | chargesEditorHtml | onchange: prefix': 1,
    'invoice_detail.html | payLineHtml | onclick: i': 1,
    'invoice_detail.html | payLineHtml | oninput: i': 4,
    'invoice_detail.html | payLineHtml | oninput: j': 1,
    'invoice_detail.html | renderCharges | onclick: s.id': 1,
    'invoice_detail.html | renderItems | onchange: i.id': 1,
    'invoice_detail.html | renderItems | onclick: i.id': 2,
    'invoice_detail.html | renderQuantityRows | onchange: i.id': 1,
    'invoice_detail.html | renderQuantityRows | onclick: i.id': 2,
    'invoice_detail.html | renderReminders | onclick: r.id': 4,
    'invoice_detail.html | renderReminders | onclick: status.next_level': 1,
    'mahnwesen.html | chargesEditorHtml | onchange: prefix': 1,
    'mahnwesen.html | renderAllRows | onclick: r.id': 7,
    'mahnwesen.html | renderAttentionRows | onclick: r.draft.id': 4,
    'mahnwesen.html | renderAttentionRows | onclick: r.invoice_id': 1,
    'mahnwesen.html | renderAttentionRows | onclick: r.next_level': 1,
    'mahnwesen.html | renderDueRows | onclick: r.invoice_id': 1,
    'mahnwesen.html | renderDueRows | onclick: r.next_level': 1,
    'maintenance_contract.html | itemRow | onclick: !item.archived': 1,
    'maintenance_contract.html | itemRow | onclick: item.id': 3,
    'master_data.html | render | onclick: x.id': 9,
    'master_data_form.html | renderAssetDocQueue | onclick: i': 1,
    'operational_asset.html | documentRow | onclick: doc.id': 1,
    'operational_asset.html | inspectionRow | onchange: insp.id': 1,
    'operational_asset.html | inspectionRow | onclick: insp.id': 4,
    'order.html | renderContract | onclick: next': 1,
    'order.html | renderContract | onclick: v.version_no': 1,
    'order.html | renderInvoices | onclick: inv.id': 1,
    'order.html | rowHtml | onchange: i.id': 3,
    'order.html | rowHtml | onclick: i.id': 1,
    'order.html | secBtn | onclick: id': 1,
    'planning.html | renderAbsences | onclick: x.id': 1,
    'planning.html | renderBacklog | onclick: x.order_id': 1,
    'planning.html | renderSlot | onclick: slot.id': 1,
    'project_folder.html | participantCard | onchange: p.id': 6,
    'project_folder.html | participantCard | onclick: p.id': 3,
    'project_folder.html | pmHitHtml | onclick: gi': 1,
    'project_folder.html | pmHitHtml | onclick: hi': 1,
    'project_folder.html | renderDocuments | onclick: d.id': 2,
    'projects.html | cardHtml | onclick: p.id': 1,
    'projects.html | menuItemsFor | onclick: !p.archived': 2,
    'projects.html | menuItemsFor | onclick: p.id': 7,
    'projects.html | renderList | onclick: p.id': 2,
    'property.html | propertyDocumentRow | onclick: d.id': 1,
    'quote_editor.html | itemHtml | onchange: i.id': 2,
    'quote_editor.html | itemHtml | onclick: i.id': 1,
    'quote_editor.html | itemHtml | onkeydown: i.id': 1,
    'quote_editor.html | renderCatalog | onclick: s.id': 1,
    'quote_editor.html | sectionHtml | onclick: section.id': 1,
    'recurring_costs.html | cancellationRow | onclick: c.id': 1,
    'recurring_costs.html | documentRow | onclick: doc.id': 1,
    'recurring_costs.html | row | onclick: c.id': 3,
    'roof_area.html | componentRow | onclick: !c.archived': 1,
    'roof_area.html | componentRow | onclick: c.id': 5,
    'roof_area.html | layerRowHtml | onchange: type.id': 2,
    'roof_area.html | layerRowHtml | onclick: type.id': 2,
    'roof_area.html | layerRowHtml | oninput: type.id': 2,
    'service_form.html | renderMaterialRows | onclick: i': 1,
    'service_reports.html | assetsPanelHtml | onchange: a.id': 1,
    'service_reports.html | assetsPanelHtml | onchange: r.id': 1,
    'service_reports.html | assetsPanelHtml | onclick: a.id': 1,
    'service_reports.html | assetsPanelHtml | onclick: r.id': 2,
    'service_reports.html | findingCard | onchange: f.id': 3,
    'service_reports.html | findingCard | onchange: r.id': 3,
    'service_reports.html | findingCard | onclick: f.id': 3,
    'service_reports.html | findingCard | onclick: r.id': 2,
    'service_reports.html | findingFormHtml | onchange: r.id': 1,
    'service_reports.html | findingFormHtml | onclick: r.id': 1,
    'service_reports.html | findingsPanelHtml | onclick: r.id': 1,
    'service_reports.html | inspectionItemRowHtml | onchange: item.id': 1,
    'service_reports.html | inspectionItemRowHtml | onclick: item.id': 3,
    'service_reports.html | inspectionItemRowHtml | onclick: r.id': 2,
    'service_reports.html | inspectionItemRowHtml | oninput: item.id': 1,
    'service_reports.html | inspectionItemsPanelHtml | onclick: r.id': 2,
    'service_reports.html | itemControlInnerHtml | onchange: item.id': 4,
    'service_reports.html | itemControlInnerHtml | onclick: g': 1,
    'service_reports.html | itemControlInnerHtml | onclick: item.id': 4,
    'service_reports.html | itemControlInnerHtml | oninput: item.id': 1,
    'service_reports.html | itemPhotoSectionHtml | onchange: item.id': 1,
    'service_reports.html | itemPhotoSectionHtml | onchange: reportId': 1,
    'service_reports.html | itemPhotoSectionHtml | onclick: item.id': 1,
    'service_reports.html | materialsPanelHtml | onchange: m.id': 3,
    'service_reports.html | materialsPanelHtml | onchange: r.id': 5,
    'service_reports.html | materialsPanelHtml | onclick: m.id': 1,
    'service_reports.html | materialsPanelHtml | onclick: r.id': 4,
    'service_reports.html | materialsPanelHtml | oninput: r.id': 4,
    'service_reports.html | photoThumbHtml | onclick: p.id': 1,
    'service_reports.html | photoThumbHtml | onclick: reportId': 1,
    'service_reports.html | reportCard | onclick: r.id': 7,
    'service_reports.html | slot | onchange: item.id': 1,
    'service_reports.html | slot | onchange: kind': 1,
    'service_reports.html | slot | onchange: reportId': 1,
    'service_reports.html | slot | onclick: item.id': 1,
    'service_reports.html | slot | onclick: kind': 1,
    'settings.html | componentTypeRow | onchange: t.id': 1,
    'settings.html | componentTypeRow | onclick: index': 2,
    'settings.html | componentTypeRow | onclick: t.id': 2,
    'settings.html | documentCategoryRow | onchange: c.id': 1,
    'settings.html | documentCategoryRow | onclick: c.id': 1,
    'settings.html | renderAccounts | onclick: a.id': 1,
    'settings.html | renderBaseRates | onclick: r.id': 2,
    'settings.html | renderEmployeeFunctions | onclick: f.id': 2,
    'settings.html | renderHolidays | onclick: x.id': 2,
    'settings.html | renderMaintenanceWindows | onblur: w.id': 3,
    'settings.html | renderMaintenanceWindows | onclick: i': 2,
    'settings.html | renderMaintenanceWindows | onclick: w.id': 1,
    'settings.html | renderOptions | onclick: o.id': 2,
    'settings.html | renderPaymentTerms | onclick: x.id': 4,
    'settings.html | renderProductiveHours | onclick: r.public_holidays_suggested': 1,
    'settings.html | renderProjectPipelineColumns | onblur: c.id': 1,
    'settings.html | renderProjectPipelineColumns | onclick: c.id': 1,
    'settings.html | renderProjectPipelineColumns | onclick: i': 2,
    'settings.html | renderReminderLevels | onclick: x.id': 1,
    'settings.html | renderTaskColumns | onblur: c.id': 1,
    'settings.html | renderTaskColumns | onchange: c.id': 1,
    'settings.html | renderTaskColumns | onclick: c.id': 1,
    'settings.html | renderTaskColumns | onclick: i': 2,
    'settings.html | renderTaxKeys | onclick: x.id': 4,
    'settings.html | roofLayerTypeRow | onchange: t.id': 1,
    'settings.html | roofLayerTypeRow | onclick: t.id': 2,
    'tasks.html | card | onclick: t.id': 2,
    'tasks.html | renderChecklist | onchange: i.id': 1,
    'tasks.html | renderChecklist | onclick: i.id': 1,
    'time_backoffice.html | absCard | onclick: r.id': 2,
    'time_backoffice.html | loadEntries | onclick: e.id': 2,
    'time_backoffice.html | loadPayroll | onclick: p.employee_id': 1,
    'time_backoffice.html | loadWorkAssignments | onchange: a.employee_id': 1,
    'time_backoffice.html | renderOptionGroup | onclick: o.id': 1,
    'time_backoffice.html | renderWorkModels | onclick: m.id': 2,
    'time_tracking.html | loadAbsenceRequests | onclick: r.id': 3,
    'time_tracking.html | renderEntry | onclick: e.id': 2,
    'time_tracking_field.html | loadAbsenceRows | onclick: r.id': 1,
    'time_tracking_field.html | renderCrewGroup | onclick: g.id': 2,
    'time_tracking_field.html | renderEntry | onclick: e.id': 2,
    'users.html | render | onclick: u.id': 3,
    'work_preparation.html | renderDelivery | onclick: x.id': 1,
    'work_preparation.html | renderMaterials | onchange: x.id': 1,
    'work_preparation.html | renderMaterials | onclick: x.id': 1,
    'work_preparation.html | renderTasks | onclick: x.id': 2,
    'work_preparation.html | renderTeamExtras | onclick: x.id': 2,
    'work_preparation.html | renderTeams | onclick: t.id': 1,
}


def _vergleich(funde, ausnahmen: dict, was: str) -> None:
    ist = Counter(f.schluessel() for f in funde)
    neu = ist - Counter(ausnahmen)
    veraltet = Counter(ausnahmen) - ist
    stellen = {f.schluessel(): f.stelle for f in funde}
    assert not neu, f"{was} -- neue Stellen:\n" + "\n".join(f"{stellen[k]}: {k} ({n}x)" for k, n in neu.items())
    assert not veraltet, "Eintrag in der Ausnahmeliste ohne Fundstelle -- bitte streichen:\n" + "\n".join(
        f"{k} ({n}x)" for k, n in veraltet.items())


def test_kein_wert_ohne_esc_im_html():
    _vergleich(alle_funde("ungeschuetzt"), AUSNAHMEN_UNGESCHUETZT, "Wert ohne esc() in HTML")


def test_keine_werte_in_on_attributen():
    _vergleich(alle_funde("handler_mit_werten"), AUSNAHMEN_HANDLER, "Wert in einem on…-Attribut (data-Attribut und aktion() nehmen)")


def test_keine_jinja_werte_in_on_attributen():
    assert [f.stelle + ": " + f.ausdruck for f in alle_funde("jinja")] == []


def test_jeder_link_aus_daten_ist_geprueft():
    assert [f"{f.stelle}: {f.ausdruck}" for f in alle_funde("links_aus_daten")] == []


def test_die_ausnahmeliste_der_handler_enthaelt_nur_zahlen_und_ids():
    """Festlegung 1.8.102: umgebaut ist jeder Handler mit Text; was bleibt, ist ein Wert, den der Scanner als Zahl, ID oder Literal
    erkennt -- oder ein Zähler/Index, den er nicht beweisen kann (die festen Namen unten)."""
    zahlen = {"i", "next", "status.next_level", "r.next_level", "v.version_no", "r.public_holidays_suggested"}
    for v in zusammenhaenge():
        p = Pruefer(v)
        for teile, _ in p.stuecke():
            for teil, ctx in p.kontexte(teile):
                if ctx[0] != "attr" or not ctx[1].startswith("on") or not p._eigen(teil[1]):
                    continue
                text = p._text(teil[1], teil[2])
                escaper = any(p.a.t[k].art == "name" and p.a.t[k + 1].wert == "(" and p.ist_escaper(p.a.t[k].wert, k)
                              for k in range(teil[1], teil[2] + 1))
                assert not escaper and (not p.unsicher(teil[1], teil[2]) or text in zahlen), f"{p._fund(teil[1], teil[2]).stelle}: {text}"


# ---------------------------------------------------------------------------
# Der Scanner an Beispielen
# ---------------------------------------------------------------------------

ESC = """const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));\n"""


def _funde(js: str) -> dict:
    p = Pruefer("beispiel.html", text=ESC + js)
    return {"u": [f.ausdruck for f in p.ungeschuetzt()], "h": [f.ausdruck for f in p.handler_mit_werten()],
            "l": [f.ausdruck for f in p.links_aus_daten()]}


@pytest.mark.parametrize("js, ungeschuetzt", [
    ("function f(x){el.innerHTML=`<b>${x.name}</b>`}", ["x.name"]),
    ("function f(x){el.innerHTML='<td>'+x.name+'</td>'}", ["x.name"]),
    ("function f(x){el.innerHTML=x.name}", ["x.name"]),
    ("function f(x){el.insertAdjacentHTML('beforeend',x.name)}", ["x.name"]),
    ("function f(x){el.innerHTML+=`<i>${x.a?x.b:'-'}</i>`}", ["x.b"]),
    ("function f(x){el.innerHTML=`<i>${x.a||x.b}</i>`}", ["x.a", "x.b"]),
    ("function f(x){el.innerHTML=`<i>${x.a&&x.b}</i>`}", ["x.b"]),
    ("function f(l){el.innerHTML=`<ul>${l.map(x=>`<li>${x}</li>`).join('')}</ul>`} f(antwort.liste)", ["x"]),
    ("function f(l){el.innerHTML=l.map(x=>x.name).join(', ')}", ["l.map(x=>x.name).join(', ')"]),
    ("function f(x){const n=x.name;el.innerHTML=`<b>${n}</b>`}", ["n"]),
    ("function f(x){let h='<b>';h+=x.name;el.innerHTML=h}", ["x.name"]),  # Variable mit Markup: die Wurzel
    ("function f(x){const l=[];l.push(x.name);el.innerHTML=`<p>${l.join(', ')}</p>`}", ["l.join(', ')"]),
    ("function f(x){el.innerHTML=`<b>${g(x.name)}</b>`} function g(v){return v}", ["g(x.name)"]),
    ("function f(x){el.innerHTML=`<b>${x.external_id}</b>`}", ["x.external_id"]),  # TEXT_IDS
    ("function f(x){el.innerHTML=`<b>${x.html}</b>`}", ["x.html"]),
    ("function f(x){el.innerHTML=`<b>${{a:x.name}[k]}</b>`}", ["{a:x.name}[k]"]),
    ("function f(x){el.innerHTML=`<b>${JSON.stringify(x)}</b>`}", ["JSON.stringify(x)"]),
    ("function f(x){h(x.name)} function h(v){el.innerHTML=`<b>${v}</b>`}", ["v"]),
    ("function f(x){el.innerHTML=`<b onclick=\"h()\">${x.name}</b>`}", ["x.name"]),
    ("function f(x){el.innerHTML=`${x.name}`}", ["x.name"]),  # Ziel ohne Markup
    ("function f(x){el.innerHTML=String(x.name)}", ["String(x.name)"]),
    ("function f(x){el.innerHTML=x.name.trim()}", ["x.name.trim()"]),
])
def test_scanner_findet_ungeschuetzte_werte(js, ungeschuetzt):
    assert _funde(js)["u"] == ungeschuetzt


@pytest.mark.parametrize("js", [
    "function f(x){el.innerHTML=`<b>${esc(x.name)}</b>`}",
    "function f(x){el.innerHTML='<td>'+esc(x.name)+'</td>'}",
    "function f(x){el.innerHTML=`<b>${x.id}</b><i>${x.order_id}</i><u>${x.items.length}</u>`}",
    "function f(x){el.innerHTML=`<b>${Number(x.a)}</b><i>${x.a-x.b}</i><u>${x.a>1}</u><s>${!x.a}</s>`}",
    "function f(x){el.innerHTML=`<b>${new Date(x.d).toLocaleDateString('de-DE')}</b><i>${Number(x.a).toFixed(2)}</i>`}",
    "function f(x){el.innerHTML=`<b>${new Intl.NumberFormat('de-DE').format(x.a)}</b>`}",
    "function f(x){el.innerHTML=`<b>${x.a?'ja':'nein'}</b>${x.b&&'<i>x</i>'}`}",
    "function f(l){el.innerHTML=`<ul>${l.map(x=>`<li>${esc(x.name)}</li>`).join('')}</ul>`}",
    "function f(l){el.innerHTML=l.map((x,i)=>`<li data-i=\"${i}\">${esc(x)}</li>`).join('')}",
    "function f(){el.innerHTML=[['a','A'],['b','B']].map(([k,l])=>`<option value=\"${k}\">${l}</option>`).join('')}",
    "const T={offen:'Offen',zu:'Zu'};function f(x){el.innerHTML=`<b>${T[x.s]||'—'}</b>`}",
    "function f(x){el.innerHTML=`<b>${{a:'<i>A</i>',b:'B'}[x.s]||esc(x.s)}</b>`}",
    "function f(x){const m=String(x.d).match(/^(\\d{4})-(\\d{2})/);el.innerHTML=m?`<b>${m[2]}.${m[1]}</b>`:''}",
    "function f(x){el.innerHTML=g(x)} function g(x){return `<b>${esc(x.name)}</b>`}",
    "function f(x){h(x.id)} function h(v){el.innerHTML=`<b>${v}</b>`}",
    "function f(x){let h='';for(const y of x.l)h+=`<li>${esc(y)}</li>`;el.innerHTML=h}",
    "function f(x){el.innerHTML=auswahlOptionen(x.l,x.v,y=>y.name)}",
    "function f(x){el.innerHTML=`<b>${berlinToday()}</b>`}",
])
def test_scanner_laesst_sichere_werte_durch(js):
    assert _funde(js)["u"] == []


def test_scanner_findet_werte_in_on_attributen_auch_mit_esc():
    js = "function f(x){el.innerHTML=`<a onclick=\"g(${x.id})\">a</a><a onclick=\"g('${esc(x.k)}')\">b</a>` +'<a onchange=\"h('+x.n+')\">c</a>'}"
    assert _funde(js)["h"] == ["onclick: x.id", "onclick: esc(x.k)", "onchange: x.n"]
    assert _funde("function f(x){el.innerHTML=`<a data-klick=\"g\" data-k=\"${esc(x.k)}\">b</a>`}")["h"] == []


@pytest.mark.parametrize("js, links", [
    ("function f(x){el.innerHTML=`<a href=\"${esc(x.url)}\">a</a>`}", ["href: esc(x.url)"]),
    ("function f(x){el.innerHTML=`<img src=\"${esc(x.url)}\">`}", ["src: esc(x.url)"]),
    ("function f(x){el.innerHTML=`<a href=\"java${x.u}\">a</a>`}", ["href='java'+x.u"]),
    ("function f(x){a.href=x.url}", ["href = x.url"]),
    ("function f(x){img.src=x.url}", ["src = x.url"]),
    ("function f(x){location.href=x.url}", ["href = x.url"]),
    ("function f(x){location=x.url}", ["location = x.url"]),
    ("function f(x){window.open(x.url)}", ["window.open = x.url"]),
    ("function f(x){a.setAttribute('href',x.url)}", ["href = x.url"]),
    ("function f(x){location.assign(x.url)}", ["location.assign = x.url"]),
])
def test_scanner_findet_links_aus_daten(js, links):
    assert _funde(js)["l"] == links


@pytest.mark.parametrize("js", [
    "function f(x){el.innerHTML=`<a href=\"/projects/${x.id}\">a</a><a href=\"mailto:${esc(x.m)}\">m</a><a href=\"#x\">h</a>`}",
    "function f(x){el.innerHTML=`<a href=\"${esc(sichererLink(x.url))}\">a</a><img src=\"${esc(sichereBildquelle(x.u))}\">`}",
    "function f(x){a.href='/orders/'+x.id;location.href=`/invoices/${x.id}`;window.open(sichererLink(x.u))}",
    "function f(x){const u={a:`/quotes/${x.id}`,b:'/mahnwesen'}[x.t];el.innerHTML=`<a href=\"${u}\">a</a>`}",
    "function f(x){a.href=URL.createObjectURL(x.blob)}",
])
def test_scanner_laesst_gepruefte_links_durch(js):
    assert _funde(js)["l"] == []


def test_jinja_werte_in_on_attributen_werden_gefunden(tmp_path, monkeypatch):
    import tests.vorlagen_html as modul
    (tmp_path / "x.html").write_text('<button onclick="f({{ wert }})">a</button><button data-wert="{{ wert }}">b</button>',
                                     encoding="utf-8")
    monkeypatch.setattr(modul, "TEMPLATES", tmp_path)
    assert [f.ausdruck for f in jinja_handler("x.html")] == ['onclick="f({{ wert }})"']


# ---------------------------------------------------------------------------
# Was der Scanner als sicher annimmt, in node geprüft
# ---------------------------------------------------------------------------

PROBE = """<a b="c" d='e'>&amp;</a>"""


def _escaper_quellen() -> dict:
    """Jede Funktion der Vorlagen, die der Scanner als esc() erkennt: Name@Datei -> Quelltext der Definition."""
    out = {}
    for v in zusammenhaenge():
        p = Pruefer(v)
        for b in p.bereiche:
            if b.start not in p.escaper_ids:
                continue
            start, _ = p.bereich(b.start, b.start)
            _, ende = p.bereich(b.rumpf[1], b.rumpf[1])
            text = p.a.quelle.text[start:ende]
            datei = p.a.quelle.datei(p.a.t[b.start].pos)
            deklaration = re.match(r"function\s+" + re.escape(b.name) + r"\b", text)
            out[f"{b.name}@{datei}"] = (b.name, text if deklaration else f"const {b.name}={text};")
    return out


def test_jede_esc_variante_ist_erkannt():
    namen = {k.split("@")[0] for k in _escaper_quellen()}
    assert {"esc", "_dhEsc", "escHtml"} <= namen


@nur_mit_node
def test_jede_esc_funktion_ersetzt_alle_fuenf_zeichen():
    quellen = _escaper_quellen()
    js = "const out={};\n" + "\n".join(
        f"out[{json.dumps(k)}]=(()=>{{{text}\nreturn {name}({json.dumps(PROBE)});}})();" for k, (name, text) in quellen.items())
    js += "\nprocess.stdout.write(JSON.stringify(out));"
    for k, wert in _node(js, "Europe/Berlin").items():
        assert not re.search(r"[<>\"']", wert) and not re.search(r"&(?!amp;|lt;|gt;|quot;|#39;|#x27;)", wert), (k, wert)
        assert re.sub(r"&(amp|lt|gt|quot|#39|#x27);", lambda m: {"amp": "&", "lt": "<", "gt": ">", "quot": '"'}.get(m.group(1), "'"),
                      wert) == PROBE, (k, wert)


def _skripte(*namen: str) -> str:
    return "\n".join(s for n in namen for s in re.findall(r"<script>(.*?)</script>", (TEMPLATES / n).read_text(encoding="utf-8"),
                                                          flags=re.S))


@nur_mit_node
def test_die_datumsfunktionen_liefern_nur_ziffern():
    aufrufe = {"berlinToday": "berlinToday(new Date('2026-12-31T23:30:00Z'))", "berlinMonth": "berlinMonth()",
               "berlinTime": "berlinTime()", "berlinAddDays": "[berlinAddDays('2026-02-28',1),berlinAddDays('<b>\"',1)]"}
    assert set(aufrufe) == DATUM_FUNKTIONEN
    js = _skripte("_berlin_date.html") + "\nprocess.stdout.write(JSON.stringify({" + ",".join(
        f"{k}:{v}" for k, v in aufrufe.items()) + "}));"
    for name, wert in _node(js, "Europe/Berlin").items():
        for w in (wert if isinstance(wert, list) else [wert]):
            assert re.fullmatch(r"[0-9NaN:\-]+", w), (name, w)


LINKS = [
    # (Wert, sichererLink, sichereBildquelle)
    ("/projects/1", "/projects/1", "/projects/1"),
    ("/api/sent-documents/2/file", "/api/sent-documents/2/file", "/api/sent-documents/2/file"),
    ("#mangel-3", "#mangel-3", "#mangel-3"),
    ("?typ=rechnung", "?typ=rechnung", "?typ=rechnung"),
    ("https://hersteller.example/leiter", "https://hersteller.example/leiter", "https://hersteller.example/leiter"),
    ("http://hersteller.example", "http://hersteller.example", "http://hersteller.example"),
    ("mailto:bea@example.com", "mailto:bea@example.com", ""),
    ("tel:+49301234", "tel:+49301234", ""),
    ("data:image/png;base64,iVBORw0KGgo=", "#", "data:image/png;base64,iVBORw0KGgo="),
    ("javascript:alert(1)", "#", ""),
    ("JavaScript:alert(1)", "#", ""),
    (" javascript:alert(1)", "#", ""),
    ("java\tscript:alert(1)", "#", ""),
    ("\x01javascript:alert(1)", "#", ""),
    ("vbscript:msgbox(1)", "#", ""),
    ("data:text/html,<script>alert(1)</script>", "#", ""),
    ("data:image/svg+xml;base64,PHN2Zz4=", "#", ""),
    ("//fremd.example/x", "#", ""),
    ("/\\fremd.example", "#", ""),
    ("/\t/fremd.example", "#", ""),
    ("/%2F/fremd.example", "#", ""),
    ("https://fremd.example\\@erp", "#", ""),
    ("https:// fremd.example", "#", ""),
    ("fremd.example/x", "#", ""),
    ("", "#", ""),
    (None, "#", ""),
    (42, "#", ""),
]


@nur_mit_node
def test_sichererlink_und_sicherebildquelle_an_angriffen():
    js = _skripte("_weiterleitung.html", "_links.html") + f"\nconst werte={json.dumps([w for w, _, _ in LINKS])};" \
        "\nprocess.stdout.write(JSON.stringify(werte.map(w=>[sichererLink(w),sichereBildquelle(w)])));"
    assert _node(js, "Europe/Berlin") == [[a, b] for _, a, b in LINKS]


AKTIONEN_DOM = """
const _listener = {};
var document = {addEventListener(art, fn) { (_listener[art] = _listener[art] || []).push(fn); }};
var window = globalThis;
class Element { constructor(attrs, eltern = null, gesperrt = false) { this.attrs = attrs; this.eltern = eltern; this.gesperrt = gesperrt;
  this.dataset = Object.fromEntries(Object.entries(attrs).filter(([k]) => k.startsWith('data-')).map(([k, v]) => [k.slice(5), v])); }
  getAttribute(k) { return this.attrs[k] ?? null; }
  matches(sel) { return sel === ':disabled' && this.gesperrt; }
  closest(sel) { const k = sel.slice(1, -1); let e = this; while (e) { if (k in e.attrs) return e; e = e.eltern; } return null; } }
globalThis.Element = Element;
function feuern(art, ziel) { for (const fn of _listener[art] || []) fn({target: ziel}); }
"""


@nur_mit_node
def test_aktionen_rufen_die_angemeldete_funktion_mit_dem_element():
    """Klick auf ein Kind eines Elements mit data-klick ruft die Funktion mit dem Element (Werte aus dataset, auch mit ' und ");
    gesperrt, unbekannt und ohne Attribut passiert nichts; zweimal eingebunden hängt der Listener nur einmal (eine Wirkung je Klick);
    change geht an data-aenderung."""
    baustein = _skripte("_aktionen.html")
    js = AKTIONEN_DOM + baustein + "\n" + baustein + """
const aufrufe = [];
aktion('gruppe', el => aufrufe.push(['gruppe', el.dataset.gruppe, Number(el.dataset.id)]));
aktion('modul', el => aufrufe.push(['modul', el.dataset.schluessel]), 'change');
const knopf = new Element({'data-klick': 'gruppe', 'data-gruppe': `x"');alert(1);//`, 'data-id': '7'});
feuern('click', new Element({}, knopf));
feuern('click', new Element({'data-klick': 'gruppe', 'data-gruppe': 'g'}, null, true));
feuern('click', new Element({'data-klick': 'unbekannt'}));
feuern('click', new Element({}));
feuern('change', new Element({'data-aenderung': 'modul', 'data-schluessel': 'wartungen'}));
feuern('click', new Element({'data-aenderung': 'modul', 'data-schluessel': 'x'}));
process.stdout.write(JSON.stringify({aufrufe, listener: Object.fromEntries(Object.entries(_listener).map(([k, v]) => [k, v.length]))}));
"""
    ergebnis = _node(js, "Europe/Berlin")
    assert ergebnis["aufrufe"] == [["gruppe", "x\"');alert(1);//", 7], ["modul", "wartungen"]]
    assert ergebnis["listener"] == {"click": 1, "change": 1, "input": 1}


# ---------------------------------------------------------------------------
# TEXT_IDS: jedes Feld "id"/"…_id" mit Text
# ---------------------------------------------------------------------------

def test_jedes_id_feld_mit_text_steht_in_text_ids():
    """Der Scanner nimmt ein Feld "id"/"…_id" als Zahl. Jede Spalte (app/models.py) und jedes Feld eines Antwortschemas
    (app/schemas.py) unter diesem Namen, das Text hält, steht deshalb in TEXT_IDS -- dort gilt es als ungeschützt."""
    import typing

    from sqlalchemy import String, Text

    from app import models, schemas
    from app.database import Base

    funde = set()
    for tabelle in Base.metadata.tables.values():
        for spalte in tabelle.columns:
            if (spalte.name == "id" or spalte.name.endswith("_id")) and isinstance(spalte.type, (String, Text)):
                funde.add(spalte.name)
    for name in dir(schemas):
        schema = getattr(schemas, name)
        felder = getattr(schema, "model_fields", None)
        if not isinstance(felder, dict):
            continue
        for feld, info in felder.items():
            if not (feld == "id" or feld.endswith("_id")):
                continue
            typen = typing.get_args(info.annotation) or (info.annotation,)
            if str in typen:
                funde.add(feld)
    assert models  # Modelle geladen (Metadaten vollständig)
    assert funde - TEXT_IDS == set()
