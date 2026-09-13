from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_caseworkers_static_route_precedes_employee_dynamic_route():
    main = (ROOT / "app" / "routers" / "employees.py").read_text(encoding="utf-8")
    static = main.index('@router.get("/api/employees/caseworkers"')
    dynamic = main.index('@router.get("/api/employees/{employee_id}"')
    assert static < dynamic

def test_quote_editor_keeps_core_masterdata_independent_from_optional_employee_loads():
    html = (ROOT / "app" / "templates" / "quote_editor.html").read_text(encoding="utf-8")
    assert "[quote,services,optionGroups]=await Promise.all" in html
    assert "api('/api/employees/caseworkers').catch(()=>[])" in html
    assert "api('/api/employees').catch(()=>[])" in html

def test_order_editor_employee_lists_are_resilient():
    html = (ROOT / "app" / "templates" / "order.html").read_text(encoding="utf-8")
    assert "api('/api/employees').catch(()=>[])" in html
    assert "api('/api/employees/caseworkers').catch(()=>[])" in html
