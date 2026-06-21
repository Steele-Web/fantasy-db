"""Database access: DuckDB connections (connection.py) and the schema migration
runner (migrate.py). The marts and dimensions live in `data/fantasy.duckdb`."""

from db.connection import connect, query

__all__ = ["connect", "query"]
