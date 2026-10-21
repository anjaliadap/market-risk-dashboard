import pytest

from src.providers.fred import parse_csv


def test_parse_missing():
    s = parse_csv("DATE,DGS10\n2024-01-01,.\n2024-01-02,4.2\n")
    assert len(s) == 1
    assert s.iloc[0] == 4.2


def test_reject_invalid():
    with pytest.raises(ValueError):
        parse_csv("DATE,X\n2024-01-01,.\n")
    with pytest.raises(ValueError):
        parse_csv("DATE,X\n2024-01-01,inf\n")


def test_maintenance_page():
    with pytest.raises(ValueError, match="maintenance"):
        parse_csv("<!doctype html><html>Site Maintenance</html>")
