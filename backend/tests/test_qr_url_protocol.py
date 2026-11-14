import pytest

from app.extraction import extract_fields


@pytest.mark.parametrize(
    "url",
    [
        "http://hoadondientu.gdt.gov.vn/lookup?id=123",
        "https://hoadondientu.gdt.gov.vn/lookup?id=123",
    ],
)
def test_qr_url_accepts_http_and_https(url):
    assert extract_fields(f"Tra cứu hóa đơn: {url}", "pdf")["qr_url"] == url


@pytest.mark.parametrize(
    "url",
    [
        "ftp://hoadondientu.gdt.gov.vn/lookup?id=123",
        "file:///C:/sensitive.txt",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "https://",
    ],
)
def test_qr_url_rejects_non_http_protocols_or_missing_host(url):
    assert extract_fields(f"Tra cứu hóa đơn: {url}", "pdf")["qr_url"] is None
