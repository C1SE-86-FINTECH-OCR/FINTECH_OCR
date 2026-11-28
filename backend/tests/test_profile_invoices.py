from datetime import date, datetime

from sqlalchemy import select

from app.models import Invoice, InvoiceFile
from tests.api_support import _token, api_env


def test_profile_invoice_period_and_access(api_env):
    client, users, password = api_env
    start, end = date(2026, 10, 29), date(2026, 11, 27)
    owner = users['employee1@phase2.test']
    admin = users['admin@phase2.test']
    with client.app.state.phase2_test_session() as db:
        existing = db.scalars(select(Invoice).order_by(Invoice.id)).all()
        for invoice, issued in zip(existing, (start, end, None, end), strict=True):
            invoice.invoice_date = issued
        owned_ids = {existing[0].id, existing[1].id}
        other_ids = {existing[3].id}
        undated_id = existing[2].id
        old_ids = {}
        for index in range(44):
            file = InvoiceFile(
                uploaded_by=owner if index < 43 else admin,
                original_filename=f'profile-{index}.xml',
                file_type='xml', mime_type='application/xml', file_size_bytes=12,
                storage_key=f'profile-{index}.xml', checksum_sha256=str(index),
            )
            db.add(file)
            db.flush()
            invoice = Invoice(
                file_id=file.id, created_at=datetime(2026, 11, 15),
                invoice_date=start if index < 42 else date(2026, 10, 28),
            )
            db.add(invoice)
            db.flush()
            if index < 42:
                owned_ids.add(invoice.id)
            else:
                old_ids[file.uploaded_by] = invoice.id
        db.commit()

    path = '/api/v1/profile/invoices'
    params = {'invoice_date_from': start.isoformat(), 'invoice_date_to': end.isoformat()}
    assert client.get(path, params=params).status_code == 401
    for role, filtered, all_owned in (
        ('admin', set(), {old_ids[admin]}),
        ('accountant', set(), set()),
        ('employee1', owned_ids, owned_ids | {undated_id, old_ids[owner]}),
        ('employee2', other_ids, other_ids),
    ):
        token = _token(client, f'{role}@phase2.test', password)
        headers = {'Authorization': f'Bearer {token}'}
        for query, expected in (({}, all_owned), (params, filtered), ({}, all_owned)):
            seen = []
            for offset in range(0, max(1, len(expected)), 20):
                result = client.get(path, params={**query, 'offset': offset}, headers=headers)
                assert result.status_code == 200
                payload = result.json()
                assert payload['total'] == len(expected)
                assert len(payload['items']) == min(20, len(expected) - offset)
                if query:
                    assert all(item['invoice_date'] in params.values() for item in payload['items'])
                seen.extend(item['id'] for item in payload['items'])
            assert len(seen) == len(set(seen))
            assert set(seen) == expected
        if role == 'employee1':
            from_only = client.get(path, params={'invoice_date_from': start}, headers=headers).json()
            to_only = client.get(path, params={'invoice_date_to': end}, headers=headers).json()
            assert from_only['total'] == len(owned_ids)
            assert to_only['total'] == len(owned_ids) + 1

    def get_period(first, last):
        return client.get(path, params={'invoice_date_from': first, 'invoice_date_to': last}, headers=headers)

    assert get_period(end, start).status_code == 422
    assert get_period('2026-11-31', end).status_code == 422
    assert get_period('2026-11-01', '2026-11-01').json() == {'items': [], 'total': 0}
    assert get_period(end, end).json()['total'] == 1
