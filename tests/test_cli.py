"""Target parsing and source dispatch shared by the ingest/stage CLIs."""

import scrapers.cli as ingest_cli
import staging.cli as stage_cli
from scrapers.cli import _enabled, _parse_target, run_source


def test_parse_target_plain_source_has_no_dataset_filter():
    assert _parse_target("nflverse") == ("nflverse", None)


def test_parse_target_splits_comma_separated_datasets():
    assert _parse_target("nflverse:pbp,player_stats") == (
        "nflverse",
        ["pbp", "player_stats"],
    )


def test_parse_target_drops_empty_dataset_tokens():
    # Trailing/duplicate colons shouldn't yield empty dataset names.
    assert _parse_target("nflverse:") == ("nflverse", [])
    assert _parse_target("nflverse:pbp,,") == ("nflverse", ["pbp"])


def test_staging_cli_parse_target_matches_ingest_behaviour():
    assert stage_cli._parse_target("nflverse:pbp") == ("nflverse", ["pbp"])


def test_enabled_reflects_sources_yaml():
    assert _enabled("nflverse") is True
    assert _enabled("pfr") is False
    assert _enabled("totally-unknown") is False


def test_run_source_dispatches_to_module_run(monkeypatch):
    captured = {}

    class FakeMod:
        @staticmethod
        def run(names):
            captured["names"] = names
            return 3

    monkeypatch.setattr(ingest_cli.importlib, "import_module", lambda path: FakeMod)
    rc = run_source("nflverse", ["pbp"])
    assert rc == 3
    assert captured["names"] == ["pbp"]


def test_run_source_coerces_none_result_to_zero(monkeypatch):
    class FakeMod:
        @staticmethod
        def run(names):
            return None

    monkeypatch.setattr(ingest_cli.importlib, "import_module", lambda path: FakeMod)
    assert run_source("nflverse", None) == 0
