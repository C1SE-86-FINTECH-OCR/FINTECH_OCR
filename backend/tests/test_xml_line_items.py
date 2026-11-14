from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.extraction import extract_line_items, validate


def xml(items: str, namespace: str = "") -> bytes:
    ns = f' xmlns="{namespace}"' if namespace else ""
    return f"<HDon{ns}><DLHDon><NDHDon><DSHHDVu>{items}</DSHHDVu></NDHDon></DLHDon></HDon>".encode()


def item(name: str, amount: str, fields: str = "") -> str:
    return f"<HHDVu><THHDVu>{name}</THHDVu>{fields}<ThTien>{amount}</ThTien></HHDVu>"


def test_extracts_single_item_and_optional_fields_as_none():
    rows = extract_line_items(xml(item("Test service", "1000")), "xml")
    assert rows == [{
        "line_no": 1, "description": "Test service", "unit": None,
        "quantity": None, "unit_price": None, "amount": Decimal("1000.0"),
    }]


def test_extracts_multiple_items_and_keeps_unverified_optional_fields_empty():
    rows = extract_line_items(xml(
        item("Consulting", "2000") + item("Support", "1000")
    ), "xml")
    assert [row["line_no"] for row in rows] == [1, 2]
    assert all(row[key] is None for row in rows for key in ("unit", "quantity", "unit_price"))


def test_extracts_namespaced_xml():
    rows = extract_line_items(xml(item("Namespace item", "123.45"), "urn:invoice"), "xml")
    assert rows[0]["description"] == "Namespace item"
    assert rows[0]["amount"] == Decimal("123.45")


def test_decimal_amount_with_currency_marker():
    rows = extract_line_items(xml(item("Decimal item", "1.234,56 VND")), "xml")
    assert rows[0]["amount"] == Decimal("1234.56")


def test_ignores_rows_without_description_or_explicit_amount():
    rows = extract_line_items(xml(
        "<HHDVu><THHDVu>Missing amount</THHDVu></HHDVu>"
        "<HHDVu><ThTien>50</ThTien></HHDVu>"
        + item("Complete", "25")
    ), "xml")
    assert len(rows) == 1
    assert rows[0]["line_no"] == 1
    assert rows[0]["amount"] == Decimal("25.0")


def test_explicit_zero_amount_is_distinct_from_missing_amount():
    rows = extract_line_items(xml(
        item("Zero amount", "0")
        + "<HHDVu><THHDVu>Missing amount</THHDVu></HHDVu>"
    ), "xml")

    assert len(rows) == 1
    assert rows[0]["description"] == "Zero amount"
    assert rows[0]["amount"] == Decimal("0.0")


def test_xml_without_details_returns_no_fake_items():
    assert extract_line_items(b"<HDon><DLHDon/></HDon>", "xml") == []


@pytest.mark.parametrize("payload", [b"<HDon><DLHDon>", b"<!DOCTYPE x [<!ENTITY e SYSTEM 'file:///x'>]><HDon>&e;</HDon>"])
def test_rejects_malformed_or_entity_xml(payload):
    with pytest.raises(Exception):
        extract_line_items(payload, "xml")


def test_non_xml_upload_formats_do_not_extract_line_items():
    assert extract_line_items(b"ignored", "pdf") == []
    assert extract_line_items(b"ignored", "jpg") == []
    assert extract_line_items(b"ignored", "png") == []


def _delimited_ocr_table(count: int) -> str:
    rows = [
        "Hóa đơn giá trị gia tăng",
        "Đơn vị bán hàng: Synthetic Supplier | Mã số thuế: 0101234567",
        "Tên đơn vị: Synthetic Buyer | Mã số thuế: 0107654321",
        "STT | Tên hàng hóa, dịch vụ | ĐVT | Số lượng | Đơn giá | Thành tiền",
    ]
    rows.extend(
        f"{number} | Synthetic service {number} | service | 2 | 100.000 | 200.000"
        for number in range(1, count + 1)
    )
    rows.extend(("Cộng tiền hàng: 200.000", "Tiền thuế GTGT: 16.000", "Tổng tiền thanh toán: 216.000"))
    return "\n".join(rows)


@pytest.mark.parametrize("extension", ["png", "jpg", "pdf"])
@pytest.mark.parametrize("count", [1, 3, 5])
def test_extracts_one_three_and_five_delimited_ocr_items(extension, count):
    raw = _delimited_ocr_table(count)
    rows = extract_line_items(b"synthetic source bytes", extension, raw)

    assert len(rows) == count
    assert [row["line_no"] for row in rows] == list(range(1, count + 1))
    assert [row["description"] for row in rows] == [f"Synthetic service {i}" for i in range(1, count + 1)]
    assert all(row["unit"] == "service" and row["quantity"] == 2 for row in rows)
    assert all(row["unit_price"] == 100000 and row["amount"] == Decimal("200000.0") for row in rows)


def test_ocr_item_fields_missing_from_explicit_table_stay_null():
    raw = "\n".join((
        "STT | Tên hàng hóa/dịch vụ | ĐVT | Số lượng | Đơn giá | Thành tiền",
        "1 | Consulting | hour |  |  | 200.000",
    ))

    rows = extract_line_items(b"", "png", raw)

    assert rows == [{
        "line_no": 1, "description": "Consulting", "unit": "hour",
        "quantity": None, "unit_price": None, "amount": Decimal("200000.0"),
    }]


def test_ambiguous_or_incomplete_ocr_rows_do_not_create_fake_items():
    raw = "\n".join((
        "STT | Tên hàng hóa/dịch vụ | ĐVT | Số lượng | Đơn giá | Thành tiền",
        "1 | Valid line | service | 1 | 100.000 | 100.000",
        "2 | OCR amount unclear | service | 1 | 100.000 | ???",
        "3 |  | service | 1 | 100.000 | 100.000",
        "4 | Ambiguous columns | 2 | 100.000",
        "Subtotal | 999.000",
        "1 | Tổng tiền thanh toán | 100.000",
        "1 | Valid line | service | 1 | 100.000 | 100.000",
    ))

    rows = extract_line_items(b"", "pdf", raw)

    assert len(rows) == 1
    assert rows[0]["description"] == "Valid line"
    assert rows[0]["amount"] == Decimal("100000.0")


def test_headerless_ocr_only_accepts_explicit_three_cell_amount_row():
    raw = "1 | Explicit service | 125.000\n2 | Incomplete service |"

    rows = extract_line_items(b"", "jpg", raw)

    assert rows == [{
        "line_no": 1, "description": "Explicit service", "unit": None,
        "quantity": None, "unit_price": None, "amount": Decimal("125000.0"),
    }]


def _invoice(subtotal):
    return SimpleNamespace(
        invoice_number="XML-1", invoice_date=date(2026, 11, 7),
        seller_tax_code="0101234567", buyer_tax_code="0107654321",
        total_amount=1080, subtotal=subtotal, vat_amount=80, vat_rate=8,
    )


def test_item_sum_passes_for_matching_lines_and_fails_for_mismatch():
    lines = [{"amount": Decimal("600")}, {"amount": Decimal("400")}]
    passed = {code: ok for code, ok, _ in validate(_invoice(1000), lines)}
    failed = {code: ok for code, ok, _ in validate(_invoice(1003), lines)}
    missing = {code: ok for code, ok, _ in validate(_invoice(1000), [])}
    assert passed["ITEM-SUM"] is True
    assert failed["ITEM-SUM"] is False
    assert missing["ITEM-SUM"] is False
