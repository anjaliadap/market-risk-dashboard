"""WCAG color-pair checks and presentation-only regression coverage."""

import copy
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard.styles import theme


def luminance(color):
    rgb = [int(color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))


def contrast(foreground, background):
    low, high = sorted((luminance(foreground), luminance(background)))
    return (high + 0.05) / (low + 0.05)


PAIRS = [
    (theme.TEXT, theme.BACKGROUND),
    (theme.TEXT, theme.SURFACE),
    (theme.MUTED, theme.SURFACE),
    (theme.MUTED, theme.BACKGROUND),
    ("#FFFFFF", theme.CONFIG["primaryColor"]),
    (theme.CONFIG["sidebar"]["textColor"], theme.CONFIG["sidebar"]["backgroundColor"]),
    (theme.CONFIG["sidebar"]["textColor"], theme.CONFIG["sidebar"]["secondaryBackgroundColor"]),
    (theme.CONFIG["dataframeHeaderTextColor"], theme.CONFIG["dataframeHeaderBackgroundColor"]),
    *[
        (theme.CONFIG[c + "TextColor"], theme.CONFIG[c + "BackgroundColor"])
        for c in ("green", "red", "yellow", "orange", "blue", "violet", "gray")
    ],
    *[(t.accent, t.soft) for t in theme.THEMES.values()],
    *[(c, theme.SURFACE) for c in theme.PALETTE],
]


@pytest.mark.parametrize(("foreground", "background"), PAIRS)
def test_text_pairs_meet_wcag_aa(foreground, background):
    assert contrast(foreground, background) >= 4.5


def test_theme_locked_light_and_no_global_native_color_overrides():
    assert theme.CONFIG["base"] == "light"
    assert "light" not in theme.CONFIG and "dark" not in theme.CONFIG
    css = (Path(theme.__file__).parent / "institutional.css").read_text()
    for forbidden in (".stApp", "!important", "button {", "h1, h2", ".st-emotion"):
        assert forbidden not in css


def test_plotly_styles_preserve_values_units_and_identity_colors():
    fig = go.Figure(
        [
            go.Scatter(x=[1, 2], y=[0.1, 0.2], name="Revenue"),
            go.Bar(x=[1, 2], y=[3, 4], name="Capex"),
        ]
    )
    fig.update_yaxes(tickformat=".0%")
    original = copy.deepcopy([list(trace.y) for trace in fig.data])
    theme.style_figure(fig)
    assert original == [list(trace.y) for trace in fig.data]
    assert fig.layout.yaxis.tickformat == ".0%"
    assert fig.layout.font.color == theme.TEXT
    assert fig.layout.xaxis.tickfont.color == theme.TEXT
    assert fig.layout.yaxis.tickfont.color == theme.TEXT
    assert fig.layout.legend.font.color == theme.TEXT
    assert fig.layout.hoverlabel.font.color == theme.TEXT
    assert fig.layout.hoverlabel.bgcolor == theme.SURFACE
    assert fig.data[0].line.color == theme.series_color("Revenue")
    assert fig.data[1].marker.color == theme.series_color("Capex")


def test_semantic_heatmaps_keep_signs_without_changing_values():
    from streamlit.testing.v1 import AppTest

    script = """import pandas as pd
from dashboard.styles.theme import financial_table
financial_table(pd.DataFrame({'1M': [1.25, -2.5, 0.0]}))
"""
    app = AppTest.from_string(script).run()
    assert not app.exception
    pd.testing.assert_frame_equal(app.dataframe[0].value, pd.DataFrame({"1M": [1.25, -2.5, 0.0]}))


def test_workbook_table_flags_and_heatmap_are_readable():
    from dashboard.excel_views import table_frame

    table = {
        "id": "market_snapshot",
        "display_columns": [("B", "Metric"), ("E", "YTD")],
        "rows": [
            [
                {"cell": "B4", "value": "Index", "format": "General"},
                {"cell": "E4", "value": 0.125, "format": "0.0%"},
            ]
        ],
    }
    styled = table_frame(table)
    assert styled.data.loc[0, "YTD"] == "+12.5%"
    html = styled.to_html()
    assert theme.POSITIVE.lower() in html.lower()
    assert theme.POSITIVE_BG.lower() in html.lower()
