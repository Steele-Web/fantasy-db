"""Scrapers: one module per source. Each writes untouched source data into
``data/raw/<source>/...`` as Parquet and never modifies a file after writing it.

Re-scraping a partition means deleting it and running the scraper again. Nothing
downstream reads from a source's website/API directly — only from ``data/raw``.
"""
