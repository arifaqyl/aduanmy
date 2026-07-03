import io
import zipfile
from pathlib import Path

from app.collectors.gtfs.anomaly import detect_route_anomalies
from app.collectors.gtfs.static_client import parse_routes_from_zip
from app.pipeline.bus_alerts import parse_myrapid_official


SAMPLE_ROUTES_CSV = """route_id,route_short_name,route_long_name,route_type
r1,300,Terminal Maluri ~ Lebuh Ampang,3
r2,450,Hentian Kajang ~ Hab Lebuh Pudu,3
"""

SAMPLE_TRIPS_CSV = """route_id,service_id,trip_id
r1,daily,t1
r1,daily,t2
r2,daily,t3
"""


def _make_zip(tmp_path: Path) -> Path:
    path = tmp_path / "rapid-bus-kl.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("routes.txt", SAMPLE_ROUTES_CSV)
        zf.writestr("trips.txt", SAMPLE_TRIPS_CSV)
    path.write_bytes(buf.getvalue())
    return path


def test_parse_routes_from_zip(tmp_path):
    zip_path = _make_zip(tmp_path)
    routes = parse_routes_from_zip("rapid-bus-kl", zip_path)
    assert len(routes) == 2
    assert routes[0]["route_short_name"] == "300"
    assert routes[0]["trip_count"] == 2


def test_detect_route_anomalies_with_mock(monkeypatch):
    from app.db.gtfs_store import upsert_routes

    upsert_routes(
        [
            {
                "network": "rapid-bus-kl",
                "route_id": "r1",
                "route_short_name": "300",
                "route_long_name": "Maluri",
                "trip_count": 100,
                "mode": "bus",
                "state": "Wilayah Persekutuan",
            }
        ]
    )
    monkeypatch.setattr(
        "app.collectors.gtfs.anomaly.fetch_all_bus_vehicle_counts",
        lambda: {"rapid-bus-kl": __import__("collections").Counter({"r2": 3})},
    )
    monkeypatch.setattr("app.collectors.gtfs.anomaly._in_service_window", lambda: True)
    rows = detect_route_anomalies()
    assert rows
    assert rows[0]["source_platform"] == "gtfs_rt"
    assert rows[0]["entity"] == "300"


def test_parse_myrapid_penang_bus():
    parsed = parse_myrapid_official("Kelewatan Bas Rapid Penang di Butterworth")
    assert parsed["entity"] == "Penang Rapid"
    assert parsed["state"] == "Penang"
