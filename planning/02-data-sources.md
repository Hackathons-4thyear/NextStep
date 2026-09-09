# Data Sources — verified September 2026

Everything below was checked against live documentation. All three sources are free.
Where a detail could not be verified, it is flagged as **VERIFY ON DAY 1** rather than assumed.

---

## 1. NASA FIRMS — active fire detections

**What it gives:** satellite-detected thermal anomalies (fires) worldwide, with location,
timestamp, and fire radiative power. VIIRS resolution is 375 m; archive runs from
20 January 2012 to present. MODIS runs from November 2000.

**Key:** free. Request a `MAP_KEY` by entering your email at
`https://firms.modaps.eosdis.nasa.gov/api/map_key/`.

**Rate limit:** 5000 transactions per 10-minute window. A multi-day request counts as
multiple transactions. This is generous — you will not hit it if you cache.

### Area endpoint

```
https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{BBOX}/{DAY_RANGE}/{START_DATE}
```

- `BBOX` — `west,south,east,north` in decimal degrees
- `DAY_RANGE` — **maximum 5**. Verified against the live API on Day 1: a request
  with `day_range` above 5 returns `HTTP 400 — Invalid day range. Expects [1..5].`
  An earlier draft of this document said 10; that was wrong and cost a fetch cycle.
  A 52-day season needs 11 sequential requests per platform. The value lives in
  `config.FIRMS_MAX_DAY_RANGE`.
- `START_DATE` — `YYYY-MM-DD`. Omit for the most recent days.
- Returns CSV directly, so `pandas.read_csv(url)` works.

### Choosing SOURCE

| Source string | Use for |
|---|---|
| `VIIRS_SNPP_NRT` | Near-real-time, recent dates |
| `VIIRS_SNPP_SP` | **Science-quality, use this for historical seasons** |
| `VIIRS_NOAA20_NRT` / `_SP` | Second VIIRS platform — combine for better temporal coverage |
| `MODIS_SP` | Longer archive, coarser (1 km) |

**Important:** NRT and SP cover *disjoint, non-overlapping* date ranges, and NRT holds only
the recent window. For any historical season `_SP` is the correct and only choice — there is
no NRT fallback, and reaching for one when `_SP` appears to fail will return an empty result
and send you chasing the wrong bug. Confirm coverage with the `data_availability` endpoint
before downloading:

```
https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/{MAP_KEY}/ALL
```

Checked on Day 1, it returned:

| Product | min_date | max_date |
|---|---|---|
| `VIIRS_SNPP_SP` | 2012-01-20 | 2026-04-27 |
| `VIIRS_NOAA20_SP` | 2018-04-01 | 2026-05-31 |
| `VIIRS_SNPP_NRT` | 2026-04-28 | 2026-09-07 |
| `VIIRS_NOAA20_NRT` | 2026-06-01 | 2026-09-07 |

The NRT products begin in 2026. For this project's Oct–Nov 2024 season they contain
nothing at all.

### Columns you will use

`latitude`, `longitude`, `acq_date`, `acq_time` (HHMM, **UTC**), `confidence`
(`l`/`n`/`h` for VIIRS), `frp` (fire radiative power, megawatts), `daynight`, `satellite`.

### Gotchas

- **`acq_time` is UTC.** Everything downstream must be UTC until the final display layer.
  Mixing local time into the trajectory integration is the single most likely silent bug
  in this project.
- **Not every detection is a fire.** FIRMS flags any thermal anomaly. Steel plants, refineries
  and gas flares appear at near-identical coordinates almost daily. Build a persistent-source
  mask: round coordinates to ~1 km, count how many distinct days each cell fires, and drop
  cells appearing on more than ~60% of days.
- Filter `confidence` to `n` and `h` for VIIRS. Keep `l` only in a sensitivity check.
- **Attribution required by NASA** when using FIRMS data in a presentation. Put this in the
  README and on the site footer: *"We acknowledge the use of data and/or imagery from NASA's
  Fire Information for Resource Management System (FIRMS), part of NASA's Earth Observing
  System Data and Information System (EOSDIS)."*

---

## 2. Open-Meteo — historical wind field

**What it gives:** hourly historical weather anywhere on Earth from 1940, backed by ERA5
reanalysis at roughly 10 km resolution, spatially complete with no missing values.

**Key:** **none required.** No authentication, CC BY 4.0 licence.

### Endpoint

```
https://archive-api.open-meteo.com/v1/archive
  ?latitude={LAT_LIST}
  &longitude={LON_LIST}
  &start_date=YYYY-MM-DD
  &end_date=YYYY-MM-DD
  &hourly=wind_speed_10m,wind_direction_10m,wind_speed_100m,wind_direction_100m
  &timezone=UTC
```

`latitude` and `longitude` accept comma-separated lists, so a whole grid can be fetched
in a small number of requests. Response is JSON; with multiple locations it is a JSON array,
one object per location, **in the order requested**.

### Which altitude to use

Use **100 m winds** as the primary field. Smoke from surface burning is mixed within the
planetary boundary layer, so a near-surface transport wind is physically more appropriate
than an upper-level one. 10 m wind is too influenced by surface friction; use it only for a
sensitivity check.

Open-Meteo also exposes pressure-level variables (1000–10 hPa), and 850 hPa is the
conventional choice in trajectory literature for longer-range transport. **VERIFY ON DAY 1**
whether `wind_speed_850hPa` is available on the *archive* endpoint for your dates — pressure
levels are documented most clearly for the Historical Forecast API
(`historical-forecast-api.open-meteo.com`, coverage from ~2021–22). If 100 m works, ship it
and mention 850 hPa as a sensitivity check rather than blocking on it.

### Converting to u/v components

Meteorological wind direction is the direction the wind blows **FROM**. To get vector
components in m/s:

```python
import numpy as np
rad = np.deg2rad(direction_deg)
u = -speed * np.sin(rad)   # eastward component
v = -speed * np.cos(rad)   # northward component
```

Getting this sign convention wrong produces trajectories that run in exactly the wrong
direction. Sanity-check on a day with a known strong prevailing wind before trusting anything.

### Gotchas

- Set `timezone=UTC` explicitly. Do not rely on the default.
- ERA5 grid is ~10 km, so a request grid finer than about 0.25° adds no real information —
  it just interpolates the same cells. 0.25°–0.5° spacing is the sensible range.
- Be polite: fetch the whole date range in one request per grid point rather than
  day-by-day loops, and cache to disk immediately.

---

## 3. OpenAQ v3 — ground-station air quality

**What it gives:** measured PM2.5 and other pollutants from government reference monitors
and research-grade sensors worldwide.

**Key:** **required.** Register at `https://explore.openaq.org/register`.
Send it as the **`X-API-Key` header**.

**Critical:** v1 and v2 endpoints were retired on 31 January 2025 and now return HTTP 410.
Any tutorial or snippet using `api.openaq.org/v1/...` or `/v2/...` is dead. Use v3 only.

### The v3 access pattern

v3 is resource-oriented and requires walking a chain — you cannot query measurements
by city directly:

```
GET /v3/locations?bbox=west,south,east,north&limit=1000   → find stations
GET /v3/locations/{locations_id}/sensors                  → get sensor IDs per station
GET /v3/sensors/{sensors_id}/measurements/hourly          → the actual time series
    ?datetime_from=...&datetime_to=...&limit=1000&page=N
```

`limit` maxes at 1000 and results are paginated via `page`. There is also an official
Python SDK (`pip install openaq`) which wraps this chain and handles rate-limit retries —
using it will save an hour and is worth it.

### Gotchas

- **Coverage is uneven and this is the project's single biggest risk.** Some regions have
  dense hourly PM2.5; others have a couple of stations with long gaps.
  **This must be checked on Day 1, before anything else is built.**
- If a station has gaps, prefer taking the median across several stations in the city rather
  than depending on one.
- An empty result means no monitoring coverage, not clean air. Never impute zero.
- Units are returned verbatim and never converted. Confirm you are reading µg/m³ for PM2.5.

### If OpenAQ coverage is inadequate

Fallbacks, in order of preference:
1. The national environmental agency's own open portal for your country — often denser
   than what OpenAQ has aggregated.
2. Choose a different receptor city with better coverage. **This is a legitimate and cheap
   fix on Day 1 and an expensive one on Day 4.**
3. Satellite aerosol optical depth as a proxy. Weaker evidence, more work — a last resort.

---

## 4. District boundaries (optional but high value)

Attribution reads far better as "Districts A, B and C" than as a scatter of coordinates.
Sources: your country's open government data portal, GADM, or Natural Earth admin-2 boundaries.
Use `geopandas.sjoin` to label each fire with its district.

If shapefile handling eats more than two hours, **drop it** and cluster fires spatially
instead, labelling clusters by their nearest named town. The visual value is nearly identical.

---

## Day 1 verification checklist

Do not write a single line of modelling code until every one of these passes.

- [ ] FIRMS MAP_KEY works; a 5-day area request returns a non-empty CSV
- [ ] The chosen season actually contains a large number of detections (thousands, not dozens)
- [ ] Those detections are **spread across the whole season**, not bunched into a few days
- [ ] Persistent industrial sources are identifiable and removable
- [ ] Open-Meteo returns hourly wind for a multi-point grid across the full date range
- [ ] u/v conversion produces a physically plausible prevailing direction for the region
- [ ] OpenAQ key works and the receptor city has **near-continuous hourly PM2.5** for the season
- [ ] The PM2.5 series contains several clear, unambiguous spike episodes
- [ ] All three sources align on a single UTC hourly index with no timezone drift

If the PM2.5 check fails, change city today. If the fire-count check fails, change season or region today.

### Do not trust `verify_day1.py`'s verdict line on its own

The script scores fire **count** but never checks temporal **spread**. On Day 1 a partial
fetch returned 894 detections drawn entirely from a single 2-day window at the end of the
season, and the script still printed `Target is viable` — the count cleared its threshold,
so the truncation registered only as a "thin" warning rather than a failure.

What actually caught it was the cross-source alignment check reporting a **1-day overlap**.
So when reading the output, check these two lines before believing the verdict:

- section 1: *days with meaningful fire activity* should be close to the season length
- section 4: *overlapping period* should be close to the season length

A green verdict with either of those collapsed means a broken fetch, not a viable target.
