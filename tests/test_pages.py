import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = json.loads((ROOT / "config/pages.json").read_text())


@pytest.mark.parametrize(
    "title",
    [title for titles in PAGES.values() for title in titles] + ["Data Sources & System Status"],
)
def test_page_render(title):
    # Exercise each page body via the app's public renderer. Navigation is tested separately.
    script = f"""from unittest.mock import patch
import runpy
with patch('streamlit.navigation'), patch('src.refresh.enqueue'):
    namespace=runpy.run_path({str(ROOT / "dashboard/app.py")!r})
with patch.dict(namespace, enqueue=lambda ids: None):
    namespace['render']({title!r})
"""
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception
    assert app.title[0].value == title


@pytest.mark.parametrize("title", ["Market Data", "S&P Relative", "Recession", "Bear Market"])
def test_page_with_saved_observations(title, tmp_path, monkeypatch):
    import numpy as np
    import pandas as pd
    from sqlalchemy import create_engine

    from src.database import store
    from src.registry import BY_ID

    engine = create_engine("sqlite:///" + str(tmp_path / "fixtures.db"))
    monkeypatch.setattr(store, "engine", engine)
    store.initialize()
    for key in ["SP500", "DGS2", "DGS5", "DGS10", "DGS30", "DCOILWTICO", "UNRATE"]:
        # Synthetic values exist exclusively in this isolated test database.
        values = pd.Series(
            np.linspace(100, 120, 400), index=pd.date_range("2023-01-01", periods=400)
        )
        store.save(BY_ID[key], values)
    script = f"""from unittest.mock import patch
import runpy
with patch('streamlit.navigation'), patch('src.refresh.enqueue'):
    namespace = runpy.run_path({str(ROOT / "dashboard/app.py")!r})
with patch.dict(namespace, enqueue=lambda ids: None):
    namespace['render']({title!r})
"""
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception
    assert len(app.get("plotly_chart")) >= 1
