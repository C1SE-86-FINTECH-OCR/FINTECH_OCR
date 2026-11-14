"""Run from backend with python -m pytest tests/test_extraction.py -q."""
from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest
import fitz
from PIL import Image
import pytesseract
import app.extraction as extraction
from app.extraction import classify, extract_fields, extract_line_items, money, text_from_file, validate


def test_vietnamese_text_fields():
    raw = (
        "HÓA ĐƠN GIÁ TRỊ GIA TĂNG\n"
        "Số hóa đơn: 0000123\nNgày: 02/11/2026\n"
        "Đơn vị bán hàng: Cửa hàng thử nghiệm\nMã số thuế: 0312345678\n"
        "Thuế suất: 8%\nTổng thanh toán: 1.234.567\n"
    )
    r = extract_fields(raw, "png")
    assert r["invoice_number"] == "0000123"
    assert r["invoice_date"] == date(2026, 11, 2)
    assert r["seller_name"] == "Cửa hàng thử nghiệm"
    assert r["seller_tax_code"] == "0312345678"
    assert r["total_amount"] == 1234567.0
    assert r["vat_rate"] == 8.0
    assert r["document_type"] == "einvoice"
    assert r["confidence_score"] == 1.0


def test_noisy_vietnamese_invoice_ocr():
    raw = (
        "HOA DON GIA TRI GIA TANG\n"
        "gây 16 tháng 10 nam 2017\nSố; 0000003\n"
        "Đxm vị bán hang: Công ty có phần ABC\nMã số thuế: 0101243150\n"
        "Họ tên người mua hàng: Nguyễn Văn Tiên\nMã số thuế: 9101243150\n"
        "Thuế suất GTGT: 10 %\nTổng tiền thanh toán:\n"
    )
    r = extract_fields(raw, "jpg")
    assert r["invoice_number"] == "0000003"
    assert r["invoice_date"] == date(2017, 10, 16)
    assert r["seller_name"] == "Công ty có phần ABC"
    assert r["seller_tax_code"] == "0101243150"
    assert r["vat_rate"] == 10.0
    assert r["total_amount"] is None  # never invent financial values


def test_money_and_english():
    assert money("8.800.000") == 8800000.0
    assert money("1,234.56") == 1234.56
    raw = (
        "Invoice No: AB12345\nDate: 12/10/2026\n"
        "Supplier: Example Shop Ltd\nTax code: 0312345678\nTOTAL: 1,234.56\n"
    )
    r = extract_fields(raw, "jpg")
    assert r["invoice_number"] == "AB12345"
    assert r["total_amount"] == 1234.56
    assert r["seller_name"] == "Example Shop Ltd"


def test_xml_structured():
    xml = b"""<?xml version='1.0'?>
    <HDon><DLHDon><NDHDon><NBan><Ten>Example Co</Ten><MST>0312345678</MST></NBan>
    </NDHDon><TTChung><SHDon>000199</SHDon><NLap>2026-11-02</NLap></TTChung>
    <TToan><TgTTTBSo>8800000</TgTTTBSo></TToan></DLHDon></HDon>"""
    text, method = text_from_file(xml, "xml")
    assert method == "xml"
    r = extract_fields(text, "xml")
    assert r["invoice_number"] == "000199"
    assert r["invoice_date"] == date(2026, 11, 2)
    assert r["seller_name"] == "Example Co"
    assert r["total_amount"] == 8800000.0
    assert r["seller_tax_code"] == "0312345678"


def test_uat_9f_xml_fields_and_line_items():
    xml_path = Path(__file__).resolve().parents[2] / "UAT_9F_XML_UPLOAD.xml"
    data = xml_path.read_bytes()
    raw, method = text_from_file(data, "xml")
    fields = extract_fields(raw, "xml")
    items = extract_line_items(data, "xml")

    assert method == "xml"
    assert fields["invoice_number"] == "UAT9F-XML-001"
    assert fields["invoice_date"] == date(2026, 11, 8)
    assert fields["seller_name"] == "UAT 9F Test Supplier"
    assert fields["seller_tax_code"] == "0101234567"
    assert fields["buyer_name"] == "FINTECH OCR Test Buyer"
    assert fields["buyer_tax_code"] == "0107654321"
    assert fields["subtotal"] == 200000
    assert fields["vat_amount"] == 16000
    assert fields["total_amount"] == 216000
    assert fields["document_type"] == "einvoice"
    assert fields["confidence_score"] == 1
    assert len(items) == 1
    assert items[0]["description"] == "Test service UAT 9F XML"
    assert items[0]["amount"] == 200000
    assert items[0]["quantity"] is None
    assert items[0]["unit_price"] is None


def test_xml_bom_and_leading_whitespace_are_accepted_without_changing_values():
    source = Path(__file__).resolve().parents[2] / "UAT_9F_XML_UPLOAD.xml"
    original = source.read_bytes()
    data = b"\xef\xbb\xbf \r\n\t" + original

    raw, method = text_from_file(data, "xml")
    fields = extract_fields(raw, "xml")
    items = extract_line_items(data, "xml")

    assert method == "xml"
    assert fields["invoice_number"] == "UAT9F-XML-001"
    assert fields["document_type"] == "einvoice"
    assert len(items) == 1 and items[0]["amount"] == 200000


def test_structured_but_incomplete_xml_keeps_missing_fields_empty():
    data = b"""<HDon><DLHDon><TTChung><KHHDon>1C26</KHHDon></TTChung><NDHDon><NBan/><NMua/></NDHDon>
    <TToan><TgTTTBSo/></TToan></DLHDon></HDon>"""
    raw, _ = text_from_file(data, "xml")
    fields = extract_fields(raw, "xml")

    assert fields["document_type"] == "einvoice"
    assert fields["invoice_number"] is None
    assert fields["invoice_date"] is None
    assert fields["seller_name"] is None
    assert fields["seller_tax_code"] is None
    assert fields["total_amount"] is None
    assert extract_line_items(data, "xml") == []


def test_turn5_line_item_xml_fixture_remains_supported():
    xml_path = Path(__file__).resolve().parent / "fixtures" / "turn5-line-items.xml"
    data = xml_path.read_bytes()
    raw, _ = text_from_file(data, "xml")
    fields = extract_fields(raw, "xml")
    items = extract_line_items(data, "xml")

    assert fields["invoice_number"] == "TURN5-XML-LINE-001"
    assert fields["document_type"] == "einvoice"
    assert fields["buyer_name"] == "XML Test Buyer"
    assert fields["total_amount"] == 1080
    assert len(items) == 1
    assert items[0]["description"] == "Test service"
    assert items[0]["amount"] == 1000
    assert items[0]["quantity"] is None
    assert items[0]["unit_price"] is None


def test_xml_extension_does_not_alone_classify_as_einvoice():
    raw, method = text_from_file(b"<root><message>VAT invoice</message></root>", "xml")
    assert method == "xml"
    assert classify("xml", raw) == "unknown"


def test_document_type_classifier_distinguishes_bill_from_unknown():
    assert classify("pdf", "Hóa đơn bán lẻ") == "bill"
    assert classify("pdf", "meeting notes and travel memo") == "unknown"


def test_pdf_text_fixture_uses_embedded_text_without_ocr():
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Synthetic PDF invoice with embedded searchable text")
    source = document.tobytes()
    document.close()

    raw, method = text_from_file(source, "pdf")

    assert method == "pdf-text"
    assert "Synthetic PDF invoice" in raw


def test_invoice_number_with_pdf_soft_hyphens_is_normalized():
    raw = "Invoice No: OCR\u00ad2026\u00ad001\nDate: 08/11/2026"
    fields = extract_fields(raw, "pdf")

    assert fields["invoice_number"] == "OCR-2026-001"


@pytest.mark.parametrize("image_format,extension", [("PNG", "png"), ("JPEG", "jpg")])
def test_image_fixture_uses_ocr_engine_output(monkeypatch, image_format, extension):
    image_bytes = BytesIO()
    Image.new("RGB", (32, 32), "white").save(image_bytes, format=image_format)
    recognized = (
        "Invoice No: IMG-12345\nDate: 2026-11-08\n"
        "Supplier: Synthetic Fixture Shop\nTax code: 0101234567\nTOTAL: 123,45"
    )
    monkeypatch.setattr(extraction.pytesseract, "image_to_string", lambda *_args, **_kwargs: recognized)

    raw, method = text_from_file(image_bytes.getvalue(), extension)

    assert method == "image-ocr"
    assert raw == recognized
    fields = extract_fields(raw, extension)
    assert fields["invoice_number"] == "IMG-12345"
    assert fields["seller_tax_code"] == "0101234567"


def test_xml_with_leading_whitespace_but_malformed_body_is_rejected():
    with pytest.raises(ET.ParseError):
        text_from_file(b"\r\n<?xml version='1.0'?><HDon><DLHDon>", "xml")


def test_dtd_rejected():
    with pytest.raises(ValueError):
        text_from_file(b"<!DOCTYPE root [<!ENTITY x SYSTEM 'file:///c:/passwd'>]><root/>", "xml")


def test_missing_tesseract_is_reported_instead_of_returning_empty_ocr(monkeypatch):
    image_bytes = BytesIO()
    Image.new("RGB", (16, 16), "white").save(image_bytes, format="PNG")

    def unavailable(*_args, **_kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(extraction.pytesseract, "image_to_string", unavailable)
    with pytest.raises(RuntimeError, match="Tesseract OCR engine is unavailable"):
        text_from_file(image_bytes.getvalue(), "png")


def test_sparse_layout_retries_only_the_item_table_with_psm6(monkeypatch):
    image_bytes = BytesIO()
    Image.new("RGB", (1500, 1500), "white").save(image_bytes, format="PNG")
    first_pass = "\n".join((
        "HÓA ĐƠN GIÁ TRỊ GIA TĂNG", "Invoice No: OCR-ITEM-003", "Date: 09/11/2026",
        "Supplier: Synthetic Supplier", "Tax code: 0101234567", "Buyer tax code: 0107654321",
        "STT | Tên hàng hóa/dịch vụ | ĐVT | Số lượng | Đơn giá | Thành tiền",
        "Cộng tiền hàng: 600.000", "Thuế suất GTGT: 8%", "Tiền thuế GTGT: 48.000",
        "Tổng tiền thanh toán: 648.000",
    ))
    table_pass = "\n".join((
        "STT | Tên hàng hóa/dịch vụ | ĐVT | Số lượng | Đơn giá | Thành tiền",
        "1 | Service one | service | 2 | 100.000 | 200.000",
        "2 | Service two | service | 2 | 100.000 | 200.000",
        "3 | Service three | service | 2 | 100.000 | 200.000",
        "Cộng tiền hàng: 600.000",
    ))
    returned = iter((first_pass, table_pass))
    calls = []

    def recognize(_image, **kwargs):
        calls.append(kwargs["config"])
        return next(returned)

    monkeypatch.setattr(extraction.pytesseract, "image_to_string", recognize)
    raw, method = text_from_file(image_bytes.getvalue(), "png")
    items = extract_line_items(image_bytes.getvalue(), "png", raw)

    assert method == "image-ocr"
    assert calls == ["--psm 11", "--psm 6"]
    assert [item["description"] for item in items] == ["Service one", "Service two", "Service three"]
    assert raw.count("Tổng tiền thanh toán") == 1


def test_validation_missing_total():
    v = SimpleNamespace(invoice_number="0000003", invoice_date=date(2017,10,16),
        seller_tax_code="0101243150", total_amount=None,
        subtotal=None, vat_amount=None)
    checks = {code: passed for code, passed, _ in validate(v)}
    assert checks == {
        "INV-NO": True,
        "DATE": True,
        "TAX-CODE": True,
        "TOTAL": False,
        "BUYER-TAX": False,
        "ITEM-SUM": False,
    }
