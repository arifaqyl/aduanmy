# Security Policy

## Status

TrafficMY is a **production** public transport pulse. Treat rider signals as early evidence, not operator confirmation.

## Reporting

If you find a security issue, do not open a public issue with exploit details.

Contact: [hello@arifaqyl.me](mailto:hello@arifaqyl.me)

Include:
- affected file or route
- reproduction steps
- impact
- whether secrets, data exposure, or remote execution is involved

## Scope

Priority areas:
- scraper input handling and SSRF-style fetch paths
- refresh/admin routes and API-key enforcement
- accidental credential or session leakage in commits or artifacts
- unsafe trust assumptions on crowd or official-source text
- Docker/nginx deployment misconfiguration

## Secret Handling

- Never commit `.env`, vault files, or browser session exports
- Never commit local SQLite runtime databases
- Keep `ADUANMY_THREADS_SESSION_PATH` owner-only on the server volume
- Public APIs must not expose raw post text or usernames

## Dependency Review

Production dependencies are pinned in `requirements.production.txt`. Run `pip-audit -r requirements.production.txt` before releases.
