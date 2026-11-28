from datetime import date
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import select

from app.models import Invoice, InvoiceFile, InvoiceItem
from tests.api_support import _token, api_env


def test_report_search_totals_and_formatted_full_export(api_env):
    client, users, password = api_env
    supplier = 'Công ty Đặng Ánh'
    count = 503
    with client.app.state.phase2_test_session() as db:
        out_of_period, wrong_status = db.scalars(select(Invoice).order_by(Invoice.id).limit(2)).all()
        for invoice in (out_of_period, wrong_status):
            invoice.seller_name = supplier
            invoice.seller_tax_code = '0101234567'
        out_of_period.approval_status = 'approved'
        out_of_period.invoice_date = date(2026, 2, 1)
        wrong_status.approval_status = 'pending'
        wrong_status.invoice_date = date(2026, 1, 31)

        files = [
            InvoiceFile(
                uploaded_by=users['employee1@phase2.test'], original_filename=f'{n}.xml',
                file_type='xml', mime_type='application/xml', file_size_bytes=1,
                storage_key=f'{n}.xml', checksum_sha256=str(n),
            )
            for n in range(count)
        ]
        db.add_all(files)
        db.flush()
        invoices = [
            Invoice(
                file_id=file.id, invoice_number='0000502' if n == count-1 else f'REP-{n:04}', seller_name=supplier,
                seller_tax_code='0101234567', buyer_tax_code='0023456789', approval_status='approved',
                invoice_date=date(2026, 1, 31), subtotal=Decimal('1000.25'),
                vat_amount=Decimal('100.03'), total_amount=Decimal('1100.28'),
            )
            for n, file in enumerate(files)
        ]
        db.add_all(invoices)
        db.flush()
        for invoice in (invoices[0], invoices[-1], wrong_status):
            db.add(InvoiceItem(invoice_id=invoice.id, line_no=1, description='Dịch vụ',
                               quantity=1, unit_price=Decimal('1000.25'), amount=Decimal('1000.25')))
        db.commit()

    def headers_for(account):
        return {'Authorization': 'Bearer ' + _token(client, f'{account}@phase2.test', password)}

    headers = headers_for('accountant')
    base = '/api/v1/reports/'
    filters = {
        'approval_status': 'approved', 'invoice_date_from': '2026-01-01',
        'invoice_date_to': '2026-01-31',
    }
    for keyword, hits in [('rEp-0001', 1), ('DANG ANH', count), ('Đặng ÁNH', count), ('0101234567', count), ('unknown', 0)]:
        response = client.get(base + 'invoices', params={**filters, 'search': keyword, 'limit': 10}, headers=headers)
        assert response.status_code == 200
        assert response.json()['total'] == hits
        assert len(response.json()['items']) == min(hits, 10)

    params = {**filters, 'search': 'dang anh 0101234567'}
    summary = client.get(base + 'summary', params=params, headers=headers)
    assert summary.json() == {
        'invoice_count': count, 'subtotal': 503125.75, 'vat_amount': 50315.09,
        'total_amount': 553440.84, 'currency': 'VND',
    }
    assert client.get(base + 'summary', params=params, headers=headers_for('admin')).json() == summary.json()
    denied = headers_for('employee1')
    for endpoint in ('summary', 'invoices', 'export'):
        assert client.get(base + endpoint, params=params, headers=denied).status_code == 403

    preview = client.get(base + 'invoices', params={**params, 'limit': 10, 'offset': 10}, headers=headers)
    assert len(preview.json()['items']) == 10
    response = client.get(base + 'export', params=params, headers=headers)
    assert response.status_code == 200
    overview, listing, details = load_workbook(BytesIO(response.content)).worksheets
    assert overview['B5'].value == count
    assert [overview[f'B{row}'].value for row in (6, 7, 8)] == [503125.75, 50315.09, 553440.84]
    numbers = {cell.value for (cell,) in listing.iter_rows(min_row=2, max_row=count+1, min_col=2, max_col=2)}
    assert numbers == {'0000502'} | {f'REP-{n:04}' for n in range(count-1)}
    assert listing[f'L{count+2}'].value == 553440.84
    assert [details['B2'].value, details['B3'].value] == ['REP-0000', '0000502']
    assert listing.auto_filter.ref == f'A1:P{count+1}'
    assert details.auto_filter.ref == 'A1:H3'
    for sheet in (overview, listing, details):
        assert sheet.freeze_panes == 'A2'
        assert sheet['A1'].font.bold and sheet['A1'].fill.patternType is None
        assert sheet['A1'].font.name == sheet['A2'].font.name == 'Arial'
        assert sheet['A2'].border.bottom.style == 'thin'
        assert sheet.row_dimensions[1].height > sheet.sheet_format.defaultRowHeight
        assert sheet.print_title_rows == '$1:$1'
        assert sheet.page_setup.paperSize == int(sheet.PAPERSIZE_A4)
        assert sheet.sheet_properties.pageSetUpPr.fitToPage and sheet.page_setup.fitToWidth == 1
        assert sheet.page_margins.left == sheet.page_margins.right == 0.35
        assert sheet.oddFooter.right.text == 'Trang &P / &N'
    assert overview.page_setup.orientation == 'portrait'
    assert listing.page_setup.orientation == details.page_setup.orientation == 'landscape'
    assert listing.page_setup.fitToHeight == details.page_setup.fitToHeight == 0
    for cell in (overview['B8'], listing['I2'], listing['K2'], listing['L2'], details['G2'], details['H2']):
        assert cell.data_type == 'n' and cell.number_format == '#,##0.00'
        assert cell.alignment.horizontal == 'right'
    assert listing['A2'].alignment.horizontal == details['C2'].alignment.horizontal == 'center'
    assert listing['H2'].alignment.horizontal == 'center'
    assert listing['D2'].alignment.horizontal == details['D2'].alignment.horizontal == 'left'
    assert overview['B8'].font.bold and listing[f'L{count+2}'].font.bold
    assert overview['B8'].border.bottom.style == listing[f'L{count+2}'].border.bottom.style == 'medium'
    for cell, value in (
        (listing['B2'], '0000502'), (listing['E2'], '0101234567'),
        (listing['G2'], '0023456789'), (details['B3'], '0000502'),
    ):
        assert cell.value == value and cell.data_type == 's' and cell.number_format == '@'
