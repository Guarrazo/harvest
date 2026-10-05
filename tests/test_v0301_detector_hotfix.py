from pathlib import Path

SOURCE = Path(__file__).parents[1] / "src" / "ncig" / "city_index_detect.py"
TEXT = SOURCE.read_text(encoding="utf-8")


def test_hotfix_is_syntax_ready_and_versioned():
    assert 'VERSION = "0.30.1"' in TEXT
    assert 'HEARTBEAT_EVERY = 100' in TEXT


def test_spatial_window_is_not_overexpanded():
    assert 'int(math.ceil(radius_m / CELL_SIZE_M)) + 1' not in TEXT
    assert 'int(math.ceil(radius / CELL_SIZE_M)) + 1' not in TEXT


def test_exact_filter_precedes_sort():
    filter_pos = TEXT.index('filtered = [')
    sort_pos = TEXT.index('filtered.sort', filter_pos)
    assert filter_pos < sort_pos
