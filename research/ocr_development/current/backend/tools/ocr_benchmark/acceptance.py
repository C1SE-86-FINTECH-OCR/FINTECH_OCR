"""Offline acceptance intake/scoring. Never imports the API, database or OCR engine."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
import math
from pathlib import Path
import unicodedata
from uuid import uuid4

from .__main__ import digest, read_manifest
from .scoring import CELLS, FIELDS, canonical, checks, matched_rows, prf, ratio, score

REQUIRED_FIELDS = {"document_type", "seller_name", "seller_tax_code", "invoice_number",
                   "invoice_date", "subtotal", "vat_amount", "total_amount"}
CATEGORIES = {"vat_pdf_text", "vat_image", "multipage_scan", "thermal_bill",
              "many_items", "multiple_vat", "different_table_layout", "bilingual_vi_en"}
CAUSES = {"ocr_recognition", "parser_assignment", "table_detection", "source_quality", "undetermined"}
HEADERS = ["document_id", "file", "split", "origin", "supplier_group", "layout_family",
           "duplicate_group", "language", "categories"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def normalize_text(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def distance(a, b):
    """Exact bit-vector Levenshtein for long page transcripts; no fuzzy matching."""
    start = 0
    while start < min(len(a), len(b)) and a[start] == b[start]:
        start += 1
    a, b = a[start:], b[start:]
    while a and b and a[-1] == b[-1]:
        a, b = a[:-1], b[:-1]
    if len(a) > len(b):
        a, b = b, a
    if not a:
        return len(b)
    matches = {}
    for i, token in enumerate(a):
        matches[token] = matches.get(token, 0) | (1 << i)
    mask, high = (1 << len(a)) - 1, 1 << (len(a) - 1)
    positive, negative, edits = mask, 0, len(a)
    for token in b:
        equal = matches.get(token, 0)
        vertical = equal | negative
        horizontal = (((equal & positive) + positive) ^ positive) | equal
        plus, minus = negative | ~(horizontal | positive), positive & horizontal
        edits += bool(plus & high) - bool(minus & high)
        plus, minus = (plus << 1) | 1, minus << 1
        positive = (minus | ~(vertical | plus)) & mask
        negative = (plus & vertical) & mask
    return edits


def text_metrics(expected, actual):
    expected, actual = normalize_text(expected), normalize_text(actual)
    characters, words = distance(expected, actual), distance(expected.split(), actual.split())
    return {"character_edits": characters, "reference_characters": len(expected),
            "cer": ratio(characters, len(expected)),
            "word_edits": words,
            "reference_words": len(expected.split()),
            "wer": ratio(words, len(expected.split())),
            "exact": expected == actual}


def page_text(page):
    # Match the benchmark's reading-row order, without importing layout/OCR.
    boxes = page.get("boxes", page.get("text_boxes", []))
    if not boxes:
        return ""
    def bounds(box):
        xs, ys = zip(*box["polygon"])
        return min(xs), min(ys), max(xs), max(ys)
    from statistics import median
    rows = []
    for box in sorted(boxes, key=lambda b: bounds(b)[1]):
        x0, y0, x1, y1 = bounds(box)
        mid = (y0 + y1) / 2
        if rows:
            recent = [bounds(b) for b in rows[-1]]
            limit = max(2, min(y1 - y0, median(b[3] - b[1] for b in recent)) * .45)
            if abs(mid - median((b[1] + b[3]) / 2 for b in recent)) <= limit:
                rows[-1].append(box)
                continue
        rows.append([box])
    return "\n".join(" ".join(b["text"] for b in sorted(row, key=lambda b: bounds(b)[0])) for row in rows)


def table_metrics(expected, actual):
    """Separate legacy 4-cell rows from stricter unit/page equality."""
    fields = (*CELLS, "unit", "page")
    def key(row):
        return tuple(canonical(k, row[k]) if k in row else "<unsupported-cell>" for k in fields)
    common = Counter(key(r) for r in expected) & Counter(key(r) for r in actual)
    exact = sum(common.values())
    remaining = list(actual)
    pairs_by_field = {k: [] for k in ("unit", "page", "vat_rate", "vat_amount")}
    # Pair equal descriptions one-to-one, preferring equal remaining cells.
    # Misspelled descriptions stay unmatched; no credit from unrelated prices.
    for ref in expected:
        candidates = [i for i, r in enumerate(remaining)
                      if canonical("description", r.get("description")) == canonical("description", ref.get("description"))]
        if candidates:
            best = max(candidates, key=lambda i: sum(canonical(k, ref.get(k)) == canonical(k, remaining[i].get(k)) for k in fields))
            item = remaining.pop(best)
        else:
            item = {}
        for name, pairs in pairs_by_field.items():
            if name in ref:
                value = item.get(name, "<unsupported-cell>") if item else "<missing-row>"
                pairs.append((ref[name], value))
    # Full unit/page rows are only scored when the labels define both keys.
    complete = all("unit" in r and "page" in r for r in expected)
    unsupported = sorted({k for k in ("unit", "page") if any(k not in r for r in actual)})
    core_exact, _ = matched_rows(expected, actual)
    expected_counts = Counter(str(r["page"]) for r in expected if "page" in r)
    predicted_counts = Counter(str(r.get("page", "unavailable")) for r in actual)
    return {"strict_rows": {**prf(exact, len(actual) - exact, len(expected) - exact),
                            "expected": len(expected), "predicted": len(actual),
                            "all_exact": exact == len(expected) == len(actual)} if complete and not unsupported else None,
            "unsupported_prediction_metadata": unsupported,
            "four_cell_rows": {**prf(core_exact, len(actual) - core_exact, len(expected) - core_exact),
                               "all_exact": core_exact == len(expected) == len(actual)},
            "unit": checks(pairs_by_field["unit"], "unit"), "row_page": checks(pairs_by_field["page"], "page"),
            "vat_rate": checks(pairs_by_field["vat_rate"], "vat_rate"),
            "vat_amount": checks(pairs_by_field["vat_amount"], "vat_amount"),
            "row_grouping": {"expected_counts_by_page": dict(expected_counts),
                             "predicted_counts_by_page": dict(predicted_counts),
                             "row_counts_equal": expected_counts == predicted_counts,
                             "limitation": "Row-count agreement does not prove correct cell grouping; see strict row exact and human error review."}}


def source_page_count(path):
    if path.suffix.lower() != ".pdf":
        return 1
    import pymupdf
    with pymupdf.open(path) as pdf:
        return len(pdf)


def validate_labels(rows, payload, known):
    if payload.get("schema_version") != 1 or not isinstance(payload.get("documents"), list):
        raise ValueError("Expected schema_version=1 and documents array")
    by_id = {r["document_id"]: r for r in rows}
    labels = {}
    known_hashes = {r["sha256"] for r in known["documents"]}
    known_groups = {key: {r[key].casefold() for r in known["documents"] if r.get(key)}
                    for key in ("supplier_group", "layout_family", "duplicate_group")}
    for label in payload["documents"]:
        id_ = label["document_id"]
        if id_ in labels or id_ not in by_id:
            raise ValueError(f"Unknown/duplicate label: {id_}")
        labels[id_] = label
        row = by_id[id_]
        categories = set(filter(None, row.get("categories", "").split(";")))
        if categories - CATEGORIES:
            raise ValueError(f"Unknown coverage categories: {id_}")
        if label.get("sha256") != row["sha256"]:
            raise ValueError(f"Source hash mismatch: {id_}")
        status = label.get("review_status")
        if status not in {"draft", "partial", "approved", "excluded"}:
            raise ValueError(f"Invalid review status: {id_}")
        if status in {"draft", "excluded"}:
            continue
        provenance = label.get("provenance", {})
        if (row["origin"] != "real" or row["split"] != "test" or row["sha256"] in known_hashes
                or any(row[key].casefold() in values for key, values in known_groups.items())
                or row["path"].suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}
                or any(provenance.get(k) is not True for k in
                       ("permitted_use", "never_used_for_development", "annotated_without_predictions"))):
            raise ValueError(f"Not independent reviewed real test data: {id_}")
        reviewers = [label.get("annotated_by", "").strip(), label.get("verified_by", "").strip()]
        if not all(reviewers) or reviewers[0].casefold() == reviewers[1].casefold() or not label.get("verified_at"):
            raise ValueError(f"Two distinct reviewers and verified_at required: {id_}")
        expected = label.get("expected")
        if not isinstance(expected, dict) or not expected or expected.keys() - {*FIELDS, "items"}:
            raise ValueError(f"Invalid verified fields: {id_}")
        for k in ("invoice_number", "invoice_symbol", "seller_tax_code", "buyer_tax_code"):
            if expected.get(k) is not None and not isinstance(expected[k], str):
                raise ValueError(f"Identifier must be a string: {id_}.{k}")
        for k in ("subtotal", "vat_amount", "total_amount", "vat_rate"):
            if expected.get(k) is not None and (type(expected[k]) not in (int, float) or not math.isfinite(expected[k])):
                raise ValueError(f"Verified money must be finite numeric or null: {id_}.{k}")
        if expected.get("document_type") not in {None, "einvoice", "bill", "unknown"}:
            raise ValueError(f"Invalid document type: {id_}")
        pages = label.get("pages", [])
        page_count = label.get("page_count")
        if type(page_count) is not int or page_count < 1 or page_count != len(pages):
            raise ValueError(f"All original pages must be enumerated: {id_}")
        if page_count != source_page_count(row["path"]):
            raise ValueError(f"Page count differs from original document: {id_}")
        if [p["page"] for p in pages] != list(range(1, page_count + 1)):
            raise ValueError(f"Invalid page numbering: {id_}")
        for p in pages:
            if p.get("transcription") is not None and not isinstance(p["transcription"], str):
                raise ValueError(f"Invalid manual transcription: {id_}")
        if "items" in expected:
            if not isinstance(expected["items"], list):
                raise ValueError(f"Unverified items must omit the key: {id_}")
            for item in expected["items"]:
                if not {*CELLS, "unit", "page"}.issubset(item) or not isinstance(item["description"], str) or not item["description"].strip():
                    raise ValueError(f"Verified rows require four cells, unit and page: {id_}")
                if type(item["page"]) is not int or not 1 <= item["page"] <= page_count:
                    raise ValueError(f"Invalid row page: {id_}")
                if item["unit"] is not None and not isinstance(item["unit"], str):
                    raise ValueError(f"Invalid unit: {id_}")
                for key in ("quantity", "unit_price", "amount", "vat_rate", "vat_amount"):
                    if item.get(key) is not None and (type(item[key]) not in (int, float) or not math.isfinite(item[key])):
                        raise ValueError(f"Invalid numeric cell: {id_}.{key}")
        if status == "approved" and not (REQUIRED_FIELDS | {"items"}).issubset(expected):
            raise ValueError(f"Approved invoice missing required verified fields/items: {id_}")
    if labels.keys() != by_id.keys():
        raise ValueError("Every manifest document requires a draft/reviewed/excluded label")
    return labels


def init_dataset(root):
    root.mkdir(parents=True, exist_ok=False)
    (root / "documents").mkdir()
    with (root / "documents.csv").open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerow(HEADERS)
    write(root / "ground_truth.json", {"schema_version": 1, "documents": []})


def prepare(root):
    rows = read_manifest(root / "documents.csv", root.resolve())
    path = root / "ground_truth.json"
    payload = read(path)
    existing = {r["document_id"] for r in payload["documents"]}
    for row in rows:
        if row["document_id"] in existing:
            continue
        count = source_page_count(row["path"])
        payload["documents"].append({
            "document_id": row["document_id"], "sha256": row["sha256"], "review_status": "draft",
            "annotated_by": "", "verified_by": "", "verified_at": "",
            "provenance": {"permitted_use": False, "never_used_for_development": False,
                           "annotated_without_predictions": False},
            "page_count": count, "pages": [{"page": n, "transcription": None} for n in range(1, count + 1)],
            "expected": {}, "source_issues": [],
        })
    # Preserve the previous file before appending only new draft records.
    if existing != {r["document_id"] for r in payload["documents"]}:
        backup = path.with_suffix(f".json.before_prepare_{uuid4().hex[:12]}")
        with backup.open("x", encoding="utf-8") as stream:
            stream.write(path.read_text(encoding="utf-8"))
        write(path, payload)
    return len(rows)


def freeze(root, known_file, output):
    manifest = root / "documents.csv"
    rows = read_manifest(manifest, root.resolve())
    payload = read(root / "ground_truth.json")
    labels = validate_labels(rows, payload, read(known_file))
    eligible = {k: v for k, v in labels.items() if v["review_status"] in {"approved", "partial"}}
    if not eligible:
        raise ValueError("WAITING FOR DATA: no independently reviewed real invoices")
    output.mkdir(parents=True, exist_ok=False)
    exported = [{"document_id": id_, "review_status": label["review_status"] if id_ in eligible else "excluded",
                 "expected": label["expected"] if id_ in eligible else {}} for id_, label in labels.items()]
    write(output / "labels.json", exported)
    write(output / "ground_truth.json", payload)
    (output / "known_documents.json").write_bytes(known_file.read_bytes())
    (output / "documents.csv").write_bytes(manifest.read_bytes())
    write(output / "freeze.json", {
        "schema_version": 1, "dataset_root": str(root.resolve()),
        "manifest_sha256": digest(manifest), "ground_truth_sha256": digest(output / "ground_truth.json"),
        "labels_sha256": digest(output / "labels.json"), "known_documents_sha256": digest(known_file),
        "documents": {r["document_id"]: r["sha256"] for r in rows},
        "categories": {r["document_id"]: r.get("categories", "").split(";") for r in rows},
        "eligible": list(eligible),
    })


def assess(prediction, label):
    layout = prediction["layout"]
    pages = {p["page"]: p for p in layout.get("pages", [])}
    text_scores = []
    for ref in label["pages"]:
        if ref.get("transcription") is None:
            continue
        p = pages.get(ref["page"])
        if not p:
            text_scores.append({"page": ref["page"], "status": "NOT TESTED", "reason": "no page-level OCR evidence"})
        else:
            text_scores.append({"page": ref["page"], "status": "SCORED", "source": p["source"],
                                **text_metrics(ref["transcription"], page_text(p))})
    expected = label["expected"]
    if all(p.get("transcription") is not None for p in label["pages"]) and layout.get("raw_text") is not None:
        raw_score = {"status": "SCORED", "source": layout.get("source", "unknown"),
                     "scope": "whole-document raw pass; separate from layout OCR boxes",
                     **text_metrics("\n".join(p["transcription"] for p in label["pages"]), layout["raw_text"])}
    else:
        raw_score = {"status": "NOT TESTED", "reason": "missing complete human transcript or raw text"}
    tables = table_metrics(expected["items"], prediction["items"]) if "items" in expected else None
    missing_pages = sorted(set(range(1, label["page_count"] + 1)) - pages.keys())
    extra_pages = sorted(pages.keys() - set(range(1, label["page_count"] + 1)))
    detection = [{"page": n, "expected": any(r["page"] == n for r in expected["items"]),
                  "actual": bool(pages[n].get("table_found", pages[n].get("items")))}
                 for n in sorted(pages) if n <= label["page_count"]] if "items" in expected else []
    return {"text": text_scores, "document_raw_text": raw_score, "table": tables, "table_detection": detection,
            "pages": {"expected": label["page_count"], "observed": sorted(pages),
                      "missing": missing_pages, "truncated": bool(layout.get("truncated")),
                      "extra": extra_pages,
                      "status": "NOT TESTED" if not pages else ("FAIL" if missing_pages or extra_pages or layout.get("truncated") else "PASS")},
            "field_comparison": {k: {"expected": v, "actual": prediction["fields"].get(k),
                                      "exact": not prediction["error"] and canonical(k, v) == canonical(k, prediction["fields"].get(k))}
                                 for k, v in expected.items() if k in FIELDS},
            "confirmed_error_reviews": [],
            "warnings": layout.get("findings", []), "source_issues": label.get("source_issues", []),
            "recognized_fields": prediction["fields"],
            "items": {"expected": expected.get("items"), "recognized": prediction["items"]},
            "pipeline_validation": prediction["validation"],
            "evidence": {"raw_text_available": bool(layout.get("raw_text")),
                         "pages_with_boxes": [n for n, p in pages.items() if p.get("boxes") or p.get("text_boxes")]}}


def evaluate(frozen, run_dir, reviews_file=None):
    snapshot = read(frozen / "freeze.json")
    for name, key in (("documents.csv", "manifest_sha256"), ("labels.json", "labels_sha256"),
                      ("ground_truth.json", "ground_truth_sha256"), ("known_documents.json", "known_documents_sha256")):
        if digest(frozen / name) != snapshot[key]:
            raise ValueError(f"Frozen evidence changed: {name}")
    labels = {r["document_id"]: r for r in read(frozen / "ground_truth.json")["documents"]}
    report, predictions = read(run_dir / "report.json"), read(run_dir / "predictions.json")
    for key in ("manifest_sha256", "labels_sha256", "documents"):
        if report[key] != snapshot[key]:
            raise ValueError(f"Run does not match frozen dataset: {key}")
    if len(predictions) != len(snapshot["documents"]) or {p["id"]: p["sha256"] for p in predictions} != snapshot["documents"]:
        raise ValueError("Missing/duplicate/changed predictions")
    legacy = {r["document_id"]: r for r in read(frozen / "labels.json")}
    metrics = {status: score(predictions, {k: v for k, v in legacy.items() if v["review_status"] == status})
               for status in ("approved", "partial")}
    if metrics["approved"] != report["approved"] or metrics["partial"] != report["verified_partial"]:
        raise ValueError("Predictions no longer reproduce the benchmark metrics")
    result = {"status": "MEASURED — NO AUTOMATIC SIGN-OFF", "engine": report["engine"],
              "predictions_file": str((run_dir / "predictions.json").resolve()),
              "predictions_sha256": digest(run_dir / "predictions.json"), "freeze_sha256": digest(frozen / "freeze.json"),
              "metrics": metrics,
              "resource": report["resource"], "documents": []}
    coverage = set()
    for p in predictions:
        label = labels[p["id"]]
        if p["id"] not in snapshot["eligible"]:
            result["documents"].append({"id": p["id"], "status": "NOT TESTED", "reason": label["review_status"]})
            continue
        details = assess(p, label)
        coverage.update(snapshot["categories"][p["id"]])
        field_ok = all(v["exact"] for v in details["field_comparison"].values())
        table_ok = details["table"] and details["table"]["strict_rows"] and details["table"]["strict_rows"]["all_exact"]
        table_wrong = details["table"] and (
            not details["table"]["four_cell_rows"]["all_exact"] or
            (details["table"]["strict_rows"] is not None and not table_ok) or
            any(details["table"][k]["exact_matches"] < details["table"][k]["scored"] for k in ("vat_rate", "vat_amount")))
        text_complete = (len(details["text"]) == label["page_count"] and
                         all(s["status"] == "SCORED" for s in details["text"]))
        text_wrong = (any(s.get("exact") is False for s in details["text"])
                      or details["document_raw_text"].get("exact") is False)
        # Never report acceptance PASS for incomplete labels or absent page evidence.
        status = ("FAIL" if p["error"] or not field_ok or text_wrong or table_wrong or details["pages"]["status"] == "FAIL"
                  else "PARTIAL" if label["review_status"] != "approved" or not table_ok or not text_complete or details["pages"]["status"] != "PASS"
                  else "PASS")
        result["documents"].append({"id": p["id"], "status": status, "error": p["error"],
                                    "elapsed_s": p["elapsed_s"], "review_status": label["review_status"],
                                    "categories": snapshot["categories"][p["id"]], **details})
    result["coverage"] = {k: k in coverage for k in sorted(CATEGORIES)}
    tables = [d["table"] for d in result["documents"] if d.get("table")]
    result["extended_line_metrics"] = {}
    for key in ("unit", "row_page", "vat_rate", "vat_amount"):
        values = [t[key] for t in tables]
        totals = {k: sum(v[k] for v in values) for k in ("tp", "fp", "fn", "exact_matches", "scored")}
        result["extended_line_metrics"][key] = {**totals, **prf(totals["tp"], totals["fp"], totals["fn"]),
                                               "exact_match": ratio(totals["exact_matches"], totals["scored"])}
    strict = [t["strict_rows"] for t in tables if t["strict_rows"] is not None]
    result["extended_line_metrics"]["strict_rows"] = {
        **prf(*(sum(r[k] for r in strict) for k in ("tp", "fp", "fn"))),
        "tables_scored": len(strict), "tables_missing_unit_or_page_metadata": len(tables) - len(strict),
        "whole_tables_exact": sum(r["all_exact"] for r in strict),
    }
    detections = [p for d in result["documents"] for p in d.get("table_detection", [])]
    result["table_detection"] = {
        **prf(sum(p["expected"] and p["actual"] for p in detections),
              sum(not p["expected"] and p["actual"] for p in detections),
              sum(p["expected"] and not p["actual"] for p in detections)),
        "pages_scored": len(detections),
        "limitation": "Presence only; not polygon IoU or proof of correct cell ownership",
    }
    result["multipage"] = dict(Counter(d["pages"]["status"] for d in result["documents"]
                                         if d.get("pages", {}).get("expected", 0) > 1))
    result["by_category"] = {
        category: {status: score(
            [p for p in predictions if category in snapshot["categories"][p["id"]]],
            {k: v for k, v in legacy.items() if v["review_status"] == status})
            for status in ("approved", "partial")}
        for category in sorted(CATEGORIES)
    }
    if reviews_file:
        reviews = read(reviews_file)
        if str(reviews.get("predictions_sha256", "")).lower() != result["predictions_sha256"]:
            raise ValueError("Error review belongs to a different predictions file")
        docs = {d["id"]: d for d in result["documents"]}
        for entry in reviews["reviews"]:
            if (entry.get("document_id") not in snapshot["eligible"] or entry.get("category") not in CAUSES
                    or not all(entry.get(k) for k in ("target", "evidence", "reviewer"))):
                raise ValueError("Error review requires eligible ID, category, reviewer and evidence")
            docs[entry["document_id"]]["confirmed_error_reviews"].append(entry)
        result["error_reviews_sha256"] = digest(reviews_file)
    result["counts"] = dict(Counter(p["status"] for p in result["documents"]))
    for kind in ("ocr", "pdf-text"):
        rows = [s for d in result["documents"] for s in d.get("text", []) if s.get("source") == kind]
        edits, chars = sum(s["character_edits"] for s in rows), sum(s["reference_characters"] for s in rows)
        words = sum(s["reference_words"] for s in rows)
        result[f"text_{kind}"] = {"pages_scored": len(rows), "character_edits": edits,
                                  "reference_characters": chars, "cer": ratio(edits, chars),
                                  "word_edits": sum(s["word_edits"] for s in rows),
                                  "reference_words": words, "wer": ratio(sum(s["word_edits"] for s in rows), words)}
    return result


def markdown(report):
    lines = ["# Kết quả đánh giá OCR ngoại tuyến", "", report["status"], "",
             "PASS từng tài liệu chỉ là kết quả các tiêu chí đã chấm, không phải ký nghiệm thu.", "",
             "| Hóa đơn | Trạng thái | Nhãn | Trường đúng/đã chấm | Dòng đúng/kỳ vọng/dự đoán (có đơn vị/trang) | Trang | Giây |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for d in report["documents"]:
        fields = d.get("field_comparison", {})
        r = (d.get("table") or {}).get("strict_rows")
        row = f'{r["tp"]}/{r["expected"]}/{r["predicted"]}' if r else "NOT TESTED"
        lines.append(f'| {str(d["id"]).replace("|", " ")} | {d["status"]} | {d.get("review_status", d.get("reason"))} | '
                     f'{sum(v["exact"] for v in fields.values())}/{len(fields)} | {row} | '
                     f'{d.get("pages", {}).get("status", "NOT TESTED")} | {d.get("elapsed_s", "—")} |')
    lines += ["", "Chi tiết expected/actual, CER/WER, cảnh báo và nguyên nhân đã được người kiểm thử xác nhận nằm trong JSON đi kèm.",
              "Lỗi CER có thể bao gồm thứ tự đọc; không tự quy lỗi trường cho parser chỉ dựa trên khác biệt kết quả.", ""]
    return "\n".join(lines)


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    subs = cli.add_subparsers(dest="command", required=True)
    init = subs.add_parser("init")
    init.add_argument("--dataset-root", type=Path, required=True)
    prep = subs.add_parser("prepare")
    prep.add_argument("--dataset-root", type=Path, required=True)
    lock = subs.add_parser("freeze")
    lock.add_argument("--dataset-root", type=Path, required=True)
    lock.add_argument("--known-documents", type=Path, required=True)
    lock.add_argument("--output", type=Path, required=True)
    check = subs.add_parser("evaluate")
    check.add_argument("--frozen", type=Path, required=True)
    check.add_argument("--run", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    check.add_argument("--reviews", type=Path)
    args = cli.parse_args(argv)
    try:
        if args.command == "init":
            init_dataset(args.dataset_root)
            print("WAITING FOR DATA: empty intake created; no ground truth inferred")
        elif args.command == "prepare":
            print(f"Prepared {prepare(args.dataset_root)} source records; existing annotations preserved")
        elif args.command == "freeze":
            freeze(args.dataset_root, args.known_documents, args.output)
            print("Review snapshot frozen; run benchmark using frozen documents.csv and labels.json")
        else:
            result = evaluate(args.frozen, args.run, args.reviews)
            args.output.mkdir(parents=True, exist_ok=False)
            write(args.output / "acceptance.json", result)
            (args.output / "acceptance.md").write_text(markdown(result), encoding="utf-8")
            print(json.dumps(result["counts"]))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Acceptance unavailable: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
