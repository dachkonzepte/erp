from pathlib import Path


def test_v061_compact_table_editor_features_exist():
    root = Path(__file__).parents[1]
    html = (root / "app" / "templates" / "quote_editor.html").read_text(encoding="utf-8")
    assert "Version {{ app_version }}" in html
    assert "lv-columns" in html
    assert ">Menge<" in html
    assert ">Einheit<" in html
    assert "Einheitspreis" in html
    assert "Gesamtpreis" in html
    assert "saveInlineField" in html
    assert "inlineQtyKey" in html
    assert "unitOptionsHtml" in html
    assert 'id="tabCatalog"' in html
    assert 'id="tabEdit"' in html
    assert 'id="tabDetails"' in html
    assert 'id="panelDetails"' in html
    assert 'id="iUnit"></select>' in html


def test_v061_offer_header_is_moved_out_of_left_lv_workspace():
    root = Path(__file__).parents[1]
    html = (root / "app" / "templates" / "quote_editor.html").read_text(encoding="utf-8")
    lv_start = html.index('<section>')
    aside_start = html.index('<aside class="sticky">')
    left = html[lv_start:aside_start]
    assert 'id="hTitle"' not in left
    assert 'id="hPayment"' not in left
    assert 'id="hTitle"' in html[aside_start:]
