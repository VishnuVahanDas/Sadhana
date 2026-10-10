from django.http import HttpResponse
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADER_FILL = PatternFill("solid", fgColor="7A1F2B")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def _fill_sheet(sheet, sheet_title, intro, headers, rows):
    sheet.title = sheet_title[:31]
    for line in intro:
        sheet.append([str(line)])
    if intro:
        sheet.append([])
    sheet.append([str(header) for header in headers])
    header_row = sheet.max_row
    for cell in sheet[header_row]:
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(vertical="center")
    for row in rows:
        sheet.append(list(row))
    sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
    for index, header in enumerate(headers, 1):
        longest = max([len(str(header))] + [len(str(row[index - 1] or "")) for row in rows])
        sheet.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 10), 50)


def workbook_response(filename, sheet_title, intro, headers, rows, extra_sheets=()):
    """An .xlsx download: a few intro lines, then a styled header row and the data.

    `extra_sheets` adds more sheets, each as (sheet_title, intro, headers, rows).
    """
    workbook = Workbook()
    _fill_sheet(workbook.active, sheet_title, intro, headers, rows)
    for extra in extra_sheets:
        _fill_sheet(workbook.create_sheet(), *extra)

    response = HttpResponse(content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="{slugify(filename)}.xlsx"'
    workbook.save(response)
    return response
