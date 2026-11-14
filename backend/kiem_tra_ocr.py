r"""FINTECH OCR C1SE.86 - chuan doan OCR truc tiep, KHONG thay doi database.

Dat file nay trong fintech-ocr-starter/backend/.
PowerShell:
  .\.venv\Scripts\python.exe .\kiem_tra_ocr.py
  .\.venv\Scripts\python.exe .\kiem_tra_ocr.py "D:\\DuLieu\\hoa_don.png"
  .\.venv\Scripts\python.exe .\kiem_tra_ocr.py "D:\\DuLieu\\hoa_don.png" --show-text
"""
import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace


def configure_tesseract():
    try:
        import pytesseract
    except ImportError:
        print("[LOI] Chua cai pytesseract. Hay cai requirements.txt vao .venv")
        return None
    specified = os.environ.get("TESSERACT_CMD", "").strip()
    candidates = [specified] if specified else []
    if os.name == "nt":
        candidates.extend([
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ])
    for path in candidates:
        if path and Path(path).is_file():
            pytesseract.pytesseract.tesseract_cmd = path
            break
    try:
        version = pytesseract.get_tesseract_version()
        languages = pytesseract.get_languages(config="")
        print(f"[OK] Tesseract version: {version}")
        print(f"[OK] Co {len(languages)} bo ngon ngu; quan trong: {', '.join(lang for lang in ('eng','vie','osd') if lang in languages) or 'chua co'}")
        if "vie" not in languages:
            print("[CANH BAO] Chua co 'vie' - OCR tieng Viet co the kem chinh xac.")
        if "eng" not in languages:
            print("[CANH BAO] Chua co 'eng' - OCR tieng Anh co the kem chinh xac.")
        return pytesseract
    except Exception as exc:
        print(f"[LOI] Python chua goi duoc Tesseract: {type(exc).__name__}: {exc}")
        print("Goi y: kiem tra C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
        return None


def direct_ocr_error(data, ext, pytesseract):
    """Dua ra loi that, vi extraction.py goc co the an exception va tra text rong."""
    if ext == "xml":
        return "Thu kiem tra XML bang xml.etree.ElementTree.parse."
    if pytesseract is None:
        return "pytesseract/Tesseract chua kha dung"
    try:
        if ext in {"png", "jpg", "jpeg"}:
            from PIL import Image
            from io import BytesIO
            with Image.open(BytesIO(data)) as img:
                img.load()
                return "OCR truc tiep lay duoc %s ky tu" % len(
                    pytesseract.image_to_string(img.convert('RGB'), lang='vie+eng')
                )
        if ext == "pdf":
            import fitz
            with fitz.open(stream=data, filetype="pdf") as doc:
                if doc.page_count == 0:
                    return "PDF khong co trang"
                pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                from PIL import Image
                from io import BytesIO
                img = Image.open(BytesIO(pix.tobytes('png')))
                return "OCR trang PDF dau lay duoc %s ky tu" % len(
                    pytesseract.image_to_string(img, lang='vie+eng')
                )
        return "Dinh dang chua duoc ho tro"
    except Exception as exc:
        return f"LOI THUC TE: {type(exc).__name__}: {exc}"


def show_results(text, method, ext, show_text):
    from app.extraction import extract_fields, validate
    print(f"\n[INFO] Phuong thuc: {method}")
    print(f"[INFO] So ky tu doc duoc: {len(text)}")
    if show_text:
        print("\n--- VAN BAN OCR (co the chua thong tin rieng tu) ---")
        print(text[:3500] if text else "<rong>")
        print("--- HET VAN BAN OCR ---\n")
    fields = extract_fields(text, ext)
    print("\n--- CAC TRUONG DA TRICH XUAT ---")
    print(json.dumps(fields, ensure_ascii=False, indent=2, default=str))
    obj = SimpleNamespace(
        invoice_number=fields.get('invoice_number'),
        invoice_date=fields.get('invoice_date'),
        seller_tax_code=fields.get('seller_tax_code'),
        total_amount=fields.get('total_amount'),
        subtotal=fields.get('subtotal'),
        vat_amount=fields.get('vat_amount'),
    )
    print("\n--- KET QUA VALIDATION CO BAN ---")
    for code, passed, message in validate(obj):
        print(f"  {'PASS' if passed else 'FAIL'}  {code}: {message if not passed else 'OK'}")
    print("\n[LƯU Y] Confidence trong starter la ty le truong co du lieu, KHONG phai do tin cay AI.")
    if not text.strip():
        print("[CANH BAO] Chua lay duoc van ban. Can kiem tra anh/PDF va cau hinh OCR.")
    elif not fields.get('invoice_number') and not fields.get('total_amount'):
        print("[CANH BAO] OCR co van ban nhung regex chua rut ra truong chinh. Day la viec can nang cap.")


def main():
    parser = argparse.ArgumentParser(description="Kiem tra OCR FINTECH OCR - khong ghi database")
    parser.add_argument('file', nargs='?', help='Duong dan day du toi hoa don PNG/JPG/PDF/XML')
    parser.add_argument('--show-text', action='store_true', help='In 3500 ky tu OCR. KHONG chia se khi chua che thong tin rieng tu.')
    args = parser.parse_args()
    print("FINTECH OCR - OCR DIAGNOSTIC (READ-ONLY)")
    print("Python:", sys.executable)
    pytesseract = configure_tesseract()
    try:
        from app.extraction import text_from_file
    except Exception as exc:
        print("[LOI] Khong import duoc app.extraction:", repr(exc))
        print("Dat kiem_tra_ocr.py trong thu muc backend, cung cap voi app/.")
        return 2
    if not args.file:
        print("\n[SELF-TEST] Du lieu mau, khong phai ket qua OCR tu anh")
        sample = (
            "HÓA ĐƠN GIÁ TRỊ GIA TĂNG\n"
            "Số hóa đơn: 0000123\n"
            "Ngày: 02/11/2026\n"
            "Đơn vị bán hàng: Cửa hàng thử nghiệm\n"
            "Mã số thuế: 0312345678\n"
            "Thuế suất: 8%\n"
            "Tổng thanh toán: 1.234.567\n"
        )
        show_results(sample, 'sample-text-no-ocr', 'png', args.show_text)
        print("\n[BUOC TIEP THEO] Chay kem DUONG DAN ANH/PDF/XML hoa don that de kiem tra OCR.")
        return 0
    path = Path(args.file.strip('"')).expanduser()
    if not path.is_file():
        print("[LOI] Khong tim thay file:", path)
        return 2
    ext = path.suffix.lower().lstrip('.')
    if ext == 'jpeg':
        ext = 'jpg'
    if ext not in {'png', 'jpg', 'pdf', 'xml'}:
        print("[LOI] Chi ho tro file .png/.jpg/.pdf/.xml")
        return 2
    data = path.read_bytes()
    print(f"\n[FILE] {path.name} - {len(data):,} bytes")
    try:
        text, method = text_from_file(data, ext)
        show_results(text, method, ext, args.show_text)
        if method.endswith('no-ocr') or not text.strip():
            print("\n[CHUAN DOAN]", direct_ocr_error(data, ext, pytesseract))
            return 1
        return 0
    except Exception as exc:
        print(f"[LOI] OCR/parse that bai: {type(exc).__name__}: {exc}")
        print("[CHUAN DOAN]", direct_ocr_error(data, ext, pytesseract))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
