from collections import Counter
from decimal import Decimal, InvalidOperation
from itertools import zip_longest
from statistics import mean, median
import math
import unicodedata


FIELDS = (
    "document_type", "invoice_number", "invoice_symbol", "invoice_date", "seller_name",
    "seller_tax_code", "buyer_name", "buyer_tax_code", "currency", "subtotal",
    "vat_rate", "vat_amount", "total_amount",
)
CELLS = ("description", "quantity", "unit_price", "amount")
NUMERIC = {"subtotal", "vat_rate", "vat_amount", "total_amount", *CELLS[1:]}


def canonical(field, value):
    if value is None or value == "":
        return None
    if field in NUMERIC:
        try:
            number = Decimal(str(value))
            return number if number.is_finite() else str(value)
        except InvalidOperation:
            return str(value)
    # Strict on accents, case, and leading zeros. Canonical Unicode and
    # whitespace avoid treating renderer wrapping as a different value.
    return " ".join(unicodedata.normalize("NFC", str(value)).split())


def ratio(numerator, denominator):
    return round(numerator / denominator, 6) if denominator else None


def prf(tp, fp, fn):
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }


def checks(pairs, name):
    correctly_filled = correct = fp = fn = present = 0
    for expected, actual in pairs:
        expected, actual = canonical(name, expected), canonical(name, actual)
        correct += expected == actual
        present += expected is not None
        correctly_filled += expected is not None and expected == actual
        fp += actual is not None and expected != actual
        fn += expected is not None and expected != actual
    return {
        **prf(correctly_filled, fp, fn),
        "exact_matches": correct, "scored": len(pairs), "present": present,
        "exact_match": ratio(correct, len(pairs)),
    }


def matched_rows(expected_rows, actual_rows):
    def key(row):
        return tuple(canonical(field, row.get(field)) for field in CELLS)

    expected, actual = [key(x) for x in expected_rows], [key(x) for x in actual_rows]
    common = Counter(expected) & Counter(actual)
    exact = sum(common.values())
    pairs = [(row, row) for row in common.elements()]
    missing = list((Counter(expected) - common).elements())
    extra = list((Counter(actual) - common).elements())
    # Compare cells within the same described product. A different product
    # cannot earn cell credit merely because it has the same price.
    descriptions = {row[0] for row in missing + extra}
    for description in sorted(descriptions, key=str):
        pairs.extend(zip_longest(
            (row for row in missing if row[0] == description),
            (row for row in extra if row[0] == description),
        ))
    return exact, pairs


def latency(values):
    if not values:
        return {"n": 0, "mean_s": None, "p50_s": None, "p95_s": None}
    values = sorted(values)
    return {"n": len(values), "mean_s": round(mean(values), 4), "p50_s": round(median(values), 4),
            "p95_s": round(values[math.ceil(len(values) * 0.95) - 1], 4)}


def score(predictions, labels):
    field_pairs = {name: [] for name in FIELDS}
    cell_pairs = {name: [] for name in CELLS}
    row_vat_pairs = {"vat_rate": [], "vat_amount": []}
    exact_rows = expected_rows = actual_rows = 0
    complete_tables = tables = exact_documents = approved = failed = 0
    validation = {}
    confusion = Counter()
    per_document = []
    for p in predictions:
        if p["error"]:
            failed += 1
        label = labels.get(p["id"])
        if not label or label["review_status"] == "excluded":
            continue
        expected = label["expected"]
        fields = {k: v for k, v in expected.items() if k in FIELDS}
        matches = {}
        for key, value in fields.items():
            actual = p["fields"].get(key)
            if p["error"]:
                # A failed document cannot receive exact credit for an absent
                # value. Count actual missing values against present labels.
                actual = None if value not in (None, "") else "<engine-error>"
            field_pairs[key].append((value, actual))
            matches[key] = canonical(key, value) == canonical(key, actual)
        if "document_type" in matches and fields["document_type"] is not None:
            confusion[fields["document_type"], p["fields"].get("document_type") or "missing"] += 1
        table_matches = None
        row_stats = None
        if isinstance(expected.get("items"), list):
            rows, pairs = matched_rows(expected["items"], p["items"])
            n_ref, n_pred = len(expected["items"]), len(p["items"])
            tables += 1
            exact_rows += rows
            expected_rows += n_ref
            actual_rows += n_pred
            table_matches = not p["error"] and rows == n_ref == n_pred
            complete_tables += table_matches
            row_stats = {"correct": rows, "expected": n_ref, "predicted": n_pred}
            for r, a in pairs:
                for i, key in enumerate(CELLS):
                    cell_pairs[key].append((r[i] if r else None, a[i] if a else None))
            if any({"vat_rate", "vat_amount"}.intersection(row) for row in expected["items"]):
                candidates = list(p["items"])
                for row in expected["items"]:
                    name = canonical("description", row.get("description"))
                    matching = [i for i, item in enumerate(candidates)
                                if canonical("description", item.get("description")) == name]
                    if matching:
                        best = max(matching, key=lambda i: sum(
                            canonical(k, candidates[i].get(k)) == canonical(k, row.get(k)) for k in CELLS
                        ))
                        actual = candidates.pop(best)
                    else:
                        actual = {}
                    for key in row_vat_pairs.keys() & row.keys():
                        row_vat_pairs[key].append((row[key], actual.get(key)))
        if label["review_status"] == "approved":
            approved += 1
            exact_documents += not p["error"] and all(matches.values()) and table_matches is not False
        for rule, passed in p["validation"].items():
            counts = validation.setdefault(rule, {"checked": 0, "passed": 0})
            counts["checked"] += 1
            counts["passed"] += passed
        per_document.append({"id": p["id"], "review_status": label["review_status"],
                             "matches": matches, "all_lines_match": table_matches, "rows": row_stats})
    return {
        "documents": len(predictions), "engine_errors": failed, "scored_documents": len(per_document),
        "approved_documents": approved, "all_scored_fields_and_lines_exact": ratio(exact_documents, approved),
        "field_metrics": {name: checks(pairs, name) for name, pairs in field_pairs.items()},
        "classification_confusion": [
            {"actual": ref, "predicted": pred, "count": count}
            for (ref, pred), count in sorted(confusion.items())
        ],
        "line_items": {
            **prf(exact_rows, actual_rows - exact_rows, expected_rows - exact_rows),
            "tables_scored": tables, "exact_table_match": ratio(complete_tables, tables),
            "cell_metrics": {name: checks(pairs, name) for name, pairs in cell_pairs.items()},
            "row_vat_metrics": {
                name: checks(pairs, "vat_amount" if name == "vat_amount" else "vat_rate")
                for name, pairs in row_vat_pairs.items()
            },
        },
        "validation": validation,
        "review_proxy": {
            "documents_needing_review": sum(
                bool(p["error"] or p["layout"].get("truncated") or p["layout"].get("requires_review")
                     or any(not passed for passed in p["validation"].values())) for p in predictions
            ),
            "documents": len(predictions),
        },
        "latency": latency([p["elapsed_s"] for p in predictions if not p["error"]]),
        "per_document": per_document,
    }
