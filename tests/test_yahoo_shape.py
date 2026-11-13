"""The adapter's pure parts: turning yfinance frames into our shapes, offline."""

import pandas as pd

from app.data import yahoo


def test_single_symbol_frame():
    df = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [100]},
        index=pd.to_datetime(["2026-11-10"]),
    )
    candles = yahoo._candles_from(df)
    assert len(candles) == 1
    assert candles[0].close == 1.5 and candles[0].volume == 100
    assert candles[0].t > 0


def test_batch_frame_is_split_by_ticker():
    cols = pd.MultiIndex.from_product([["AAPL", "MSFT"], ["Open", "Close"]])
    df = pd.DataFrame([[1, 1, 2, 2]], columns=cols)
    assert list(yahoo._sub(df, "AAPL").columns) == ["Open", "Close"]
    assert yahoo._sub(df, "NOPE") is None


def test_nan_rows_are_skipped():
    df = pd.DataFrame(
        {
            "Open": [1.0, None],
            "High": [1.0, None],
            "Low": [1.0, None],
            "Close": [1.0, None],
            "Volume": [10, None],
        },
        index=pd.to_datetime(["2026-11-09", "2026-11-10"]),
    )
    assert len(yahoo._candles_from(df)) == 1


def test_batch_frame_candles_are_flattened():
    cols = pd.MultiIndex.from_product([["AAPL"], ["Open", "High", "Low", "Close", "Volume"]])
    df = pd.DataFrame(
        [[1.0, 2.0, 0.5, 1.5, 100]], columns=cols, index=pd.to_datetime(["2026-11-10"])
    )
    candles = yahoo._candles_from(df)
    assert len(candles) == 1 and candles[0].close == 1.5
