import argparse
import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter
from types import SimpleNamespace

from .resources import Monitor
from .scoring import CELLS, FIELDS, score


SPLITS = {"development", "validation", "test"}
GROUPS = ("supplier_group", "layout_family", "duplicate_group")
EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".xml"}
TABLE_V3 = "tesseract-table-v3"
CONTEXT_V4 = "tesseract-context-v4"
CONTEXT_V5 = "tesseract-region-v5"
HYBRID_V6 = "tesseract-hybrid-v6"
ENGINES = ("tesseract-current", "tesseract-layout", "paddle-layout", TABLE_V3, CONTEXT_V4, CONTEXT_V5, HYBRID_V6)


def digest(path):
    with path.open("rb") as stream:
        from hashlib import file_digest
        return file_digest(stream, "sha256").hexdigest()


def read_manifest(path, root):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids, groups = set(), {}
    required = {"document_id", "file", "split", "origin", *GROUPS}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Manifest requires a row and columns {', '.join(sorted(required))}")
    for row in rows:
        if any(not row[key] or not row[key].strip() for key in required):
            raise ValueError("Manifest required values cannot be empty")
        row.update({key: row[key].strip() for key in required})
        id_ = row["document_id"]
        if id_ in ids or row["split"] not in SPLITS or row["origin"] not in {"real", "synthetic"}:
            raise ValueError(f"Invalid ID, split or origin for {id_}")
        ids.add(id_)
        file = (root / row["file"]).resolve()
        if not file.is_relative_to(root) or not file.is_file() or file.suffix.lower() not in EXTENSIONS:
            raise ValueError(f"Invalid document path for {id_}")
        if not 0 < file.stat().st_size <= 20 * 1024 * 1024:
            raise ValueError(f"Unsupported file size for {id_}")
        row["path"], row["sha256"] = file, digest(file)
        for field in (*GROUPS, "sha256"):
            group = (field, row[field].casefold())
            previous = groups.setdefault(group, row["split"])
            if previous != row["split"]:
                raise ValueError(f"Split leakage via {field} for {id_}")
    return rows


def read_labels(path, known_ids):
    if not path:
        return {}
    raw = path.read_text(encoding="utf-8-sig")
    rows = json.loads(raw) if raw.lstrip().startswith("[") else [
        json.loads(line) for line in raw.splitlines() if line.strip()
    ]
    result = {}
    for row in rows:
        id_ = row["document_id"]
        status, expected = row["review_status"], row["expected"]
        if id_ in result or id_ not in known_ids or status not in {"approved", "partial", "excluded"}:
            raise ValueError(f"Unexpected label ID, duplicate or review status for {id_}")
        if not isinstance(expected, dict) or (status != "excluded" and not expected):
            raise ValueError(f"Missing expected values for {id_}")
        extra = expected.keys() - {*FIELDS, "items"}
        if extra:
            raise ValueError(f"Unknown labeled fields for {id_}: {sorted(extra)}")
        items = expected.get("items")
        if items is not None and (
            not isinstance(items, list)
            or any(not isinstance(item, dict) or not set(CELLS).issubset(item) for item in items)
        ):
            raise ValueError(f"Every verified row must define {', '.join(CELLS)} for {id_}")
        if any(key in expected and expected[key] is not None and not isinstance(expected[key], str)
               for key in ("invoice_number", "invoice_symbol", "seller_tax_code", "buyer_tax_code")):
            raise ValueError(f"Identifiers must be strings for {id_}, including leading zeros")
        result[id_] = row
    return result


def local_model(path):
    if path is None or not path.is_dir():
        raise ValueError("PaddleOCR requires explicit local --det-model and --rec-model directories")
    files = sorted(file for file in path.iterdir() if file.is_file())
    if not any(file.suffix == ".pdiparams" for file in files) or not any(
        file.name == "inference.json" or file.suffix == ".pdmodel" for file in files
    ):
        raise ValueError("PaddleOCR requires unpacked local inference weights and model graph")
    return {file.name: digest(file) for file in files}


def legacy(data, ext, _reader, _max_pages):
    from app import extraction
    raw, method = extraction.text_from_file(data, ext)
    fields = extraction.extract_fields(raw, ext)
    items = extraction.extract_line_items(data, ext, raw)
    return fields, items, {"source": method, "raw_text": raw, "pages": []}


def inference(row, engine, reader, max_pages):
    from app import extraction
    from .layout import extract_with_layout
    from .profiling import measured

    start = perf_counter()
    fields, items, layout, validation = {}, [], {}, {}
    error = None
    timing = None
    try:
        with measured() as timing:
            data = row["path"].read_bytes()
            if sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("Document content changed after manifest preflight")
            ext = row["path"].suffix.lower().lstrip(".")
            if engine == ENGINES[0] or ext == "xml":
                fields, items, layout = legacy(data, ext, reader, max_pages)
            elif engine == HYBRID_V6:
                from .hybrid_v6 import extract_hybrid
                fields, items, layout = extract_hybrid(data, ext, max_pages)
            elif engine == CONTEXT_V5:
                from .pipeline_v5 import extract_v5
                fields, items, layout = extract_v5(data, ext, max_pages)
            elif engine == CONTEXT_V4:
                from .pipeline_v4 import extract_v4
                fields, items, layout = extract_v4(data, ext, max_pages)
            elif engine == TABLE_V3:
                from .table_v3 import extract_v3
                fields, items, layout = extract_v3(data, ext, max_pages)
            else:
                fields, items, layout = extract_with_layout(data, ext, reader, max_pages)
            fields = {key: fields[key] for key in FIELDS if key in fields}
            validation = {code: passed for code, passed, _ in extraction.validate(SimpleNamespace(**fields), items)}
    except Exception as exc:
        # Evidence may contain sensitive document text. Keep public failures
        # to exception type; the run is still scored as a failure.
        error = type(exc).__name__
        fields, items, layout, validation = {}, [], {}, {}
    if timing is not None:
        layout['performance'] = timing.report()
    return {
        "id": row["document_id"], "split": row["split"], "origin": row["origin"],
        "layout_family": row["layout_family"], "language": row.get("language") or "unknown",
        "sha256": row["sha256"], "format": row["path"].suffix.lower(),
        "fields": fields, "items": items, "layout": layout, "validation": validation,
        "elapsed_s": round(perf_counter() - start, 5), "error": error,
    }


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str, allow_nan=False), encoding="utf-8")


def run(args):
    from importlib.metadata import version

    rows = read_manifest(args.manifest, args.dataset_root.resolve())
    selected = [row for row in rows if row["split"] == args.split]
    if not selected:
        raise ValueError(f"No documents for split {args.split}")
    if args.engine != "paddle-layout" and args.device != "cpu":
        raise ValueError("Only the PaddleOCR adapter supports GPU")
    models = None
    if args.engine == "paddle-layout":
        models = {kind: local_model(path) for kind, path in (("detect", args.det_model), ("recognize", args.rec_model))}
    args.output.mkdir(parents=False, exist_ok=False)
    # The same ceiling is passed to Tesseract and Paddle. It bounds the
    # external Tesseract OpenMP process; each backend may use fewer threads.
    os.environ["OMP_THREAD_LIMIT"] = str(args.cpu_threads)
    if args.engine == "paddle-layout":
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    with Monitor(args.device) as monitor:
        init_start = perf_counter()
        from app import extraction
        from .layout import paddle_reader, tesseract_boxes
        if args.engine == "paddle-layout":
            reader, paddle_version = paddle_reader(
                args.det_model.resolve(), args.rec_model.resolve(), args.device, args.cpu_threads
            )
            versions = {"paddleocr": version("paddleocr"), "paddle": paddle_version}
        else:
            reader = tesseract_boxes
            versions = {"tesseract": str(extraction.pytesseract.get_tesseract_version()),
                        "pytesseract": version("pytesseract")}
        init_s = perf_counter() - init_start
        predictions = [inference(row, args.engine, reader, args.max_pages) for row in selected]

    # The ground truth is opened only after the predictions are saved.
    save(args.output / "predictions.json", predictions)
    labels = read_labels(args.labels, {row["document_id"] for row in rows})
    approved = {key: value for key, value in labels.items() if value["review_status"] == "approved"}
    partial = {key: value for key, value in labels.items() if value["review_status"] == "partial"}
    strata = {}
    for key in ("origin", "format", "language", "layout_family"):
        strata[key] = {
            value: score([p for p in predictions if p[key] == value], approved)
            for value in sorted({p[key] for p in predictions})
        }
    document_types = {
        label["expected"]["document_type"] for label in approved.values()
        if label["expected"].get("document_type")
    }
    strata["expected_document_type"] = {
        kind: score(
            [p for p in predictions if approved.get(p["id"], {}).get("expected", {}).get("document_type") == kind],
            approved,
        ) for kind in sorted(document_types)
    }
    report = {
        "engine": args.engine, "split": args.split, "device": args.device, "cpu_threads": args.cpu_threads,
        "max_pages_layout": args.max_pages if args.engine != ENGINES[0] else None,
        "host": {"node": platform.node(), "platform": platform.platform(), "cpu_count": os.cpu_count()},
        "runtime": {"python": platform.python_version(), **versions, "pillow": version("Pillow"),
                    "pymupdf": version("PyMuPDF"), "model_files_sha256": models},
        "manifest_sha256": digest(args.manifest), "labels_sha256": digest(args.labels) if args.labels else None,
        "parser_sha256": digest(Path(extraction.__file__)),
        "tool_sha256": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "resource": monitor.report(), "init_s": round(init_s, 4),
        "documents": {p["id"]: p["sha256"] for p in predictions},
        "approved": score(predictions, approved), "verified_partial": score(predictions, partial),
        "by_group": strata,
    }
    save(args.output / "report.json", report)
    print(f"{args.engine} | {len(predictions)} documents | report: {args.output / 'report.json'}")
    return 1 if all(p["error"] for p in predictions) else 0


def compare_reports(a, b):
    for key in ("documents", "manifest_sha256", "labels_sha256", "split", "parser_sha256",
                "tool_sha256", "host", "cpu_threads"):
        if a[key] != b[key]:
            raise ValueError(f"Cannot compare benchmark reports: different {key}")
    if a["engine"] != ENGINES[0] and b["engine"] != ENGINES[0] and (
        a["max_pages_layout"] != b["max_pages_layout"]
    ):
        raise ValueError("Layout caps must match for the controlled comparison")
    if a["device"] != b["device"]:
        raise ValueError("Compare the same device class; report CPU and GPU runs separately")
    return {
        "split": a["split"], "engines": [a["engine"], b["engine"]], "documents": len(a["documents"]),
        "device": a["device"], "approved": [r["approved"] for r in (a, b)],
        "by_origin": [r["by_group"]["origin"] for r in (a, b)],
        "verified_partial": [r["verified_partial"] for r in (a, b)],
        "resource": [r["resource"] for r in (a, b)], "init_s": [r["init_s"] for r in (a, b)],
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description="Offline invoice OCR benchmark")
    commands = cli.add_subparsers(dest="command", required=True)
    bench = commands.add_parser("run")
    bench.add_argument("--engine", choices=ENGINES, required=True)
    bench.add_argument("--manifest", type=Path, required=True)
    bench.add_argument("--dataset-root", type=Path, required=True)
    bench.add_argument("--split", choices=sorted(SPLITS), required=True)
    bench.add_argument("--labels", type=Path)
    bench.add_argument("--output", type=Path, required=True)
    bench.add_argument("--det-model", type=Path)
    bench.add_argument("--rec-model", type=Path)
    bench.add_argument("--cpu-threads", type=int, choices=range(1, 17), default=4)
    bench.add_argument("--max-pages", type=int, choices=range(1, 101), default=12)
    bench.add_argument("--device", choices=("cpu", "gpu:0"), default="cpu")
    compare = commands.add_parser("compare")
    compare.add_argument("reference", type=Path)
    compare.add_argument("candidate", type=Path)
    compare.add_argument("--output", type=Path, required=True)
    args = cli.parse_args(argv)
    try:
        if args.command == "run":
            return run(args)
        a, b = (json.loads(file.read_text(encoding="utf-8")) for file in (args.reference, args.candidate))
        result = compare_reports(a, b)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        return 0
    except (ValueError, OSError, ImportError, KeyError) as exc:
        print(f"Benchmark unavailable: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
