"""The fdb-query example app's pure table-rendering helper."""

from apps.query import _print_table


def test_print_table_empty_rows(capsys):
    _print_table([])
    assert capsys.readouterr().out.strip() == "(no rows)"


def test_print_table_renders_header_and_aligned_columns(capsys):
    rows = [
        {"player": "Jefferson", "rec": 9},
        {"player": "Hill", "rec": 11},
    ]
    _print_table(rows)
    out = capsys.readouterr().out.splitlines()

    # Header, a separator rule, then one line per row.
    assert out[0].split() == ["player", "rec"]
    assert set(out[1]) <= {"-", " "}
    assert len(out) == 4
    # Column is padded to the widest value ("Jefferson").
    assert out[2].startswith("Jefferson")
    assert out[3].startswith("Hill     ")
