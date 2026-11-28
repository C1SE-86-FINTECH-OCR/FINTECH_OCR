"""Explicit localhost development preview; does not issue G13 acceptance."""
from pathlib import Path
import argparse
import json
import os
import sys


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--enable-preview', action='store_true', help='Explicitly opt in to UNVERIFIED development use')
    cli.add_argument('--pipeline', choices=('current', 'hybrid_v8_final'), default='hybrid_v8_final')
    cli.add_argument('--port', type=int, default=8000)
    args = cli.parse_args()
    if not args.enable_preview:
        cli.error('Preview is disabled by default; --enable-preview is required')
    if not 1 <= args.port <= 65535:
        cli.error('Invalid listening port')

    backend = Path(__file__).resolve().parents[1]
    os.chdir(backend)
    sys.path.insert(0, str(backend))
    from dotenv import dotenv_values
    from sqlalchemy.engine import make_url
    config = dotenv_values(backend / '.env')
    url = make_url(os.environ.get('DATABASE_URL') or config['DATABASE_URL'])
    if url.get_backend_name() != 'postgresql' or url.host not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Preview requires existing local PostgreSQL configuration')
    # Keep the same isolated database/uploads as the existing Website runtime.
    # Only the child process environment changes; no .env or DB writes occur.
    url = url.set(database='fintech_ocr_rbac_test')
    uploads = (backend / 'uploads_rbac_test').resolve()
    if not uploads.is_dir():
        raise ValueError('Existing uploads_rbac_test directory is required')
    os.environ.update(
        DATABASE_URL=url.render_as_string(hide_password=False), UPLOAD_DIR=str(uploads),
        APP_ENV='development', OCR_PIPELINE='current', OCR_HYBRID_FALLBACK='true',
        OCR_LOCAL_PREVIEW_ENABLED='true', OCR_LOCAL_PREVIEW_PIPELINE=args.pipeline,
        OCR_LOCAL_PREVIEW_HOST='127.0.0.1',
    )
    # Gemini flags, references and SHA-256 permissions are NOT granted here.
    from app.core import settings
    from app.main import app
    import uvicorn
    print(json.dumps({
        'pid': os.getpid(), 'mode': 'UNVERIFIED / DEVELOPMENT PREVIEW',
        'app_env': settings.app_env, 'pipeline': settings.effective_ocr_pipeline,
        'fallback': settings.ocr_hybrid_fallback, 'database': url.database,
        'upload_dir': str(uploads), 'host': settings.ocr_local_preview_host,
        'port': args.port, 'gemini_requested': settings.gemini_enabled,
        'external_transfer_requested': settings.gemini_allow_external_transfer,
        'g13_acceptance': 'NOT_GRANTED',
    }, ensure_ascii=False), flush=True)
    uvicorn.run(app, host=settings.ocr_local_preview_host, port=args.port,
                workers=1, proxy_headers=False, forwarded_allow_ips='')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Configuration exceptions may contain credential-bearing URLs.
        print('Preview startup failed: ' + type(exc).__name__, file=sys.stderr, flush=True)
        sys.exit(1)
