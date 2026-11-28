"""Source-backed financial scopes; calculations are for review, never repairs."""
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from statistics import median
from datetime import date


def folded(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', str(text)).lower().replace('đ', 'd')
                           if not unicodedata.combining(c)).split())


REFERENCE_ANCHOR = re.compile(
    r'\b(?:(?:dieu chinh|thay the)(?: cho)? (?:hoa don|hd|invoice)|'
    r'(?:hoa don|invoice) (?:goc|lien quan|(?:bi|duoc) (?:dieu chinh|thay the))|'
    r'(?:original|adjusted|replaced|previous) invoice|(?:adjustment|replacement) (?:of|for) invoice)\b')
NON_FINANCIAL_TARGET = re.compile(r'\b(?:ma so thue|mst|tax (?:id|code)|dia chi|address|'
                                    r'ten (?:don vi|cong ty|nguoi mua|nguoi ban)|(?:buyer|seller|company) name)\b')
CORRECTION_ROW = re.compile(r'^[\s|]*(?:\d+[.)]?\s*(?:\|\s*)?)?(?:noi dung dieu chinh|ly do dieu chinh|'
                            r'dieu chinh|correction(?: of)?|correcting|amendment(?: details)?)\b')


def correction_statement(text):
    return bool(CORRECTION_ROW.match(folded(text)))


def reference_line_indices(lines):
    """Keep related-invoice and correction narratives out of current fields.

    An ambiguous continuation label stays with the explicitly referenced
    invoice, rather than becoming a new issue date/identifier by proximity.
    Original text is retained separately; no field is manufactured here.
    """
    ignored, related, pending_value, narrative = set(), False, False, False
    attribute = re.compile(r'^(?:so hoa don|so(?=\s*[:：]|\s*$)|ky hieu(?: hoa don)?|ngay(?: lap| hoa don)?|'
                           r'invoice (?:no\.?|number|date|symbol)|series|issue date)'
                           r'(?:\s*[:：]\s*|\s+(?=[a-z0-9])|$)(.*)$')
    for index, original in enumerate(lines):
        plain = folded(original).strip(' |')
        if REFERENCE_ANCHOR.search(plain):
            ignored.add(index)
            related, pending_value, narrative = True, plain.endswith((':', '：')), False
        elif correction_statement(original):
            ignored.add(index)
            related, pending_value, narrative = False, False, True
        elif narrative and (NON_FINANCIAL_TARGET.search(plain) or re.match(r'^(?:tu|thanh|cu|moi|sai|dung|from|to|old|new)\b', plain)):
            ignored.add(index)
        elif related and (field := attribute.match(re.sub(r'\([^)]*\)', '', plain))):
            ignored.add(index)
            pending_value = not field[1].strip()
        elif related and pending_value and re.fullmatch(r'[a-z0-9/., _-]+', plain) and re.search(r'\d', plain):
            ignored.add(index)
            pending_value = False
        else:
            related, pending_value, narrative = False, False, False
    return ignored


def current_document_text(raw):
    pages = []
    for page in (raw or '').split('\f'):
        lines = page.splitlines()
        ignored = reference_line_indices(lines)
        pages.append('\n'.join(line for index, line in enumerate(lines) if index not in ignored))
    return '\f'.join(pages)


SELLER_NAME_LABEL = (r'(?:(?:ten|ho ten)\s+)?(?:don\s+vi\s+ban(?:\s+hang)?|'
                     r'nguoi\s+ban(?:\s+hang)?|ben\s+ban|nha\s+cung\s+cap|don\s+vi\s+cung\s+cap|'
                     r'seller(?:\s+name|\s+company)?|supplier(?:\s+name|\s+company)?)')
BUYER_NAME_LABEL = (r'(?:(?:ten|ho ten)\s+)?(?:don\s+vi\s+mua(?:\s+hang)?|'
                    r'nguoi\s+mua(?:\s+hang)?|ben\s+mua|buyer(?:\s+name|\s+company)?|customer(?:\s+name)?)')


def party_section_role(value):
    """An explicit section heading owns fields below it; a signature does not."""
    if not isinstance(value, str):
        return None
    text = folded(value).strip(' :;.,()|')
    for role, label in (('seller', SELLER_NAME_LABEL), ('buyer', BUYER_NAME_LABEL)):
        if re.fullmatch(r'(?:thong tin|chi tiet|information (?:on|about)|details (?:of|about))\s+(?:' + label + r')', text):
            return role
        if re.fullmatch(r'(?:' + label + r')\s+(?:information|details)', text):
            return role
    return None


def party_name_literal(value):
    """Remove nested, explicit name labels only; keep the printed name."""
    if not isinstance(value, str):
        return value
    for _ in range(2):
        parts = re.split('[:：]', value, maxsplit=1)
        if len(parts) != 2 or not re.fullmatch(
                r'ten (?:don vi|cong ty)|company name|ho ten|name',
                folded(re.sub(r'\([^)]*\)', '', parts[0])).strip()):
            break
        value = parts[1].strip()
    return value


def document_semantics(raw, evidence=None):
    """Source-derived relation metadata, orthogonal to einvoice/bill/unknown."""
    evidence = evidence or {}
    references, descriptions, old_tax_codes = [], [], set()
    kinds = set()
    inferred_correction = False
    for page, text in _source_pages(raw, evidence):
        lines = text.splitlines()
        ignored = reference_line_indices(lines)
        for index, original in enumerate(lines):
            plain = folded(original)
            if re.fullmatch(r'hoa don(?: gia tri gia tang| gtgt| dien tu)?', plain) and index + 1 < len(lines):
                following_title = folded(lines[index + 1]).strip(' ()')
                if following_title in ('dieu chinh', 'thay the'):
                    kinds.add('adjustment' if following_title == 'dieu chinh' else 'replacement')
            if re.search(r'\b(?:hoa don(?: gia tri gia tang| gtgt| dien tu)?\s*\(?\s*dieu chinh|adjustment invoice|credit note|debit note)\b', plain) or re.search(r'\bdieu chinh(?: cho)? (?:hoa don|hd)\b', plain):
                kinds.add('adjustment')
            if re.search(r'\b(?:hoa don(?: gia tri gia tang| gtgt| dien tu)?\s*\(?\s*thay the|replacement invoice|thay the(?: cho)? (?:hoa don|hd))\b', plain):
                kinds.add('replacement')
            if (index in ignored and not correction_statement(original)) or REFERENCE_ANCHOR.search(plain):
                references.append({'page': page, 'line': index + 1, 'text': original})
            if correction_statement(original):
                parts = [original]
                for following in lines[index + 1:index + 9]:
                    p = folded(following)
                    if (not p or correction_statement(following) or financial_heading(following)
                            or re.match(r'^(?:tong|cong tien|tien thue|thue suat|subtotal|total|vat|'
                                        r'nguoi (?:mua|ban)|don vi (?:mua|ban)|seller|buyer|chu ky|ghi chu)\b', p)
                            or not (NON_FINANCIAL_TARGET.search(p) or re.match(r'^(?:tu|thanh|cu|moi|sai|dung|from|to|old|new)\b', p))):
                        break
                    parts.append(following)
                literal = '\n'.join(parts)
                descriptions.append({'page': page, 'line': index + 1, 'text': literal,
                                     'non_financial_target': bool(NON_FINANCIAL_TARGET.search(folded(literal)))})
                if NON_FINANCIAL_TARGET.search(folded(literal)):
                    inferred_correction = True
                for match in re.finditer(r'\b(?:tu|mst cu\s*[:：]?|ma so thue cu\s*[:：]?|old tax (?:id|code)\s*[:：]?)\s*(\d{10}(?:-?\d{3})?)\b', folded(literal)):
                    old_tax_codes.add(match[1])
    if not kinds and inferred_correction:
        kinds.add('adjustment')
    kind = next(iter(kinds)) if len(kinds) == 1 else 'unknown' if kinds or references else 'regular'
    ref_text = '\n'.join(entry['text'] for entry in references)
    ref_plain = folded(ref_text)
    numbers = {match[1] for match in re.finditer(r'\b(?:so(?: hoa don)?|hoa don so|invoice(?: (?:no\.?|number)|(?=\s*#)))\s*[:#：]?\s*([a-z0-9][a-z0-9/._-]*)', ref_plain) if re.search(r'\d', match[1])}
    symbols = {match[1] for match in re.finditer(r'\b(?:ky hieu(?: hoa don)?|invoice (?:symbol|series)|series|serial)\s*[:：]?\s*([a-z0-9][a-z0-9/_-]*)', ref_plain)}
    def printed_identifier(value):
        originals = {match[0] for match in re.finditer(r'(?<![A-Za-z0-9/._-])' + re.escape(value)
                     + r'(?![A-Za-z0-9/._-])', ref_text, re.I)}
        return next(iter(originals)) if len(originals) == 1 else value
    numbers = {printed_identifier(value) for value in numbers}
    symbols = {printed_identifier(value) for value in symbols}
    dates = set()
    for match in re.finditer(r'\b(?:ngay(?: lap| hoa don)?|date|dated|issued)\s*[:：]?\s*(\d{1,4})\s*(?:[/.-]|thang)\s*(\d{1,2})\s*(?:[/.-]|nam)\s*(\d{2,4})\b', ref_plain):
        a, b, c = match.groups()
        if len(a) != 4 and len(c) != 4:
            continue  # A two-digit year does not establish its century.
        try:
            dates.add(date(int(a), int(b), int(c)).isoformat() if len(a) == 4 else date(int(c), int(b), int(a)).isoformat())
        except ValueError:
            pass
    change_text = ' '.join(folded(entry['text']) for entry in descriptions)
    # Only explicit non-financial corrections qualify. General discounts,
    # amount adjustments and uncertain mixed scopes retain normal validation.
    without_no_change = re.sub(
        r'\b(?:khong (?:lam )?(?:thay doi|dieu chinh)|no change (?:in|to))\s+'
        r'(?:(?:so tien|gia tri|tien hang|tien thue|thue suat|thue|vat|amount|tax)[\s,/]*(?:va\s+|and\s+)?)+', '', change_text)
    monetary_change = bool(re.search(r'\b(?:so luong|don gia|so tien|thanh tien|tien hang|tien thue|thue suat|'
                                    r'gia tri|vat|chiet khau|phu phi|quantity|unit price|amount|tax rate|tax amount|discount|surcharge)\b', without_no_change))
    non_financial = (kind == 'adjustment' and any(entry['non_financial_target'] for entry in descriptions) and not monetary_change)
    page_count = evidence.get('total_pages')
    if type(page_count) is not int or page_count < 1:
        page_count = len((raw or '').split('\f'))
    return {'kind': kind, 'multiple_pages': page_count > 1, 'page_count': page_count,
            'references': references, 'referenced_invoice_number': next(iter(numbers)) if len(numbers) == 1 else None,
            'referenced_invoice_symbol': next(iter(symbols)) if len(symbols) == 1 else None,
            'referenced_invoice_date': next(iter(dates)) if len(dates) == 1 else None,
            'reference_candidates': {'invoice_number': sorted(numbers), 'invoice_symbol': sorted(symbols), 'invoice_date': sorted(dates)},
            'descriptions': descriptions, 'old_tax_codes': sorted(old_tax_codes),
            'declared_non_financial': non_financial, 'requires_review': kind != 'regular'}


def non_financial_adjustment(fields, rows, context):
    semantics = (context or {}).get('document_semantics', {})
    if (not semantics.get('declared_non_financial') or (context or {}).get('coverage_incomplete')
            or (context or {}).get('document_semantics_error') or (context or {}).get('error_type')):
        return False
    values = [fields.get(key) for key in ('subtotal', 'vat_amount', 'total_amount')]
    values.extend(row.get(key) for row in rows for key in ('unit_price', 'amount'))
    adjustments = {'discount', 'fee', 'taxable_fee', 'non_taxable_fee'}
    for observation in (context or {}).get('observations', []):
        if observation.get('scope') == 'page' or observation.get('role') == 'vat_rate':
            continue
        if observation.get('role') in adjustments and observation.get('value') is None:
            return False  # Unresolved actual adjustment, not an absent VAT column.
        values.append(observation.get('value'))
    values.extend(group.get(key) for group in (context or {}).get('tax_groups', []) for key in ('base', 'tax'))
    for observation in (context or {}).get('layout_observations', []):
        if observation.get('role') in ('discount', 'surcharge', 'discount_amount'):
            if not observation.get('observed_amounts'):
                return False
            values.extend(observation['observed_amounts'])
    return all(value is None or decimal(value) == Decimal('0') for value in values)


def financial_heading(value):
    """A financial section label, not a merchant-name substring."""
    text = folded(value).strip(' :;|')
    if text.startswith('(') and text.endswith(')'):
        text = text[1:-1].strip()
    return bool(re.fullmatch(
        r'(?:(?:tong hop|bang tong hop|chi tiet|thong tin|bao cao)\s+(?:thanh toan|tien hang|tien thue|thue|chi phi|cong no)|'
        r'(?:payment|financial|tax|invoice|expense)\s+(?:summary|totals|details)|'
        r'(?:summary|details)\s+of\s+(?:payment|tax|charges))(?:\s*\([^)]*\))?', text))


def amount_in_words(value):
    """Recognize a printed money phrase, without converting it to an amount.

    The value often occupies a different OCR row from its label. Match number
    grammar rather than isolated words such as 'Một' or 'Đồng' in real names.
    A numeric suffix also disqualifies a name contaminated by a footer.
    """
    text = folded(value)
    if re.search(r'\b(?:so tien (?:viet )?bang chu|(?:tien )?bang chu|'
                 r'(?:amount|total)(?: written)? in words|in words)\b', text):
        return True
    tokens = re.findall(r'[a-z]+', text)
    vn_numbers = set('khong mot hai ba bon nam sau bay tam chin muoi tram nghin ngan trieu ty ti linh le lam tu phay am'.split())
    en_numbers = set('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion trillion and point minus'.split())
    vn_currency = set('dong chan xu hao vnd vndong vn do la my'.split())
    en_currency = set('dong vnd dollar dollars cent cents pound pounds euro euros only'.split())
    scales = {'muoi', 'tram', 'nghin', 'ngan', 'trieu', 'ty', 'ti', 'hundred', 'thousand', 'million', 'billion', 'trillion'}
    for numbers, currency in ((vn_numbers, vn_currency), (en_numbers, en_currency)):
        # Look only at the trailing grammatical phrase, in linear time.
        start = len(tokens)
        while start and tokens[start - 1] in numbers | currency:
            start -= 1
        phrase = tokens[start:]
        if (len(phrase) >= 2 and any(token in numbers - {'and', 'point', 'minus', 'am', 'phay'} for token in phrase)
                and (any(token in currency - {'chan', 'only', 'vn', 'my'} for token in phrase)
                     or (len(phrase) >= 3 and any(token in scales for token in phrase)))):
            return True
    return False


def party_value_kind(value):
    """Shared semantic veto, never a score that promotes a value to a party."""
    if not isinstance(value, str) or not value.strip():
        return 'metadata'
    text = folded(value).strip(' :;.,()|')
    if party_section_role(value):
        return 'document_heading'
    # Document-purpose captions are not legal names. Anchor the statement,
    # rather than banning words such as "data" inside an actual company name.
    if re.match(r'^(?:(?:du lieu|tai lieu|chung tu|hoa don)(?: mau| gia lap)?\s+'
                r'(?:chi\s+)?(?:dung|danh|phuc vu)(?:\s+rieng)?\s+(?:de|cho)\s+(?:kiem tra|thu nghiem|mo phong)|'
                r'(?:sample|synthetic|test|demo)\s+(?:data|document|invoice)'
                r'(?:\s+only|\s+(?:for|used for)\s+(?:testing|evaluation|demonstration)|$)|'
                r'(?:data|document|invoice)\s+(?:for|used for)\s+(?:testing|evaluation|demonstration))\b', text):
        return 'document_notice'
    if amount_in_words(value):
        return 'amount_in_words'
    if correction_statement(value) or REFERENCE_ANCHOR.search(text):
        return 'document_relationship'
    if financial_heading(value):
        return 'financial_heading'
    if re.match(r'^(?:nguoi dai dien(?: theo phap luat)?|dai dien ben (?:mua|ban)|legal representative|authorized representative)\s*(?::.*)?$',text):
        return 'metadata'
    if re.fullmatch(r'(?:hoa don(?: gia tri gia tang| ban hang| dien tu)?|vat invoice|tax invoice|'
                    r'invoice|receipt|bill|phieu (?:thu|chi|thanh toan)|trang\s+\d+(?:\s*/\s*\d+)?)', text):
        return 'document_heading'
    # Classify complete metadata labels, not arbitrary words inside a legal
    # name (e.g. a name beginning with "Tổng công ty" is still a name).
    metadata = r'(?:so tien (?:viet )?bang chu|amount (?:written )?in words|in words|payment terms|terms (?:and|of)|dieu (?:khoan|kien)|ghi chu|notes?|phuong thuc thanh toan|hinh thuc thanh toan|bank account|tai khoan|(?:ten )?ngan hang|bank(?: name)?|dia chi|address|dien thoai|phone|tel|email|ma so thue|mst|tax (?:id|code))'
    allowed = bool(len(text) >= 2 and re.search(r'[^\W\d_]', text)
        and not re.match(r'^(?:da ky dien tu|chu ky|digitally signed|ky ghi ro ho ten)\b', text)
        and not re.fullmatch(metadata, text)
        and not re.fullmatch(r'(?:' + SELLER_NAME_LABEL + r'|' + BUYER_NAME_LABEL + r')', text)
        and not re.search(r'\b(?:' + SELLER_NAME_LABEL + r'|' + BUYER_NAME_LABEL + r')\s*[:：]', text)
        and not re.search(r'\b' + metadata + r'\s*[:：]', text)
        and not re.match(r'^(?:so tien (?:viet )?bang chu|amount (?:written )?in words|in words|payment terms|dieu khoan|ghi chu|digitally signed)\b', text)
        and not re.match(r'^(?:tong (?:tien|cong)|cong tien|tien thue|thue suat|vat|subtotal|total|payment|thanh toan)\s*[:：]?\s*[\d.,%]', text)
        and not re.match(r'^notes?\s*[:：]', text)
        and not re.fullmatch(r'(?:nguoi (?:mua|ban)(?: hang)?|seller|supplier|buyer|customer|'
                             r'ky|ho ten|signature|director|giam doc|ke toan truong)', text)
        and not re.search(r'\b(?:nguoi (?:mua|ban)(?: hang)?|seller|supplier|buyer|customer|'
                          r'don vi (?:mua|ban)(?: hang)?|dia chi|address|ma so thue|mst)\s*[:：]', text))
    return 'name_candidate' if allowed else 'metadata'


def party_name_allowed(value):
    return party_value_kind(value) == 'name_candidate'


def item_description_boundary(value):
    """Recognize structural rows, independently of merchant/product names."""
    text = folded(value).strip(' |')
    if amount_in_words(value) or financial_heading(value) or re.match(
            r'^(?:(?:chi tiet|danh muc|bang)\s+(?:hang hoa|san pham|dich vu)|'
            r'(?:bang hang hoa|danh sach hang)\b|(?:table|list) of (?:goods|items|services))', text):
        return True
    if re.match(r'^(?:tong tien|tien thue|thue vat|vat)\b', text) and re.search(
            r'\b(?:chi tinh|toan (?:bo )?hoa don|trang (?:cuoi|sau)|cuoi hoa don|final page|entire invoice)\b', text):
        return True
    if re.match(r'^(?:ghi chu|chu thich|luu y|so tien (?:viet )?bang chu|amount in words|chu ky|digitally signed|dieu khoan|terms and conditions)\b', text):
        return True
    if re.match(r'^(?:page|trang)\s+\d+\b', text) or re.match(r'^(?:notes?|remarks?)\s*(?:[:：]|$)', text):
        return True
    if re.match(r'^(?:cong tien hang|tong (?:tien|cong|thanh toan)|subtotal|grand total|total payable|amount due|tien thue|thue suat|vat|chiet khau|giam gia|discount|phu phi|phu thu)\s*[:：]?\s*(?:[\d.,%()+−-]|$)', text):
        return True
    headers = (r'\b(?:ten hang(?: hoa)?|dien giai|description|goods|product|item name)\b',
               r'\b(?:don vi tinh|dvt|unit)\b', r'\b(?:so luong|quantity|qty)\b',
               r'\b(?:don gia|unit price)\b', r'\b(?:thanh tien|line total|amount)\b')
    return (sum(bool(re.search(pattern, text)) for pattern in headers) >= 2
            or any(re.fullmatch(pattern, text) for pattern in headers)
            or bool(re.fullmatch(r'(?:stt|no\.?|vnd|vnđ|usd|\(?[1-9]\)?(?:\s+\(?[1-9]\)?){2,})', text)))


LABELS = (
    ('taxable_base', r'(?:(?:tong|cong) )?(?:tien(?: hang)?|gia(?: tri)?|doanh so) (?:lam can cu )?tinh thue|(?:tong )?tien hang chiu thue|taxable (?:amount|base)|tax base'),
    ('gross', r'(?:tong )?tien hang truoc (?:chiet khau|giam gia)|subtotal before discount|gross subtotal'),
    ('net', r'(?:tong )?tien (?:hang )?sau (?:chiet khau|giam gia)|net subtotal|subtotal after discount'),
    ('subtotal', r'cong tien hang|tong tien hang|tien truoc thue|tam tinh|total before tax|subtotal|sub total'),
    ('discount', r'(?:tong )?(?:tien )?(?:chiet khau|giam gia)(?: (?:toan )?hoa don)?|(?:invoice |total |order )?discount'),
    ('non_taxable_fee', r'(?:phu phi|phu thu)(?: dich vu)? khong chiu thue|non[ -]taxable (?:fee|surcharge)|tax exempt (?:fee|surcharge)'),
    ('taxable_fee', r'(?:phu phi|phu thu)(?: dich vu)? chiu thue|taxable (?:fee|surcharge)'),
    ('fee', r'phu phi(?: dich vu)?|phu thu(?: dich vu)?|surcharge|service charge'),
    ('vat_rate', r'thue suat(?: gtgt| vat)?|vat rate|tax rate'),
    ('vat', r'tong tien thue(?: gtgt| vat)?|tien thue(?: gtgt| vat)?|thue (?:gtgt|vat)|vat amount|tax amount|total (?:vat|tax)'),
    ('payable', r'tong (?:cong )?(?:tien )?(?:phai )?thanh toan|tong tien phai tra|grand total|amount due|total payable|total amount'),
)
LABEL = re.compile(r'(?<!\w)(?:' + '|'.join('(?P<' + key + '>' + pattern + ')' for key, pattern in LABELS) + r')(?!\w)')
PAGE_FINANCIAL_SUMMARY = re.compile(
    r'\b(?:page\s+(?:sub\s*total|subtotal|total)|(?:sub\s*total|subtotal|total)\s+(?:for\s+)?(?:this\s+)?page|'
    r'(?:cong|tong)(?:\s+cong)?(?:\s+tien)?(?:\s+hang)?\s+(?:cua\s+)?trang|'
    r'carried\s+forward|brought\s+forward|running\s+total|chuyen\s+(?:sang|tu)\s+(?:trang|page))\b|'
    r'^(?:tong(?: tien)?\s+)?(?:luy\s+ke|cong\s+don)\b')


def decimal(value):
    try:
        number = Decimal(str(value)) if value is not None else None
        return number if number is not None and number.is_finite() else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def amount_literal(text, parse_money):
    """Separate one printed percentage from one printed monetary literal."""
    amount = parse_money(text) if text else None
    if amount is not None:
        return amount, None
    rates = list(re.finditer(r'\d{1,3}(?:[.,]\d+)?\s*%', text))
    if len(rates) != 1:
        return None, None
    printed = rates[0]
    remainder = (text[:printed.start()] + text[printed.end():]).strip(' :;|=()')
    amount = parse_money(remainder) if remainder else None
    rate = decimal(printed[0].rstrip('%').strip().replace(',', '.'))
    return (amount, rate) if amount is not None else (None, None)


def _source_pages(raw_text, evidence):
    """Recover original page boundaries from saved boxes, not concatenated text.

    This reads existing evidence only. No second OCR pass or cross-page
    geometry is introduced, and a failed page is not silently renumbered.
    """
    pages = []
    for page in evidence.get('pages', []):
        if isinstance(page.get('raw_text'), str) and page['raw_text'].strip():
            pages.append((page.get('page'), page['raw_text']))
            continue
        boxes = [box for box in page.get('boxes', []) if box.get('polygon') and box.get('text')]
        if not boxes:
            if 'raw_text' in page:
                pages.append((page.get('page'), page.get('raw_text') or ''))
            continue
        height = max(1, median(max(y for _x, y in box['polygon']) - min(y for _x, y in box['polygon']) for box in boxes))
        bands = []
        for box in sorted(boxes, key=lambda box: (sum(y for _x, y in box['polygon']) / len(box['polygon']), min(x for x, _y in box['polygon']))):
            y = sum(y for _x, y in box['polygon']) / len(box['polygon'])
            if not bands or y - bands[-1][0] > .5 * height:
                bands.append((y, []))
            bands[-1][1].append(box)
        lines = []
        for _y, band in bands:
            parts, right = [], None
            for box in sorted(band, key=lambda box: min(x for x, _y in box['polygon'])):
                left = min(x for x, _y in box['polygon'])
                separator = '\t' if right is not None and left - right > 1.5 * height else ' '
                parts.append((separator if parts else '') + box['text'])
                right = max(x for x, _y in box['polygon'])
            lines.append(''.join(parts))
        pages.append((page.get('page'), '\n'.join(lines)))
    if pages:
        return pages
    parts = (raw_text or '').split('\f')
    return [(n + 1 if len(parts) > 1 or len(evidence.get('pages', [])) <= 1 else None, text)
            for n, text in enumerate(parts)]


def observe(raw_text, parse_money, evidence=None):
    """Keep labelled literals, rates, scope and page positions in private JSON."""
    evidence = evidence or {}
    pages = _source_pages(raw_text, evidence)
    observations, groups = [], []
    for page, text in pages:
        lines = text.splitlines()
        # Normalize the roles of short sales-bill summary labels only when the
        # printed document title and ordered gross/discount/payable rows support them.
        # The original recognized text is retained in the evidence and raw_text.
        if any(re.fullmatch(r'hoa don ban hang|hoa don ban le|phieu ban hang', folded(line).strip(' :|.-')) for line in lines):
            def rows(pattern):
                return [i for i, line in enumerate(lines) if (m := re.fullmatch('(?:' + pattern + r')\s*[:：]?\s*(.+)', folded(line).strip(' |')))
                        and parse_money(m[1]) is not None]
            gross, discount, payable = rows(r'tong cong'), rows(r'giam|giam gia|chiet khau'), rows(r'thanh toan|tong thanh toan|tong tien thanh toan')
            if len(gross) == len(discount) == len(payable) == 1 and gross[0] < discount[0] < payable[0]:
                aliases = {gross[0]: (r'^tong cong', 'tong tien hang truoc giam gia'),
                           discount[0]: (r'^giam(?: gia)?|^chiet khau', 'giam gia hoa don'),
                           payable[0]: (r'^(?:tong tien |tong )?thanh toan', 'tong thanh toan')}
            else:
                aliases = {i: (r'^(?:tong tien |tong )?thanh toan', 'tong thanh toan') for i in payable}
        else:
            aliases = {}
        def role_text(i, line):
            plain = folded(line)
            return re.sub(*aliases[i], plain, count=1) if i in aliases else plain
        related_lines = reference_line_indices(lines)
        payable_lines = [n for n, line in enumerate(lines) if any(m.lastgroup == 'payable'
            and parse_money(role_text(n, line)[m.end():].strip(' :;|=')) is not None for m in LABEL.finditer(role_text(n, line)))]
        last_subtotal = None
        tax_columns = None
        tax_section = None
        for n, line in enumerate(lines):
            if n in related_lines:
                continue  # Original invoice values are not current financials.
            plain = role_text(n, line)
            cells = [cell.strip() for cell in re.split(r'\s*\|\s*|\t+|\s{2,}', line.strip().strip('|'))]
            header = {}
            for column, cell in enumerate(cells):
                for role, pattern in LABELS:
                    if role in ('vat_rate', 'taxable_base', 'subtotal', 'vat') and re.fullmatch(pattern, folded(cell)):
                        header['taxable_base' if role == 'subtotal' else role] = column
            if {'vat_rate', 'taxable_base', 'vat'}.issubset(header) and len(set(header.values())) == len(header):
                tax_columns = header
                tax_section = n
                continue
            if tax_columns and len(cells) > max(tax_columns.values()):
                rate_cell = cells[tax_columns['vat_rate']].rstrip('%').strip()
                r = decimal(rate_cell.replace(',', '.')) if re.fullmatch(r'\d{1,3}(?:[.,]\d+)?', rate_cell) else None
                b, t = (parse_money(cells[tax_columns[key]]) for key in ('taxable_base', 'vat'))
                if r is not None and 0 <= r <= 100 and b is not None and t is not None:
                    groups.append({'base': str(b), 'tax': str(t), 'rate': str(r), 'page': page, 'line': n,
                                   'section': tax_section, 'raw_text': line})
                    continue
                tax_columns = None
            matches = list(LABEL.finditer(plain))
            entries = []
            for index, match in enumerate(matches):
                role = match.lastgroup
                tail = plain[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(plain)].strip(' :;|=')
                rate = None
                percentage = re.fullmatch(r'([+-]?\d+(?:[.,]\d+)?)\s*%', tail)
                if role == 'vat_rate' and re.fullmatch(r'\d{1,3}(?:[.,]\d+)?\s*%?', tail):
                    rate = decimal(tail.rstrip('%').strip().replace(',', '.'))
                    value = None
                elif percentage:
                    rate = decimal(percentage[1].replace(',', '.'))
                    value = None
                else:
                    value = parse_money(tail) if tail else None
                    if role in ('discount', 'fee', 'taxable_fee', 'non_taxable_fee', 'vat'):
                        value, rate = amount_literal(tail, parse_money)
                if (role in ('discount', 'fee', 'taxable_fee', 'non_taxable_fee')
                        and value is None and rate is None and tail
                        and not re.fullmatch(r'[\d\s.,%():;|+−-]*(?:vnd|dong|d|₫)?', tail)):
                    continue  # A word inside a company/product name is not an adjustment.
                scope = 'unspecified'
                if role not in ('discount', 'fee', 'taxable_fee', 'non_taxable_fee'):
                    scope = 'summary'
                elif ('hoa don' in match[0] or 'invoice' in match[0] or 'total' in match[0] or match[0].startswith('tong ')
                      or (last_subtotal is not None and last_subtotal < n and any(end > n for end in payable_lines))):
                    scope = 'document'
                entry = {'role': role, 'value': str(value) if value is not None else None,
                         'rate': str(rate) if rate is not None else None, 'scope': scope,
                         'page': page, 'line': n, 'raw_text': line, 'source': 'recognized_text'}
                if PAGE_FINANCIAL_SUMMARY.search(plain):
                    entry['scope'] = 'page'
                observations.append(entry)
                entries.append(entry)
            # Only a printed amount establishes a subtotal anchor. Column
            # headings and empty labels cannot confer invoice-wide scope on a
            # later line discount. Inline summary cells retain their order.
            if any(entry['role'] in ('subtotal', 'gross', 'net', 'taxable_base') and entry['scope'] != 'page'
                   and entry['value'] is not None for entry in entries):
                for index, entry in enumerate(entries):
                    prior_base = any(prior['role'] in ('subtotal', 'gross', 'net', 'taxable_base') and prior['scope'] != 'page'
                                     and prior['value'] is not None for prior in entries[:index])
                    if entry['scope'] == 'unspecified' and prior_base and any(end >= n for end in payable_lines):
                        entry['scope'] = 'document'
                last_subtotal = n
            grouped = {role: [entry for entry in entries if entry['role'] == role and entry['value'] is not None]
                       for role in ('taxable_base', 'vat')}
            rates = [entry['rate'] for entry in entries if entry['role'] in ('vat_rate', 'vat') and entry['rate'] is not None]
            if len(grouped['taxable_base']) == len(grouped['vat']) == len(rates) == 1:
                groups.append({'base': grouped['taxable_base'][0]['value'], 'tax': grouped['vat'][0]['value'],
                               'rate': rates[0], 'page': page, 'line': n, 'section': 'inline', 'raw_text': line})
    # Layout observations are retained without adding them again to money sums.
    extra = evidence.get('final_financial_observations', evidence.get('financial_adjustments', []))
    summary_pages = [entry['page'] for entry in observations if entry['role'] == 'payable'
                     and entry['scope'] != 'page' and entry['value'] is not None and type(entry['page']) is int]
    summary_page = max(summary_pages, default=None)
    active = [entry for entry in observations if entry['scope'] != 'page'
              and (summary_page is None or entry['page'] == summary_page)]
    return {'observations': observations, 'tax_groups': groups, 'layout_observations': extra,
            'document_semantics': document_semantics(raw_text, evidence),
            'summary_page': summary_page,
            'adjustment_observed': bool(any(entry['role'] in ('discount', 'fee', 'taxable_fee', 'non_taxable_fee') for entry in active)
                or any(entry.get('role') in ('discount', 'surcharge', 'discount_amount') for entry in extra if isinstance(entry, dict))
                or any(row.get('discount_observations') for row in evidence.get('recognized_items', []))),
            'semantics': 'Printed evidence only; no public financial columns or inferred invoice values'}


def arithmetic_rules(fields, rows, context):
    """Use one evidence-selected interpretation, never search numbers for a fit."""
    context = context or {}
    # Validate each supplied numeric cell even when other cells are absent.
    # A missing value is not zero and does not excuse an invalid printed value.
    invalid_fields = [key for key in ('subtotal', 'vat_amount', 'total_amount', 'vat_rate')
                      if fields.get(key) is not None and (decimal(fields[key]) is None
                          or decimal(fields[key]) < 0)]
    invalid_rows = []
    for index, row in enumerate(rows, 1):
        for key in ('quantity', 'unit_price', 'amount'):
            value = row.get(key)
            if value is not None and (decimal(value) is None or decimal(value) < 0):
                invalid_rows.append(index)
                break
    numeric_results = []
    if invalid_fields:
        labels = {'subtotal': 'tiền trước thuế', 'vat_amount': 'tiền VAT',
                  'total_amount': 'tổng thanh toán', 'vat_rate': 'thuế suất'}
        numeric_results.append(('FINANCIAL-NUMERIC', False,
                                'Số liệu tài chính âm hoặc không hợp lệ: '
                                + ', '.join(labels[key] for key in invalid_fields)
                                + '; giữ số nguồn và cần đối chiếu.'))
    if invalid_rows:
        numeric_results.append(('ROW-NUMERIC', False,
                                'Số liệu dòng hàng không hợp lệ tại dòng: '
                                + ', '.join(map(str, invalid_rows))))
    if not numeric_results and non_financial_adjustment(fields, rows, context):
        return [('NON-FINANCIAL-ADJUSTMENT', True,
                 'Chỉ điều chỉnh thông tin phi tài chính theo nội dung nguồn; các cột tiền/VAT không xuất hiện không phải lỗi số học, không tự điền 0.')]
    summary_page = context.get('summary_page')
    obs = [entry for entry in context.get('observations', []) if entry.get('scope') != 'page'
           and (summary_page is None or entry.get('page') == summary_page or entry.get('source') == 'xml_element')]
    adjustment_seen = bool(context.get('adjustment_observed') or any(
        entry.get('role') in ('discount', 'fee', 'taxable_fee', 'non_taxable_fee') for entry in obs))
    currency = str(fields.get('currency') or 'VND').upper()
    epsilon = Decimal('2') if currency in ('VND','JPY','KRW') else Decimal('0.02')
    explanation = f' (sai số làm tròn tuyệt đối phải nhỏ hơn {epsilon} {currency}; không sửa số nguồn)'
    get = lambda key: None if key in invalid_fields else decimal(fields.get(key))
    subtotal, vat, total, rate = (get(key) for key in ('subtotal', 'vat_amount', 'total_amount', 'vat_rate'))

    def unique(roles, *, document=False):
        grouped_positions = {(group.get('page'), group.get('line')) for group in context.get('tax_groups', [])}
        entries = [entry for entry in obs if entry['role'] in roles and (not document or entry['scope'] == 'document')
                   and (entry.get('value') is not None or entry['role'] in ('discount', 'fee', 'taxable_fee', 'non_taxable_fee'))
                   and not (roles == ('taxable_base',) and (entry.get('page'), entry.get('line')) in grouped_positions)]
        values = {decimal(entry.get('value')) for entry in entries}
        return (next(iter(values)) if len(values) == 1 and None not in values else None), entries

    discount, discounts = unique(('discount',), document=True)
    taxed_fee, taxed_fees = unique(('taxable_fee',), document=True)
    untaxed_fee, untaxed_fees = unique(('non_taxable_fee',), document=True)
    base, bases = unique(('taxable_base',))
    gross, grosses = unique(('gross',))
    net, nets = unique(('net',))
    unresolved = any(entry['role'] in ('discount', 'fee', 'taxable_fee', 'non_taxable_fee')
                     and (entry['scope'] != 'document' or entry['value'] is None or entry['role'] == 'fee') for entry in obs)
    unresolved |= any(entries and value is None for value, entries in ((discount, discounts), (taxed_fee, taxed_fees), (untaxed_fee, untaxed_fees), (base, bases)))
    unresolved |= any(entries and value is None for value, entries in ((gross, grosses), (net, nets)))
    if discount is not None:
        discount = abs(discount)  # A labelled deduction can be printed negative.
    if any(value is not None and value < 0 for value in (taxed_fee, untaxed_fee, base)):
        unresolved = True
    matching = [entry for entry in obs if entry['role'] in ('subtotal', 'gross', 'net', 'taxable_base')
                and subtotal is not None and decimal(entry.get('value')) == subtotal]
    interpretations = set()
    for entry in matching:
        if entry['role'] == 'gross':
            interpretations.add('gross')
        elif entry['role'] in ('net', 'taxable_base'):
            interpretations.add('net')
        else:
            relative = [other for other in (*discounts, *taxed_fees, *untaxed_fees) if other['page'] == entry['page']
                        and isinstance(other.get('line'), int) and isinstance(entry.get('line'), int)]
            if relative and all(other['line'] > entry['line'] for other in relative):
                interpretations.add('gross')
    # Explicit before/after-discount labels outrank a generic subtotal alias
    # with the same amount. Do not choose an interpretation because it makes
    # the numbers happen to balance.
    explicit = {('gross' if entry['role'] == 'gross' else 'net') for entry in matching
                if entry['role'] in ('gross', 'net', 'taxable_base')}
    if explicit:
        interpretations = explicit
    basis = next(iter(interpretations)) if len(interpretations) == 1 else None
    if not adjustment_seen:
        basis = 'gross'
    if adjustment_seen and not discounts and not taxed_fees and not untaxed_fees:
        unresolved = True
    if adjustment_seen and basis is None:
        unresolved = True
    d = discount if discount is not None else Decimal('0')
    ft = taxed_fee if taxed_fee is not None else Decimal('0')
    fn = untaxed_fee if untaxed_fee is not None else Decimal('0')
    # Unspecified fee inclusion cannot be resolved from a single subtotal.
    if basis == 'net' and (taxed_fees or untaxed_fees) and base is None:
        unresolved = True
    computed_base = None if subtotal is None else subtotal - d + ft if basis == 'gross' else subtotal
    selected_base = base if base is not None else computed_base
    results = list(numeric_results)
    if context.get('error_type'):
        results.append(('FINANCIAL-CONTEXT', False,
                        'Chưa phân tích được bằng chứng tài chính; các phép tính dưới đây không xác nhận đầy đủ phạm vi hóa đơn.'))
    before_adjustment = gross if gross is not None else subtotal if basis == 'gross' else None
    if before_adjustment is not None and (base is not None or net is not None) and not unresolved:
        compared_base = base if base is not None else net
        results.append(('TAX-BASE', abs(compared_base - (before_adjustment - d + ft)) < epsilon,
                        'Cơ sở tính thuế in trên hóa đơn không khớp tiền hàng - chiết khấu + phụ phí chịu thuế' + explanation))
    if adjustment_seen:
        results.append(('ADJUSTMENT-SCOPE', not unresolved,
                        'Chưa xác định đầy đủ phạm vi chiết khấu/phụ phí/cơ sở tính thuế; giữ bằng chứng và cần xem xét, không mặc định VAT trên tiền hàng gộp.'))
    discount_rates = {decimal(entry['rate']) for entry in discounts if entry.get('rate') is not None}
    if discount_rates and before_adjustment is not None and discount is not None:
        good = len(discount_rates) == 1 and not unresolved
        if good:
            observed_rate = next(iter(discount_rates))
            good = observed_rate is not None and 0 <= observed_rate <= 100 and abs(before_adjustment * observed_rate / 100 - discount) < epsilon
        results.append(('DISCOUNT-ARITH', good, 'Chiết khấu in trên chứng từ chưa khớp tỷ lệ và cơ sở tiền hàng trước chiết khấu' + explanation))
    if not unresolved and selected_base is not None and selected_base >= 0 and vat is not None and total is not None:
        okay = abs(selected_base + vat + fn - total) < epsilon
        results.append(('ARITH', okay, 'Tổng thanh toán lệch cơ sở sau điều chỉnh + VAT + phụ phí không chịu thuế' + explanation))
    else:
        results.append(('ARITH-EVIDENCE', False,
                        'Chưa đủ tiền trước thuế/cơ sở tính thuế, VAT, tổng thanh toán hoặc phạm vi điều chỉnh để đối chiếu tổng tiền; không mặc định khoản thiếu bằng 0.'))
    groups = [group for group in context.get('tax_groups', []) if not PAGE_FINANCIAL_SUMMARY.search(folded(group.get('raw_text', '')))
              and (summary_page is None or group.get('page') == summary_page)]
    if groups:
        sections = {}
        for group in groups:
            sections.setdefault((group.get('page'), group.get('section', 'legacy')), []).append(group)
        section_checks = []
        group_evidence_missing = False
        for section in sections.values():
            checks, positions = [], set()
            group_bases, group_taxes = Decimal('0'), Decimal('0')
            for group in section:
                position = (group.get('page'), group.get('line'))
                b, t, r = (decimal(group.get(key)) for key in ('base', 'tax', 'rate'))
                supported = (position not in positions and b is not None and t is not None
                             and r in (Decimal('0'), Decimal('5'), Decimal('8'), Decimal('10'))
                             and b >= 0 and t >= 0)
                if supported:
                    checks.append(abs(b * r / 100 - t) < epsilon)
                else:
                    group_evidence_missing = True
                positions.add(position)
                if b is not None and t is not None:
                    group_bases += b
                    group_taxes += t
            # A broken/missing group must not suppress arithmetic conflicts in
            # the other fully printed groups, or be treated as a zero group.
            section_checks.extend(checks)
            if len(checks) == len(section):
                if vat is not None:
                    section_checks.append(abs(group_taxes - vat) < epsilon)
                else:
                    group_evidence_missing = True
                if selected_base is not None and (base is not None or not unresolved):
                    section_checks.append(abs(group_bases - selected_base) < epsilon)
                else:
                    group_evidence_missing = True
        if section_checks:
            results.append(('VAT-ARITH', all(section_checks), 'Nhóm VAT lệch cơ sở × thuế suất hoặc tổng cơ sở/tiền thuế; không cộng lặp giữa các bảng' + explanation))
        if group_evidence_missing:
            results.append(('VAT-EVIDENCE', False,
                            'Chưa đủ bằng chứng để đối chiếu toàn bộ nhóm VAT với tổng cuối hóa đơn; không suy ra nhóm hoặc giá trị thiếu.'))
    elif context.get('tax_groups'):
        results.append(('VAT-EVIDENCE', False,
                        'Có nhóm VAT trên trang khác nhưng chưa xác định được phạm vi đối chiếu với tổng cuối hóa đơn; giữ bằng chứng và cần xem xét.'))
    elif (base is not None or not unresolved) and selected_base is not None and selected_base >= 0 and vat is not None and rate is not None:
        okay = rate in (Decimal('0'), Decimal('5'), Decimal('8'), Decimal('10')) and abs(selected_base * rate / 100 - vat) < epsilon
        results.append(('VAT-ARITH', okay, 'VAT lệch cơ sở tính thuế sau điều chỉnh × thuế suất' + explanation))
    elif vat is not None or rate is not None or any(entry['role'] in ('vat', 'vat_rate', 'taxable_base') for entry in obs):
        results.append(('VAT-EVIDENCE', False,
                        'Có thông tin VAT nhưng thiếu cơ sở, thuế suất, tiền thuế hoặc bảng phân nhóm đủ bằng chứng để kiểm tra; không coi là đã đối chiếu.'))
    amounts = [decimal(row.get('amount')) for row in rows]
    item_base = gross if gross is not None else subtotal if basis == 'gross' else subtotal + d - ft if subtotal is not None and basis == 'net' else None
    item_scope_known = gross is not None or not unresolved
    complete_items = (bool(rows) and item_base is not None and item_base >= 0 and item_scope_known
                      and not invalid_rows and 'subtotal' not in invalid_fields
                      and all(amount is not None and amount >= 0 for amount in amounts))
    okay = complete_items and abs(sum(amounts, Decimal('0')) - item_base) < epsilon
    item_message = ('Tổng thành tiền các dòng lệch tiền hàng theo phạm vi đã xác định'
                    if complete_items else 'Chưa đủ dòng hàng hoặc bằng chứng phạm vi trước/sau chiết khấu và phụ phí để đối chiếu tổng dòng hàng')
    results.append(('ITEM-SUM', okay, item_message + explanation))
    row_conflicts = []
    invalid_row_set = set(invalid_rows)
    for index, row in enumerate(rows, 1):
        literals = [row.get(key) for key in ('quantity', 'unit_price', 'amount')]
        if index in invalid_row_set or any(value is None for value in literals):
            continue  # Check multiplication only when all three valid cells exist.
        q, p, a = map(decimal, literals)
        if abs(q * p - a) >= epsilon:
            row_conflicts.append(index)
    if row_conflicts:
        results.append(('ROW-ARITH', False,
                        'Số lượng × đơn giá lệch thành tiền tại dòng: ' + ', '.join(map(str, row_conflicts))
                        + '; cần đối chiếu chiết khấu/phụ phí hoặc phạm vi thuế theo dòng, không tự sửa số nguồn' + explanation))
    return results


def xml_adjustments(context, root, parse_money):
    """Retain printed XML adjustments without assuming gross/net semantics."""
    for node in root.iter():
        tag = node.tag.rsplit('}', 1)[-1] if isinstance(node.tag, str) else ''
        if tag not in ('STCKhau', 'TTCKhau', 'TgTCKhau', 'TLCKhau'):
            continue
        literal = (node.text or '').strip()
        value = parse_money(literal) if tag != 'TLCKhau' else None
        context['observations'].append({'role': 'discount', 'value': str(value) if value is not None else None,
            'rate': literal if tag == 'TLCKhau' else None,
            'scope': 'document' if tag == 'TgTCKhau' else 'unspecified',
            'page': None, 'line': None, 'raw_text': '<' + tag + '>' + literal,
            'source': 'xml_element'})
        context['adjustment_observed'] = True
    return context
