"""Every panel must render without a template error, for every ticker it can show."""

import pytest

from app.data.mock import SYMBOLS
from app.main import render_panel


@pytest.mark.parametrize("fn", ["WATCH", "N", "ECO", "MOV"])
def test_tickerless_panels_render(fn):
    html = render_panel(0, fn, "", "")
    assert f'data-fn="{fn}"' in html


@pytest.mark.parametrize("fn", ["GP", "DES"])
@pytest.mark.parametrize("sym", list(SYMBOLS))
def test_ticker_panels_render(fn, sym):
    assert f'data-sym="{sym}"' in render_panel(0, fn, sym, "1D")


def test_unknown_panel_falls_back():
    assert 'data-fn="WATCH"' in render_panel(0, "NOPE", "", "")


def test_chart_has_a_path():
    html = render_panel(0, "GP", "AAPL", "1Y")
    assert 'class="line"' in html and "M" in html
