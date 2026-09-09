"""
Fetch and clean active fire detections from NASA FIRMS.

Two things here are easy to get wrong and both are silent:

  1. acq_time is UTC in HHMM form. Parsed as local time, every attribution in
     the project shifts by the timezone offset and nothing errors.
  2. FIRMS reports thermal anomalies, not fires. Steel plants, refineries and
     gas flares light up at the same coordinates nearly every day. Left in,
     they attach a constant background to every trajectory that happens to
     pass over an industrial area.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

import config

CACHE = config.DATA_RAW / f"fires_{config.TARGET_NAME}.parquet"
CLEAN = config.DATA_PROCESSED / f"fires_clean_{config.TARGET_NAME}.parquet"


def fetch_fires(force=False, use_nrt=False, verbose=True):
    """Download the season's detections, cache raw, return the raw DataFrame."""
    if CACHE.exists() and not force:
        if verbose:
            print(f"fires: using cache {CACHE.name}")
        return pd.read_parquet(CACHE)

    key = os.environ.get("FIRMS_MAP_KEY")
    if not key:
        raise RuntimeError(
            "FIRMS_MAP_KEY not set. Get one free at\n"
            "  https://firms.modaps.eosdis.nasa.gov/api/map_key/\n"
            "then put it in .env as FIRMS_MAP_KEY=..."
        )

    bbox = f"{config.BBOX['west']},{config.BBOX['south']},{config.BBOX['east']},{config.BBOX['north']}"
    sources = config.FIRMS_SOURCES_NRT if use_nrt else config.FIRMS_SOURCES

    start = datetime.fromisoformat(config.SEASON_START).date()
    end = datetime.fromisoformat(config.SEASON_END).date()

    frames = []
    for source in sources:
        cursor = start
        while cursor <= end:
            span = min(config.FIRMS_MAX_DAY_RANGE, (end - cursor).days + 1)
            url = f"{config.FIRMS_BASE_URL}/{key}/{source}/{bbox}/{span}/{cursor:%Y-%m-%d}"

            try:
                chunk = pd.read_csv(url)
                if len(chunk):
                    chunk["source"] = source
                    frames.append(chunk)
                if verbose:
                    print(f"  {source} {cursor} +{span}d -> {len(chunk)} detections")
            except Exception as e:
                print(f"  WARN {source} {cursor}: {e}")

            cursor += timedelta(days=span)
            time.sleep(0.6)

    if not frames:
        raise RuntimeError(
            "No detections returned. Check that:\n"
            "  - the MAP_KEY is valid\n"
            "  - the season and bbox are right\n"
            "  - the science-quality (_SP) product covers your dates; if the\n"
            "    season is within the last ~3 months, retry with use_nrt=True"
        )

    raw = pd.concat(frames, ignore_index=True)
    raw.to_parquet(CACHE, index=False)
    if verbose:
        print(f"fires: {len(raw):,} raw detections cached to {CACHE.name}")
    return raw


def clean_fires(raw=None, force=False, verbose=True):
    """
    Parse timestamps to UTC, filter by confidence, strip persistent industrial
    sources. Prints how many each filter removed so the effect is visible
    rather than assumed.
    """
    if CLEAN.exists() and not force:
        if verbose:
            print(f"fires: using cleaned cache {CLEAN.name}")
        return pd.read_parquet(CLEAN)

    df = raw if raw is not None else fetch_fires(verbose=verbose)
    n0 = len(df)
    steps = []

    df = df.rename(columns={"latitude": "lat", "longitude": "lon"})

    # acq_time is HHMM as an integer, in UTC.
    hhmm = df["acq_time"].astype(int).astype(str).str.zfill(4)
    df["datetime"] = pd.to_datetime(
        df["acq_date"].astype(str) + " " + hhmm.str[:2] + ":" + hhmm.str[2:],
        utc=True,
    )

    df["frp"] = pd.to_numeric(df["frp"], errors="coerce")
    df = df.dropna(subset=["frp", "lat", "lon", "datetime"])
    steps.append(("missing frp or coordinates", n0 - len(df)))

    n = len(df)
    if "confidence" in df.columns:
        conf = df["confidence"].astype(str).str.lower().str[0]
        df = df[conf.isin(config.FIRE_CONFIDENCE_KEEP)]
        steps.append((f"confidence not in {config.FIRE_CONFIDENCE_KEEP}", n - len(df)))

    n = len(df)
    df = df.drop_duplicates(subset=["lat", "lon", "datetime"])
    steps.append(("duplicate detections across satellites", n - len(df)))

    n = len(df)
    df, industrial = _strip_persistent_sources(df)
    steps.append(("persistent industrial thermal anomalies", n - len(df)))

    df = df.sort_values("datetime").reset_index(drop=True)
    df.to_parquet(CLEAN, index=False)

    if verbose:
        print(f"\nfires: cleaning {n0:,} -> {len(df):,}")
        for label, removed in steps:
            if removed:
                print(f"  -{removed:>7,}  {label}")
        if len(industrial):
            print(f"\n  {len(industrial)} persistent source cells masked. Spot-check a few "
                  "on a map -\n  they should be plants or flares, not fields:")
            for _, r in industrial.head(5).iterrows():
                print(f"    {r['cell_lat']:.2f}, {r['cell_lon']:.2f}  "
                      f"active on {int(r['n_days'])} days")

    return df


def _strip_persistent_sources(df):
    """
    Drop grid cells that burn on most days of the season.

    A crop fire happens once. A refinery flare happens every day. Rounding
    coordinates to about a kilometre and counting distinct active days
    separates them cleanly without needing an industrial-site database.
    """
    g = config.PERSISTENT_SOURCE_GRID_DEG
    df = df.copy()
    df["cell_lat"] = (df["lat"] / g).round() * g
    df["cell_lon"] = (df["lon"] / g).round() * g
    df["day"] = df["datetime"].dt.date

    total_days = df["day"].nunique()
    threshold = max(3, int(total_days * config.PERSISTENT_SOURCE_DAY_FRACTION))

    per_cell = (
        df.groupby(["cell_lat", "cell_lon"])["day"]
        .nunique()
        .reset_index(name="n_days")
    )
    bad = per_cell[per_cell["n_days"] >= threshold]

    if len(bad) == 0:
        return df.drop(columns=["cell_lat", "cell_lon", "day"]), bad

    keys = set(zip(bad["cell_lat"], bad["cell_lon"]))
    mask = [k not in keys for k in zip(df["cell_lat"], df["cell_lon"])]
    kept = df[mask].drop(columns=["cell_lat", "cell_lon", "day"])
    return kept, bad.sort_values("n_days", ascending=False)


def assign_districts(fires, geojson_path=None):
    """
    Label each fire with a district.

    Falls back to a coarse grid label when no boundary file is supplied.
    Attribution reads far better as named places than as coordinates, but if
    shapefile wrangling starts eating hours, this fallback keeps the pipeline
    moving - see the cut list in 04-build-plan.md.
    """
    fires = fires.copy()

    if geojson_path is None:
        cell = (
            fires["lat"].round(0).astype(int).astype(str) + "N, "
            + fires["lon"].round(0).astype(int).astype(str) + "E"
        )
        # Named towns where we have them, the raw cell where we do not, so an
        # unmapped region shows as a coordinate rather than disappearing.
        fires["district"] = cell.map(config.DISTRICT_NAMES).fillna(cell)
        return fires

    import geopandas as gpd

    gdf = gpd.GeoDataFrame(
        fires,
        geometry=gpd.points_from_xy(fires["lon"], fires["lat"]),
        crs="EPSG:4326",
    )
    districts = gpd.read_file(geojson_path).to_crs("EPSG:4326")

    name_col = next(
        (c for c in ["NAME_2", "district", "DISTRICT", "NAME_1", "name"] if c in districts.columns),
        districts.columns[0],
    )
    joined = gpd.sjoin(gdf, districts[[name_col, "geometry"]], how="left", predicate="within")
    fires["district"] = joined[name_col].fillna("Unassigned").values
    return fires


if __name__ == "__main__":
    raw = fetch_fires()
    clean = clean_fires(raw)
    print(f"\n{len(clean):,} usable detections")
    print(f"date range: {clean['datetime'].min()} to {clean['datetime'].max()}")
    print(f"total FRP:  {clean['frp'].sum():,.0f} MW")
