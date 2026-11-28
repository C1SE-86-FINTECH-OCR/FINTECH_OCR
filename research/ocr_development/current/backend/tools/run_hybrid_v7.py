r"""Offline trial, no database/API imports, no model/network downloads.

From backend: .venv\Scripts\python.exe -m tools.run_hybrid_v7 FILE --output NEW.json
"""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from fastapi.encoders import jsonable_encoder
from tools.ocr_benchmark.hybrid_v7 import extract_hybrid


def main():
    parser=argparse.ArgumentParser(description='Experimental Hybrid V7 offline evidence; not acceptance')
    parser.add_argument('document',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--max-pages',type=int,default=12,choices=range(1,13))
    args=parser.parse_args()
    ext=args.document.suffix.lower().lstrip('.')
    if ext not in ('jpg','jpeg','png','pdf'):parser.error('Supported files: JPG/JPEG/PNG/PDF')
    if args.output.exists():parser.error('Output already exists; choose a new path to preserve evidence')
    if not 0<args.document.stat().st_size<=20*1024*1024:parser.error('File must be between 1 byte and 20 MB')
    data=args.document.read_bytes();start=perf_counter()
    fields,items,evidence=extract_hybrid(data,ext,args.max_pages)
    result={'experimental':True,'requires_review':True,'sha256':hashlib.sha256(data).hexdigest(),
            'elapsed_s':perf_counter()-start,'fields':fields,'items':items,'evidence':evidence}
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(jsonable_encoder(result),stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'output':str(args.output.resolve()),'items':len(items),'requires_review':True},ensure_ascii=False))


if __name__=='__main__':main()
