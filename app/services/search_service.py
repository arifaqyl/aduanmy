"""Full-text incident search.

Searches the rider-signal rows already in the DB and returns matching
*incidents* (clusters) — never raw signal text. This respects the public
redaction model: when ``expose_raw_sources`` is False (prod default) the
response only carries the same public_cluster fields the board already shows,
plus a ``matched_signals`` count. No author handles or raw posts are leaked.
"""
from __future__ import annotations

from app.db.session import connect, init_db
from app.services.incident_service import list_clusters
from app.services.public_incident_service import public_cluster

MIN_QUERY_LEN = 2
MAX_QUERY_LEN = 80


def search_incidents(query: str, *, limit: int = 20) -> dict:
    q = (query or "").strip()
    if len(q) < MIN_QUERY_LEN:
        return {"query": query or "", "total": 0, "items": []}
    q = q[:MAX_QUERY_LEN]
    like = f"%{q.lower()}%"

    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT cluster_id, COUNT(*) AS matched
            FROM complaints
            WHERE source_platform != 'official'
              AND (LOWER(normalized_text) LIKE ?
                   OR LOWER(entity) LIKE ?
                   OR LOWER(location) LIKE ?
                   OR LOWER(state) LIKE ?)
            GROUP BY cluster_id
            ORDER BY matched DESC
            LIMIT ?
            """,
            (like, like, like, like, max(limit, 1) * 4),
        ).fetchall()

    matches = {row["cluster_id"]: int(row["matched"]) for row in rows}
    if not matches:
        return {"query": query or "", "total": 0, "items": []}

    clusters = list_clusters()
    items = []
    for cluster in clusters:
        matched = matches.get(cluster["cluster_id"])
        if not matched:
            continue
        pub = public_cluster(cluster)
        pub["matched_signals"] = matched
        items.append(pub)
    items.sort(key=lambda c: c.get("matched_signals", 0), reverse=True)
    return {"query": query or "", "total": len(matches), "items": items[:limit]}
