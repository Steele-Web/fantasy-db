"""The draft tool: value-over-replacement and tiering — all DB-free.

``load_projections`` touches DuckDB; the board math (starter allocation, flex
greed, replacement levels, VOR, tiers) is pure over ``PlayerProj`` dataclasses,
so it's exercised here without a database.
"""

from apps.draft_tool import board
from apps.draft_tool.board import PlayerProj
from apps.draft_tool.cli import _filter_position, _parse_args

# A 12-team league that starts 1QB/2RB/2WR/1TE/1FLEX (RB/WR/TE).
ROSTER = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DST": 1, "BENCH": 6}
TEAMS = 12


def _players(position: str, n: int, top: float, step: float = 5.0) -> list[PlayerProj]:
    """``n`` players at ``position`` with points stepping down from ``top``."""
    return [PlayerProj(f"{position}{i}", position, top - i * step) for i in range(n)]


# --- starter counts & flex allocation ------------------------------------


def test_base_starter_counts_scale_with_team_count():
    pools = {pos: [] for pos in board.VBD_POSITIONS}
    counts = board.starter_counts({"QB": 1, "RB": 2, "WR": 2, "TE": 1}, TEAMS, pools)
    assert counts == {"QB": 12, "RB": 24, "WR": 24, "TE": 12}


def test_flex_slots_go_to_the_most_valuable_eligible_position():
    # 1-team league: 1 RB + 1 WR + 1 FLEX. The flex should land on whichever of the
    # next RB/WR is more valuable. Make WR3 (the 3rd-best WR) beat RB2.
    pools = {"RB": [100.0, 50.0], "WR": [120.0, 110.0, 90.0], "TE": [], "QB": []}
    counts = board.starter_counts({"RB": 1, "WR": 1, "FLEX": 1}, 1, pools)
    # base: RB1, WR1. flex candidates: RB[1]=50 vs WR[1]=110 -> WR wins.
    assert counts["WR"] == 2
    assert counts["RB"] == 1


def test_flex_stops_when_eligible_pool_is_exhausted():
    pools = {"RB": [100.0], "WR": [], "TE": [], "QB": []}
    counts = board.starter_counts({"RB": 1, "FLEX": 3}, 1, pools)
    # Only one RB exists and he's already a base starter; flex can't be filled.
    assert counts["RB"] == 1


def test_superflex_can_draw_a_quarterback_into_flex():
    pools = {"QB": [300.0, 280.0], "RB": [100.0], "WR": [], "TE": []}
    counts = board.starter_counts({"QB": 1, "RB": 1, "SUPERFLEX": 1}, 1, pools)
    # SUPERFLEX candidates: QB[1]=280 vs RB[1]=missing -> QB.
    assert counts["QB"] == 2


# --- replacement levels --------------------------------------------------


def test_replacement_level_is_the_first_non_starter():
    pools = {"QB": [300.0, 280.0, 260.0, 240.0]}
    # 2 starters -> replacement is the 3rd-best QB (index 2).
    levels = board.replacement_levels(pools, {"QB": 2})
    assert levels["QB"] == 260.0


def test_replacement_falls_back_to_last_player_when_pool_too_shallow():
    pools = {"TE": [100.0, 80.0]}
    levels = board.replacement_levels(pools, {"TE": 5})
    assert levels["TE"] == 80.0


def test_replacement_is_zero_for_empty_pool():
    assert board.replacement_levels({"K": []}, {"K": 3}) == {"K": 0.0}


# --- VOR board -----------------------------------------------------------


def test_vor_is_points_above_positional_replacement():
    # 1-team league: 1QB, 1RB. Replacement = the 2nd-best at each position.
    projections = [
        PlayerProj("qb1", "QB", 300.0),
        PlayerProj("qb2", "QB", 250.0),  # replacement QB
        PlayerProj("rb1", "RB", 200.0),
        PlayerProj("rb2", "RB", 120.0),  # replacement RB
    ]
    board_entries = board.build_board(projections, {"QB": 1, "RB": 1}, 1)
    by_id = {e.player_id: e for e in board_entries}
    assert by_id["qb1"].vor == 50.0  # 300 - 250
    assert by_id["rb1"].vor == 80.0  # 200 - 120
    # Despite fewer raw points, the RB has more value over replacement -> ranks 1st.
    assert by_id["rb1"].overall_rank == 1
    assert by_id["qb1"].overall_rank == 2


def test_board_marks_leaguewide_starters_and_position_ranks():
    # Only WRs on the board, so every one of the 12 flex slots lands on WR:
    # 2 WR * 12 = 24 base starters + 12 flex = 36 WR starters.
    projections = _players("WR", 45, top=300.0)
    entries = board.build_board(projections, ROSTER, TEAMS)
    wrs = sorted((e for e in entries if e.position == "WR"), key=lambda e: e.position_rank)
    assert wrs[0].position_rank == 1
    starters = [e for e in wrs if e.starter]
    assert len(starters) == 36
    assert all(s.position_rank <= 36 for s in starters)
    assert not wrs[-1].starter  # the 45th WR isn't a starter


def test_empty_projection_list_yields_empty_board():
    assert board.build_board([], ROSTER, TEAMS) == []


# --- tiers ---------------------------------------------------------------


def test_tiers_break_on_a_vor_cliff_within_a_position():
    # Three tight RBs, a cliff, then two more: expect a tier break at the cliff.
    entries = [
        board.BoardEntry("a", "RB", 0, 0, 0, vor=100.0),
        board.BoardEntry("b", "RB", 0, 0, 0, vor=98.0),
        board.BoardEntry("c", "RB", 0, 0, 0, vor=96.0),
        board.BoardEntry("d", "RB", 0, 0, 0, vor=60.0),  # cliff
        board.BoardEntry("e", "RB", 0, 0, 0, vor=58.0),
    ]
    board.assign_tiers(entries, tier_factor=2.0)
    assert [e.tier for e in entries] == [1, 1, 1, 2, 2]


def test_tiers_are_independent_per_position():
    # RBs have a cliff after the third; WRs step down uniformly. Interleaved by VOR
    # so a cross-position tiering would mingle them — per-position tiering must not.
    entries = [
        board.BoardEntry("r1", "RB", 0, 0, 0, vor=100.0),
        board.BoardEntry("w1", "WR", 0, 0, 0, vor=99.0),
        board.BoardEntry("r2", "RB", 0, 0, 0, vor=98.0),
        board.BoardEntry("w2", "WR", 0, 0, 0, vor=97.0),
        board.BoardEntry("r3", "RB", 0, 0, 0, vor=96.0),
        board.BoardEntry("w3", "WR", 0, 0, 0, vor=95.0),
        board.BoardEntry("r4", "RB", 0, 0, 0, vor=50.0),  # RB cliff
    ]
    board.assign_tiers(entries, tier_factor=2.0)
    by_id = {e.player_id: e.tier for e in entries}
    assert [by_id[k] for k in ("r1", "r2", "r3", "r4")] == [1, 1, 1, 2]  # cliff splits RBs
    assert [by_id[k] for k in ("w1", "w2", "w3")] == [1, 1, 1]  # WRs stay together


def test_uniform_gaps_stay_one_tier():
    entries = [board.BoardEntry(str(i), "RB", 0, 0, 0, vor=100.0 - 5 * i) for i in range(5)]
    board.assign_tiers(entries, tier_factor=2.0)
    assert {e.tier for e in entries} == {1}


# --- CLI -----------------------------------------------------------------


def test_parse_args_defaults():
    args = _parse_args([])
    assert args.source == "my_model_v1"
    assert args.limit == 50
    assert args.tier_factor == 2.0
    assert args.position is None


def test_filter_position_flex_includes_rb_wr_te_only():
    entries = [
        board.BoardEntry("q", "QB", 0, 0, 0, vor=10.0),
        board.BoardEntry("r", "RB", 0, 0, 0, vor=10.0),
        board.BoardEntry("w", "WR", 0, 0, 0, vor=10.0),
        board.BoardEntry("t", "TE", 0, 0, 0, vor=10.0),
    ]
    flex = {e.position for e in _filter_position(entries, "flex")}
    assert flex == {"RB", "WR", "TE"}
    assert {e.position for e in _filter_position(entries, "qb")} == {"QB"}
