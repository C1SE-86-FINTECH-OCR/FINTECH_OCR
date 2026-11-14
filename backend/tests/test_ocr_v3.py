"""Conservative OCR total recovery tests; no real invoice or database required."""
from PIL import Image
from app import extraction as module


def _label_data(words=("Tổng", "tiền", "thanh", "toán")):
    n = len(words)
    return {
        "text": list(words),
        "block_num": [1] * n,
        "par_num": [1] * n,
        "line_num": [1] * n,
        "top": [360] * n,
        "left": [130 + j * 40 for j in range(n)],
        "width": [35] * n,
        "height": [12] * n,
    }


def test_money_parse_thousands_ocr_fragment():
    assert module._amount_from_total_row_ocr("8.800.000") == 8_800_000
    assert module._amount_from_total_row_ocr("8.800,000") == 8_800_000
    assert module._amount_from_total_row_ocr("8,800.000") == 8_800_000
    assert module._amount_from_total_row_ocr("Số 8.800.000 và 800.000") is None


def test_recover_total_from_matching_crops(monkeypatch):
    monkeypatch.setattr(module.pytesseract, "image_to_data", lambda *a, **k: _label_data())
    reads = iter(("8.800.000", "8,800.000"))
    monkeypatch.setattr(module.pytesseract, "image_to_string", lambda *a, **k: next(reads))
    assert module._recover_total_from_image(Image.new("RGB", (800, 650), "white")) == 8_800_000


def test_does_not_guess_total_when_crops_disagree(monkeypatch):
    monkeypatch.setattr(module.pytesseract, "image_to_data", lambda *a, **k: _label_data())
    reads = iter(("8.000.000", "8.800.000"))
    monkeypatch.setattr(module.pytesseract, "image_to_string", lambda *a, **k: next(reads))
    assert module._recover_total_from_image(Image.new("RGB", (800, 650), "white")) is None


def test_no_label_does_not_infer_total(monkeypatch):
    monkeypatch.setattr(module.pytesseract, "image_to_data", lambda *a, **k: _label_data(("Thuế", "GTGT")))
    def must_not_run(*args, **kwargs):
        raise AssertionError("Should not OCR unlabelled numeric regions")
    monkeypatch.setattr(module.pytesseract, "image_to_string", must_not_run)
    assert module._recover_total_from_image(Image.new("RGB", (800, 650), "white")) is None
