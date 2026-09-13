from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Service, ProjectDocument, WorkPreparationDeliveryNote, WorkPreparationMaterialDeliveryNote
from app.main import (
    create_customer, create_project, create_quote, add_quote_item, create_supplier,
    bulk_assign_work_preparation_materials, unlink_material_delivery_note,
)
from app.schemas import (
    CustomerCreate, ProjectCreate, QuoteCreate, QuoteItemCreate, SupplierCreate,
    WorkPreparationMaterialBulkAssign,
)
from app.importers.leistungen_dach import parse_leistungen_dach_xml
from app.service import persist_project
from app.orders import create_order_from_quote
from app.work_preparation import ensure_preparation, preparation_to_dict, refresh_preparation_materials


def db_session():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup_order(db):
    sample=Path(__file__).parents[1]/'sample_data'/'Thiefes.xml'
    persist_project(db,parse_leistungen_dach_xml(sample.read_bytes()),'Thiefes.xml')
    c=create_customer(CustomerCreate(last_name='Bulk Kunde'),db)
    p=create_project(ProjectCreate(customer_id=c.id,name='Bulk Projekt'),db)
    q=create_quote(p.id,QuoteCreate(title='Bulk Angebot'),db)
    service=db.scalar(select(Service).where(Service.external_id=='L600109101011'))
    add_quote_item(q.id,QuoteItemCreate(service_id=service.id,quantity=Decimal('10')),db)
    return create_order_from_quote(db,q.id,order_date=date(2026,9,1),execution_start=None,execution_end=None,caseworker_employee_id=None,project_manager_employee_id=None,payment_terms=None,remarks=None)


def add_delivery_note(db, order, prep, supplier):
    doc=ProjectDocument(project_id=order.project_id,category='Lieferscheine',original_filename='LS-100.pdf',stored_filename='test.pdf',content_type='application/pdf',file_size=100,document_date=date(2026,9,1))
    db.add(doc); db.flush()
    note=WorkPreparationDeliveryNote(preparation_id=prep.id,project_document_id=doc.id,supplier_id=supplier.id,delivery_note_number='LS-100',document_date=date(2026,9,1))
    db.add(note); db.commit()
    return note


def test_bulk_assign_supplier_and_delivery_note_to_multiple_materials_and_unlink():
    db=db_session(); order=setup_order(db); prep=ensure_preparation(db,order.id)
    supplier=create_supplier(SupplierCreate(supplier_number='L-1',name='Dachhandel GmbH'),db)
    note=add_delivery_note(db,order,prep,supplier)
    data=preparation_to_dict(db,prep)
    ids=[x['id'] for x in data['materials'][:2]]
    updated=bulk_assign_work_preparation_materials(WorkPreparationMaterialBulkAssign(material_ids=ids,supplier_id=supplier.id,delivery_note_id=note.id),db)
    for mid in ids:
        row=next(x for x in updated['materials'] if x['id']==mid)
        assert row['supplier_id']==supplier.id
        assert any(d['id']==note.id and d['delivery_note_number']=='LS-100' for d in row['delivery_notes'])
    assert db.scalar(select(WorkPreparationMaterialDeliveryNote).where(WorkPreparationMaterialDeliveryNote.material_id==ids[0],WorkPreparationMaterialDeliveryNote.delivery_note_id==note.id)) is not None
    after=unlink_material_delivery_note(ids[0],note.id,db)
    row=next(x for x in after['materials'] if x['id']==ids[0])
    assert row['delivery_notes']==[]
    other=next(x for x in after['materials'] if x['id']==ids[1])
    assert len(other['delivery_notes'])==1


def test_material_delivery_note_links_survive_order_material_refresh():
    db=db_session(); order=setup_order(db); prep=ensure_preparation(db,order.id)
    supplier=create_supplier(SupplierCreate(name='Lieferant Test'),db)
    note=add_delivery_note(db,order,prep,supplier)
    data=preparation_to_dict(db,prep); mid=data['materials'][0]['id']
    bulk_assign_work_preparation_materials(WorkPreparationMaterialBulkAssign(material_ids=[mid],supplier_id=supplier.id,delivery_note_id=note.id),db)
    refresh_preparation_materials(db,order.id)
    data2=preparation_to_dict(db,ensure_preparation(db,order.id))
    assert any(any(d['id']==note.id for d in x['delivery_notes']) for x in data2['materials'])


def test_v083_ui_has_bulk_material_assignment():
    root=Path(__file__).parents[1]
    html=(root/'app/templates/work_preparation.html').read_text(encoding='utf-8')
    main=(root/'app/main.py').read_text(encoding='utf-8') + "".join(p.read_text(encoding="utf-8") for p in sorted((root/'app/routers').glob("*.py")))
    assert 'Positionen markiert' in html
    assert 'bulkAssignMaterials' in html
    assert 'Lieferschein zuordnen' in html
    assert '/api/work-preparation/materials/bulk-assign' in main
