# Security Policy

## Status

This repository is an in-progress research and product-shaping build.
Do not treat current outputs as authoritative public safety alerts.

## Reporting

If you find a security issue, do not open a public issue with exploit details.

Contact:
- `hello@arifaqyl.me`

Include:
- affected file or route
- reproduction steps
- impact
- whether secrets, data exposure, or remote execution is involved

## Scope Notes

Current areas worth checking:
- scraper input handling
- report generation paths
- GitHub Actions workflow behavior
- accidental credential leakage in committed artifacts
- unsafe assumptions around public-source trust

## Secret Handling

- Never commit `.env`
- Never commit vault files or local secret stores
- Never commit local SQLite runtime databases
- Public social and official-source evidence may be committed only in sanitized derived reports
