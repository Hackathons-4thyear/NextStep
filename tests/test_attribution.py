"""
Attribution tests.

Builds a synthetic scenario with a known correct answer: a westerly wind, a
line of real fires directly upwind of the receptor, and a set of decoy fires
that are either too far off the path or detected at the wrong time. A correct
implementation picks up the real ones and rejects every decoy.

Run:  python -m tests.test_attribution
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from pipeline.attribution import attribute_ensemble, attribute_fires, naive_baseline
from pipeline.trajectory import back_trajectory, ensemble_trajectories
from pipeline.windfield import WindField

PASS, FAIL = "PASS", "FAIL"
_results = []


def check(name, condition, detail=""):
    _results.append((PASS if condition else FAIL, name, detail))
    print(f"  [{PASS if condition else FAIL}] {name}" + (f"  --  {detail}" if detail else ""))
    return condition


ARRIVAL = datetime(2024, 11, 8, 0, 0, tzinfo=timezone.utc)
RECEPTOR_LAT, RECEPTOR_LON = 28.6139, 77.2090


def westerly_field(speed=10.0):
    lats = np.arange(20.0, 40.001, 0.5)
    lons = np.arange(65.0, 90.001, 0.5)
    t0 = datetime(2024, 11, 4, 0, 0, tzinfo=timezone.utc)
    times = [t0 + timedelta(hours=h) for h in range(120)]
    u, v = WindField.uv_from_speed_direction(speed, 270.0)
    shape = (len(times), len(lats), len(lons))
    return WindField(lats, lons, times, np.full(shape, u), np.full(shape, v))


def build_scenario():
    """
    Westerly at 10 m/s. Air arriving at the receptor at T=0 was at longitude
    L(h) roughly RECEPTOR_LON - h * 0.368 degrees h hours earlier.

    Fires placed:
      - 5 'real'      : on the path, at the time the parcel was there
      - 3 'far'       : on the path's longitude but 3 degrees north
      - 3 'wrong_time': on the path but detected 40 hours off
    """
    wf = westerly_field()
    traj = back_trajectory(wf, RECEPTOR_LAT, RECEPTOR_LON, ARRIVAL, hours_back=48)

    by_hour = {round(p.hours_before): p for p in traj.points}
    rows = []

    for h in [8, 14, 20, 26, 32]:
        p = by_hour[h]
        rows.append(dict(lat=p.lat, lon=p.lon, datetime=p.time, frp=20.0,
                         district="SourceRegion", kind="real"))

    for h in [10, 18, 24]:
        p = by_hour[h]
        rows.append(dict(lat=p.lat + 3.0, lon=p.lon, datetime=p.time, frp=100.0,
                         district="FarNorth", kind="far"))

    for h in [12, 22, 30]:
        p = by_hour[h]
        rows.append(dict(lat=p.lat, lon=p.lon, datetime=p.time - timedelta(hours=40),
                         frp=100.0, district="WrongTime", kind="wrong_time"))

    return wf, traj, pd.DataFrame(rows)


def test_selects_correct_fires():
    print("\n1. Selects the right fires")
    wf, traj, fires = build_scenario()
    r = attribute_fires(traj, fires)

    kinds = r.fires["kind"].value_counts().to_dict() if len(r.fires) else {}

    check("all 5 on-path fires attributed", kinds.get("real", 0) == 5, f"got {kinds.get('real', 0)}")
    check("no fires 3 degrees off-path", kinds.get("far", 0) == 0,
          f"got {kinds.get('far', 0)} (these had 5x the FRP - a distance bug would grab them)")
    check("no fires outside the time window", kinds.get("wrong_time", 0) == 0,
          f"got {kinds.get('wrong_time', 0)}")
    check("smoke index positive", r.smoke_index > 0, f"{r.smoke_index:.1f}")


def test_distance_weighting():
    print("\n2. Distance weighting")
    wf, traj, _ = build_scenario()
    p = {round(q.hours_before): q for q in traj.points}[20]

    rows = []
    for offset_km, tag in [(0.0, "on"), (15.0, "near"), (28.0, "edge")]:
        rows.append(dict(lat=p.lat + offset_km / 110.54, lon=p.lon,
                         datetime=p.time, frp=100.0, district="D", kind=tag))
    r = attribute_fires(traj, pd.DataFrame(rows))

    w = dict(zip(r.fires["kind"], r.fires["weight"]))
    check("all three attributed", len(w) == 3, f"{len(w)}")
    if len(w) == 3:
        check("weight falls with distance", w["on"] > w["near"] > w["edge"],
              f"on={w['on']:.1f} near={w['near']:.1f} edge={w['edge']:.1f}")
        check("on-path fire keeps nearly full FRP", w["on"] > 99.0, f"{w['on']:.2f}")
        check("edge fire heavily discounted", w["edge"] < 50.0, f"{w['edge']:.2f}")


def test_frp_scaling():
    print("\n3. FRP scaling")
    wf, traj, _ = build_scenario()
    p = {round(q.hours_before): q for q in traj.points}[20]

    base = pd.DataFrame([dict(lat=p.lat, lon=p.lon, datetime=p.time, frp=10.0, district="D")])
    big = base.copy()
    big["frp"] = 100.0

    r_small = attribute_fires(traj, base)
    r_big = attribute_fires(traj, big)
    ratio = r_big.smoke_index / r_small.smoke_index

    check("index scales linearly with FRP", abs(ratio - 10.0) < 0.01, f"ratio {ratio:.4f}")


def test_district_rollup():
    print("\n4. District rollup")
    wf, traj, _ = build_scenario()
    pts = {round(q.hours_before): q for q in traj.points}

    rows = []
    for h in [8, 12, 16]:
        rows.append(dict(lat=pts[h].lat, lon=pts[h].lon, datetime=pts[h].time,
                         frp=50.0, district="Alpha"))
    for h in [24, 28]:
        rows.append(dict(lat=pts[h].lat, lon=pts[h].lon, datetime=pts[h].time,
                         frp=10.0, district="Beta"))

    r = attribute_fires(traj, pd.DataFrame(rows))
    bd = r.by_district

    check("two districts", len(bd) == 2, f"{len(bd)}")
    check("ranked by weight", bd.iloc[0]["district"] == "Alpha", f"top: {bd.iloc[0]['district']}")
    check("shares sum to 1", abs(bd["share"].sum() - 1.0) < 1e-6, f"{bd['share'].sum():.6f}")
    check("Alpha counts 3 fires", int(bd.iloc[0]["fire_count"]) == 3)


def test_corridor_sensitivity():
    print("\n5. Corridor radius sensitivity")
    wf, traj, fires = build_scenario()
    counts = {}
    for radius in config.CORRIDOR_SENSITIVITY_KM:
        r = attribute_fires(traj, fires, corridor_radius_km=radius)
        counts[radius] = r.fire_count
    check("wider corridor never attributes fewer fires",
          all(counts[a] <= counts[b] for a, b in zip(config.CORRIDOR_SENSITIVITY_KM,
                                                     config.CORRIDOR_SENSITIVITY_KM[1:])),
          str(counts))
    check("real fires found at every radius", all(c >= 5 for c in counts.values()), str(counts))


def test_empty_inputs():
    print("\n6. Degenerate inputs")
    wf, traj, fires = build_scenario()

    r = attribute_fires(traj, pd.DataFrame(columns=["lat", "lon", "datetime", "frp"]))
    check("empty fire set returns zero, not an error", r.smoke_index == 0 and r.fire_count == 0)

    far = pd.DataFrame([dict(lat=10.0, lon=10.0,
                             datetime=ARRIVAL, frp=500.0, district="Elsewhere")])
    r2 = attribute_fires(traj, far)
    check("distant fires excluded by prefilter", r2.fire_count == 0)


def test_ensemble_stability():
    print("\n7. Ensemble stability")
    wf, traj, fires = build_scenario()
    ens = ensemble_trajectories(wf, RECEPTOR_LAT, RECEPTOR_LON, ARRIVAL, hours_back=48)
    r = attribute_ensemble(ens, fires)

    check("ensemble metadata attached", "ensemble_cv" in r.meta, str(list(r.meta)))
    check("members counted", r.meta.get("ensemble_n") == config.ENSEMBLE_SIZE)
    check("coefficient of variation is sane", 0.0 <= r.meta["ensemble_cv"] < 2.0,
          f"cv={r.meta['ensemble_cv']:.3f}")


def test_naive_baseline():
    """
    The baseline must be a fair opponent. It sees every fire in the same
    lookback window the trajectory covers, including the high-FRP decoys that
    the wind-aware model correctly rejects. That is the whole point: both
    models get the same data, and only one knows about the wind.
    """
    print("\n8. Naive baseline")
    wf, traj, fires = build_scenario()

    # Scenario FRP: real 5x20=100, far 3x100=300, wrong_time 3x100=300.
    # The wrong_time fires sit 52-70h before arrival, so a 48h window should
    # exclude them and a 72h window should pick them up.
    in_48h = fires[fires["kind"].isin(["real", "far"])]["frp"].sum()   # 400
    far_frp = fires[fires["kind"] == "far"]["frp"].sum()               # 300

    total_48 = naive_baseline(fires, ARRIVAL, window_hours=48)
    total_72 = naive_baseline(fires, ARRIVAL, window_hours=72)

    check("sums every in-window fire regardless of wind",
          abs(total_48 - in_48h) < 1e-6, f"{total_48:.0f} MW, expected {in_48h:.0f}")
    check("window boundary excludes older fires",
          total_72 > total_48, f"72h={total_72:.0f} MW vs 48h={total_48:.0f} MW")
    check("window covers transport time, not just arrival day",
          total_48 > 0, "a same-day-only window would return 0 here and be a straw man")

    # The off-path decoys are exactly what separates the two models.
    wind_aware = attribute_fires(traj, fires)
    check("baseline swallows the off-path decoys", total_48 >= far_frp,
          f"includes {far_frp:.0f} MW of fires the wind never crossed")
    check("wind-aware model rejects them",
          wind_aware.total_frp < total_48,
          f"wind-aware {wind_aware.total_frp:.0f} MW vs naive {total_48:.0f} MW")


if __name__ == "__main__":
    print("=" * 70)
    print("ATTRIBUTION VALIDATION  --  synthetic scenario, known answer")
    print("=" * 70)

    test_selects_correct_fires()
    test_distance_weighting()
    test_frp_scaling()
    test_district_rollup()
    test_corridor_sensitivity()
    test_empty_inputs()
    test_ensemble_stability()
    test_naive_baseline()

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
