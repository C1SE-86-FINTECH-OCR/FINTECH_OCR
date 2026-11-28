"""Business identity lookup; never certifies invoice authenticity."""
import re
import time
import unicodedata
from threading import Lock
from datetime import datetime, timezone
import httpx
import os
from pathlib import Path

_cache = {}
_lock = Lock()
_token = None


def supplementary_business(code):
    """Optional authorized Casso IDKit; never scrape tax portals or log credentials."""
    global _token
    app_id, secret = os.getenv('CASSO_APP_ID'), os.getenv('CASSO_APP_SECRET')
    if not app_id or not secret:
        from dotenv import dotenv_values
        config = dotenv_values(Path(__file__).resolve().parents[1]/'.env', interpolate=False)
        app_id, secret = app_id or config.get('CASSO_APP_ID'), secret or config.get('CASSO_APP_SECRET')
    if not app_id or not secret:
        return None
    try:
        with _lock:
            token = _token
        if not token or token[0] <= time.monotonic():
            response = httpx.post('https://openapi.casso.vn/oauth/token',
                                 json={'app_id':app_id,'app_secret':secret},timeout=8)
            response.raise_for_status()
            data = response.json()
            value = data.get('access_token')
            if not isinstance(value,str) or not value:
                return None
            token = (time.monotonic()+min(840,max(1,int(data.get('expires_in',900))-30)),value)
            with _lock:
                _token = token
        path_code = code[:10]+'-'+code[10:] if len(code)==13 else code
        response = httpx.get('https://openapi.casso.vn/idkit/v1/business/'+path_code,
                             headers={'Authorization':'Bearer '+token[1]},timeout=8)
        response.raise_for_status()
        data=response.json()
        business=data.get('business') or (data.get('data') or {}).get('business')
        if not isinstance(business,dict) or re.sub(r'[^0-9]','',str(business.get('taxCode',''))) != code:
            return None
        return business
    except (httpx.HTTPError,ValueError,TypeError,AttributeError):
        return None

def normalize_name(value):
    text = unicodedata.normalize('NFD', str(value or '').casefold().replace('\u0111', 'd'))
    return ''.join(c for c in text if c.isalnum())


def name_tokens(value):
    text = unicodedata.normalize('NFD', str(value or '').casefold().replace('\u0111','d'))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    for pattern, replacement in ((r'\bcty\b','cong ty'), (r'\btnhh\b','trach nhiem huu han'),
                                 (r'\b(?:ctcp|cp)\b','co phan'), (r'\btm\b','thuong mai'),
                                 (r'\bdv\b','dich vu'), (r'\bvn\b','viet nam')):
        text = re.sub(pattern,replacement,text)
    return re.findall(r'[a-z0-9]+',text)


def compare_names(observed, registered, *, complete=False):
    left,right = name_tokens(observed),name_tokens(registered)
    if not left or not right:
        return 'insufficient_data'
    if left == right:
        return 'match'
    # Preserve order; missing OCR words never prove a different legal identity.
    def subsequence(a,b):
        values=iter(b)
        return all(any(word==candidate for candidate in values) for word in a)
    if subsequence(left,right) or subsequence(right,left):
        return 'partial_match'
    return 'mismatch' if complete else 'insufficient_data'


def document_identity(raw, fields, source_format=None):
    """Recover only contiguous source lines, never complete a name from registry data."""
    result=dict(fields)
    folded=' '.join(name_tokens(raw))
    kind = ('tax_registration' if 'giay chung nhan dang ky thue' in folded else
            'business_registration' if 'giay chung nhan dang ky doanh nghiep' in folded else
            'invoice' if re.search(r'\b(?:hoa don|invoice)\b',folded) or (source_format=='xml' and fields.get('document_type')=='einvoice') else 'other')
    result['tax_document_kind']=kind
    result['seller_name_complete'] = source_format == 'xml' and bool(fields.get('seller_name'))
    lines=[line.strip() for line in raw.replace('\f','\n\n').splitlines()]
    original=str(fields.get('seller_name') or '').strip()
    from .invoice_financials import party_value_kind
    def allowed_name(value):
        folded=' '.join(name_tokens(value))
        return (bool(value) and party_value_kind(value) in (None,'name_candidate')
                and not re.search(r'^(?:giay chung nhan|dang ky thue|dang ky doanh nghiep|hoa don|tong hop thanh toan|cong hoa|doc lap tu do)\b',folded))
    if original and not allowed_name(original):
        result['rejected_name_observation']=original
        result['seller_name']=None
        original=''
    # A labeled taxpayer/seller field takes precedence over an OCR title.
    for index,line in enumerate(lines):
        match=re.match(r'^\s*(?:\d+[.)]\s*)?(?:tên người nộp thuế|tên doanh nghiệp|tên công ty|đơn vị bán hàng|người bán|seller|supplier)\s*[:：]\s*(.*)$',line,re.I)
        if match:
            candidate=match.group(1).strip() or (lines[index+1] if index+1<len(lines) else '')
            if allowed_name(candidate):
                original=candidate
                result['seller_name']=candidate
                break
    if not original and kind in ('tax_registration','business_registration'):
        candidates=[line for line in lines if re.match(r'^(?:cong ty|cty|company)\b',' '.join(name_tokens(line))) and allowed_name(line)]
        if len({tuple(name_tokens(value)) for value in candidates})==1:
            original=candidates[0]
            result['seller_name']=original
    for index,line in enumerate(lines):
        literal=re.sub(r'^(?:tên người nộp thuế|tên doanh nghiệp|tên công ty|đơn vị bán hàng|người bán|seller|supplier)\s*[:：]\s*','',line,flags=re.I)
        candidate, previous = name_tokens(literal), name_tokens(original)
        if previous and candidate[:len(previous)] == previous and (candidate==previous or candidate[:2]==['cong','ty']):
            parts=[literal]
            for continuation in lines[index+1:index+3]:
                if (not allowed_name(continuation) or ':' in continuation or re.search(r'\d',continuation)
                        or not continuation.isupper()
                        or re.match(r'^(?:cong ty|cty|company|corporation|cuc thue|tong cuc|so ke hoach)\b',' '.join(name_tokens(continuation)))
                        or re.search(r'\b(?:mst|ma so|dia chi|nguoi mua|buyer|ngan hang|tax|address|ky ten|hoa don|giay chung nhan|cong hoa|doc lap|ten nguoi)\b',' '.join(name_tokens(continuation)))):
                    break
                parts.append(continuation)
            result['seller_name']=' '.join(parts)
            result['seller_name_source_lines']=parts
            break
    return result

def verify_tax_code(tax_code, expected_name=None, expected_address=None, refresh=False):
    code = re.sub(r"[\s-]", "", str(tax_code or ""))
    base = {'tax_code': code, 'source': 'VietQR business API',
            'invoice_authenticity_verified': False}
    if not re.fullmatch(r"[0-9]{10}(?:[0-9]{3})?", code):
        return {**base, 'status': 'invalid_or_missing_tax_code'}
    key = code
    with _lock:
        entry = _cache.get(key)
    if entry and entry[0] > time.monotonic() and (not refresh or time.monotonic() - entry[2] < 10):
        result = dict(entry[1], cached=True)
    else:
        try:
            path_code = code[:10]+'-'+code[10:] if len(code)==13 else code
            response = httpx.get('https://api.vietqr.io/v2/business/' + path_code,
                                 timeout=httpx.Timeout(10, connect=5), follow_redirects=False)
            response.raise_for_status()
            payload = response.json()
            data = payload.get('data')
            if payload.get('code') == '52':
                result = {**base, 'status': 'not_found'}
            elif payload.get('code') == '51':
                result = {**base, 'status': 'invalid_or_missing_tax_code'}
            elif payload.get('code') == '00' and isinstance(data, dict) and re.sub(r'[^0-9]', '', str(data.get('id', ''))) == code and isinstance(data.get('name'), str) and data['name'].strip():
                result = {**base, 'status': 'found', 'registered_name': data['name'],
                          'registered_address': data.get('address') if isinstance(data.get('address'),str) else None}
            else:
                return {**base, 'status': 'unavailable', 'reason': 'invalid_provider_response'}
            result.update(checked_at=datetime.now(timezone.utc).isoformat(), cached=False)
            with _lock:
                if len(_cache) >= 512:
                    _cache.pop(next(iter(_cache)))
                _cache[key] = (time.monotonic() + (3600 if result['status'] == 'found' else 60), dict(result), time.monotonic())
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            failure = {**base, 'status': 'unavailable', 'error_type': type(exc).__name__,
                       'checked_at': datetime.now(timezone.utc).isoformat(),
                       'http_status': getattr(getattr(exc, 'response', None), 'status_code', None)}
            with _lock:
                if len(_cache) >= 512:
                    _cache.pop(next(iter(_cache)))
                _cache[key] = (time.monotonic()+30, dict(failure), time.monotonic())
            return failure
    if result['status'] == 'found':
        result['name_comparison'] = compare_names(expected_name,result['registered_name'])
    return result


def verification_context(fields, refresh=False):
    result = verify_tax_code(fields.get('seller_tax_code'), fields.get('seller_name'), refresh=refresh)
    result['official_lookup_url'] = 'https://hoadondientu.gdt.gov.vn/'
    result['invoice_verification_status'] = 'not_verified'
    result['document_kind'] = fields.get('tax_document_kind','unknown')
    if result['document_kind'] in ('tax_registration','business_registration','other'):
        result['invoice_verification_status']='not_applicable'
    result['name_observation_complete'] = fields.get('seller_name_complete') is True
    if result['status']=='found':
        result['name_comparison']=compare_names(fields.get('seller_name'),result['registered_name'],complete=result['name_observation_complete'])
    result['operating_status'] = None
    result['tax_department'] = None
    extra = supplementary_business(result['tax_code']) if result['status'] == 'found' else None
    if extra:
        for target, key in (('operating_status','status'),('tax_department','taxDepartment')):
            value = extra.get(key)
            if isinstance(value, dict):
                value = value.get('name') or value.get('label')
            result[target] = value if isinstance(value,str) else None
        result['supplementary_source'] = 'Casso IDKit'
    result['comparisons'] = [
        {'field': 'tax_code', 'observed': fields.get('seller_tax_code'),
         'registered': result.get('tax_code') if result['status'] == 'found' else None,
         'status': 'match' if result['status'] == 'found' else 'unconfirmed'},
        {'field': 'name', 'observed': fields.get('seller_name'),
         'registered': result.get('registered_name'), 'status': result.get('name_comparison', 'unconfirmed')},
        {'field': 'address', 'observed': fields.get('seller_address'),
         'registered': result.get('registered_address'), 'status': ('unconfirmed' if not fields.get('seller_address') or not result.get('registered_address') else
             'match' if normalize_name(fields['seller_address']) == normalize_name(result['registered_address']) else 'needs_review')},
    ]
    for key in ('operating_status','tax_department'):
        result['comparisons'].append({'field':key, 'observed':fields.get(key),
            'registered':result.get(key), 'status':'unconfirmed'})
    states=[row['status'] for row in result['comparisons'] if row['field'] in ('tax_code','name','address')]
    result['overall_comparison'] = ('mismatch' if 'mismatch' in states else
        'partial_match' if 'partial_match' in states else
        'match' if states and all(state=='match' for state in states) else
        'insufficient_data')
    result['comparison_note'] = {
        'match':'Các trường có dữ liệu đối chiếu trùng khớp; không phải xác nhận hóa đơn hợp pháp.',
        'partial_match':'Tên có phần trùng khớp nhưng OCR có thể chưa đầy đủ; cần đối chiếu chứng từ.',
        'mismatch':'Có trường khác dữ liệu đăng ký; chưa kết luận gian lận hoặc tính hợp pháp.',
        'insufficient_data':'Đã giữ các kết quả từng trường; chưa đủ dữ liệu để kết luận tổng thể.'}[result['overall_comparison']]
    return result


def tax_question_code(question):
    if not re.search(r'\b(?:mst|tax|ma so thue)\b', unicodedata.normalize('NFD', question.casefold()).encode('ascii','ignore').decode()):
        return None
    match = re.search(r'(?<![0-9])([0-9]{10}(?:-?[0-9]{3})?)(?![0-9])', question)
    return match.group(1) if match else None


def tax_summary(result):
    if result['status'] == 'found':
        return ('Đã tìm thấy thông tin doanh nghiệp: ' + result.get('registered_name', '')
                + '. Kết quả chỉ đối chiếu thông tin đăng ký doanh nghiệp. '
                + ('Tình trạng hoạt động: '+result['operating_status']+'. ' if result.get('operating_status') else 'Chưa có dữ liệu tình trạng hoạt động. ')
                + ('Cơ quan thuế: '+result['tax_department']+'.' if result.get('tax_department') else 'Chưa có dữ liệu cơ quan thuế quản lý.'))
    return {'not_found': 'Nguồn tra cứu không tìm thấy mã số thuế; chưa thể kết luận doanh nghiệp không tồn tại.',
            'invalid_or_missing_tax_code': 'Chưa đọc được mã số thuế người bán hợp lệ; không tự suy đoán.',
            'unavailable': 'Nguồn tra cứu thuế tạm thời không khả dụng; dữ liệu OCR được giữ nguyên.'}.get(result['status'], 'Chưa xác minh.')
