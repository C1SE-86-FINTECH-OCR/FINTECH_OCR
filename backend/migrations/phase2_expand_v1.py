"""Expand the isolated PostgreSQL test schema toward Database Design v1.0.

This migration is deliberately test-database-only. It adds columns and
constraints without removing or renaming fields used by the current backend.
Schedule date/time alignment is excluded until its business meaning is settled.
"""
from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import text

VERSION = "20261107_phase2_expand_v1"
REQUIRED_DATABASE = "fintech_ocr_rbac_test"

DDL = (
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS submitted_at timestamptz",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS source_type varchar(10) NOT NULL DEFAULT 'ocr'",
    "ALTER TABLE invoice_items ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now()",
    "ALTER TABLE invoice_items ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()",
    "ALTER TABLE invoice_files ADD COLUMN IF NOT EXISTS storage_url text NOT NULL DEFAULT ''",
    "ALTER TABLE invoice_lookups ADD COLUMN IF NOT EXISTS query_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE invoice_lookups ADD COLUMN IF NOT EXISTS notes text",
    "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS type varchar(40) NOT NULL DEFAULT 'legacy'",
    "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS read_at timestamptz",
    """UPDATE invoices i
       SET source_type = CASE WHEN f.file_type = 'xml' THEN 'xml' ELSE 'ocr' END
       FROM invoice_files f WHERE f.id = i.file_id""",
    """UPDATE invoices i SET submitted_at = s.submitted_at
       FROM (SELECT invoice_id, max(created_at) AS submitted_at
             FROM invoice_approvals WHERE action = 'submitted' GROUP BY invoice_id) s
       WHERE s.invoice_id = i.id AND i.submitted_at IS NULL""",
    """UPDATE invoice_files f SET storage_url = '/api/v1/invoices/' || i.id || '/file'
       FROM invoices i WHERE i.file_id = f.id AND f.storage_url = ''""",
    """UPDATE invoice_lookups SET notes = note
       WHERE notes IS NULL AND note IS NOT NULL""",
    """UPDATE invoice_items item
       SET created_at = COALESCE(parent.created_at, item.created_at),
           updated_at = COALESCE((
               SELECT max(c.corrected_at) FROM invoice_corrections c
               WHERE c.invoice_id = item.invoice_id
                 AND (c.field_name = 'items[' || item.line_no || ']'
                      OR left(c.field_name, length('items[' || item.line_no || '].')) =
                         'items[' || item.line_no || '].')
           ), parent.updated_at, item.updated_at)
       FROM invoices parent WHERE parent.id = item.invoice_id""",
    """DO $$ BEGIN
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoices_source_type') THEN
         ALTER TABLE invoices ADD CONSTRAINT ck_invoices_source_type CHECK (source_type IN ('ocr','xml'));
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoice_items_line_no_positive') THEN
         ALTER TABLE invoice_items ADD CONSTRAINT ck_invoice_items_line_no_positive CHECK (line_no > 0);
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_invoice_items_invoice_line') THEN
         ALTER TABLE invoice_items ADD CONSTRAINT uq_invoice_items_invoice_line UNIQUE (invoice_id,line_no);
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoice_items_quantity_nonnegative') THEN
         ALTER TABLE invoice_items ADD CONSTRAINT ck_invoice_items_quantity_nonnegative CHECK (quantity IS NULL OR quantity >= 0);
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoice_items_unit_price_nonnegative') THEN
         ALTER TABLE invoice_items ADD CONSTRAINT ck_invoice_items_unit_price_nonnegative CHECK (unit_price IS NULL OR unit_price >= 0);
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoice_items_amount_nonnegative') THEN
         ALTER TABLE invoice_items ADD CONSTRAINT ck_invoice_items_amount_nonnegative CHECK (amount >= 0);
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoice_files_file_type') THEN
         ALTER TABLE invoice_files ADD CONSTRAINT ck_invoice_files_file_type CHECK (file_type IN ('pdf','jpg','png','xml'));
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoice_files_size_positive') THEN
         ALTER TABLE invoice_files ADD CONSTRAINT ck_invoice_files_size_positive CHECK (file_size_bytes > 0);
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoice_lookups_result') THEN
         ALTER TABLE invoice_lookups ADD CONSTRAINT ck_invoice_lookups_result CHECK (result IN ('verified','mismatch','not_found'));
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoices_validation_status') THEN
         ALTER TABLE invoices ADD CONSTRAINT ck_invoices_validation_status CHECK (validation_status IS NULL OR validation_status IN ('valid','needs_review','error'));
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoices_approval_status') THEN
         ALTER TABLE invoices ADD CONSTRAINT ck_invoices_approval_status CHECK (approval_status IN ('draft','pending','approved','rejected'));
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoices_lookup_status') THEN
         ALTER TABLE invoices ADD CONSTRAINT ck_invoices_lookup_status CHECK (lookup_status IN ('not_checked','verified','mismatch','not_found','not_applicable'));
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoices_document_type') THEN
         ALTER TABLE invoices ADD CONSTRAINT ck_invoices_document_type CHECK (document_type IN ('einvoice','bill','unknown'));
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoices_vat_rate_range') THEN
         ALTER TABLE invoices ADD CONSTRAINT ck_invoices_vat_rate_range CHECK (vat_rate IS NULL OR vat_rate BETWEEN 0 AND 100);
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoices_amounts_nonnegative') THEN
         ALTER TABLE invoices ADD CONSTRAINT ck_invoices_amounts_nonnegative CHECK (
           (subtotal IS NULL OR subtotal >= 0) AND
           (vat_amount IS NULL OR vat_amount >= 0) AND
           (total_amount IS NULL OR total_amount >= 0));
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoices_confidence_range') THEN
         ALTER TABLE invoices ADD CONSTRAINT ck_invoices_confidence_range CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1);
       END IF;
       IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_invoices_qr_http_url') THEN
         ALTER TABLE invoices ADD CONSTRAINT ck_invoices_qr_http_url CHECK (qr_url IS NULL OR qr_url ~* '^https?://');
       END IF;
    END $$""",
    "CREATE INDEX IF NOT EXISTS ix_invoice_files_uploaded_by_uploaded_at ON invoice_files(uploaded_by,uploaded_at)",
    "CREATE INDEX IF NOT EXISTS ix_invoice_files_checksum_sha256 ON invoice_files(checksum_sha256)",
    "CREATE INDEX IF NOT EXISTS ix_invoices_validation_created_at ON invoices(validation_status,created_at)",
    "CREATE INDEX IF NOT EXISTS ix_invoices_date_validation ON invoices(invoice_date,validation_status)",
    "CREATE INDEX IF NOT EXISTS ix_invoices_invoice_number ON invoices(invoice_number)",
    "CREATE INDEX IF NOT EXISTS ix_invoices_seller_tax_code ON invoices(seller_tax_code)",
    "CREATE INDEX IF NOT EXISTS ix_invoices_reviewed_by ON invoices(reviewed_by)",
    "CREATE INDEX IF NOT EXISTS ix_invoices_duplicate_check ON invoices(seller_tax_code,invoice_number,total_amount)",
    "CREATE INDEX IF NOT EXISTS ix_invoice_corrections_invoice_corrected_at ON invoice_corrections(invoice_id,corrected_at)",
    "CREATE INDEX IF NOT EXISTS ix_invoice_corrections_corrected_by ON invoice_corrections(corrected_by)",
)


def _reconstruct_lookup_snapshots(connection) -> int:
    rows = connection.execute(text("""
        SELECT l.id, l.checked_at, l.invoice_id,
               i.invoice_number, i.invoice_symbol, i.seller_tax_code,
               i.invoice_date, i.total_amount
        FROM invoice_lookups l JOIN invoices i ON i.id = l.invoice_id
        ORDER BY l.id
    """)).mappings().all()
    corrections = connection.execute(text("""
        SELECT invoice_id, field_name, old_value, corrected_at
        FROM invoice_corrections
        ORDER BY corrected_at DESC, id DESC
    """)).mappings().all()
    by_invoice: dict[int, list] = defaultdict(list)
    for correction in corrections:
        by_invoice[correction["invoice_id"]].append(correction)

    fields = {
        "invoice_number": "invoice_number",
        "invoice_symbol": "invoice_symbol",
        "seller_tax_code": "seller_tax_code",
        "invoice_date": "invoice_date",
        "total_amount": "total_amount",
    }
    updated = 0
    for row in rows:
        state = {
            "invoice_number": row["invoice_number"],
            "invoice_symbol": row["invoice_symbol"],
            "seller_tax_code": row["seller_tax_code"],
            "invoice_date": row["invoice_date"].isoformat() if row["invoice_date"] else None,
            "total_amount": str(row["total_amount"]) if row["total_amount"] is not None else None,
        }
        # Reverse later, audited corrections so the snapshot reflects the data
        # visible when the lookup was recorded, rather than today's invoice.
        for correction in by_invoice[row["invoice_id"]]:
            field_name = correction["field_name"]
            if field_name in fields and correction["corrected_at"] > row["checked_at"]:
                state[field_name] = correction["old_value"]
        state["legacy_reconstructed"] = True
        connection.execute(
            text("UPDATE invoice_lookups SET query_snapshot = CAST(:snapshot AS jsonb) WHERE id = :id"),
            {"id": row["id"], "snapshot": json.dumps(state, ensure_ascii=False)},
        )
        updated += 1
    return updated


def upgrade(connection) -> int:
    database = connection.execute(text("SELECT current_database()")).scalar_one()
    if database != REQUIRED_DATABASE:
        raise RuntimeError(f"Migration blocked: expected {REQUIRED_DATABASE}, got {database}")

    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS phase2_schema_migrations (
            version varchar(80) PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now(),
            description text NOT NULL
        )
    """))
    connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('fintech_ocr_phase2_migrations'))"))
    applied = connection.execute(
        text("SELECT 1 FROM phase2_schema_migrations WHERE version = :version"),
        {"version": VERSION},
    ).scalar_one_or_none()
    if applied:
        return 0

    bad_data = {
        "file type/size": "SELECT count(*) FROM invoice_files WHERE file_type NOT IN ('pdf','jpg','png','xml') OR file_size_bytes <= 0",
        "invoice state": "SELECT count(*) FROM invoices WHERE (validation_status IS NOT NULL AND validation_status NOT IN ('valid','needs_review','error')) OR approval_status NOT IN ('draft','pending','approved','rejected') OR lookup_status NOT IN ('not_checked','verified','mismatch','not_found','not_applicable') OR document_type NOT IN ('einvoice','bill','unknown')",
        "invoice money/confidence": "SELECT count(*) FROM invoices WHERE vat_rate < 0 OR vat_rate > 100 OR subtotal < 0 OR vat_amount < 0 OR total_amount < 0 OR confidence_score < 0 OR confidence_score > 1 OR subtotal::text IN ('NaN','Infinity','-Infinity') OR vat_amount::text IN ('NaN','Infinity','-Infinity') OR total_amount::text IN ('NaN','Infinity','-Infinity') OR confidence_score::text IN ('NaN','Infinity','-Infinity')",
        "invoice items": "SELECT count(*) FROM invoice_items WHERE line_no <= 0 OR amount < 0 OR quantity < 0 OR unit_price < 0 OR amount::text IN ('NaN','Infinity','-Infinity') OR quantity::text IN ('NaN','Infinity','-Infinity') OR unit_price::text IN ('NaN','Infinity','-Infinity')",
        "duplicate invoice lines": "SELECT count(*) FROM (SELECT invoice_id,line_no FROM invoice_items GROUP BY invoice_id,line_no HAVING count(*) > 1) d",
        "lookup result": "SELECT count(*) FROM invoice_lookups WHERE result NOT IN ('verified','mismatch','not_found')",
        "qr scheme": "SELECT count(*) FROM invoices WHERE qr_url IS NOT NULL AND qr_url !~* '^https?://'",
    }
    violations = {
        name: connection.execute(text(query)).scalar_one()
        for name, query in bad_data.items()
    }
    violations = {name: count for name, count in violations.items() if count}
    if violations:
        raise RuntimeError(f"Migration precondition failed; no schema change applied: {violations}")

    for statement in DDL:
        connection.exec_driver_sql(statement)
    snapshots = _reconstruct_lookup_snapshots(connection)
    connection.execute(
        text("INSERT INTO phase2_schema_migrations(version,description) VALUES (:version,:description)"),
        {"version": VERSION, "description": "Additive Phase 2 design fields and validated constraints"},
    )
    return snapshots
