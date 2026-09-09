"""
Write the static JSON the site reads.

The browser does no science. Everything here is computed offline and dropped
into docs/data/ as plain JSON, so the page has no server, no API key, and no
network dependency at judging time. Every failure mode involving rate limits,
expired keys, CORS and cold starts is removed by construction.

Two contracts, both specified in planning/03-architecture.md:

    episode.json   drives the Nov 18 animation
    season.json    drives the evidence section below the fold

One detail is load-bearing. Trajectory timestamps are **seconds elapsed from
the start of the animation window**, not epoch. deck.gl's TripsLayer keeps
timestamps in float32, which has 24 bits of mantissa; epoch milliseconds need
41 bits and lose roughly a minute of precision, which shows up as visible
juddering in the trail. Subtracting the window start here keeps every value
under 200,000 and exact.

    python -m pipeline.export
"""

from __future__ import annotations

import json
from datetime import timedelta

import numpy as np
import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import config
from pipeline.attribution import attribute_ensemble, naive_baseline
from pipeline.fetch_airquality import fetch_pm25
from pipeline.fetch_fires import assign_districts, clean_fires
from pipeline.fetch_wind import fetch_wind
from pipeline.trajectory import ensemble_trajectories
from pipeline.validate import DAILY_CSV, STATS_JSON, straightness

EPISODE_JSON = config.SITE_DATA / "episode.json"
SEASON_JSON = config.SITE_DATA / "season.json"
TERRAIN_JSON = config.SITE_DATA / "terrain.json"
META_JSON = config.SITE_DATA / "meta.json"

P = config.EXPORT_COORD_PRECISION

NASA_ATTRIBUTION = (
    "We acknowledge the use of data and/or imagery from NASA's Fire Information "
    "for Resource Management System (FIRMS), part of NASA's Earth Observing "
    "System Data and Information System (EOSDIS)."
)


def _round(x):
    return round(float(x), P)


def _elapsed(when, window_start):
    """Seconds from the start of the animation window. Small, exact in float32."""
    return int((pd.Timestamp(when) - window_start).total_seconds())


def export_episode(wind, fires, pm, verbose=True):
    arrival = pd.Timestamp(config.EPISODE_ARRIVAL_UTC)
    window_start = arrival - pd.to_timedelta(config.ANIMATION_HOURS, unit="h")
    loop_length = int(config.ANIMATION_HOURS * 3600)

    ens = ensemble_trajectories(
        wind, config.RECEPTOR["lat"], config.RECEPTOR["lon"],
        arrival.to_pydatetime(),
    )
    primary = ens[0]
    result = attribute_ensemble(ens, fires)

    stride = config.EXPORT_TRAJECTORY_STRIDE
    trajectories = []
    for t in ens:
        pts = t.points[::stride]
        if pts[-1] is not t.points[-1]:
            pts.append(t.points[-1])          # always land exactly on the receptor
        trajectories.append({
            "member": t.member,
            "is_primary": bool(t.is_primary),
            "path": [[_round(p.lon), _round(p.lat)] for p in pts],
            "timestamps": [_elapsed(p.time, window_start) for p in pts],
        })

    # PM2.5 across the window, plus a tail so the gauge crests and falls
    # instead of stopping dead on the peak.
    pm_idx = pm.set_index(pd.to_datetime(pm["datetime"], utc=True))["pm25"].sort_index()
    tail = arrival + pd.to_timedelta(config.EXPORT_PM25_TRAIL_HOURS, unit="h")
    series = pm_idx.loc[window_start:tail]
    pm25_series = [
        {"t": _elapsed(ts, window_start), "v": round(float(v), 1)}
        for ts, v in series.items()
        if np.isfinite(v)
    ]
    in_window = pm_idx.loc[window_start:arrival]

    # The level *before* this episode built, not the window median. The median
    # is dragged up by the episode it is supposed to precede, which would make
    # the animation open on a number that misrepresents the starting air.
    pre = pm_idx.loc[
        window_start:window_start + pd.to_timedelta(
            config.VALIDATION_PM25_WINDOW_HOURS, unit="h")
    ]

    fire_rows = []
    attributed_keys = set()

    for _, f in result.fires.iterrows():
        # Reveal when the air actually passed over the fire, never at its
        # detection time -- a fire must not light up before the trajectory
        # reaches it, or the animation asserts a causal order that is wrong.
        passage = max(0, int((config.ANIMATION_HOURS - f["hours_upwind"]) * 3600))
        attributed_keys.add((round(f["lat"], 5), round(f["lon"], 5),
                             pd.Timestamp(f["datetime"]).value))
        fire_rows.append({
            "lon": _round(f["lon"]), "lat": _round(f["lat"]),
            "t": passage,
            "t_detect": _elapsed(f["datetime"], window_start),
            "frp": round(float(f["frp"]), 1),
            "attributed": True,
            "district": str(f.get("district", "")),
            "hours_upwind": round(float(f["hours_upwind"]), 1),
            "weight": round(float(f["weight"]), 2),
        })

    # Context fires: burning in view that the corridor did NOT pick up. Without
    # them the map implies these were the only fires, and the selection the
    # model is making becomes invisible.
    lat_pad = lon_pad = config.CORRIDOR_RADIUS_KM / 100.0 + 1.0
    t = pd.to_datetime(fires["datetime"], utc=True)
    near = fires[
        (t >= window_start) & (t <= arrival)
        & fires["lat"].between(primary.lats.min() - lat_pad, primary.lats.max() + lat_pad)
        & fires["lon"].between(primary.lons.min() - lon_pad, primary.lons.max() + lon_pad)
    ]
    context = near[[
        (round(r.lat, 5), round(r.lon, 5), pd.Timestamp(r.datetime).value)
        not in attributed_keys for r in near.itertuples()
    ]]
    if len(context) > config.EXPORT_MAX_CONTEXT_FIRES:
        context = context.sample(config.EXPORT_MAX_CONTEXT_FIRES, random_state=0)

    for r in context.itertuples():
        fire_rows.append({
            "lon": _round(r.lon), "lat": _round(r.lat),
            "t": _elapsed(r.datetime, window_start),
            "t_detect": _elapsed(r.datetime, window_start),
            "frp": round(float(r.frp), 1),
            "attributed": False,
        })

    fire_rows.sort(key=lambda r: r["t"])

    payload = {
        "receptor": config.RECEPTOR,
        "episode": {
            "arrival_utc": arrival.isoformat().replace("+00:00", "Z"),
            "pm25_peak": round(float(in_window.max()), 1),
            "pm25_baseline": round(float(pre.median()), 1),
            "pm25_window_median": round(float(in_window.median()), 1),
            "pm25_window_min": round(float(in_window.min()), 1),
            "smoke_index": round(result.smoke_index, 1),
            "fires_attributed": int(result.fire_count),
            "total_frp": round(result.total_frp, 1),
            "mean_hours_upwind": round(result.mean_hours_upwind, 1),
            "straightness": round(straightness(primary), 3),
            "ensemble_cv": round(float(result.meta.get("ensemble_cv", 0.0)), 3),
            "origin": {"lat": _round(primary.origin().lat),
                       "lon": _round(primary.origin().lon)},
            "path_km": round(primary.total_distance_km(), 1),
            "naive_index": round(naive_baseline(fires, arrival), 1),
        },
        "pm25_series": pm25_series,
        "trajectories": trajectories,
        "fires": fire_rows,
        "attribution": [
            {"district": str(r["district"]), "fire_count": int(r["fire_count"]),
             "frp_sum": round(float(r["frp_sum"]), 1),
             "share": round(float(r["share"]), 4)}
            for _, r in result.by_district.head(8).iterrows()
        ],
        "loop_length": loop_length,
        "window_start_utc": window_start.isoformat().replace("+00:00", "Z"),
    }

    EPISODE_JSON.write_text(json.dumps(payload))
    if verbose:
        n_att = sum(1 for f in fire_rows if f["attributed"])
        print(f"episode.json  {EPISODE_JSON.stat().st_size/1e6:.2f} MB  "
              f"{len(trajectories)} trajectories, {n_att} attributed fires, "
              f"{len(fire_rows)-n_att} context fires")
    return payload


def export_season(verbose=True):
    daily = pd.read_csv(DAILY_CSV)
    stats = json.loads(STATS_JSON.read_text())

    rows = []
    for _, r in daily.iterrows():
        rows.append({
            "date": str(r["date"]),
            "pm25": round(float(r["pm25"]), 1),
            "smoke_index": round(float(r["smoke_index"]), 1),
            "naive_index": round(float(r["naive_index"]), 1),
            "upwind_bearing": round(float(r["upwind_bearing"]), 1),
            "fires_attributed": int(r["fires_attributed"]),
            "straightness": round(float(r["straightness"]), 3),
            "ventilation_ms": round(float(r["ventilation_ms"]), 2),
            "path_km": round(float(r["path_km"]), 1),
            "exited_domain": bool(r["exited_domain"]),
        })

    def day(date):
        m = daily[daily["date"] == date]
        if m.empty:
            return None
        r = m.iloc[0]
        return {
            "date": date,
            "pm25": round(float(r["pm25"]), 1),
            "smoke_index": round(float(r["smoke_index"]), 1),
            "fires_attributed": int(r["fires_attributed"]),
            "straightness": round(float(r["straightness"]), 3),
            "upwind_bearing": round(float(r["upwind_bearing"]), 1),
            "path_km": round(float(r["path_km"]), 1),
        }

    payload = {
        "daily": rows,
        "stats": stats["stats"],
        "specification_grid": stats["specification_grid"],
        "detrended_comparison": stats["detrended_comparison"],
        "negative_control": stats["negative_control"],
        "corridor_sensitivity": stats["corridor_sensitivity"],
        "lag_sweep": stats["lag_sweep"],

        # The two-frame argument: more fires crossed, cleaner air.
        "ventilation_paradox": {
            "high_pm_day": day("2024-11-18"),
            "high_index_day": day("2024-11-19"),
        },

        # Where attribution is and is not possible at all. Carries the
        # within-group correlations, not just the group means: the means alone
        # would not test the claim.
        "straightness_split": stats["straightness_split"],
        "confound": stats["confound"],
    }

    SEASON_JSON.write_text(json.dumps(payload))
    if verbose:
        print(f"season.json   {SEASON_JSON.stat().st_size/1e6:.2f} MB  "
              f"{len(rows)} days")
    return payload


def _geom_bbox(geom):
    xs, ys = [], []

    def walk(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        else:
            for part in c:
                walk(part)

    walk(geom["coordinates"])
    return min(xs), min(ys), max(xs), max(ys)


def export_terrain(verbose=True):
    """
    Clip Natural Earth admin-1 boundaries to the domain.

    No basemap tiles anywhere in this project: a tile server that rate-limits
    or goes down while a judge is watching loses the hackathon. Local GeoJSON
    cannot do that.
    """
    if not config.TERRAIN_SOURCE.exists():
        print(f"terrain: source missing. Download once:\n"
              f"  curl -L -o {config.TERRAIN_SOURCE} \\\n"
              f"    {config.TERRAIN_URL}")
        return None

    src = json.loads(config.TERRAIN_SOURCE.read_text(encoding="utf-8"))
    b = config.BBOX
    kept = []
    for f in src["features"]:
        if not f.get("geometry"):
            continue
        x0, y0, x1, y1 = _geom_bbox(f["geometry"])
        if x1 < b["west"] or x0 > b["east"] or y1 < b["south"] or y0 > b["north"]:
            continue
        kept.append({
            "type": "Feature",
            "properties": {
                "name": f["properties"].get("name"),
                "admin": f["properties"].get("admin"),
            },
            "geometry": f["geometry"],
        })

    out = {"type": "FeatureCollection", "features": kept}
    TERRAIN_JSON.write_text(json.dumps(out))
    if verbose:
        print(f"terrain.json  {TERRAIN_JSON.stat().st_size/1e6:.2f} MB  "
              f"{len(kept)} regions")
    return out


def export_meta(verbose=True):
    payload = {
        "target": config.TARGET_NAME,
        "receptor": config.RECEPTOR,
        "bbox": dict(config.BBOX),
        "season": {"start": config.SEASON_START, "end": config.SEASON_END},
        "model": {
            "trajectory_hours_back": config.TRAJECTORY_HOURS_BACK,
            "dt_seconds": config.TRAJECTORY_DT_SECONDS,
            "wind_level": config.WIND_LEVEL,
            "corridor_radius_km": config.CORRIDOR_RADIUS_KM,
            "fire_time_tolerance_hours": config.FIRE_TIME_TOLERANCE_HOURS,
            "ensemble_size": config.ENSEMBLE_SIZE,
            "naive_window_hours": config.NAIVE_BASELINE_WINDOW_HOURS,
        },
        "attribution_text": NASA_ATTRIBUTION,
        "sources": [
            "NASA FIRMS (VIIRS SNPP + NOAA-20, science-quality)",
            "Open-Meteo ERA5 reanalysis, 100 m wind",
            "OpenAQ v3 ground PM2.5",
            "Natural Earth admin-1 boundaries",
        ],
    }
    META_JSON.write_text(json.dumps(payload, indent=2))
    if verbose:
        print(f"meta.json     {META_JSON.stat().st_size/1e3:.1f} KB")
    return payload


def main(verbose=True):
    wind = fetch_wind(verbose=verbose)
    fires = assign_districts(clean_fires(verbose=verbose))
    pm = fetch_pm25(verbose=verbose)

    export_episode(wind, fires, pm, verbose=verbose)
    export_season(verbose=verbose)
    export_terrain(verbose=verbose)
    export_meta(verbose=verbose)

    total = sum(p.stat().st_size for p in config.SITE_DATA.glob("*.json")) / 1e6
    print(f"\ntotal {total:.2f} MB in {config.SITE_DATA}")
    if total > config.MAX_EXPORT_MB:
        print(f"WARNING: over the {config.MAX_EXPORT_MB} MB budget")


if __name__ == "__main__":
    main()
