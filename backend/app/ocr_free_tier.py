"""Local, per-document permission boundary for optional Gemini Free Tier.

No network, billing, database or credential access. Approved source files may
be hashed locally to establish scope membership, never OCRed by this module.
Approvals do not certify privacy or Google eligibility automatically.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from types import MappingProxyType
from datetime import datetime, timezone
from uuid import uuid4
from time import monotonic


# Verified text models in Google's Standard Free Tier pricing, 2026-11-23.
# No prefix matching: an arbitrary model/preview/paid service is not eligible.
FREE_TEXT_MODELS = frozenset((
    'gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite',
))
_document_digest = ContextVar('ocr_free_tier_document_digest', default=None)
_web_approval = ContextVar('ocr_free_tier_web_approval', default=None)
_web_consent_required = ContextVar('ocr_free_tier_web_consent_required', default=False)


@dataclass(frozen=True)
class ApprovedFreeDocument:
    sha256: str
    data_class: str
    approval_reference: str
    policy_manifest_path: str | None = field(default=None, repr=False, compare=False)
    scope_policy_path: str | None = field(default=None, repr=False, compare=False)
    scope_id: str | None = None
    user_id: int | None = None
    file_type: str | None = None
    sensitivity: str = 'not_assessed'
    authority_source_path: str | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class ApprovedUploadScope:
    scope_id: str
    description: str
    user_ids: frozenset[int]
    file_types: frozenset[str]
    data_class: str
    approval_reference: str
    sensitivity: str = 'not_assessed'
    authorized_source_roots: tuple[Path, ...] = ()
    requires_source_proof: bool = False


def _policy_path(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('An administrator policy path is required')
    path = Path(value)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    return path.resolve()


def load_approved_upload_scope(value):
    """One operator-approved upload domain, never a model privacy decision.

    The administrator can delegate a named upload-account domain, or choose
    stricter source-directory membership. Account-domain authority is an
    operator attestation, not an OCR finding or proof of document ownership.
    Sensitivity is recorded separately; it is not a substitute for permission.
    """
    path = _policy_path(value)
    repository = Path(__file__).resolve().parents[2]
    if (path.is_relative_to(repository) or any((p / '.git').exists() for p in path.parents)
            or path.suffix.lower() != '.json' or path.stat().st_size > 256_000):
        raise ValueError('Administrator scope policy must be a small JSON file outside Git')
    data = json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=_unique_object)
    common = {'enabled', 'scope_id', 'scope_basis', 'description', 'user_ids', 'file_types',
              'data_class', 'external_transfer_approved', 'approval_reference'}
    legacy = common | {'non_sensitive_confirmed'}
    rights_account = common | {'sharing_authority_confirmed', 'free_tier_terms_accepted', 'sensitivity'}
    rights_sources = rights_account | {'authorized_source_roots'}
    if (not isinstance(data, dict) or set(data) not in (legacy, rights_account, rights_sources) or data['enabled'] is not True
            or data['external_transfer_approved'] is not True
            or any(not isinstance(data[k], str) or not data[k].strip() for k in ('scope_id', 'description', 'approval_reference'))):
        raise ValueError('An explicit administrator sharing approval is required')
    source_roots = ()
    rights_based = set(data) in (rights_account, rights_sources)
    requires_source_proof = set(data) == rights_sources
    sensitivity = 'non_sensitive'
    if rights_based:
        basis = 'authorized_source_documents' if requires_source_proof else 'administrator_authorized_uploads'
        if (data['scope_basis'] != basis or data['data_class'] != 'authorized_invoice'
                or data['sharing_authority_confirmed'] is not True or data['free_tier_terms_accepted'] is not True
                or data['sensitivity'] not in ('not_assessed', 'sensitive', 'non_sensitive')
                or (requires_source_proof and (not isinstance(data['authorized_source_roots'], list)
                                               or len(data['authorized_source_roots']) > 20))):
            raise ValueError('An administrator sharing scope and accepted Free Tier terms are required')
        roots = []
        for value in data.get('authorized_source_roots', []):
            if not isinstance(value, str) or not value.strip():
                raise ValueError('An authorized source root must be an explicit local directory')
            root = Path(value)
            if not root.is_absolute() or root.drive.startswith('\\\\'):
                raise ValueError('Only absolute local source directories are supported')
            root = root.resolve(strict=True)
            # The upload store, repository and a parent containing them cannot
            # authorize themselves merely because an upload was saved there.
            if (not root.is_dir() or root.is_relative_to(repository) or repository.is_relative_to(root)
                    or any((parent / '.git').exists() for parent in (root, *root.parents))):
                raise ValueError('Approved sources must be outside Git and the application upload store')
            roots.append(root)
        source_roots = tuple(dict.fromkeys(roots))
        sensitivity = data['sensitivity']
    elif (data['scope_basis'] != 'all_uploads_from_authorized_accounts' or data['non_sensitive_confirmed'] is not True
          or data['data_class'] not in ('sample', 'approved_non_sensitive')):
        raise ValueError('Legacy scope needs its explicit non-sensitive domain approval')
    users, types = data['user_ids'], data['file_types']
    if (not isinstance(users, list) or not users or len(users) > 10_000
            or any(type(user) is not int or user <= 0 for user in users)
            or len(set(users)) != len(users)
            or not isinstance(types, list) or not types or any(type(t) is not str for t in types)
            or not set(types).issubset({'pdf', 'jpg', 'png', 'xml'}) or len(set(types)) != len(types)):
        raise ValueError('Upload scope needs explicit uploader IDs and supported file types')
    return ApprovedUploadScope(data['scope_id'].strip(), data['description'].strip(), frozenset(users),
                               frozenset(types), data['data_class'], data['approval_reference'].strip(),
                               sensitivity, source_roots, requires_source_proof)


def _source_member(scope, value, digest, file_type, *, size=None, deadline=None):
    """Prove membership by exact local bytes, not filename or OCR inference."""
    try:
        source = Path(value)
        if source.is_symlink():
            return False
        source = source.resolve(strict=True)
        if not any(source.is_relative_to(root) for root in scope.authorized_source_roots):
            return False
        kind = source.suffix.lower().lstrip('.')
        if ('jpg' if kind == 'jpeg' else kind) != file_type or not source.is_file():
            return False
        length = source.stat().st_size
        if length > 20 * 1024 * 1024 or (size is not None and length != size):
            return False
        observed = sha256()
        count = 0
        with source.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                count += len(chunk)
                if count > 20 * 1024 * 1024 or (deadline is not None and monotonic() > deadline):
                    return False
                observed.update(chunk)
        return count == length and observed.hexdigest() == digest
    except (OSError, ValueError, TypeError):
        return False


def _find_authorized_source(scope, digest, file_type, size):
    """Bounded lookup; unknown/over-budget documents stay local without prompts."""
    deadline, visited, bytes_considered = monotonic() + 3, 0, 0
    pending = list(scope.authorized_source_roots)
    while pending:
        if monotonic() > deadline:
            return None
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited += 1
                    if visited > 2000 or monotonic() > deadline:
                        return None
                    if entry.is_symlink() or entry.name == '.git':
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                        continue
                    source = Path(entry.path)
                    kind = source.suffix.lower().lstrip('.')
                    if ('jpg' if kind == 'jpeg' else kind) != file_type:
                        continue
                    if not entry.is_file(follow_symlinks=False) or entry.stat(follow_symlinks=False).st_size != size:
                        continue
                    bytes_considered += size
                    if bytes_considered > 128 * 1024 * 1024:
                        return None
                    if _source_member(scope, source, digest, file_type, size=size, deadline=deadline):
                        return str(source.resolve())
        except OSError:
            continue
    return None


@contextmanager
def document_scope(data, *, web_approval=None, require_web_consent=False):
    """Bind permission to the actual upload bytes; never trust a client label."""
    digest = sha256(data).hexdigest()
    if web_approval is not None and (
            not isinstance(web_approval, ApprovedFreeDocument) or web_approval.sha256 != digest
            or web_approval.data_class not in ('sample', 'approved_non_sensitive', 'authorized_invoice')
            or not web_approval.approval_reference.strip()
            or (web_approval.data_class == 'authorized_invoice'
                and (not web_approval.scope_policy_path or type(web_approval.user_id) is not int
                     or web_approval.user_id <= 0 or web_approval.file_type not in ('pdf', 'jpg', 'png', 'xml')))):
        raise ValueError('Web approval must match the actual upload bytes')
    token = _document_digest.set(digest)
    approval_token = _web_approval.set(web_approval)
    required_token = _web_consent_required.set(require_web_consent)
    try:
        yield
    finally:
        _web_consent_required.reset(required_token)
        _web_approval.reset(approval_token)
        _document_digest.reset(token)


def current_document_approval(approved_documents, *, scope_policy_path=None):
    approval = _web_approval.get()
    if approval is not None and approval.sha256 == _document_digest.get():
        # OCR can take minutes. Recheck administrator revocation before both
        # proposal preparation and the provider's actual outbound request.
        if approval.scope_policy_path:
            try:
                if not scope_policy_path or _policy_path(scope_policy_path) != _policy_path(approval.scope_policy_path):
                    return None
                scope = load_approved_upload_scope(scope_policy_path)
                if (approval.scope_id != scope.scope_id or approval.user_id not in scope.user_ids
                        or approval.file_type not in scope.file_types or approval.data_class != scope.data_class
                        or approval.approval_reference != scope.approval_reference
                        or approval.sensitivity != scope.sensitivity):
                    return None
                if scope.requires_source_proof and (not approval.authority_source_path
                        or not _source_member(scope, approval.authority_source_path, approval.sha256, approval.file_type)):
                    return None
            except (OSError, ValueError, TypeError):
                return None
        elif scope_policy_path:
            return None  # Scope-mode provider cannot reuse an old per-file grant.
        elif approval.policy_manifest_path:
            try:
                active = load_approved_documents(approval.policy_manifest_path).get(approval.sha256)
                if (active is None or active.data_class != approval.data_class
                        or active.approval_reference != approval.approval_reference):
                    return None
            except (OSError, ValueError, TypeError):
                return None
        return approval
    if _web_consent_required.get() or scope_policy_path:
        return None  # Website uploads require the server's per-file decision.
    return approved_documents.get(_document_digest.get())


def automatic_policy_user_ids(settings):
    values = str(getattr(settings, 'gemini_auto_policy_user_ids', '') or '').strip()
    if not values:
        return frozenset()
    entries = [value.strip() for value in values.split(',')]
    if any(not re.fullmatch(r'[1-9][0-9]*', value) for value in entries):
        return frozenset()  # Invalid permission configuration fails closed.
    return frozenset(int(value) for value in entries)


def automatic_policy_status(settings, user_id, provider_state):
    if not getattr(settings, 'gemini_auto_policy_enabled', False):
        return False, 'policy_disabled'
    mode = getattr(settings, 'gemini_auto_policy_mode', 'manifest')
    if mode == 'approved_scope':
        try:
            scope = load_approved_upload_scope(getattr(settings, 'gemini_auto_policy_path', None))
        except (OSError, ValueError, TypeError):
            return False, 'policy_unavailable'
        if user_id not in scope.user_ids:
            return False, 'user_not_authorized'
        if scope.requires_source_proof and not scope.authorized_source_roots:
            return False, 'scope_sources_missing'
    elif mode != 'manifest':
        return False, 'policy_unavailable'
    elif user_id not in automatic_policy_user_ids(settings):
        return False, 'user_not_authorized'
    if provider_state.get('status') != 'configured':
        return False, 'provider_not_configured'
    return True, 'available'


def automatic_document_approval(settings, data, *, user_id, invoice_id, provider_state, file_type=None):
    """Apply existing administrator permission; never classify arbitrary data.

    Scope mode applies an existing administrator grant to new upload bytes.
    Manifest mode remains available for old deployments; neither mode creates
    approval from a filename, OCR guess or uploader checkbox.
    """
    available, reason = automatic_policy_status(settings, user_id, provider_state)
    if not available:
        return None, reason
    digest = sha256(data).hexdigest()
    mode = getattr(settings, 'gemini_auto_policy_mode', 'manifest')
    try:
        if mode == 'approved_scope':
            path = _policy_path(settings.gemini_auto_policy_path)
            scope = load_approved_upload_scope(str(path))
            if user_id not in scope.user_ids or file_type not in scope.file_types:
                return None, 'document_not_approved'
            source = None
            if scope.requires_source_proof:
                source = _find_authorized_source(scope, digest, file_type, len(data))
                if source is None:
                    return None, 'document_not_approved'
            approval = ApprovedFreeDocument(digest, scope.data_class, scope.approval_reference,
                                           scope_policy_path=str(path), scope_id=scope.scope_id,
                                           user_id=user_id, file_type=file_type, sensitivity=scope.sensitivity,
                                           authority_source_path=source)
        else:
            documents = load_approved_documents(settings.gemini_free_tier_manifest)
            approval = documents.get(digest)
            if approval is not None:
                approval = ApprovedFreeDocument(approval.sha256, approval.data_class, approval.approval_reference,
                                                policy_manifest_path=str(_policy_path(settings.gemini_free_tier_manifest)))
    except (OSError, ValueError, TypeError):
        return None, 'policy_unavailable'
    if approval is None:
        return None, 'document_not_approved'
    repository = Path(__file__).resolve().parents[2]
    root = Path(settings.gemini_policy_audit_dir).resolve()
    if root.is_relative_to(repository) or any((parent / '.git').exists() for parent in (root, *root.parents)):
        return None, 'decision_store_unavailable'
    event_id = str(uuid4())
    record = {'event_id': event_id, 'user_id': user_id, 'invoice_id': invoice_id,
              'created_at': datetime.now(timezone.utc).isoformat(),
              'sha256': digest, 'data_class': approval.data_class,
              'document_approval_reference': approval.approval_reference,
              'processing_approval_reference': settings.gemini_approval_reference,
              'free_tier_reference': settings.gemini_free_tier_reference,
              'policy_mode': mode, 'scope_id': approval.scope_id, 'file_type': file_type,
              'sensitivity': approval.sensitivity,
              'scope_membership': ('administrator_source_bytes' if approval.authority_source_path else
                                   'administrator_account_scope' if approval.data_class == 'authorized_invoice' else 'legacy_grant'),
              'meaning': 'Applied existing administrator approval; not new consent, data classification or G13 acceptance'}
    try:
        root.mkdir(parents=True, exist_ok=True)
        # No invoice text, filenames or credentials are stored in the audit.
        with (root / (event_id + '.json')).open('x', encoding='utf-8') as output:
            json.dump(record, output, ensure_ascii=False, allow_nan=False)
    except (OSError, ValueError, TypeError):
        return None, 'decision_store_unavailable'
    return approval, 'approved'


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate Free Tier manifest key')
        result[key] = value
    return result


def load_approved_documents(manifest_path):
    """Load hashes/permission references only, never the original documents.

    Absence/invalidity disables Gemini registration. An empty documents list is
    valid but authorizes no uploads. Legal/privacy review remains human-owned.
    """
    path = Path(manifest_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    if path.suffix.lower() != '.json' or path.stat().st_size > 256_000:
        raise ValueError('Invalid Free Tier approval manifest')
    payload = json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=_unique_object)
    if (not isinstance(payload, dict) or set(payload) != {'documents'}
            or not isinstance(payload['documents'], list)):
        raise ValueError('Free Tier manifest must contain a documents list')
    approved = {}
    required = {'sha256', 'data_class', 'non_sensitive_confirmed',
                'external_transfer_approved', 'approval_reference'}
    for entry in payload['documents']:
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError('Invalid Free Tier document approval')
        digest = entry['sha256']
        reference = entry['approval_reference']
        if (not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest)
                or entry['data_class'] not in ('sample', 'approved_non_sensitive')
                or entry['non_sensitive_confirmed'] is not True
                or entry['external_transfer_approved'] is not True
                or not isinstance(reference, str) or not reference.strip()):
            raise ValueError('Free Tier document lacks non-sensitive data approval')
        digest = digest.lower()
        if digest in approved:
            raise ValueError('Duplicate Free Tier document hash')
        approved[digest] = ApprovedFreeDocument(digest, entry['data_class'], reference.strip())
    return MappingProxyType(approved)
