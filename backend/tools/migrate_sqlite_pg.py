"""Migrate a backed-up SQLite snapshot to an EMPTY PostgreSQL database.
The live SQLite file is never opened or modified. Do not switch .env until success.
"""
import argparse, hashlib, json, os, sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from sqlalchemy import create_engine, func, inspect, select, text, update

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core import Base  # noqa: E402
import app.models  # noqa: F401,E402 -- register all mapped tables


def normalized(value):
    if isinstance(value, datetime):
        if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec='microseconds')
    if isinstance(value, Decimal): return str(value)
    if hasattr(value, 'isoformat'): return value.isoformat()
    if isinstance(value, (dict, list)): return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def fingerprint(rows):
    h = hashlib.sha256()
    for record in rows:
        h.update(json.dumps({k: normalized(v) for k, v in sorted(record.items())}, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8') + b'\n')
    return h.hexdigest()


def fetch_rows(conn, table):
    return [dict(row) for row in conn.execute(select(table).order_by(*table.primary_key.columns)).mappings()]


def migrate(snapshot: Path, url: str, *, test_sqlite=False):
    if not snapshot.is_file(): raise RuntimeError(f'Không tìm thấy snapshot: {snapshot}')
    if snapshot.resolve() == (BACKEND / 'fintech_ocr.db').resolve():
        raise RuntimeError('Hãy dùng SNAPSHOT trong Database_Backup, không dùng SQLite gốc đang chạy.')
    if not test_sqlite and not url.startswith('postgresql+psycopg://'):
        raise RuntimeError('PG_MIGRATION_URL phải là postgresql+psycopg://...')
    source = create_engine('sqlite+pysqlite:///' + snapshot.resolve().as_posix())
    target = create_engine(url, pool_pre_ping=True)
    try:
        with source.connect() as conn:
            integrity = conn.exec_driver_sql('PRAGMA integrity_check').scalar()
            fk_errors = conn.exec_driver_sql('PRAGMA foreign_key_check').all()
        if integrity != 'ok' or fk_errors:
            raise RuntimeError(f'SQLite snapshot không hợp lệ: integrity={integrity}, FK={len(fk_errors)}')
        src_inspector = inspect(source)
        existing = set(src_inspector.get_table_names())
        for table in Base.metadata.sorted_tables:
            if table.name not in existing: raise RuntimeError(f'SQLite thiếu bảng {table.name}')
            src_cols = {col['name'] for col in src_inspector.get_columns(table.name)}
            required = {col.name for col in table.columns}
            if required - src_cols: raise RuntimeError(f'SQLite {table.name} thiếu cột {sorted(required - src_cols)}')
            if src_cols - required: raise RuntimeError(f'SQLite {table.name} có cột ngoài mô hình: {sorted(src_cols - required)}. Cần xem lại để không mất dữ liệu.')
        if target.dialect.name == 'postgresql':
            with target.begin() as conn: conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        Base.metadata.create_all(target)
        dst_inspector = inspect(target)
        for table in Base.metadata.sorted_tables:
            columns = {col['name'] for col in dst_inspector.get_columns(table.name)}
            if {c.name for c in table.columns} - columns:
                raise RuntimeError(f'PostgreSQL bảng {table.name} khác mô hình hiện tại.')
            with target.connect() as conn:
                if conn.scalar(select(func.count()).select_from(table)):
                    raise RuntimeError(f'PostgreSQL bảng {table.name} đã có dữ liệu. Chỉ chuyển vào DB mới, KHÔNG ghi đè.')
        summary = {}
        with source.connect() as sqlite, target.begin() as pg:
            if target.dialect.name == 'postgresql': pg.execute(text("SET TIME ZONE 'UTC'"))
            for table in Base.metadata.sorted_tables:
                rows = fetch_rows(sqlite, table)
                deferred = []
                for record in rows:
                    if table.name == 'users' and record.get('created_by') is not None:
                        deferred.append((record['id'], record['created_by'], record.get('updated_at')))
                        record = {**record, 'created_by': None}
                    pg.execute(table.insert().values(**record))
                if table.name == 'users':
                    for user_id, creator, original_updated_at in deferred:
                        pg.execute(update(table).where(table.c.id == user_id).values(created_by=creator, updated_at=original_updated_at))
                copied = fetch_rows(pg, table)
                if len(rows) != len(copied) or fingerprint(rows) != fingerprint(copied):
                    raise RuntimeError(f'Dữ liệu {table.name} KHÔNG khớp (transaction sẽ rollback).')
                summary[table.name] = len(rows)
                print(f'[OK] {table.name}: {len(rows)} rows; checksums match')
                if target.dialect.name == 'postgresql' and 'id' in table.c and table.c.id.primary_key:
                    seq = pg.scalar(text('SELECT pg_get_serial_sequence(:tbl, :col)'), {'tbl': 'public.' + table.name, 'col': 'id'})
                    if seq:
                        highest = pg.scalar(select(func.max(table.c.id)))
                        pg.execute(text('SELECT setval(CAST(:seq AS regclass), :mx, :called)'), {'seq': seq, 'mx': highest or 1, 'called': bool(highest)})
        print('[SUCCESS] PostgreSQL migration complete. Total rows:', sum(summary.values()))
        print('[SUMMARY]', json.dumps(summary, ensure_ascii=False))
        return summary
    finally:
        source.dispose()
        target.dispose()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--snapshot', required=True, type=Path)
    args = p.parse_args()
    url = os.environ.get('PG_MIGRATION_URL', '')
    if not url: raise SystemExit('[STOP] Chưa đặt PG_MIGRATION_URL; xem HUONG_DAN.md')
    try: migrate(args.snapshot, url)
    except Exception as e:
        print('[STOP]', type(e).__name__ + ':', e)
        print('[INFO] Không đổi .env khi chưa thấy [SUCCESS]. SQLite gốc vẫn được giữ nguyên.')
        raise SystemExit(1) from e

if __name__ == '__main__': main()
