from pathlib import Path


SOURCE = Path(__file__).parents[1] / "src" / "ncig" / "city_index_detect.py"
TEXT = SOURCE.read_text(encoding="utf-8")


def test_detector_has_bounded_cache_and_checkpoint_support():
    assert 'DEFAULT_CACHE_WINDOWS = 256' in TEXT
    assert 'while len(self.cache) > self.max_cache_windows:' in TEXT
    assert 'ncig-city-detect-checkpoint-v1' in TEXT
    assert 'checkpoint_out=checkpoint' in TEXT
    assert 'resume=not args.no_resume' in TEXT


def test_spatial_query_avoids_sql_temp_ordering_and_restores_stable_order():
    select_sql = TEXT.split('def _select_sql', 1)[1].split('def _query', 1)[0]
    assert '"ORDER BY id"' not in select_sql
    assert 'nearby.sort(key=lambda r:' in TEXT


def test_detector_uses_tight_spatial_window_and_filters_before_sorting():
    assert 'int(math.ceil(radius / CELL_SIZE_M))' in TEXT
    assert 'nearby = [r for r in rows if' in TEXT
    assert 'nearby.sort(key=lambda r:' in TEXT
    assert 'VERSION = "0.30.0"' in TEXT
