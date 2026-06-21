"""Config files load and the nflverse registry is well-formed."""

import config
from config.settings import raw_path, seasons, staging_path
from scrapers.nflverse import DATASETS


def test_scoring_formats_have_required_keys():
    scoring = config.scoring()
    assert {"ppr", "half_ppr", "standard"} <= set(scoring)
    assert scoring["ppr"]["rec_pts"] == 1.0
    assert scoring["standard"]["rec_pts"] == 0.0


def test_sources_have_defaults_and_nflverse():
    sources = config.sources()
    assert "defaults" in sources
    assert sources["sources"]["nflverse"]["enabled"] is True


def test_seasons_are_plausible():
    yrs = seasons()
    assert yrs and all(y >= 1999 for y in yrs)


def test_nflverse_datasets_unique_and_callable():
    names = [d.name for d in DATASETS]
    assert len(names) == len(set(names))
    for d in DATASETS:
        url = d.url(2023 if d.per_season else None)
        assert url.startswith("http")


def test_path_helpers_nest_under_data():
    tail = raw_path("nflverse", "players", "all.parquet").parts[-3:]
    assert tail == ("nflverse", "players", "all.parquet")
    assert staging_path("nflverse_player_stats").name == "nflverse_player_stats"
