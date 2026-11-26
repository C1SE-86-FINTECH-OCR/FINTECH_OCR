from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.worksheet import Worksheet


NUMBER_FORMAT = '#,##0.00'
TEXT_FORMAT = '@'
THIN = Side(style='thin', color='000000')
MEDIUM = Side(style='medium', color='000000')
TABLE_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
TOTAL_BORDER = Border(left=THIN, right=THIN, top=MEDIUM, bottom=MEDIUM)
FONT = Font(name='Arial', size=10, color='000000')
EMPHASIS = Font(name='Arial', size=10, bold=True, color='000000')
TITLE = Font(name='Arial', size=16, bold=True, color='000000')
ALIGNMENTS = {
    (side, wrap): Alignment(horizontal=side, vertical='center', wrap_text=wrap)
    for side in ('left', 'center', 'right')
    for wrap in (False, True)
}


def report_sheet(workbook: Workbook, title, widths, *, landscape=False):
    sheet = workbook.create_sheet(title)
    sheet.freeze_panes = 'A2'
    sheet.print_title_rows = '1:1'
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.paperSize = Worksheet.PAPERSIZE_A4
    sheet.page_setup.orientation = 'landscape' if landscape else 'portrait'
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0 if landscape else 1
    sheet.page_margins = PageMargins(left=0.35, right=0.35, top=0.65, bottom=0.60, header=0.25, footer=0.25)
    sheet.oddHeader.center.text = title
    sheet.oddHeader.center.font = 'Arial,Bold'
    sheet.oddFooter.right.text = 'Trang &P / &N'
    sheet.print_options.horizontalCentered = True
    sheet.sheet_view.showGridLines = False
    sheet.sheet_format.defaultRowHeight = 19
    sheet.row_dimensions[1].height = 30
    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    return sheet


def append_report_row(sheet, values, *, center=(), right=(), wrap=(), formats=None, emphasis=None):
    cells = []
    for column, value in enumerate(values, start=1):
        cell = WriteOnlyCell(sheet, value=value)
        cell.border = TOTAL_BORDER if emphasis == 'total' else TABLE_BORDER
        alignment = 'center' if column in center else 'right' if column in right else 'left'
        cell.alignment = ALIGNMENTS[alignment, emphasis == 'header' or column in wrap]
        if formats and column in formats:
            cell.number_format = formats[column]
        cell.font = TITLE if emphasis == 'title' else EMPHASIS if emphasis else FONT
        cells.append(cell)
    sheet.append(cells)
