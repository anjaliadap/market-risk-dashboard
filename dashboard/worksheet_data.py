"""Display the populated cells of a saved workbook without changing its contents."""

import csv
from datetime import date, time
from io import StringIO
from pathlib import Path
from zipfile import BadZipFile

import pandas as pd
import streamlit as st
from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException


@st.cache_data(show_spinner="Reading worksheet…", max_entries=16)
def read_worksheet(path, sheet, saved_values, modified_ns, size):
    workbook = load_workbook(path, data_only=saved_values, read_only=True, keep_links=False)
    rows = {}
    last_column = 0
    try:
        if sheet not in workbook.sheetnames:
            raise ValueError(f"The workbook does not contain the {sheet} sheet.")
        for row_number, row in enumerate(workbook[sheet].values, 1):
            end = next((i for i in range(len(row), 0, -1) if row[i - 1] is not None), 0)
            if end:
                rows[row_number] = tuple(getattr(value, "text", value) for value in row[:end])
                last_column = max(last_column, end)
    finally:
        workbook.close()
    stat = Path(path).stat()
    if (stat.st_mtime_ns, stat.st_size) != (modified_ns, size):
        raise ValueError(
            "The workbook changed during the read. Reload after Excel finishes saving."
        )
    return rows, last_column


def cell_text(value):
    if value is None:
        return ""
    if isinstance(value, (date, time)):
        return value.isoformat()
    return str(value)


def window(rows, first_row, last_row, first_column, last_column):
    labels = [get_column_letter(col) for col in range(first_column, last_column + 1)]
    data = []
    for row_number in range(first_row, last_row + 1):
        row = rows.get(row_number, ())
        values = row[first_column - 1 : last_column]
        data.append([cell_text(value) for value in values] + [""] * (len(labels) - len(values)))
    return pd.DataFrame(data, columns=labels, index=range(first_row, last_row + 1)).rename_axis(
        "Excel row"
    )


def export_values(rows, last_row, last_column):
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Excel row", *(get_column_letter(i) for i in range(1, last_column + 1))])
    for number in range(1, last_row + 1):
        row = rows.get(number, ())
        # Spreadsheet programs may interpret saved text as a formula when opening a CSV.
        values = [
            "'" + value
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
            else cell_text(value)
            for value in row
        ]
        writer.writerow([number, *values, *([""] * (last_column - len(row)))])
    return output.getvalue().encode("utf-8-sig")


def render_worksheet_data(configured, sheet):
    if not configured:
        st.info("Set EXCEL_WORKBOOK_PATH or PROCESS_WORKBOOK_PATH to view this worksheet.")
        return
    path = Path(configured).expanduser()
    st.caption(f"{path.name} · {sheet}")
    view = st.radio(
        "Cell contents",
        ["Saved values", "Formulas and constants"],
        horizontal=True,
        key=f"cells_{sheet}",
    )
    saved_values = view == "Saved values"
    try:
        stat = path.stat()
        rows, last_column = read_worksheet(
            str(path), sheet, saved_values, stat.st_mtime_ns, stat.st_size
        )
    except (OSError, ValueError, BadZipFile, InvalidFileException) as exc:
        st.warning(f"Could not read the worksheet. {exc}")
        return
    if not rows:
        st.info("This worksheet has no cells with content in the selected view.")
        return

    last_row = max(rows)
    row_starts = range(1, last_row + 1, 100)
    column_starts = range(1, last_column + 1, 24)
    left, right = st.columns(2)
    with left:
        first_row = st.selectbox(
            "Excel rows",
            row_starts,
            format_func=lambda x: f"{x}–{min(x + 99, last_row)}",
            key=f"rows_{sheet}",
        )
    with right:
        first_column = st.selectbox(
            "Excel columns",
            column_starts,
            format_func=lambda x: (
                f"{get_column_letter(x)}–{get_column_letter(min(x + 23, last_column))}"
            ),
            key=f"columns_{sheet}",
        )
    st.dataframe(
        window(
            rows,
            first_row,
            min(first_row + 99, last_row),
            first_column,
            min(first_column + 23, last_column),
        ),
        width="stretch",
        height=480,
        alt=f"Worksheet cells from {sheet}",
    )
    if saved_values:
        st.caption(
            "Blank cells have no saved value. Choose Formulas and constants to inspect the source cells."
        )
        st.download_button(
            "Download all saved values",
            lambda: export_values(rows, last_row, last_column),
            file_name=f"{sheet}.csv",
            mime="text/csv",
        )
