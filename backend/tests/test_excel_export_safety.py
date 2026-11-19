import pytest

from app.main import excel_text


@pytest.mark.parametrize("value", [
    "=1+1",
    "+SUM(1,1)",
    "-1+2",
    "@SUM(1,1)",
    " \t=HYPERLINK('https://example.invalid','open')",
    "\r\n+SUM(1,1)",
    "\x00-1+2",
    "\x1f@SUM(1,1)",
    "\ufeff=HYPERLINK('https://example.invalid','open')",
    "\u200b+SUM(1,1)",
])
def test_user_controlled_excel_text_is_neutralized(value):
    result = excel_text(value)
    assert result.startswith("'")
    import unicodedata
    assert not any(unicodedata.category(char) in ("Cc", "Cf") for char in result)


def test_safe_excel_text_is_preserved_and_none_is_empty():
    assert excel_text("Invoice 2026-001") == "Invoice 2026-001"
    assert excel_text(None) == ""
