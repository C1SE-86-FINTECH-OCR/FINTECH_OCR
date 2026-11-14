"""Deterministic OCR v5 tests: spatial row parsing never invents money."""
from PIL import Image
from app import extraction as ex


def test_financial_row_labels_and_no_vat_rate_confusion():
    assert ex._financial_row_kind('Cộng tiền hàng:') == 'subtotal'
    assert ex._financial_row_kind('Công tiễn hing:') == 'subtotal'
    assert ex._financial_row_kind('Tiên thuế GTGT:') == 'vat_amount'
    assert ex._financial_row_kind('Thuế suất GTGT: 10%') is None
    assert ex._financial_row_kind('Số tiền viết bằng chữ:') is None


def test_spatial_amount_parser_formats():
    assert ex._money_from_numeric_crop('8.000.000\n') == 8000000
    assert ex._money_from_numeric_crop('800.000,\n') == 800000
    assert ex._money_from_numeric_crop('8,000,000') == 8000000
    assert ex._money_from_numeric_crop('8.000.000 800.000') is None
    assert ex._money_from_numeric_crop('Có một trăm nghìn đồng') is None


def test_only_fill_explicitly_recognized_fields():
    existing={'subtotal': None, 'vat_amount': None, 'total_amount': 8_800_000}
    assert ex._consistent_recovered_amounts(existing, {'subtotal':8_000_000,'vat_amount':800_000}) == {'subtotal':8_000_000,'vat_amount':800_000}
    assert ex._consistent_recovered_amounts(existing, {}) == {}


def test_contradictory_amounts_are_not_auto_filled():
    existing={'subtotal': None, 'vat_amount': None, 'total_amount': 8_800_000}
    assert ex._consistent_recovered_amounts(existing, {'subtotal':8_000_000,'vat_amount':900_000}) == {}


def test_no_arithmetic_fabrication_when_vat_missing():
    existing={'subtotal':None, 'vat_amount':None, 'total_amount':8_800_000}
    assert ex._consistent_recovered_amounts(existing, {'subtotal':8_000_000}) == {'subtotal':8_000_000}


def test_preserves_explicitly_existing_values():
    existing={'subtotal': 7_000_000, 'vat_amount':None, 'total_amount':8_800_000}
    assert ex._consistent_recovered_amounts(existing, {'subtotal':8_000_000, 'vat_amount':800_000}) == {}


def _fake_spatial_data(include_vat=True):
    groups=[(20,650,['Công','tiễn','hing:']), (21,704,['Tiên','thuế','GTGT:'])]
    if not include_vat:groups=groups[:1]
    rows=[]
    for key,top,words in groups:
        for j, word in enumerate(words):
            rows.append((word,key,1,1,top,26,250+j*45,40))
    names=('text','block_num','par_num','line_num','top','height','left','width')
    return {name:[row[idx] for row in rows] for idx,name in enumerate(names)}


def test_spatial_rows_require_two_matching_reads(monkeypatch):
    monkeypatch.setattr(ex.pytesseract,'image_to_data',lambda *a,**kw:_fake_spatial_data())
    responses=iter(['8,000,000','8.000.000','8.000.000','200.000','800.000','800.000'])
    monkeypatch.setattr(ex.pytesseract,'image_to_string',lambda *a,**kw:next(responses))
    im=Image.new('RGB',(1600,1200),'white')
    assert ex._recover_financial_rows_from_image(im,{'subtotal','vat_amount'}) == {'subtotal':8_000_000,'vat_amount':800_000}


def test_ambiguous_readings_leave_vat_empty(monkeypatch):
    monkeypatch.setattr(ex.pytesseract,'image_to_data',lambda *a,**kw:_fake_spatial_data())
    responses=iter(['8,000,000','8.000.000','8.000.000','200.000','400.000','800.000'])
    monkeypatch.setattr(ex.pytesseract,'image_to_string',lambda *a,**kw:next(responses))
    im=Image.new('RGB',(1600,1200),'white')
    assert ex._recover_financial_rows_from_image(im,{'subtotal','vat_amount'}) == {'subtotal':8_000_000}


def test_no_label_no_spatial_guess(monkeypatch):
    monkeypatch.setattr(ex.pytesseract,'image_to_data',lambda *a,**kw:_fake_spatial_data(include_vat=False))
    monkeypatch.setattr(ex.pytesseract,'image_to_string',lambda *a,**kw:'800.000')
    im=Image.new('RGB',(1600,1200),'white')
    assert ex._recover_financial_rows_from_image(im,{'vat_amount'}) == {}


def test_error_in_optional_ocr_fallback_is_nonfatal(monkeypatch):
    def broken(*a,**kw): raise RuntimeError('No OCR process')
    monkeypatch.setattr(ex.pytesseract, 'image_to_data',broken)
    assert ex._recover_financial_rows_from_image(Image.new('RGB',(1600,1200)),{'subtotal'}) == {}
