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
