from app.services.map_geometry import (
    haversine_m,
    nearest_point_on_linestring,
    snap_coords_to_lines,
)


def test_haversine_zero_distance():
    assert haversine_m(3.14, 101.69, 3.14, 101.69) == 0.0


def test_nearest_point_on_linestring_midpoint():
    coords = [[101.0, 3.0], [101.01, 3.0]]
    lat, lon, dist = nearest_point_on_linestring(3.0, 101.005, coords)
    assert dist < 300
    assert abs(lon - 101.005) < 0.001
    assert abs(lat - 3.0) < 0.001


def test_snap_coords_to_lines_moves_off_track_stop():
    # Deliberately offset ~500m north of the Kelana Jaya corridor
    lat, lon = 3.12, 101.67
    snapped_lat, snapped_lon = snap_coords_to_lines(lat, lon, ["kelana-jaya"])
    moved = haversine_m(lat, lon, snapped_lat, snapped_lon)
    assert moved > 50
    assert moved < 2500


def test_snap_coords_to_lines_respects_max_distance():
    lat, lon = 1.0, 100.0
    snapped_lat, snapped_lon = snap_coords_to_lines(lat, lon, ["kelana-jaya"], max_snap_m=100.0)
    assert snapped_lat == lat
    assert snapped_lon == lon
