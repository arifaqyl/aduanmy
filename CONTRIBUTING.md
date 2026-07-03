# Contributing

## Setup

```bash
pip install -e .[dev]
python -m pytest tests -q
```

Optional for richer collection paths:

```bash
pip install playwright
playwright install chromium
```

Playwright improves timestamp extraction and some public-page collection paths, but the core repo degrades safely without it.

## Working Rules

- keep collector changes narrow and evidence-backed
- prefer exact-source verification over broad scraping claims
- do not add credentials, cookies, or personal tokens
- keep official sources clearly separated from crowd signals
- add or update tests with behavior changes
- run `pip-audit -r requirements.production.txt` when changing dependencies

## Validation

Before opening a PR or pushing to `main`:

```bash
python -m pytest tests -q
python scripts/run_snapshot.py
```

CI runs the test suite on every push and pull request.

If a source is blocked, document the limitation instead of faking completeness.

## Security

See [SECURITY.md](SECURITY.md). Do not open public issues for exploit details.
