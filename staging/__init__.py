"""Staging: raw -> staging transforms. Reads ``data/raw/<source>/...``, does
per-source cleaning (type coercion, dedup, basic validation), and writes
``data/staging/<source_table>/...`` partitioned by season (and week where it
applies). A partition is never modified after a successful run — re-stage by
overwriting it wholesale.
"""
