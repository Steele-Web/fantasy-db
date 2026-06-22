"""Draft tool (``fdb-draft``).

Rank/tier available players for a league (``config/leagues.yaml``) by **value over
replacement** — projected points priced against the best player at each position
left once the league's starting slots are filled — so cross-position draft value
is comparable. The board logic lives in :mod:`apps.draft_tool.board`; the CLI in
:mod:`apps.draft_tool.cli`. Reads marts + dimensions only.
"""
