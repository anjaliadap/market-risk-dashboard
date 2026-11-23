from datetime import date

from openpyxl import Workbook

from dashboard.worksheet_data import export_values, read_worksheet, window


def test_worksheet_keeps_sparse_coordinates_and_uncached_formulas(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = 0
    sheet["AA101"] = date(2026, 11, 1)
    sheet["AB101"] = "=A1+1"
    sheet["AD104"] = "#N/A"
    path = tmp_path / "worksheet.xlsx"
    workbook.save(path)
    stat = path.stat()

    values, last_column = read_worksheet(
        str(path), sheet.title, True, stat.st_mtime_ns, stat.st_size
    )
    formulas, _ = read_worksheet(str(path), sheet.title, False, stat.st_mtime_ns, stat.st_size)
    visible = window(values, 101, 104, 27, last_column)

    assert set(values) == {1, 101, 104}
    assert list(visible.columns) == ["AA", "AB", "AC", "AD"]
    assert visible.loc[101, "AA"].startswith("2026-11-01")
    assert visible.loc[101, "AB"] == ""
    assert visible.loc[104, "AD"] == "#N/A"
    assert window(formulas, 101, 101, 28, 28).loc[101, "AB"] == "=A1+1"
    csv_data = export_values(values, 104, last_column).decode("utf-8-sig")
    assert csv_data.splitlines()[1].startswith("1,0,")
    assert csv_data.splitlines()[-1].endswith(",#N/A")
