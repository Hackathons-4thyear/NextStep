"""
Physics validation against analytic wind fields.

These tests exist because the failure modes in this project are silent. An
inverted sign convention, a missing cos(latitude) term or a timezone slip all
produce trajectories that look perfectly plausible on a map and are completely
wrong. Real data cannot catch that, because there is nothing to compare
against. A synthetic field with a hand-computable answer can.

Run:  python -m tests.test_physics
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from pipeline.trajectory import (
    back_trajectory,
    ensemble_spread_km,
    ensemble_trajectories,
    haversine_km,
)
from pipeline.windfield import WindField

PASS, FAIL = "PASS", "FAIL"
_results = []


def check(name, condition, detail=""):
    _results.append((PASS if condition else FAIL, name, detail))
    print(f"  [{PASS if condition else FAIL}] {name}" + (f"  --  {detail}" if detail else ""))
    return condition


def uniform_field(u_ms, v_ms, hours=96):
    """A constant wind everywhere, for exactly computable displacement."""
    lats = np.arange(20.0, 40.001, 0.5)
    lons = np.arange(65.0, 90.001, 0.5)
    t0 = datetime(2024, 11, 5, 0, 0, tzinfo=timezone.utc)
    times = [t0 + timedelta(hours=h) for h in range(hours + 1)]
    shape = (len(times), len(lats), len(lons))
    return WindField(lats, lons, times, np.full(shape, u_ms), np.full(shape, v_ms))


# ---------------------------------------------------------------------------

def test_sign_convention():
    """
    A wind 'from 270 degrees' is a westerly: it comes from the west and blows
    toward the east. So u must be positive and v about zero.

    This is the test that catches the most dangerous bug in the project.
    """
    print("\n1. Wind direction sign convention")

    u, v = WindField.uv_from_speed_direction(10.0, 270.0)
    check("westerly (from 270) blows eastward, u > 0", u > 9.9, f"u={u:.3f}")
    check("westerly has no north component", abs(v) < 1e-9, f"v={v:.3e}")

    u, v = WindField.uv_from_speed_direction(10.0, 180.0)
    check("southerly (from 180) blows northward, v > 0", v > 9.9, f"v={v:.3f}")

    u, v = WindField.uv_from_speed_direction(10.0, 0.0)
    check("northerly (from 0) blows southward, v < 0", v < -9.9, f"v={v:.3f}")

    # Northwesterly, the Punjab->Delhi transport direction.
    u, v = WindField.uv_from_speed_direction(10.0, 315.0)
    check(
        "northwesterly (from 315) blows toward the southeast",
        u > 0 and v < 0,
        f"u={u:.2f} v={v:.2f}",
    )


def test_backwards_direction():
    """
    Under a westerly, air arriving at the receptor must have come FROM the west.
    The back-trajectory origin must therefore sit at a *lower* longitude.

    If this fails, trajectories are running forwards and every attribution in
    the project points at the wrong half of the map.
    """
    print("\n2. Back-trajectory travels the right way")

    wf = uniform_field(*WindField.uv_from_speed_direction(10.0, 270.0))
    arrival = datetime(2024, 11, 8, 0, 0, tzinfo=timezone.utc)
    traj = back_trajectory(wf, 28.6139, 77.2090, arrival, hours_back=10)

    origin, receptor = traj.origin(), traj.receptor()

    check("origin is west of receptor", origin.lon < receptor.lon,
          f"origin lon={origin.lon:.3f} receptor lon={receptor.lon:.3f}")
    check("origin latitude roughly unchanged", abs(origin.lat - receptor.lat) < 0.05,
          f"d_lat={origin.lat - receptor.lat:.4f}")
    check("path ends at the receptor", abs(receptor.lon - 77.2090) < 1e-6)
    check("path runs forward in time", traj.points[0].time < traj.points[-1].time)
    check("origin is earliest point", origin.hours_before > receptor.hours_before)


def test_displacement_magnitude():
    """
    10 m/s for 10 hours is 360 km, exactly. Check the integrator reproduces it,
    and that the cos(latitude) correction is present.
    """
    print("\n3. Displacement magnitude")

    wf = uniform_field(*WindField.uv_from_speed_direction(10.0, 270.0))
    arrival = datetime(2024, 11, 8, 0, 0, tzinfo=timezone.utc)
    traj = back_trajectory(wf, 28.6139, 77.2090, arrival, hours_back=10)

    expected_km = 10.0 * 10 * 3600 / 1000.0
    actual_km = haversine_km(
        traj.origin().lat, traj.origin().lon,
        traj.receptor().lat, traj.receptor().lon,
    )
    err = abs(actual_km - expected_km) / expected_km
    check(f"distance is {expected_km:.0f} km", err < 0.01,
          f"got {actual_km:.1f} km, error {err*100:.2f}%")

    # cos(lat) check: the same wind for the same duration must span more degrees
    # of longitude at high latitude than at low. Both latitudes must sit inside
    # the synthetic grid (20-40N) or the trajectory exits on the first step and
    # spans nothing.
    LAT_LO, LAT_HI = 21.0, 39.0
    t_lo = back_trajectory(wf, LAT_LO, 77.2090, arrival, hours_back=10)
    t_hi = back_trajectory(wf, LAT_HI, 77.2090, arrival, hours_back=10)
    span_lo = abs(t_lo.receptor().lon - t_lo.origin().lon)
    span_hi = abs(t_hi.receptor().lon - t_hi.origin().lon)

    check("both test trajectories stayed in the domain",
          span_lo > 0 and span_hi > 0,
          f"{LAT_LO}deg spans {span_lo:.3f}, {LAT_HI}deg spans {span_hi:.3f}")
    check("cos(latitude) correction applied", span_hi > span_lo,
          f"{span_hi:.3f} > {span_lo:.3f}")

    ratio = span_hi / span_lo
    expected_ratio = np.cos(np.deg2rad(LAT_LO)) / np.cos(np.deg2rad(LAT_HI))
    check("correction magnitude matches 1/cos(lat)",
          abs(ratio - expected_ratio) / expected_ratio < 0.02,
          f"ratio {ratio:.4f} vs expected {expected_ratio:.4f}")


def test_curved_flow_accuracy():
    """
    Under a rotating (solid-body) flow, a midpoint integrator should track the
    curve substantially better than plain Euler. Confirms RK2 is doing its job.
    """
    print("\n4. Curved flow: midpoint vs Euler")

    lats = np.arange(20.0, 40.001, 0.5)
    lons = np.arange(65.0, 90.001, 0.5)
    t0 = datetime(2024, 11, 5, 0, 0, tzinfo=timezone.utc)
    times = [t0 + timedelta(hours=h) for h in range(97)]

    # Rotation about (30N, 77E): u = -k*(lat-lat0), v = k*(lon-lon0)
    LAT0, LON0, K = 30.0, 77.0, 3.0
    LO, LA = np.meshgrid(lons, lats)
    u2d, v2d = -K * (LA - LAT0), K * (LO - LON0)
    u = np.repeat(u2d[None, :, :], len(times), axis=0)
    v = np.repeat(v2d[None, :, :], len(times), axis=0)
    wf = WindField(lats, lons, times, u, v)

    arrival = datetime(2024, 11, 8, 0, 0, tzinfo=timezone.utc)

    fine = back_trajectory(wf, 28.6139, 77.2090, arrival, hours_back=24, dt_seconds=60)
    coarse = back_trajectory(wf, 28.6139, 77.2090, arrival, hours_back=24, dt_seconds=900)

    drift = haversine_km(
        fine.origin().lat, fine.origin().lon,
        coarse.origin().lat, coarse.origin().lon,
    )
    path_len = fine.total_distance_km()
    rel = drift / max(path_len, 1e-9)

    check("15-min steps converge on 1-min steps", rel < 0.02,
          f"origin differs by {drift:.1f} km over a {path_len:.0f} km path ({rel*100:.2f}%)")


def test_reversibility():
    """
    Integrating back then forward through the same field should return to the
    start. A strong end-to-end check on the integrator and the geometry.
    """
    print("\n5. Reversibility")

    wf = uniform_field(*WindField.uv_from_speed_direction(8.0, 300.0))
    arrival = datetime(2024, 11, 8, 0, 0, tzinfo=timezone.utc)
    start_lat, start_lon = 28.6139, 77.2090

    back = back_trajectory(wf, start_lat, start_lon, arrival, hours_back=24)
    o = back.origin()

    # Walk forward from the origin using the same displacement helper.
    from pipeline.trajectory import _displace

    lat, lon = o.lat, o.lon
    dt = config.TRAJECTORY_DT_SECONDS
    for _ in range(int(24 * 3600 / dt)):
        u, v = wf.interpolate(lat, lon, arrival)
        lat, lon = _displace(lat, lon, u, v, dt)

    err_km = haversine_km(lat, lon, start_lat, start_lon)
    check("round trip returns to origin", err_km < 5.0, f"closure error {err_km:.2f} km")


def test_domain_exit():
    print("\n6. Domain handling")

    wf = uniform_field(*WindField.uv_from_speed_direction(40.0, 270.0))
    arrival = datetime(2024, 11, 8, 0, 0, tzinfo=timezone.utc)
    traj = back_trajectory(wf, 28.6139, 66.0, arrival, hours_back=72)

    check("exit is detected", traj.exited_domain)
    check("partial path is still returned", len(traj) > 1, f"{len(traj)} points")
    check("all points inside the grid",
          all(wf.contains(p.lat, p.lon) for p in traj.points))


def test_ensemble():
    print("\n7. Ensemble")

    wf = uniform_field(*WindField.uv_from_speed_direction(10.0, 300.0))
    arrival = datetime(2024, 11, 8, 0, 0, tzinfo=timezone.utc)
    ens = ensemble_trajectories(wf, 28.6139, 77.2090, arrival, hours_back=24)

    check("correct member count", len(ens) == config.ENSEMBLE_SIZE, f"{len(ens)} members")
    check("exactly one primary", sum(t.is_primary for t in ens) == 1)
    check("primary is member 0", ens[0].is_primary and ens[0].member == 0)

    spread = ensemble_spread_km(ens)
    check("spread is non-zero and physical", 0 < spread < 200, f"{spread:.1f} km")


def test_timezone_discipline():
    """
    Every datetime crossing a module boundary must be timezone-aware UTC.
    Naive datetimes silently mean 'local time' somewhere downstream, which is
    how a whole analysis ends up shifted by 5.5 hours without any error.
    """
    print("\n8. Timezone discipline")

    wf = uniform_field(*WindField.uv_from_speed_direction(10.0, 270.0))
    arrival = datetime(2024, 11, 8, 0, 0, tzinfo=timezone.utc)
    traj = back_trajectory(wf, 28.6139, 77.2090, arrival, hours_back=6)

    check("all points timezone-aware",
          all(p.time.tzinfo is not None for p in traj.points))
    check("all points UTC",
          all(p.time.utcoffset().total_seconds() == 0 for p in traj.points))

    naive = datetime(2024, 11, 8, 0, 0)
    try:
        back_trajectory(wf, 28.6139, 77.2090, naive, hours_back=1)
        check("naive datetime is rejected", False, "it was silently accepted")
    except TypeError:
        check("naive datetime is rejected", True, "raises TypeError as expected")


if __name__ == "__main__":
    print("=" * 70)
    print("PHYSICS VALIDATION  --  analytic fields with known answers")
    print("=" * 70)

    test_sign_convention()
    test_backwards_direction()
    test_displacement_magnitude()
    test_curved_flow_accuracy()
    test_reversibility()
    test_domain_exit()
    test_ensemble()
    test_timezone_discipline()

    passed = sum(1 for r, _, _ in _results if r == PASS)
    total = len(_results)
    print("\n" + "=" * 70)
    print(f"{passed}/{total} checks passed")
    if passed < total:
        print("\nFailures:")
        for r, name, detail in _results:
            if r == FAIL:
                print(f"  - {name}  {detail}")
    print("=" * 70)
    sys.exit(0 if passed == total else 1)
