from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core import Base
from app.models import Invoice
from app.invoice_search import apply_invoice_search, normalize_search


def test_accent_case_and_spacing():
    assert normalize_search('  ĐẶNG  Ngọc Ánh ') == 'dang ngoc anh'


def test_relevance_literal_tokens_and_access_scope():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Invoice(id=1,file_id=1,invoice_number='120001',seller_name='Other'),
            Invoice(id=2,file_id=2,invoice_number='0001',seller_name='Công ty Đặng Ngọc',seller_tax_code='0401234567'),
            Invoice(id=3,file_id=3,invoice_number='000123',seller_name='Other'),
            Invoice(id=4,file_id=4,invoice_number='SPECIAL%_01',seller_name='Literal'),
            Invoice(id=5,file_id=5,invoice_number='SPECIALXX01',seller_name='Literal'),
        ])
        db.commit()
        def find(term, allowed=None, limit=20):
            q=select(Invoice)
            if allowed is not None:q=q.where(Invoice.id.in_(allowed))
            q,rank=apply_invoice_search(q,db,term)
            return [i.id for i in db.scalars(q.order_by(*([rank] if rank is not None else []),Invoice.id).limit(limit))]
        assert find('0001') == [2,3,1]
        assert find('0001',limit=1) == [2]
        assert find('NGOC dang') == [2]
        assert find('dang 0001') == [2]
        assert find('0401234567') == [2]
        assert find('%_') == [4]
        assert find('dang missing') == []
        assert find('0001',allowed=[1,3]) == [3,1]
        assert find('dang',allowed=[1,3]) == []
        assert find('   ') == [1,2,3,4,5]
    engine.dispose()
