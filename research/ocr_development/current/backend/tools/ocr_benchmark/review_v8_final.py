"""Review/provenance metadata for Final; never business-status decisions."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from .document_fields_v8_final import target_observations


def review_summary(fields, rows, observations, findings, layout):
    result = []
    mandatory = ('seller_name', 'invoice_number', 'invoice_date', 'total_amount')
    if fields.get('document_type') == 'einvoice':
        mandatory += ('seller_tax_code',)
    for key in mandatory:
        if fields.get(key) is None:
            result.append({'code':'V8_FINAL_FIELD_NOT_OBSERVED','field':key,
                           'reason':'not established from source; no default or inference'})
    if not rows:
        result.append({'code':'V8_FINAL_NO_CONFIRMED_ITEMS'})
    for n, row in enumerate(rows, 1):
        for key in ('description', 'unit', 'quantity', 'unit_price', 'amount'):
            if row.get(key) is None or row.get(key) == '':
                result.append({'code':'V8_FINAL_CELL_NOT_OBSERVED','line':n, 'field':key,
                               'page':row.get('page'), 'reason':'missing in source or unresolved OCR'})
        if not row.get('evidence', {}).get('amount'):
            result.append({'code':'V8_FINAL_AMOUNT_EVIDENCE_MISSING','line':n,
                           'reason':'value retained from baseline, not independently established'})
        values = [row.get(k) for k in ('quantity', 'unit_price', 'amount')]
        if all(value is not None for value in values):
            try:
                quantity, price, amount = map(lambda value: Decimal(str(value)), values)
                if all(value.is_finite() for value in (quantity, price, amount)) and abs(quantity * price - amount) > 2:
                    result.append({'code':'V8_FINAL_ROW_SCOPE_REVIEW','line':n,
                                   'reason':'arithmetic differs; printed discounts/tax or OCR may explain it; values unchanged'})
            except (InvalidOperation, ValueError):
                result.append({'code':'V8_FINAL_NUMERIC_OBSERVATION_INVALID','line':n})
    if layout.get('truncated'):
        result.append({'code':'DOCUMENT_TRUNCATED','reason':'page limit reached; not full document coverage'})
    # Keep recognition/operational failures, with their stage clearly marked.
    # Old arithmetic/field-missing warnings may be stale after refinement and
    # remain in v8_baseline instead of being presented as current failures.
    for prior in layout.get('findings', []):
        code = prior.get('code', '')
        if any(word in code for word in ('FAILED', 'ERROR', 'TRUNCATED', 'TIMEOUT')):
            result.append({**deepcopy(prior), 'stage':'v8_baseline'})
    for target, candidates in target_observations(fields.get('document_type'), observations).items():
        alternatives = {str(candidate['value']) for candidate in candidates}
        if len(alternatives) > 1:
            result.append({'code':'V8_FINAL_SOURCE_VARIANTS','field':target,
                           'values':sorted(alternatives), 'selected':fields.get(target),
                           'reason':'OCR alternatives are retained, not a calibrated confidence'})
    return result


def selected_field_evidence(fields, observations):
    selected = {}
    for target, candidates in target_observations(fields.get('document_type'), observations).items():
        if fields.get(target) is None:
            continue
        matches = [deepcopy(candidate) for candidate in candidates
                   if str(candidate['value']) == str(fields[target])]
        if matches:
            selected.setdefault(target, []).extend(matches)
    return selected
