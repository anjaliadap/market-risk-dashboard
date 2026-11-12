from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_overview_loads():
    with patch("src.refresh.enqueue"), patch("dashboard.workbook_sections.enqueue"):
        app = AppTest.from_file(
            str(__import__("pathlib").Path(__file__).resolve().parents[1] / "dashboard/app.py")
        ).run(timeout=30)
    assert not app.exception
    assert app.title[0].value == "Executive Overview"
