from app import render


def test_line_path_shape():
    d = render.line_path([1, 3, 2], 100, 20, 1)
    assert d.startswith("M")
    assert d.count("L") == 2


def test_line_path_flat_series_does_not_divide_by_zero():
    assert render.line_path([5, 5, 5], 100, 20, 1)


def test_vol_rects_stay_in_box():
    rects = render.vol_rects([1, 5, 3], 100, 20, 1)
    assert len(rects) == 3
    for r in rects:
        assert r["x"] >= 0 and r["x"] + r["w"] <= 100.1
        assert r["y"] >= 0 and r["y"] + r["h"] <= 20.1


def test_no_negative_zero():
    assert render.signed(-0.001) == "0.00"
    assert render.signed_pct(-0.001) == "0.00%"
    assert render.signed(1.5) == "+1.50"


def test_compact():
    assert render.compact(3.44e12) == "3.44T"
    assert render.compact(1.75e9) == "1.75B"
    assert render.vol_compact(42_300_000) == "42.3M"
