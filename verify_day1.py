#!/usr/bin/env python3
"""
Day 1 verification. Run this before writing anything else.

Every check below corresponds to an item on the Day 1 checklist in
02-data-sources.md. The point is to find out today whether the chosen target
can support the project, because changing city on Day 1 costs an hour and
changing it on Day 4 costs the hackathon.

    python verify_day1.py

Exits 0 if the target is viable, 1 if it is not.
"""

import sys
import traceback
from datetime import timedelta

import numpy as np
import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("note: python-dotenv not installed, relying on shell environment\n")

import config

GO, NOGO, WARN = "GO", "NO-GO", "WARN"
_checks = []


def record(status, name, detail=""):
    icon = {GO: "  OK ", NOGO: " FAIL", WARN: " WARN"}[status]
    print(f"[{icon}] {name}" + (f"\n         {detail}" if detail else ""))
    _checks.append((status, name, detail))
    return status == GO


def header(t):
    print(f"\n{'-' * 70}\n{t}\n{'-' * 70}")


def main():
    print("=" * 70)
    print(f"DAY 1 VERIFICATION  --  target: {config.TARGET_NAME}")
    print("=" * 70)
    print(f"receptor : {config.RECEPTOR['name']} "
          f"({config.RECEPTOR['lat']:.3f}, {config.RECEPTOR['lon']:.3f})")
    print(f"domain   : {config.BBOX['west']}W {config.BBOX['south']}S "
          f"{config.BBOX['east']}E {config.BBOX['north']}N")
    print(f"season   : {config.SEASON_START} to {config.SEASON_END}")

    fires = wind = pm25 = None

    # -- fires ------------------------------------------------------------
    header("1. Fire detections (NASA FIRMS)")
    try:
        from pipeline.fetch_fires import clean_fires, fetch_fires
        raw = fetch_fires()
        record(GO, "FIRMS key works and returns data", f"{len(raw):,} raw detections")

        fires = clean_fires(raw)

        if len(fires) >= 2000:
            record(GO, "enough detections for a season-wide result", f"{len(fires):,} after cleaning")
        elif len(fires) >= 500:
            record(WARN, "detection count is thin", f"{len(fires):,} - workable but weak")
        else:
            record(NOGO, "too few detections", f"{len(fires):,} - change season or region")

        per_day = fires.groupby(fires["datetime"].dt.date).size()
        active = int((per_day > 20).sum())
        record(GO if active >= 20 else WARN, "days with meaningful fire activity",
               f"{active} of {len(per_day)} days have >20 detections")

    except Exception as e:
        record(NOGO, "FIRMS fetch failed", str(e))
        traceback.print_exc()

    # -- wind -------------------------------------------------------------
    header("2. Wind field (Open-Meteo, no key needed)")
    try:
        from pipeline.fetch_wind import fetch_wind
        wind = fetch_wind()
        record(GO, "wind field fetched", f"{len(wind.times):,} hourly steps")

        prevailing = wind.prevailing_direction()
        speed = wind.mean_speed()

        record(GO, "prevailing direction computed",
               f"{prevailing:.0f} deg (wind FROM this direction), mean {speed:.1f} m/s")
        print("\n         >> SANITY CHECK, do this by hand:")
        print("         >> Does that direction match what you know of this")
        print("         >> region's climate in this season? If it is roughly")
        print("         >> 180 degrees off, the sign convention is inverted")
        print("         >> and every result downstream will be wrong.\n")

        record(GO if 0.5 < speed < 30 else WARN, "wind speeds are physical",
               f"{speed:.1f} m/s mean")

    except Exception as e:
        record(NOGO, "wind fetch failed", str(e))
        traceback.print_exc()

    # -- air quality ------------------------------------------------------
    header("3. Ground PM2.5 (OpenAQ v3)  --  the highest-risk check")
    try:
        from pipeline.fetch_airquality import fetch_pm25, find_episodes
        pm25 = fetch_pm25()

        span = pd.date_range(
            pd.Timestamp(config.SEASON_START, tz="UTC"),
            pd.Timestamp(config.SEASON_END, tz="UTC") + pd.Timedelta(hours=23),
            freq="h",
        )
        coverage = len(pm25) / len(span)

        if coverage >= 0.85:
            record(GO, "PM2.5 coverage is strong", f"{coverage*100:.1f}% of hours")
        elif coverage >= 0.70:
            record(WARN, "PM2.5 coverage has gaps", f"{coverage*100:.1f}% of hours")
        else:
            record(NOGO, "PM2.5 coverage too sparse",
                   f"{coverage*100:.1f}% - change receptor city TODAY")

        stations = pm25["n_stations"].median()
        record(GO if stations >= config.OPENAQ_MIN_STATIONS else WARN,
               "multiple stations per hour", f"median {stations:.0f}")

        episodes = find_episodes(pm25)
        strong = episodes[episodes["ratio"] >= 2.0] if len(episodes) else episodes

        if len(strong) >= 3:
            record(GO, "clear spike episodes exist", f"{len(strong)} with 2x+ over baseline")
        elif len(strong) >= 1:
            record(WARN, "few clear episodes", f"only {len(strong)}")
        else:
            record(NOGO, "no clear spike episodes", "nothing to animate - change target")

        if len(episodes):
            print("\n         Episode candidates (set one as EPISODE_ARRIVAL_UTC):")
            for _, e in episodes.iterrows():
                print(f"           {e['arrival_utc']:%Y-%m-%d %H:%M} UTC  "
                      f"peak {e['peak']:>6.1f}  ratio {e['ratio']:.1f}x  "
                      f"24h rise {e['rise_24h']:>6.1f}")

    except Exception as e:
        record(NOGO, "OpenAQ fetch failed", str(e))
        traceback.print_exc()

    # -- alignment --------------------------------------------------------
    header("4. Cross-source alignment")
    if fires is not None and wind is not None and pm25 is not None:
        try:
            fire_tz = str(fires["datetime"].dt.tz)
            pm_tz = str(pm25["datetime"].dt.tz)
            wind_tz = str(wind.times[0].tzinfo)
            aligned = "UTC" in fire_tz and "UTC" in pm_tz and "UTC" in wind_tz
            record(GO if aligned else NOGO, "all three sources are UTC",
                   f"fires={fire_tz} pm25={pm_tz} wind={wind_tz}")

            overlap_start = max(fires["datetime"].min(), pm25["datetime"].min(), wind.times[0])
            overlap_end = min(fires["datetime"].max(), pm25["datetime"].max(), wind.times[-1])
            days = (overlap_end - overlap_start).days
            record(GO if days >= 30 else WARN, "overlapping period is long enough",
                   f"{days} days: {overlap_start:%Y-%m-%d} to {overlap_end:%Y-%m-%d}")

        except Exception as e:
            record(NOGO, "alignment check failed", str(e))
    else:
        record(NOGO, "alignment check skipped", "an earlier source failed")

    # -- end-to-end smoke test -------------------------------------------
    header("5. End-to-end: one trajectory, one attribution")
    if fires is not None and wind is not None:
        try:
            from pipeline.attribution import attribute_ensemble
            from pipeline.fetch_fires import assign_districts
            from pipeline.trajectory import ensemble_trajectories

            arrival = config.EPISODE_ARRIVAL_UTC
            if not (wind.times[0] <= arrival <= wind.times[-1]):
                arrival = wind.times[-1] - timedelta(hours=config.TRAJECTORY_HOURS_BACK + 1)
                record(WARN, "configured episode outside wind range",
                       f"using {arrival:%Y-%m-%d %H:%M} instead")

            ens = ensemble_trajectories(
                wind, config.RECEPTOR["lat"], config.RECEPTOR["lon"], arrival
            )
            primary = ens[0]
            record(GO, "trajectory integrates", f"{len(primary)} points")

            origin = primary.origin()
            dist = primary.total_distance_km()
            record(GO if dist > 50 else WARN, "air travelled a meaningful distance",
                   f"{dist:.0f} km, origin at {origin.lat:.2f}N {origin.lon:.2f}E")

            fires_d = assign_districts(fires)
            result = attribute_ensemble(ens, fires_d)

            if result.fire_count > 0:
                record(GO, "fires attributed on the smoke-test episode",
                       f"{result.fire_count} fires, index {result.smoke_index:,.0f}")
                print()
                for line in result.summary().split("\n"):
                    print(f"         {line}")
                print(f"\n         ensemble CV {result.meta.get('ensemble_cv', 0):.2f} "
                      "(lower is more robust)")
            else:
                record(WARN, "no fires attributed on this episode",
                       "try another episode, or widen CORRIDOR_RADIUS_KM")

        except Exception as e:
            record(NOGO, "end-to-end run failed", str(e))
            traceback.print_exc()
    else:
        record(NOGO, "end-to-end skipped", "an earlier source failed")

    # -- verdict ----------------------------------------------------------
    print("\n" + "=" * 70)
    n_go = sum(1 for s, _, _ in _checks if s == GO)
    n_warn = sum(1 for s, _, _ in _checks if s == WARN)
    n_nogo = sum(1 for s, _, _ in _checks if s == NOGO)
    print(f"VERDICT: {n_go} passed, {n_warn} warnings, {n_nogo} blocking")
    print("=" * 70)

    if n_nogo:
        print("\nBlocking issues:")
        for s, name, detail in _checks:
            if s == NOGO:
                print(f"  - {name}: {detail}")
        print("\nDo not proceed to Day 2. Fix the target or switch it. Changing")
        print("region or city today costs an hour; discovering this on Day 4")
        print("costs the project.")
        return 1

    if n_warn:
        print("\nWarnings to weigh before Day 2:")
        for s, name, detail in _checks:
            if s == WARN:
                print(f"  - {name}: {detail}")

    print("\nTarget is viable. Before moving on:")
    print("  1. Confirm the prevailing wind direction by hand (section 2).")
    print("  2. Pick your hero episode and set EPISODE_ARRIVAL_UTC in config.py.")
    print("  3. Then run: python -m tests.test_physics")
    return 0


if __name__ == "__main__":
    sys.exit(main())
