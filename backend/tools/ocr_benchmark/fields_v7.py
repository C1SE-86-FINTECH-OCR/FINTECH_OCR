"""Printed party/financial scopes only. Missing is distinct from printed zero."""
import re
from . import pipeline_v4 as v4, pipeline_v5 as v5
from .table_v3 import row_evidence


def labelled_context(base,reads):
    fields=dict(base);observations={};findings=[]
    for read in reads:
        if read.tag.startswith(('table','v7-table','v7-supplier')):continue
        party='seller'
        for line in sorted(read.lines,key=lambda l:l.y):
            p=v4.plain(line.text)
            if re.search(r'nguoi mua|don vi mua|buyer|customer',p):party='buyer'
            elif re.search(r'don vi ban|nguoi ban|seller|supplier',p):party='seller'
            tax=re.search(r'\b(?:mst|ma so thue|tax code|tax id)\s*[:.;]?\s*(\d{10}(?:-?\d{3})?)\b',p)
            value=None;key=None
            if tax:key=party+'_tax_code';value=tax[1]
            else:
                name=re.search(r'^(?:ten\s*)?(?:don vi ban hang|don vi ban|nguoi ban|seller|supplier|don vi mua hang|don vi mua|nguoi mua hang|buyer|customer)\s*[:：]\s*(.+)',p)
                if name:
                    value=line.text[name.start(1):name.end(1)].strip()
                    key=party+'_name'
                    if v6_metadata(value):value=None
            if key and value is not None:
                observations.setdefault(key,[]).append({'value':value,'read':read.tag,'score':v5.line_conf(line),
                    'evidence':row_evidence(read.boxes,{'line':line.ids})['line']})
            # Capture money roles separately, never sum or subtract to invent a
            # field. The next-line fallback needs the label alone on its line.
            role=None
            if re.search(r'tien khach|khach (?:dua|tra)|tien mat|cash|tendered',p):role='cash_tendered'
            elif re.search(r'tien (?:thoi|thua|tra lai)|change',p):role='change'
            elif re.search(r'giam gia|chiet khau|discount',p):role='discount_amount'
            elif re.search(r'tong.*(?:thanh toan|phai tra)|grand total|amount due|total payable',p):role='total_amount'
            elif re.search(r'tien truoc thue|subtotal|tam tinh|cong tien hang',p):role='subtotal'
            elif re.search(r'tien thue|vat amount|tax amount',p):role='vat_amount'
            if role:
                nums=[n for n in v4.money_tokens(line) if not n.get('percent')]
                if nums:
                    amount=max(nums,key=lambda n:n['x'])
                    observations.setdefault(role,[]).append({'value':amount['value'],'read':read.tag,'score':v5.line_conf(line),
                        'label':line.text,'evidence':row_evidence(read.boxes,{'value':amount['ids']})['value']})
            if re.search(r'vat|thue suat|thue gtgt',p):
                rates=[n for n in v4.money_tokens(line) if n.get('percent')]
                for rate in rates:observations.setdefault('printed_vat_rates',[]).append({'value':rate['value'],'read':read.tag,
                    'evidence':row_evidence(read.boxes,{'value':rate['ids']})['value']})
    for key,values in observations.items():
        distinct={str(c['value']) for c in values}
        if len(distinct)>1:findings.append({'code':'V7_LABEL_VALUE_CONFLICT','field':key,'values':sorted(distinct)})
        # Do not overwrite existing financial choices or turn a cash/change
        # observation into total. Extra adjustment roles live only in evidence.
        if key not in ('seller_name','buyer_name','seller_tax_code','buyer_tax_code','subtotal','vat_amount','total_amount'):continue
        if fields.get(key) is not None:continue
        if len(distinct)==1 and len({c['read'] for c in values})>=2 and max(c['score'] for c in values)>=.8:
            fields[key]=values[0]['value']
    return fields,observations,findings


def v6_metadata(value):
    p=v4.plain(value)
    return bool(not value or re.search(r'ky dien tu|ky ten|ho ten|chu ky|dien thoai|tai khoan|signed',p))
