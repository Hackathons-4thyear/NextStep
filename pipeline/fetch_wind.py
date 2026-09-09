"""
Fetch gridded historical wind from the Open-Meteo archive API.

No API key required. The archive endpoint is backed by ERA5 reanalysis, hourly
from 1940, spatially complete. Multiple locations can be requested at once via
comma-separated coordinate lists, which keeps the whole grid to a handful of
requests.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import numpy as np
import requests

import config
from pipeline.windfield import WindField

CACHE = config.DATA_RAW / f"wind_{config.TARGET_NAME}_{config.WIND_LEVEL}.npz"


def build_grid():
    """Coordinate arrays for the wind grid, ascending."""
    s = config.WIND_GRID_SPACING
    lats = np.arange(config.BBOX["south"], config.BBOX["north"] + s / 2, s)
    lons = np.arange(config.BBOX["west"], config.BBOX["east"] + s / 2, s)
    return np.round(lats, 4), np.round(lons, 4)


def fetch_wind(force=False, verbose=True):
    """
    Fetch (or load from cache) the wind field for the configured domain and season.

    Returns a WindField.
    """
    if CACHE.exists() and not force:
        if verbose:
            print(f"wind: using cache {CACHE.name}")
        return WindField.from_npz(CACHE)

    lats, lons = build_grid()
    speed_var = f"wind_speed_{config.WIND_LEVEL}"
    dir_var = f"wind_direction_{config.WIND_LEVEL}"

    # Every grid point, flattened, so we can batch them into requests.
    pairs = [(la, lo) for la in lats for lo in lons]
    if verbose:
        print(f"wind: {len(lats)}x{len(lons)} = {len(pairs)} grid points, "
              f"{config.SEASON_START} to {config.SEASON_END}")

    u_flat, v_flat, times = {}, {}, None

    for start in range(0, len(pairs), config.WIND_BATCH_SIZE):
        batch = pairs[start:start + config.WIND_BATCH_SIZE]
        params = {
            "latitude": ",".join(f"{la:.4f}" for la, _ in batch),
            "longitude": ",".join(f"{lo:.4f}" for _, lo in batch),
            "start_date": config.SEASON_START,
            "end_date": config.SEASON_END,
            "hourly": f"{speed_var},{dir_var}",
            "timezone": "UTC",
            "wind_speed_unit": "ms",
        }

        payload = _get_with_retry(config.OPEN_METEO_ARCHIVE_URL, params)

        # A single location returns an object; multiple return a list.
        entries = payload if isinstance(payload, list) else [payload]
        if len(entries) != len(batch):
            raise RuntimeError(
                f"Open-Meteo returned {len(entries)} entries for {len(batch)} "
                "locations. Responses are ordered by request, so a mismatch "
                "would silently misalign the grid."
            )

        for (la, lo), entry in zip(batch, entries):
            hourly = entry["hourly"]
            if times is None:
                times = [
                    datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
                    for t in hourly["time"]
                ]
            sp = np.array(hourly[speed_var], dtype=float)
            dr = np.array(hourly[dir_var], dtype=float)

            # Reanalysis is spatially complete, but guard anyway: a NaN that
            # reaches the interpolator poisons every trajectory through it.
            sp = np.nan_to_num(sp, nan=0.0)
            dr = np.nan_to_num(dr, nan=0.0)

            u, v = WindField.uv_from_speed_direction(sp, dr)
            u_flat[(la, lo)] = u
            v_flat[(la, lo)] = v

        if verbose:
            done = min(start + config.WIND_BATCH_SIZE, len(pairs))
            print(f"  {done}/{len(pairs)} points")
        time.sleep(0.4)  # be a good citizen on a free API

    # Reshape flat dict into (time, lat, lon).
    nt, nla, nlo = len(times), len(lats), len(lons)
    u = np.zeros((nt, nla, nlo), dtype=np.float32)
    v = np.zeros((nt, nla, nlo), dtype=np.float32)
    for i, la in enumerate(lats):
        for j, lo in enumerate(lons):
            u[:, i, j] = u_flat[(la, lo)]
            v[:, i, j] = v_flat[(la, lo)]

    wf = WindField(lats, lons, times, u, v)
    wf.to_npz(CACHE)
    if verbose:
        print(f"wind: cached to {CACHE.name}")
        print(wf.summary())
    return wf


def _get_with_retry(url, params, tries=4):
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, timeout=90)
            if r.status_code == 429:
                wait = 2 ** attempt * 5
                print(f"  rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Open-Meteo request failed after {tries} attempts: {last}")


if __name__ == "__main__":
    wf = fetch_wind()
    print()
    print(wf.summary())
    print()
    print("Sanity check: does the prevailing direction match what you know of")
    print("this region's climate? For Punjab->Delhi in the burning season,")
    print("expect broadly northwesterly, roughly 290-330 degrees.")
    print("If it is close to 180 degrees off, the sign convention is inverted.")
