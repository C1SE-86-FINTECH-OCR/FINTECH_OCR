"""Blind, local OCR evaluation for newly supplied invoice images/PDFs.

The OCR pass reads documents.csv and image/PDF bytes only. labels.jsonl is not
opened until every prediction has been produced, so gold values cannot affect
the baseline run. This tool never calls the API, opens a database, or changes
the parser.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.extraction import extract_fields, extract_line_items, text_from_file

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTRACTION_SOURCE = REPO_ROOT / "backend" / "app" / "extraction.py"
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}
FIELD_NAMES = (
    "document_type", "seller_name", "invoice_date", "seller_tax_code",
    "invoice_number", "line_item_count", "subtotal", "vat_amount", "total_amount",
)
ITEM_FIELD_NAMES = ("description", "quantity", "unit_price", "amount")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_documents(dataset_dir: Path, manifest_file: Path | None = None) -> list[dict]:
    manifest = manifest_file.resolve() if manifest_file else dataset_dir / "documents.csv"
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or not {"document_id", "file", "split"}.issubset(rows[0]):
        raise ValueError("documents.csv cần các cột document_id,file,split và ít nhất một dòng")
    ids = set()
    documents = []
    for row in rows:
        document_id = (row.get("document_id") or "").strip()
        relative_file = (row.get("file") or "").strip()
        split = (row.get("split") or "").strip().lower()
        if not document_id or document_id in ids:
            raise ValueError("document_id phải có giá trị và không được trùng")
        if split not in {"development", "held_out"}:
            raise ValueError(f"split không hợp lệ cho {document_id}; dùng development hoặc held_out")
        ids.add(document_id)
        source = (dataset_dir / relative_file).resolve()
        if not source.is_relative_to(dataset_dir.resolve()) or not source.is_file():
            raise ValueError(f"Đường dẫn file không hợp lệ hoặc nằm ngoài tập dữ liệu: {document_id}")
        if source.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Định dạng không được hỗ trợ trong benchmark: {document_id}")
        size = source.stat().st_size
        if not size or size > MAX_DOCUMENT_BYTES:
            raise ValueError(f"File rỗng hoặc vượt 20 MB: {document_id}")
        documents.append({
            "document_id": document_id,
            "file": source,
            "split": split,
            "category": (row.get("category") or "unspecified").strip().lower() or "unspecified",
            "layout_family": (row.get("layout_family") or "unspecified").strip() or "unspecified",
        })
    return documents


def _predict(document: dict) -> dict:
    data = document["file"].read_bytes()
    extension = document["file"].suffix.lower().lstrip(".")
    raw_text, method = text_from_file(data, extension)
    fields = extract_fields(raw_text, extension)
    items = extract_line_items(data, extension, raw_text)
    prediction = {
        "document_id": document["document_id"],
        "split": document["split"],
        "category": document["category"],
        "layout_family": document["layout_family"],
        "source_sha256": _sha256(data),
        "method": method,
        "fields": {
            name: _json_value(fields.get(name))
            for name in FIELD_NAMES if name != "line_item_count"
        },
        "items": [
            {key: _json_value(item.get(key)) for key in ITEM_FIELD_NAMES}
            for item in items
        ],
    }
    prediction["fields"]["line_item_count"] = len(items)
    return prediction


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _load_labels_after_predictions(path: Path, prediction_ids: set[str]) -> dict:
    labels = {}
    if path.suffix.lower() == ".json":
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(rows, list):
            raise ValueError("labels.json phải là danh sách JSON các nhãn")
    else:
        rows = []
        with path.open("r", encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                if line.strip():
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError(f"Nhãn không hợp lệ ở dòng {line_number}")
                    rows.append(row)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Mỗi nhãn phải là một JSON object")
        document_id = str(row.get("document_id", "")).strip()
        expected = row.get("expected")
        if not document_id or document_id in labels or not isinstance(expected, dict):
            raise ValueError(f"Nhãn không hợp lệ hoặc trùng: {document_id or '(thiếu document_id)'}")
        review_status = row.get("review_status", "approved")
        if review_status not in {"approved", "partial", "excluded"}:
            raise ValueError(f"Nhãn {document_id} chưa được duyệt; từ chối chấm điểm")
        required = {"document_type", "seller_name", "invoice_date", "seller_tax_code",
                    "invoice_number", "items", "subtotal", "vat_amount", "total_amount"}
        if not required.issubset(expected):
            raise ValueError(f"Nhãn {document_id} thiếu trường: {sorted(required - set(expected))}")
        if not isinstance(expected.get("items"), list):
            raise ValueError(f"Nhãn {document_id} cần expected.items là một danh sách")
        for item in expected["items"]:
            if not isinstance(item, dict) or not set(ITEM_FIELD_NAMES).issubset(item):
                raise ValueError(f"Mỗi dòng hàng của {document_id} cần description, quantity, unit_price, amount")
        verified_fields = row.get("verified_fields", [])
        if review_status == "partial":
            if not isinstance(verified_fields, list) or not verified_fields:
                raise ValueError(f"Nhãn partial {document_id} cần danh sách verified_fields")
            for field in verified_fields:
                item_match = re.fullmatch(r"items\.(\d+)\.(description|quantity|unit_price|amount)", field)
                if field not in FIELD_NAMES and not item_match:
                    raise ValueError(f"Trường verified_fields không hợp lệ: {field}")
                if field not in FIELD_NAMES and item_match and int(item_match.group(1)) >= len(expected["items"]):
                    raise ValueError(f"Chỉ số item verified_fields vượt expected.items: {field}")
                if field in {"subtotal", "vat_amount"} and field not in expected:
                    raise ValueError(f"Thiếu expected.{field} cho trường đã xác minh: {document_id}")
        if review_status == "excluded" and not row.get("review_notes"):
            raise ValueError(f"Nhãn bị loại {document_id} cần lý do trong review_notes")
        labels[document_id] = {
            "expected": expected,
            "review_status": review_status,
            "verified_fields": verified_fields,
            "review_notes": row.get("review_notes", []),
        }
    if set(labels) != prediction_ids:
        missing = sorted(prediction_ids - set(labels))
        extra = sorted(set(labels) - prediction_ids)
        raise ValueError(f"ID labels phải khớp documents.csv; thiếu={missing}, thừa={extra}")
    return labels


def _text(value, remove_accents=False):
    if value is None:
        return None
    result = " ".join(str(value).split()).casefold()
    if remove_accents:
        result = "".join(
            char for char in unicodedata.normalize("NFKD", result)
            if not unicodedata.combining(char)
        )
    return result


def _normalize(field: str, value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if field in {"subtotal", "vat_amount", "total_amount", "line_item_count", *ITEM_FIELD_NAMES[1:]}:
        try:
            number = Decimal(str(value).strip().replace(",", "."))
            return number.normalize() if number.is_finite() else None
        except (InvalidOperation, ValueError):
            return None
    if field == "invoice_date":
        text = str(value).strip()
        for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, pattern).date().isoformat()
            except ValueError:
                pass
        return text
    if field == "seller_tax_code":
        return re.sub(r"\D", "", str(value)) or None
    if field == "document_type":
        return _text(value)
    return _text(value)


def _compare(field: str, expected, actual) -> tuple[bool, bool]:
    exact = _normalize(field, expected) == _normalize(field, actual)
    accent_folded = field in {"seller_name", "description"}
    normalized = exact or (
        accent_folded
        and _text(expected, remove_accents=True) == _text(actual, remove_accents=True)
    )
    return exact, normalized


def _aggregate(results: list[dict], group_by: tuple[str, ...]) -> dict:
    groups = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    for result in results:
        group = tuple(result[key] for key in group_by)
        for check in result["checks"]:
            metric_field = check.get("metric_field", check["field"])
            for mode in ("exact", "normalized"):
                counts = groups[group][f"{metric_field}:{mode}"]
                counts[0] += 1
                counts[1] += int(check[mode])
                counts[2] += int(not check[mode])
    output = []
    for group, metrics in sorted(groups.items()):
        output.append({
            **dict(zip(group_by, group)),
            "fields": {
                key: {
                    "total": counts[0],
                    "correct": counts[1],
                    "incorrect": counts[2],
                    "accuracy": round(counts[1] / counts[0], 4) if counts[0] else None,
                }
                for key, counts in sorted(metrics.items())
            },
        })
    return output


def _score(predictions: list[dict], labels: dict) -> dict:
    official = []
    verified_only = []
    excluded_ids = []
    pending_ids = []
    for prediction in predictions:
        label = labels[prediction["document_id"]]
        expected = label["expected"]
        status = label["review_status"]
        if status == "excluded":
            excluded_ids.append(prediction["document_id"])
            continue
        if status == "partial":
            selected = set(label["verified_fields"])
            if not selected:
                pending_ids.append(prediction["document_id"])
                continue
        else:
            selected = set(FIELD_NAMES)
        actual_fields = prediction["fields"]
        checks = []
        for name in FIELD_NAMES:
            if name not in selected:
                continue
            if name == "line_item_count":
                expected_value = len(expected["items"])
                actual_value = len(prediction["items"])
            else:
                expected_value = expected.get(name)
                actual_value = actual_fields.get(name)
            exact, normalized = _compare(name, expected_value, actual_value)
            checks.append({
                "field": name, "expected": expected_value, "actual": actual_value,
                "exact": exact, "normalized": normalized,
            })
        expected_items = expected["items"]
        max_rows = max(len(expected_items), len(prediction["items"]))
        for index in range(max_rows):
            expected_item = expected_items[index] if index < len(expected_items) else {}
            actual_item = prediction["items"][index] if index < len(prediction["items"]) else {}
            for field in ITEM_FIELD_NAMES:
                field_path = f"items.{index}.{field}"
                if status != "approved" and field_path not in selected:
                    continue
                exact, normalized = _compare(
                    "description" if field == "description" else field,
                    expected_item.get(field), actual_item.get(field),
                )
                checks.append({
                    "field": f"item[{index + 1}].{field}",
                    "metric_field": f"items.{field}",
                    "expected": expected_item.get(field),
                    "actual": actual_item.get(field),
                    "exact": exact, "normalized": normalized,
                })
        if status == "approved":
            official.append({**prediction, "scope": "official", "checks": checks})
        else:
            verified_only.append({**prediction, "scope": "verified_fields_only", "checks": checks})
    return {
        "official": official,
        "verified_fields_only": verified_only,
        "excluded_ids": excluded_ids,
        "pending_ids": pending_ids,
    }


def _write_outputs(output_dir: Path, predictions: list[dict], scored: dict | None,
                   metadata: dict, labels_sha256: str | None):
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "predictions.json").write_text(
        json.dumps(predictions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = {
        "status": "scored" if scored is not None else "awaiting_labels",
        "metadata": metadata,
        "labels_sha256": labels_sha256,
        "metrics": None,
    }
    scored_rows = []
    if scored is not None:
        official = scored["official"]
        partial = scored["verified_fields_only"]

        def scope_metrics(rows):
            return {
                "document_count": len(rows),
                "overall_by_split": _aggregate(rows, ("split",)),
                "by_split_and_category": _aggregate(rows, ("split", "category")),
                "by_split_and_layout": _aggregate(rows, ("split", "layout_family")),
                "fully_correct_documents": sum(
                    all(check["normalized"] for check in row["checks"]) for row in rows
                ),
                "documents": [{
                    "document_id": row["document_id"], "split": row["split"],
                    "category": row["category"], "layout_family": row["layout_family"],
                    "scope": row["scope"],
                    "all_scored_fields_normalized_correct": all(
                        check["normalized"] for check in row["checks"]
                    ),
                    "scored_field_count": len(row["checks"]),
                    "checks": row["checks"],
                } for row in rows],
            }

        report["metrics"] = {
            "official": scope_metrics(official),
            "verified_fields_only": scope_metrics(partial),
            "excluded_document_ids": scored["excluded_ids"],
            "pending_document_ids": scored["pending_ids"],
            "documents_in_dataset": len(predictions),
        }
        scored_rows = official + partial
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if scored is not None:
        with (output_dir / "per_document.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=(
                "document_id", "scope", "split", "category", "layout_family", "source_sha256",
                "method", "field", "expected", "actual", "exact", "normalized",
            ), extrasaction="ignore")
            writer.writeheader()
            for row in scored_rows:
                for check in row["checks"]:
                    writer.writerow({
                        **{key: row[key] for key in (
                            "document_id", "scope", "split", "category", "layout_family",
                            "source_sha256", "method",
                        )},
                        **check,
                        "expected": json.dumps(check["expected"], ensure_ascii=False),
                        "actual": json.dumps(check["actual"], ensure_ascii=False),
                    })


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--manifest-file", type=Path,
        help="CSV chỉ mục tài liệu; mặc định là <dataset-dir>/documents.csv",
    )
    parser.add_argument(
        "--labels-file", type=Path,
        help="JSONL đáp án chuẩn; mặc định là <dataset-dir>/labels.jsonl",
    )
    args = parser.parse_args(argv)
    dataset_dir = args.dataset_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not dataset_dir.is_dir():
        parser.error("dataset-dir phải là một thư mục tồn tại")
    if output_dir == REPO_ROOT or output_dir.is_relative_to(REPO_ROOT):
        parser.error("output-dir phải nằm ngoài repository để tránh ghi đè dữ liệu dự án")
    if output_dir == dataset_dir or output_dir.is_relative_to(dataset_dir):
        parser.error("output-dir không được nằm trong dataset đầu vào")

    try:
        manifest_file = args.manifest_file.resolve() if args.manifest_file else dataset_dir / "documents.csv"
        labels_file = args.labels_file.resolve() if args.labels_file else dataset_dir / "labels.jsonl"
        documents = _read_documents(dataset_dir, manifest_file)
        predictions = []
        failures = []
        for document in documents:
            try:
                predictions.append(_predict(document))
            except Exception as exc:
                failures.append({"document_id": document["document_id"], "error": str(exc)[:500]})
        if failures:
            print(json.dumps({"ocr_failures": failures}, ensure_ascii=False), file=sys.stderr)
            return 2

        # Deliberately access gold labels only after baseline predictions exist.
        metadata = {
            "dataset_dir": str(dataset_dir),
            "manifest_sha256": _sha256(manifest_file.read_bytes()),
            "extractor_sha256": _sha256(EXTRACTION_SOURCE.read_bytes()),
            "document_count": len(predictions),
        }
        try:
            import pytesseract
            metadata["tesseract_version"] = str(pytesseract.get_tesseract_version())
            metadata["tesseract_languages"] = pytesseract.get_languages(config="")
        except Exception as exc:
            metadata["tesseract_probe_error"] = str(exc)[:300]

        if labels_file.is_file():
            label_bytes = labels_file.read_bytes()
            labels = _load_labels_after_predictions(labels_file, {row["document_id"] for row in predictions})
            scored = _score(predictions, labels)
            _write_outputs(output_dir, predictions, scored, metadata, _sha256(label_bytes))
        else:
            _write_outputs(output_dir, predictions, None, metadata, None)
        print(json.dumps({"status": "scored" if labels_file.is_file() else "awaiting_labels",
                          "documents": len(predictions), "output_dir": str(output_dir)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
