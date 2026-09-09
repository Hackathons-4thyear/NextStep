# Architecture

## The core decision: precompute everything

Python does all the science offline and writes static JSON. The website reads those JSON
files and does nothing else. There is no server, no API key in the browser, and no network
dependency at judging time.

This matters more than it sounds. A judge opening the site during grading gets an instant,
guaranteed-working demo. Every failure mode involving rate limits, expired keys, CORS,
cold starts and downed third-party APIs is eliminated by construction. It also means the
site can be hosted free on GitHub Pages.

```
  RAW APIs            PYTHON PIPELINE (offline)              STATIC SITE
┌───────────┐      ┌───────────────────────────┐      ┌──────────────────┐
│  FIRMS    │─────▶│ ingest → clean → cache    │      │  index.html      │
│ Open-Meteo│─────▶│ wind field (u,v grid)     │─────▶│  deck.gl + JS    │
│  OpenAQ   │─────▶│ back-trajectory engine    │ JSON │  reads JSON only │
└───────────┘      │ attribution + validation  │      └──────────────────┘
                   └───────────────────────────┘
                     runs on your laptop              deployed to Pages
```

## Repository layout

```
smoke-forensics/
├── README.md
├── requirements.txt
├── .env.example              # FIRMS_MAP_KEY=, OPENAQ_API_KEY=
├── .gitignore                # .env, data/raw/, __pycache__
├── config.py                 # ALL tunable constants live here, nowhere else
├── pipeline/
│   ├── __init__.py
│   ├── fetch_fires.py        # FR1
│   ├── fetch_wind.py         # FR2
│   ├── fetch_airquality.py   # FR2 receptor observations
│   ├── windfield.py          # interpolation class
│   ├── trajectory.py         # FR3 — the physics
│   ├── attribution.py        # FR4
│   ├── validate.py           # FR5
│   ├── export.py             # FR6
│   └── run_all.py            # orchestrator
├── data/
│   ├── raw/                  # cached API responses, gitignored
│   └── processed/
├── docs/                     # THE SITE — GitHub Pages serves from here
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── data/                 # exported JSON, committed
│       ├── episode.json
│       ├── season.json
│       └── meta.json
└── notebooks/
    └── exploration.ipynb     # Day 1 scratch work, kept for the Learning criterion
```

Putting the site in `docs/` lets GitHub Pages serve it from the main branch with one
settings toggle and no CI. Keep the exploration notebook — the Learning criterion explicitly
asks whether the team stretched themselves, and a visible record of Day 1 dead ends is evidence.

## Data contracts

Fix these before writing code. Both sides depend on them.

### `episode.json` — drives the animation

```json
{
  "receptor": { "name": "...", "lat": 0.0, "lon": 0.0 },
  "episode": {
    "arrival_utc": "2024-11-08T06:00:00Z",
    "pm25_peak": 412.0,
    "pm25_baseline": 68.0
  },
  "pm25_series": [ { "t": "2024-11-05T00:00:00Z", "v": 61.2 } ],
  "trajectories": [
    {
      "member": 0,
      "is_primary": true,
      "path": [[lon, lat], [lon, lat]],
      "timestamps": [0, 3600, 7200]
    }
  ],
  "fires": [
    { "lon": 0.0, "lat": 0.0, "t": 0, "frp": 12.4,
      "attributed": true, "district": "...", "hours_upwind": 14.5 }
  ],
  "attribution": [
    { "district": "...", "fire_count": 340, "frp_sum": 4210.5, "share": 0.42 }
  ],
  "loop_length": 259200
}
```

**Timestamps are seconds elapsed from the start of the animation window, not epoch.**
deck.gl's TripsLayer stores timestamps as float32, and passing raw epoch milliseconds
causes visible precision loss and juddering trails. The official docs work around this by
subtracting the start timestamp — do the subtraction in Python at export time instead, so
the browser never sees a large number.

### `season.json` — drives the validation view

```json
{
  "daily": [
    { "date": "2024-11-08", "pm25": 412.0,
      "smoke_index": 0.87, "naive_index": 0.44,
      "upwind_bearing": 291.0, "fires_attributed": 340 }
  ],
  "stats": {
    "spearman_smoke": 0.71, "spearman_naive": 0.38,
    "r2_smoke": 0.52, "r2_naive": 0.18,
    "best_lag_hours": 14, "n_days": 61
  },
  "lag_sweep": [ { "lag_h": 0, "rho": 0.31 } ],
  "negative_control": {
    "no_upwind_fire_days": 18,
    "mean_pm25_those_days": 74.1,
    "mean_pm25_other_days": 236.8
  }
}
```

`stats.r2_smoke` vs `stats.r2_naive` is the headline number. Design the site around it.

## The trajectory algorithm

This is the technical heart. Roughly 60 lines of Python.

```
FUNCTION back_trajectory(receptor_lat, receptor_lon, arrival_time, hours_back, dt_seconds):
    position ← (receptor_lat, receptor_lon)
    time     ← arrival_time
    path     ← [position]

    REPEAT (hours_back * 3600 / dt_seconds) TIMES:
        u, v ← windfield.interpolate(position, time)     # m/s, eastward & northward

        # step BACKWARDS: subtract the displacement the wind would have caused
        dlat ← -(v * dt) / 110540
        dlon ← -(u * dt) / (111320 * cos(radians(position.lat)))

        position ← position + (dlat, dlon)
        time     ← time - dt
        APPEND position TO path

        IF position outside domain: BREAK

    RETURN reversed(path)     # so it reads forward in time for the animation
```

Notes that matter:

- **`dt` of 900 s (15 min)** is a good balance. Hourly steps visibly cut corners on curved flow.
- **The `cos(lat)` term is required.** Without it, longitude displacement is wrong everywhere
  except the equator, and the error grows with latitude.
- **Reverse the path before export.** The trajectory is computed backwards but should animate
  forwards — air flowing from the fires toward the city is far more legible than the reverse.
- **Ensemble:** launch ~8 members from small offsets around the receptor (±0.15°) and
  ±2 hours in arrival time. Their spread *is* the uncertainty estimate. Render the primary
  member bright and the ensemble faint. This is both honest and visually excellent.

## Wind field interpolation

Load the grid once into a numpy array shaped `(n_time, n_lat, n_lon, 2)`. Interpolate
bilinearly in space and linearly in time. `scipy.interpolate.RegularGridInterpolator` does
this in a few lines and is fast enough for thousands of trajectories.

## Attribution scoring

For each fire, compute the minimum distance to any trajectory point whose timestamp is within
a tolerance window of the fire's detection time. Then:

```
weight = frp × exp(−(distance / corridor_radius)²)
```

Summing over attributed fires gives the smoke index. The Gaussian falloff means a fire
directly under the path counts fully and one at the corridor edge counts little, which is
physically sensible and avoids an arbitrary hard cutoff.

**The time window matters.** A fire detected 30 hours before the air passed over that location
did not contribute to this episode. Require the fire's detection time to fall within roughly
±12 hours of the trajectory's passage over it.

`corridor_radius` starts at 30 km. Put it in `config.py` and report sensitivity to it —
showing the result is stable across 20/30/50 km is a mark of rigour that costs ten minutes.

## The naive baseline

Deliberately simple, and it must be genuinely reasonable rather than a straw man:
total FRP of all fires anywhere in the region on that day, ignoring wind entirely.

That is what a normal project would build. Beating it by a clear margin is the entire
technical claim, so do not weaken it artificially. If the honest comparison is close,
report it honestly — judges respect that far more than an inflated number, and an
overstated claim that collapses under one question is the most common way a strong
project loses.
