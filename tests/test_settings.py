"""Season selection and path helpers in config.settings."""

from config.settings import _default_seasons, raw_path, seasons, staging_path


def test_default_seasons_is_five_consecutive_years():
    yrs = _default_seasons()
    assert len(yrs) == 5
    assert yrs == sorted(yrs)
    assert yrs[-1] - yrs[0] == 4


def test_seasons_env_override_is_parsed_and_sorted_order_preserved(monkeypatch):
    monkeypatch.setenv("SEASONS", "2022, 2023 ,2024")
    assert seasons() == [2022, 2023, 2024]


def test_seasons_env_drops_implausible_years(monkeypatch):
    monkeypatch.setenv("SEASONS", "1998,1999,2021")
    # 1998 predates the >= 1999 floor and is filtered out.
    assert seasons() == [1999, 2021]


def test_seasons_whitespace_only_env_yields_no_seasons(monkeypatch):
    # The `if not raw` guard treats "   " as set, so it parses to nothing rather
    # than falling back to the default — pin this edge case so it can't silently
    # change. (A whitespace SEASONS means "ingest no per-season datasets".)
    monkeypatch.setenv("SEASONS", "   ")
    assert seasons() == []


def test_seasons_empty_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SEASONS", "")
    assert seasons() == _default_seasons()


def test_seasons_unset_env_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("SEASONS", raising=False)
    assert seasons() == _default_seasons()


def test_raw_path_and_staging_path_nest_correctly():
    assert raw_path("nflverse", "players", "all.parquet").parts[-3:] == (
        "nflverse",
        "players",
        "all.parquet",
    )
    p = staging_path("nflverse_player_stats", "season=2023", "data.parquet")
    assert p.parts[-3:] == ("nflverse_player_stats", "season=2023", "data.parquet")
