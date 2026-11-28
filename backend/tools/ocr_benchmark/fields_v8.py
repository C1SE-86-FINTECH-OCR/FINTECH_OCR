"""Explicit labels and provenance, including native PDF text without scores."""
import re
import unicodedata
from . import pipeline_v4 as v4, pipeline_v5 as v5
from .table_v3 import row_evidence

def labelled_fields(base,reads):
    fields=dict(base);observations={};warnings=[]
    for read in reads:
        party='seller'
        for line in sorted(read.lines,key=lambda l:l.y):
            plain=v4.plain(line.text)
            if re.search(r'nguoi mua|don vi mua|buyer|customer',plain):party='buyer'
            elif re.search(r'nguoi ban|don vi ban|seller|supplier',plain):party='seller'
            # A printed/signature timestamp is not an issue date.
            if re.search(r'ngay (?:in|ky)|printed|signed|transaction|so gd|ma giao dich|phone|dien thoai|tai khoan',plain):continue
            key=None;value=None
            if ':' in line.text:
                label,tail=line.text.split(':',1);label=v4.plain(label);tail=tail.strip()
                if re.fullmatch(r'(?:ten )?(?:don vi ban hang|don vi ban|nguoi ban|seller|supplier)',label):key='seller_name';value=tail
                elif re.fullmatch(r'(?:ten )?(?:don vi mua hang|don vi mua|nguoi mua hang|buyer|customer)',label):key='buyer_name';value=tail
                elif re.fullmatch(r'(?:ma so thue|mst|tax code|tax id)(?: nguoi (?:ban|mua))?',label):
                    key=('buyer' if 'mua' in label else party)+'_tax_code'
                    match=re.fullmatch(r'\d{10}(?:-?\d{3})?',tail);value=match[0] if match else None
                elif re.fullmatch(r'(?:ky hieu(?: hoa don)?|series|serial)',label):
                    key='invoice_symbol';value=tail if re.fullmatch(r'[A-Za-z0-9/-]{1,40}',tail) else None
                elif re.fullmatch(r'(?:so hoa don|so hd|so bill|so|invoice no\.?|invoice number|receipt no\.?)',label):
                    key='invoice_number';value=tail if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9/-]{2,49}',tail) and any(c.isdigit() for c in tail) else None
                elif re.fullmatch(r'(?:ngay(?: lap)?|date|issue date|invoice date)',label):key='invoice_date';value=v4.date_value(tail)
                elif re.fullmatch(r'(?:currency|tien te|loai tien|don vi tien te)',label):key='currency';value=tail.upper() if re.fullmatch(r'[A-Za-z]{3}',tail) else None
            if not key:
                match=re.search(r'\b(?:so hoa don|so hd|so|invoice no\.?|invoice number)\s*[:.]\s*([a-z0-9][a-z0-9/-]{2,49})\b',plain)
                if match and any(c.isdigit() for c in match[1]):key='invoice_number';value=match[1].upper()
            if not key or value is None:continue
            if key.endswith('_name') and re.search(r'ky ten|ho ten|ky dien tu|signed',v4.plain(value)):continue
            source='pdf-text' if read.transform.get('trusted_text_layer') else 'ocr'
            observations.setdefault(key,[]).append({'value':value,'read':read.tag,'source':source,'score':v5.line_conf(line),
                'evidence':row_evidence(read.boxes,{'source':line.ids})['source']})
        # Unlabelled retail headers may improve spelling/accents only with
        # direct OCR consensus and the same accent-folded baseline identity.
        for candidate in v5.seller_candidates(read):
            if candidate['score']<1.15:continue
            value=candidate['value']
            if base.get('seller_name') and v4.plain(value)!=v4.plain(base['seller_name']):continue
            observations.setdefault('seller_name',[]).append({**candidate,'source':'ocr','read':read.tag})
        if base.get('seller_name') is None:
            titles=[l.y for l in read.lines if v5.TYPE.search(v4.plain(l.text))]
            metadata=[l.y for l in read.lines if re.search(r'^(?:so (?:bill|hoa don|hd)|ngay|date|invoice no|receipt no)',v4.plain(l.text))]
            if titles and metadata:
                for line in read.lines:
                    p=v4.plain(line.text)
                    if not min(titles)<line.y<min(metadata) or v4.META.match(p) or v5.ADDRESS.match(p) or v5.TYPE.search(p):continue
                    if len(re.sub(r'[^a-z]','',p))<5 or v4.money_tokens(line):continue
                    observations.setdefault('seller_name',[]).append({'value':line.text,'read':read.tag,'source':'ocr','score':v5.line_conf(line),
                        'evidence':row_evidence(read.boxes,{'source':line.ids})['source']})
    for key,cs in observations.items():
        groups={}
        for c in cs:groups.setdefault(str(c['value']),[]).append(c)
        if len(groups)>1:warnings.append({'code':'V8_LABEL_CONFLICT','field':key,'values':list(groups)})
        native=[c for c in cs if c['source']=='pdf-text']
        if native and len({str(c['value']) for c in native})==1:
            winner=native[0]
        else:
            ranked=sorted(groups.values(),key=lambda g:(len({c['read'] for c in g}),max(c['score'] for c in g)),reverse=True)
            group=ranked[0];winner=max(group,key=lambda c:c['score'])
            if len({c['read'] for c in group})<2 or winner['score']<.8:continue
        if key=='seller_name' and fields.get(key) and not native:
            marks=lambda s:sum(bool(unicodedata.combining(c)) for c in unicodedata.normalize('NFD',s))+sum(c in 'đĐ' for c in s)
            if marks(winner['value'])<marks(fields[key]):
                warnings.append({'code':'V8_DIACRITICS_UNCERTAIN','field':key,'alternative':winner['value'],'retained':fields[key]});continue
        if fields.get(key) is None or native or (key in ('seller_name','invoice_number') and len({c['read'] for c in groups[str(winner['value'])]})>=2 and winner['score']>=.9):
            fields[key]=winner['value']
    return fields,observations,warnings
