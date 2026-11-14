"""Non-destructive SQLite snapshot and local uploads backup."""
import hashlib, json, shutil, sqlite3
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / 'fintech_ocr.db'

def main():
    if not DB.is_file(): raise SystemExit(f'[STOP] Không thấy {DB}')
    destdir = BACKEND.parent.parent / 'Database_Backup' / ('snapshot_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    destdir.mkdir(parents=True, exist_ok=False)
    snapshot = destdir / 'fintech_ocr.db'
    with sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True) as source:
        with sqlite3.connect(snapshot) as dest: source.backup(dest)
    with sqlite3.connect(snapshot) as conn:
        integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
        fk_errors = conn.execute('PRAGMA foreign_key_check').fetchall()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
    if integrity != 'ok' or fk_errors:
        raise SystemExit(f'[STOP] Backup được lưu tại {destdir}, nhưng database có vấn đề: integrity={integrity}; FK errors={len(fk_errors)}')
    if (BACKEND / 'uploads').is_dir(): shutil.copytree(BACKEND / 'uploads', destdir / 'uploads')
    if (BACKEND / '.env').is_file(): shutil.copy2(BACKEND / '.env', destdir / 'backend.env.original')
    manifest = {'snapshot': str(snapshot), 'sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(), 'counts': counts}
    (destdir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('[OK] BACKUP:', destdir)
    print('[SNAPSHOT]', snapshot)
    print('[TABLE COUNT]', len(counts), '| [TOTAL RECORDS]', sum(counts.values()))
    print('[INFO] Không xóa fintech_ocr.db hoặc uploads trên máy.')
    print('[SECURITY] backend.env.original có thể chứa bí mật đăng nhập, chỉ lưu trên máy cá nhân.')

if __name__ == '__main__': main()
