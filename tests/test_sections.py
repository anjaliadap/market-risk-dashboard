from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.sections import banks, consumer, housing, valuation

ROOT = Path(__file__).resolve().parents[1]
FREQ = {"daily": "B", "weekly": "W-THU", "monthly": "MS", "quarterly": "QS", "annual": "YS"}
SCRIPT = """from unittest.mock import patch
import runpy
with patch('streamlit.navigation'), patch('src.refresh.enqueue'):
    namespace = runpy.run_path({path!r})
with patch.dict(namespace, enqueue=lambda ids: None):
    namespace['render']({title!r})
"""


def seed(ids, monkeypatch, tmp_path):
    from sqlalchemy import create_engine

    from src.database import store
    from src.registry import BY_ID

    engine = create_engine("sqlite:///" + str(tmp_path / "fixtures.db"))
    monkeypatch.setattr(store, "engine", engine)
    store.initialize()
    rng = np.random.default_rng(7)
    for key in ids:
        meta = BY_ID[key]
        index = pd.date_range("2000-01-01", "2025-06-30", freq=FREQ[meta["frequency"]])
        if key == "USREC":
            values = pd.Series(0.0, index=index)
            values.loc["2008-01-01":"2009-06-01"] = 1.0
        else:
            # Synthetic values exist exclusively in this isolated test database.
            walk = np.cumsum(rng.normal(0.002, 0.01, len(index)))
            values = pd.Series(5 * np.exp(walk), index=index)
        store.save(meta, values)


@pytest.mark.parametrize(
    "title,module,charts",
    [
        ("Housing", housing, 6),
        ("Banks", banks, 5),
        ("Valuation", valuation, 4),
        ("Consumer", consumer, 6),
    ],
)
def test_dedicated_page_with_observations(title, module, charts, tmp_path, monkeypatch):
    seed(module.IDS, monkeypatch, tmp_path)
    app = AppTest.from_string(SCRIPT.format(path=str(ROOT / "dashboard/app.py"), title=title)).run(
        timeout=60
    )
    assert not app.exception
    assert app.title[0].value == title
    assert len(app.tabs) == 4
    assert len(app.get("plotly_chart")) >= charts
    assert len(app.metric) >= 6
    # Every KPI tile is populated when its series exists.
    assert all(m.value != "—" for m in app.metric[: len(module.KPIS)])


@pytest.mark.parametrize("title", ["Housing", "Banks", "Valuation", "Consumer"])
def test_dedicated_page_without_observations(title):
    app = AppTest.from_string(SCRIPT.format(path=str(ROOT / "dashboard/app.py"), title=title)).run(
        timeout=60
    )
    assert not app.exception
    assert any("UNAVAILABLE" in w.value for w in app.warning)
    assert len(app.get("plotly_chart")) <= 1  # only assumption-driven visuals


def test_valuation_requires_pe_input(tmp_path, monkeypatch):
    seed(valuation.IDS, monkeypatch, tmp_path)
    app = AppTest.from_string(
        SCRIPT.format(path=str(ROOT / "dashboard/app.py"), title="Valuation")
    ).run(timeout=60)
    assert any("No multiple is assumed" in i.value for i in app.info)
    app.number_input(key="valuation_pe").set_value(20.0).run(timeout=60)
    assert not app.exception
    labels = {m.label: m.value for m in app.metric}
    assert labels["Earnings yield"] == "5.00%"
    assert labels["Implied perpetual growth"] == "7.00%"


def test_registry_covers_section_ids():
    from src.registry import BY_ID

    for module in (housing, banks, valuation, consumer):
        assert set(module.IDS) <= BY_ID.keys()
        assert {k.series_id for k in module.KPIS} <= set(module.IDS)
