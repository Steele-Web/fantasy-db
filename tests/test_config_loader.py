"""The YAML loader: caching, error handling, and the league/scoring accessors."""

import pytest

import config
from config import load_yaml


def test_load_yaml_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_yaml("does_not_exist")


def test_load_yaml_caches_by_name():
    # @cache means repeated calls return the very same object.
    assert load_yaml("scoring") is load_yaml("scoring")


def test_leagues_config_is_well_formed():
    cfg = config.leagues()
    assert cfg["leagues"], "expected at least one league"
    first = cfg["leagues"][0]
    assert {"id", "scoring_format", "roster"} <= set(first)


def test_every_league_scoring_format_exists_in_scoring():
    formats = set(config.scoring())
    for lg in config.leagues()["leagues"]:
        assert lg["scoring_format"] in formats, (
            f"league {lg['id']} references unknown scoring_format {lg['scoring_format']!r}"
        )
