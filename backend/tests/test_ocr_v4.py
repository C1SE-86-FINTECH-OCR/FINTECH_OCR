"""FINTECH OCR v4: new automatic fields and conservative validation."""
from datetime import date
from types import SimpleNamespace
from app.extraction import text_from_file, extract_fields, validate


def test_invoice_symbol_and_buyer_not_confused_with_seller():
    raw = (
        "HÓA ĐƠN GIÁ TRỊ GIA TĂNG\n"
        "Mẫu số: 01GTKT0/001\nKý hiệu: HM/17E\nSố: 0000003\n"
        "Ngày 16 tháng 10 năm 2017\n"
        "Đơn vị bán hàng: Công ty cổ phần ABC\nMã số thuế: 0101243150\n"
        "Họ tên người mua hàng: Nguyễn Văn Tiến\n"
        "Tên đơn vị: Công ty TNHH Bảo Ngọc\nMã số thuế: 0101243150\n"
        "Cộng tiền hàng: 8.000.000\nThuế suất GTGT: 10%\n"
        "Tiền thuế GTGT: 800.000\nTổng tiền thanh toán: 8.800.000"
    )
    r = extract_fields(raw, "jpg")
    assert r["invoice_number"] == "0000003"
    assert r["invoice_symbol"] == "HM/17E"
    assert r["seller_name"] == "Công ty cổ phần ABC"
    assert r["seller_tax_code"] == "0101243150"
    assert r["buyer_name"] == "Công ty TNHH Bảo Ngọc"
    assert r["buyer_tax_code"] == "0101243150"
    assert r["subtotal"] == 8_000_000
    assert r["vat_amount"] == 800_000
    assert r["total_amount"] == 8_800_000
    assert r["vat_rate"] == 10


def test_missing_buyer_and_money_not_fabricated():
    raw = "Số hóa đơn: 0000004\nĐơn vị bán hàng: Công ty A\nMã số thuế: 0101243150\nThuế suất: 10%\nTổng tiền thanh toán: 8.800.000"
    r = extract_fields(raw, 'jpg')
    assert r['buyer_name'] is None
    assert r['buyer_tax_code'] is None
    assert r['subtotal'] is None
    assert r['vat_amount'] is None
    assert r['total_amount'] == 8800000


def test_buyer_block_not_confused_with_signature_labels():
    raw = "Số: 0000004\nĐơn vị bán hàng: Công ty A\nMã số thuế: 0101243150\n" \
          "Người mua hàng\nNgười bán hàng\n"
    r = extract_fields(raw, 'jpg')
    assert r['buyer_name'] is None
    assert r['buyer_tax_code'] is None


def test_xml_seller_buyer_scoping_and_amounts():
    xml = b'''<HDon><DLHDon><TTChung><SHDon>001011</SHDon><KHHDon>1C26TAA</KHHDon><NLap>2026-11-03</NLap></TTChung>
      <NDHDon><NBan><Ten>Seller Co</Ten><MST>0312345678</MST></NBan>
      <NMua><Ten>Buyer Co</Ten><MST>0401234567</MST></NMua></NDHDon>
      <TToan><TgTCThue>1000000</TgTCThue><TgTThue>100000</TgTThue><TgTTTBSo>1100000</TgTTTBSo></TToan>
    </DLHDon></HDon>'''
    raw, method = text_from_file(xml, 'xml')
    r = extract_fields(raw, 'xml')
    assert method == 'xml'
    assert r['invoice_symbol'] == '1C26TAA'
    assert r['buyer_name'] == 'Buyer Co'
    assert r['buyer_tax_code'] == '0401234567'
    assert r['seller_tax_code'] == '0312345678'
    assert r['subtotal'] == 1_000_000
    assert r['vat_amount'] == 100_000
    assert r['total_amount'] == 1_100_000


def _invoice(**overrides):
    data = dict(invoice_number='0000003', invoice_date=date(2017,10,16),
                seller_tax_code='0101243150', buyer_tax_code=None,
                total_amount=8_800_000, subtotal=8_000_000,
                vat_amount=800_000, vat_rate=10)
    data.update(overrides)
    return SimpleNamespace(**data)


def test_valid_arithmetic():
    checks={k:ok for k,ok,_ in validate(_invoice())}
    assert checks['ARITH'] is True
    assert checks['VAT-ARITH'] is True


def test_invalid_arithmetic_rejected():
    checks={k:ok for k,ok,_ in validate(_invoice(vat_amount=900_000))}
    assert checks['ARITH'] is False
    assert checks['VAT-ARITH'] is False


def test_vat_rate_matches_srs_supported_rates():
    for rate in (0, 5, 8, 10):
        assert {k:ok for k,ok,_ in validate(_invoice(vat_rate=rate))}["VAT-RATE"] is True
    for rate in (-0.01, 0.01, 7, 8.5, 20, 30, 100.01):
        assert {k:ok for k,ok,_ in validate(_invoice(vat_rate=rate))}["VAT-RATE"] is False
    for rate in (float("nan"), float("inf"), float("-inf")):
        checks = {k:ok for k,ok,_ in validate(_invoice(vat_rate=rate))}
        assert checks["VAT-RATE"] is False
        assert checks["VAT-ARITH"] is False


def test_invalid_buyer_tax_code_if_supplied():
    checks={k:ok for k,ok,_ in validate(_invoice(buyer_tax_code='abc'))}
    assert checks['BUYER-TAX'] is False


def test_missing_buyer_tax_code_and_line_items_are_validation_findings():
    checks={k:ok for k,ok,_ in validate(_invoice())}
    assert checks['BUYER-TAX'] is False
    assert checks['ITEM-SUM'] is False


def test_optional_money_values_do_not_force_calculation():
    checks={k:ok for k,ok,_ in validate(_invoice(subtotal=None,vat_amount=None))}
    assert 'ARITH' not in checks
    assert 'VAT-ARITH' not in checks
