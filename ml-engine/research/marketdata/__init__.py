"""Market data for the research engine (spec 3): NSE bhavcopy ingest and gap-fill,
entity linking, split/bonus adjustment (``px_idx``), quality checks, the curated
store and the point-in-time universe NSE_LIQ200.

Modules: ``bhavcopy`` (URLs, downloader, parsers), ``adjust`` (factors, index,
quality), ``store`` (raw/curated layout, ``load_panel`` and friends, CLI) and
``universe`` (``membership``).
"""
