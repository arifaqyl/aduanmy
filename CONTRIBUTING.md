# Contributing

## Current State

This repo is still in progress.
Prefer small, evidence-backed changes over broad rewrites.

## Setup

```bash
pip install -e .[dev]
python -m pytest tests -q
```

Optional:

```bash
pip install playwright
playwright install chromium
```

Playwright improves timestamp extraction and some public-page collection paths, but the core repo should still degrade safely without it.

## Working Rules

- keep collector changes narrow
- prefer exact-source verification over broad scraping claims
- do not add credentials, cookies, or personal tokens
- keep official sources clearly separated from crowd signals
- add or update tests with behavior changes

## Validation

Before opening a PR or push:

```bash
python -m pytest tests -q
python scripts/run_snapshot.py
```

If a source is blocked, document the limitation instead of faking completeness.
