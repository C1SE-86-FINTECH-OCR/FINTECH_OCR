"""Approved confidence policy seam. No default formula or threshold for TBD-02."""
from dataclasses import dataclass
from math import isfinite
from typing import Callable


@dataclass(frozen=True)
class ConfidencePolicy:
    name: str
    approval_reference: str
    threshold: float
    calculate: Callable


_policy = None
_quality_preview_enabled = False


def configure_quality_preview(enabled: bool):
    """Startup opt-in for an unapproved, diagnostic-only score."""
    global _quality_preview_enabled
    _quality_preview_enabled = bool(enabled)


def configure_confidence_policy(policy: ConfidencePolicy):
    """Startup-only integration point for an explicitly approved policy."""
    if not policy.name.strip() or not policy.approval_reference.strip():
        raise ValueError('Confidence policy needs an approval reference')
    if isinstance(policy.threshold, bool) or not isfinite(policy.threshold) or not 0 <= policy.threshold <= 1:
        raise ValueError('Invalid approved confidence threshold')
    if not callable(policy.calculate):
        raise ValueError('Confidence policy must implement calculate')
    global _policy
    _policy = policy



# Preview v1 intentionally covers standard single-rate VAT invoices only.
# No confidence is inferred from OCR word scores, missing evidence or a match
# between arithmetic totals alone. Never use this value to approve an invoice.
_PREVIEW_FIELDS = ('invoice_number', 'invoice_symbol', 'invoice_date', 'seller_name',
                   'seller_tax_code', 'buyer_name', 'buyer_tax_code', 'subtotal',
                   'vat_rate', 'vat_amount', 'total_amount')
_PREVIEW_CELLS = ('description', 'unit', 'quantity', 'unit_price', 'amount')
_NUMERIC = {'subtotal', 'vat_rate', 'vat_amount', 'total_amount', 'quantity', 'unit_price', 'amount'}


def _number(value):
    from decimal import Decimal, InvalidOperation
    try:
        d = Decimal(str(value))
        return d if d.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _present(key, value):
    if key in _NUMERIC:
        d = _number(value)
        return d is not None and d >= 0
    return value is not None and bool(str(value).strip())


def _same(key, left, right):
    if not _present(key, left) or not _present(key, right):
        return False
    if key in _NUMERIC:
        return _number(left) == _number(right)
    return str(left).strip() == str(right).strip()


def _source_parts(parts):
    return isinstance(parts, list) and any(isinstance(part, dict)
        and isinstance(part.get('text'), str) and part['text'].strip()
        and part.get('polygon') for part in parts)


def _quality_preview(fields, items, metadata):
    from decimal import Decimal
    if (metadata.get('used_pipeline') != 'hybrid_v8_final'
            or fields.get('document_type') != 'einvoice'
            or metadata.get('manual_corrections_present')):
        return None
    context = metadata.get('financial_context') or {}
    # Do not apply ordinary invoice requirements to adjustments or multi-rate VAT.
    if context.get('adjustment_observed') or len({str(g.get('rate')) for g in context.get('tax_groups', [])}) > 1:
        return None
    evidence = metadata.get('evidence') or {}
    selected = evidence.get('final_field_evidence') or {}
    recognized = evidence.get('recognized_items') or []
    findings = metadata.get('findings') or []
    required = list(_PREVIEW_FIELDS)
    missing = [key for key in required if not _present(key, fields.get(key))]
    completeness = (len(required) - len(missing)) / len(required)
    supported = sum(any(isinstance(candidate, dict)
                    and _same(key, fields.get(key), candidate.get('value'))
                    and _source_parts(candidate.get('evidence'))
                    for candidate in selected.get(key, [])) for key in required)
    # Row evidence is historical. Only count it for matching rows/values and
    # never transfer evidence from another row after a merge or a manual edit.
    row_slots = max(len(items), 1) * len(_PREVIEW_CELLS)
    filled_cells = sum(_present(key, row.get(key)) for row in items for key in _PREVIEW_CELLS)
    if len(recognized) == len(items):
        for index, (row, original) in enumerate(zip(items, recognized), 1):
            if row.get('line_no') != index or original.get('line_no') != index:
                continue
            if not _same('description', row.get('description'), original.get('description')):
                continue
            supported += sum(_same(key, row.get(key), original.get(key))
                             and _source_parts((original.get('evidence') or {}).get(key))
                             for key in _PREVIEW_CELLS)
    provenance = supported / (len(required) + row_slots)
    checks = metadata.get('financial_review') or []
    def passed(rule):
        results = [c.get('passed') for c in checks if c.get('rule') == rule]
        return bool(results) and all(v is True for v in results)
    row_math = bool(items)
    for row in items:
        q, p, a = (_number(row.get(k)) for k in ('quantity', 'unit_price', 'amount'))
        if any(v is None or v < 0 for v in (q, p, a)) or abs(q * p - a) >= Decimal('2'):
            row_math = False
    financial_checks = {'total': passed('ARITH'), 'vat': passed('VAT-ARITH'),
                        'item_sum': passed('ITEM-SUM'), 'row_math': row_math}
    financial = sum(financial_checks.values()) / len(financial_checks)
    total = evidence.get('total_pages')
    read_pages = {p.get('page') for p in evidence.get('pages', [])
                  if isinstance(p.get('page'), int) and p.get('page') > 0
                  and p.get('status') not in ('partial', 'failed')
                  and (_source_parts(p.get('boxes')) or any(c.isalnum() for c in str(p.get('raw_text') or '')))}
    page_ratio = (sum(1 <= n <= total for n in read_pages) / total
                  if isinstance(total, int) and total > 0 else 0.0)
    incomplete = bool(metadata.get('truncated') or metadata.get('coverage_incomplete')
                      or any(f.get('incomplete') for f in findings))
    if incomplete:
        # Even a full page count does not prove full text coverage.
        page_ratio = min(page_ratio, 0.5)
    coverage = (page_ratio + filled_cells / row_slots) / 2
    components = {'completeness': completeness, 'source_evidence': provenance,
                  'financial_consistency': financial, 'coverage': coverage}
    score = .25 * completeness + .35 * provenance + .25 * financial + .15 * coverage
    blockers = []
    if missing or filled_cells != row_slots:
        blockers.append('missing_required_data')
    if not all(financial_checks.values()) or any(c.get('passed') is not True for c in checks):
        blockers.append('financial_or_validation_review')
    if incomplete or page_ratio < 1:
        blockers.append('coverage_unconfirmed')
    if any(f.get('requires_review') for f in findings if f.get('code') != 'CONFIDENCE_REVIEW_REQUIRED'):
        blockers.append('source_review_required')
    return {'policy': 'local-quality-preview-v1', 'score': round(score, 6),
            'threshold': .90, 'threshold_met': score >= .90 and not blockers,
            'components': {key: round(value, 6) for key, value in components.items()},
            'weights': {'completeness': .25, 'source_evidence': .35,
                        'financial_consistency': .25, 'coverage': .15},
            'blockers': blockers, 'missing_fields': missing,
            'financial_checks': financial_checks,
            'semantics': 'Unapproved diagnostic quality score, not OCR accuracy or verification'}


def assess_confidence(fields, items, metadata):
    from copy import deepcopy

    policy = _policy
    selected = metadata.get('evidence', {}).get('final_field_evidence', {})
    llm_fields = metadata.get('llm', {}).get('applied_fields', [])
    field_observations = {
        key: {'value_present': value is not None, 'score': None,
              'evidence_reference': ('_ocr.llm.proposal.fields.' + key if key in llm_fields else
                                     '_ocr.evidence.final_field_evidence.' + key if key in selected else None)}
        for key, value in fields.items() if key != 'confidence_score'
    }
    decision = {'status': 'undetermined', 'score': None, 'threshold': None,
                'policy': None, 'approval_reference': None, 'requires_review': True,
                'reason': 'TBD-02 chưa có công thức và ngưỡng được phê duyệt.',
                'semantics': 'No calibrated field confidence has been established',
                'fields': field_observations,
                'evidence': {'ocr_evidence_available': bool(metadata.get('evidence')),
                             'field_count': len(fields), 'item_count': len(items),
                             'manual_corrections_present': bool(metadata.get('manual_corrections_present')),
                             'note': 'OCR provenance remains historical when values have been edited.'}}
    if policy is None:
        if _quality_preview_enabled:
            try:
                preview = _quality_preview(fields, items, metadata)
                if preview is not None:
                    decision['quality_preview'] = preview
            except Exception:
                # A diagnostic score must never interrupt extraction or validation.
                decision['quality_preview_status'] = 'unavailable'
        return decision
    decision.update(policy=policy.name, approval_reference=policy.approval_reference,
                    threshold=float(policy.threshold),
                    reason='Chính sách chưa xác định được điểm cho dữ liệu hiện tại.')
    try:
        value = policy.calculate(deepcopy(fields), deepcopy(items), deepcopy(metadata))
        if value is None or isinstance(value, bool):
            return decision
        score = float(value)
        if not isfinite(score) or not 0 <= score <= 1:
            raise ValueError('Invalid confidence policy result')
        return {**decision, 'status': 'low' if score < policy.threshold else 'assessed',
                'score': score, 'threshold': float(policy.threshold), 'policy': policy.name,
                'approval_reference': policy.approval_reference, 'requires_review': score < policy.threshold,
                'reason': ('Điểm thấp hơn ngưỡng của chính sách đã được phê duyệt.'
                           if score < policy.threshold else 'Điểm được tính theo chính sách đã được phê duyệt.'),
                'semantics': 'Approved policy score; not an automatic legal or tax verification'}
    except Exception as exc:
        return {**decision, 'reason': 'Không xác định được điểm theo chính sách đã cấu hình.',
                'policy': policy.name, 'approval_reference': policy.approval_reference,
                'error_type': type(exc).__name__}
