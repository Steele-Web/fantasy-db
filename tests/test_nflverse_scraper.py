"""nflverse scraper: read-expression building, URL shape, and run() dispatch."""

import scrapers.nflverse as nflverse
from scrapers.nflverse import _BY_NAME, DATASETS, Dataset, _read_expr, run


def _dataset(name: str) -> Dataset:
    return _BY_NAME[name]


def test_by_name_index_covers_every_dataset():
    assert set(_BY_NAME) == {d.name for d in DATASETS}


def test_read_expr_picks_reader_by_format():
    csv_ds = _dataset("schedules")  # fmt == "csv"
    pq_ds = _dataset("players")  # fmt == "parquet"
    assert "read_csv_auto(" in _read_expr(csv_ds, "http://x/y.csv")
    assert "read_parquet(" in _read_expr(pq_ds, "http://x/y.parquet")
    # Both lean on union_by_name so schema drift across seasons doesn't break reads.
    assert "union_by_name = true" in _read_expr(pq_ds, "http://x/y.parquet")


def test_per_season_url_includes_year():
    url = _dataset("player_stats").url(2023)
    assert "player_stats_2023.parquet" in url


def test_run_reports_unknown_datasets_without_crashing(capsys, monkeypatch):
    # Stub the network call: every requested dataset "succeeds".
    monkeypatch.setattr(nflverse, "scrape_dataset", lambda ds, yrs: (1, 1))
    failures = run(["players", "not_a_dataset"], season_list=[2023])
    err = capsys.readouterr().err
    assert "unknown nflverse dataset: not_a_dataset" in err
    # The unknown name is skipped, not counted as a scrape failure.
    assert failures == 0


def test_run_counts_scrape_failures(monkeypatch):
    def boom(ds, yrs):
        raise RuntimeError("network down")

    monkeypatch.setattr(nflverse, "scrape_dataset", boom)
    assert run(["players", "schedules"], season_list=[2023]) == 2


def test_run_with_no_names_targets_all_datasets(monkeypatch):
    seen = []
    monkeypatch.setattr(nflverse, "scrape_dataset", lambda ds, yrs: seen.append(ds.name) or (0, 0))
    run(None, season_list=[2023])
    assert seen == [d.name for d in DATASETS]
