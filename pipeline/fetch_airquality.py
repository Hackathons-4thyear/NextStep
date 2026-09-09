"""
Fetch ground-station PM2.5 from OpenAQ v3.

Note that v1 and v2 were retired on 31 January 2025 and now return HTTP 410,
so any snippet you find online using api.openaq.org/v1 or /v2 is dead. v3 is
resource-oriented: you cannot query measurements by city directly, you walk
locations -> sensors -> measurements.

The key goes in an X-API-Key header. Register free at
https://explore.openaq.org/register
"""

from __future__ import annotations

import os
import time

import pandas as pd
import requests

import config

CACHE = config.DATA_PROCESSED / f"pm25_{config.TARGET_NAME}.parquet"


def _headers():
    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAQ_API_KEY not set. Register free at\n"
            "  https://explore.openaq.org/register\n"
            "then put it in .env as OPENAQ_API_KEY=..."
        )
    return {"X-API-Key": key}


def _get(path, params=None, tries=4):
    url = f"{config.OPENAQ_BASE_URL}{path}"
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=_headers(), params=params or {}, timeout=60)
            if r.status_code == 429:
                wait = 2 ** attempt * 5
                print(f"  rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            if r.status_code == 410:
                raise RuntimeError(
                    "HTTP 410 Gone - this is a retired v1/v2 endpoint. Use v3."
                )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenAQ request failed after {tries} attempts: {last}")


def find_stations(verbose=True):
    """Stations near the receptor that measure PM2.5."""
    r = config.OPENAQ_SEARCH_RADIUS_DEG
    lat, lon = config.RECEPTOR["lat"], config.RECEPTOR["lon"]
    bbox = f"{lon - r},{lat - r},{lon + r},{lat + r}"

    payload = _get("/locations", {"bbox": bbox, "limit": 1000})
    stations = []

    for loc in payload.get("results", []):
        sensors = [
            s for s in loc.get("sensors", [])
            if s.get("parameter", {}).get("name") == config.OPENAQ_PARAMETER
        ]
        if sensors:
            stations.append({
                "location_id": loc["id"],
                "name": loc.get("name", "?"),
                "lat": loc["coordinates"]["latitude"],
                "lon": loc["coordinates"]["longitude"],
                "sensor_ids": [s["id"] for s in sensors],
            })

    if verbose:
        print(f"pm25: {len(stations)} stations measuring "
              f"{config.OPENAQ_PARAMETER} near {config.RECEPTOR['name']}")
    return stations


def fetch_pm25(force=False, verbose=True):
    """
    Hourly PM2.5 at the receptor, as the median across nearby stations.

    Median rather than a single station: individual monitors go offline,
    drift, or sit next to a construction site. The median across several is
    far more robust and costs nothing extra.
    """
    if CACHE.exists() and not force:
        if verbose:
            print(f"pm25: using cache {CACHE.name}")
        return pd.read_parquet(CACHE)

    stations = find_stations(verbose=verbose)
    if len(stations) < config.OPENAQ_MIN_STATIONS:
        print(
            f"\nWARNING: only {len(stations)} stations found, wanted at least "
            f"{config.OPENAQ_MIN_STATIONS}.\n"
            "Thin coverage is the single biggest risk to this project. Consider\n"
            "widening OPENAQ_SEARCH_RADIUS_DEG, switching receptor city, or\n"
            "falling back to your national agency's own portal. Decide today,\n"
            "not on Day 4."
        )

    frames = []
    for st in stations:
        for sensor_id in st["sensor_ids"]:
            series = _fetch_sensor_hourly(sensor_id, verbose=verbose)
            if series is not None and len(series):
                series["location_id"] = st["location_id"]
                series["station"] = st["name"]
                frames.append(series)
            time.sleep(0.3)

    if not frames:
        raise RuntimeError(
            "No PM2.5 measurements returned for the season. Check the season "
            "dates against what the stations actually cover - an empty result "
            "means no monitoring coverage, never clean air."
        )

    allrows = pd.concat(frames, ignore_index=True)

    hourly = (
        allrows.groupby("datetime")["value"]
        .agg(pm25="median", n_stations="size")
        .reset_index()
        .sort_values("datetime")
        .reset_index(drop=True)
    )

    hourly.to_parquet(CACHE, index=False)

    if verbose:
        _report_coverage(hourly)
    return hourly


def _fetch_sensor_hourly(sensor_id, verbose=False):
    rows, page = [], 1
    while True:
        payload = _get(
            f"/sensors/{sensor_id}/measurements/hourly",
            {
                "datetime_from": f"{config.SEASON_START}T00:00:00Z",
                "datetime_to": f"{config.SEASON_END}T23:59:59Z",
                "limit": 1000,
                "page": page,
            },
        )
        results = payload.get("results", [])
        if not results:
            break

        for m in results:
            period = m.get("period", {}).get("datetimeFrom", {})
            stamp = period.get("utc")
            value = m.get("value")
            if stamp is not None and value is not None:
                rows.append({"datetime": stamp, "value": value})

        if len(results) < 1000:
            break
        page += 1
        time.sleep(0.3)

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    # Negative values are instrument artefacts, not real measurements.
    return df[df["value"] >= 0]


def _report_coverage(hourly):
    span = pd.date_range(
        pd.Timestamp(config.SEASON_START, tz="UTC"),
        pd.Timestamp(config.SEASON_END, tz="UTC") + pd.Timedelta(hours=23),
        freq="h",
    )
    coverage = len(hourly) / len(span)
    print(f"\npm25: {len(hourly):,} hourly values, {coverage*100:.1f}% coverage")
    print(f"  median {hourly['pm25'].median():.1f}  "
          f"p95 {hourly['pm25'].quantile(0.95):.1f}  "
          f"max {hourly['pm25'].max():.1f} ug/m3")
    print(f"  stations per hour: median {hourly['n_stations'].median():.0f}")

    if coverage < 0.7:
        print("\n  WARNING: coverage below 70%. Gaps will weaken the season-wide")
        print("  correlation. Consider another receptor city before Day 3.")


def find_episodes(hourly, n=5, min_gap_hours=48):
    """
    Rank the season's strongest pollution episodes.

    Returns candidates for the hero animation. Prefer an episode with a sharp
    rise and a high peak-to-baseline ratio: that shape is characteristic of
    transported smoke, whereas a slow symmetric bulge is more likely local
    accumulation under stagnant air.
    """
    df = hourly.copy().sort_values("datetime").reset_index(drop=True)
    df["baseline"] = df["pm25"].rolling(72, center=True, min_periods=12).median()
    df["ratio"] = df["pm25"] / df["baseline"].clip(lower=1.0)

    episodes, used = [], []
    for _, row in df.sort_values("pm25", ascending=False).iterrows():
        t = row["datetime"]
        if any(abs((t - u).total_seconds()) < min_gap_hours * 3600 for u in used):
            continue
        window = df[(df["datetime"] >= t - pd.Timedelta(hours=24)) & (df["datetime"] <= t)]
        rise = row["pm25"] - window["pm25"].min() if len(window) else 0.0

        episodes.append({
            "arrival_utc": t,
            "peak": float(row["pm25"]),
            "baseline": float(row["baseline"]) if pd.notna(row["baseline"]) else float("nan"),
            "ratio": float(row["ratio"]) if pd.notna(row["ratio"]) else float("nan"),
            "rise_24h": float(rise),
        })
        used.append(t)
        if len(episodes) >= n:
            break

    return pd.DataFrame(episodes)


if __name__ == "__main__":
    hourly = fetch_pm25()
    print("\nStrongest episodes - pick one as the hero for the animation:")
    eps = find_episodes(hourly)
    for _, e in eps.iterrows():
        print(f"  {e['arrival_utc']:%Y-%m-%d %H:%M} UTC   "
              f"peak {e['peak']:>6.1f}  baseline {e['baseline']:>6.1f}  "
              f"ratio {e['ratio']:.1f}x  24h rise {e['rise_24h']:>6.1f}")
    print("\nSet EPISODE_ARRIVAL_UTC in config.py to your choice.")
