# Requirements

## Hackathon deliverables (hard requirements from the rules)

- [ ] Video demonstration / pitch, **no longer than 5 minutes**
- [ ] Public link to the code repository
- [ ] Link to the live site (applicable here — we are deploying)
- [ ] If any code predates the hackathon, Devpost must state what was built before vs during

## Functional requirements

### FR1 — Fire ingestion
Load satellite active-fire detections for a chosen bounding box and date range.
Each detection must carry: latitude, longitude, acquisition date, acquisition time,
fire radiative power (FRP), confidence, satellite source.
Low-confidence detections must be filterable. Persistent industrial thermal anomalies
(steel plants, refineries, gas flares) must be removable — they appear at the same
coordinates nearly every day and will otherwise pollute the attribution.

### FR2 — Wind field
Build a gridded, hourly wind field (u, v components) covering the full bounding box
across the full date range. Must support lookup at arbitrary (lat, lon, time) via
bilinear spatial interpolation and linear time interpolation.

### FR3 — Back-trajectory engine
Given a receptor point, a receptor time, a duration and a timestep, integrate the wind
field backwards in time and return an ordered list of (lat, lon, timestamp) points.
Must support launching an ensemble of perturbed trajectories to express uncertainty.

### FR4 — Attribution
Given a trajectory and the fire set, return fires that fall within a corridor radius of
any trajectory point *within a matching time window*, and produce a weighted smoke index.
Weighting must account for fire radiative power and decay with distance from the trajectory
centreline. Attribution must be broken down by administrative district.

### FR5 — Season-wide validation
Run FR3 and FR4 for every day of the season. Produce:
- correlation between the smoke index and observed PM2.5
- the same correlation for a naive baseline (unweighted total fire count, no wind)
- a lag sweep showing which transport delay maximises correlation
- a negative-control subset (no-fire-upwind days) with its PM2.5 distribution

### FR6 — Static export
All computation happens offline in Python. The frontend consumes only pre-generated
JSON files. No API keys, no network calls, and no server exist in the deployed site.

### FR7 — Visualisation
An animated map that plays a single episode: trajectory drawing backwards in time, fires
appearing as the trajectory passes over them, a PM2.5 readout climbing, an attribution
panel filling in. Plus a static validation view showing the season-wide result.
Full specification in `05-animation-spec.md`.

## Non-functional requirements

| ID | Requirement |
|---|---|
| NFR1 | Deployed site loads and plays on a judge's laptop with no setup, no login, no key |
| NFR2 | Total payload of exported JSON under ~8 MB; animation runs at 60fps on integrated graphics |
| NFR3 | Works offline once loaded — no runtime dependency on any third-party API |
| NFR4 | Pipeline is reproducible: `python -m pipeline.run_all` regenerates every export from raw data |
| NFR5 | Raw downloaded data is cached to disk; re-runs never re-hit the APIs |
| NFR6 | Respects `prefers-reduced-motion`; animation has a manual scrub control as an alternative |
| NFR7 | Readable on a 1280px laptop screen — this is what judges will use |

## Technical constraints

- **Python 3.11+** for the pipeline. Libraries: `pandas`, `numpy`, `requests`, `scipy`,
  `geopandas` *(optional — only if district shapefiles are used)*, `matplotlib` for validation plots.
- **Vanilla JS + deck.gl via CDN** for the frontend. **No build step, no bundler, no npm install.**
  This is a deliberate risk-reduction decision: a broken build on Day 6 is a lost hackathon.
- **Static hosting** — GitHub Pages, Netlify drop, or Vercel. No backend.
- Secrets in a `.env` file, never committed. `.env.example` committed instead.

## Explicit non-goals

Real-time data. Forecasting. Multiple receptor cities. User accounts. A chatbot.
Mobile-first design. Any machine learning model. Any of these added before the core
result is proven and animated is a scope failure.

## Definition of done

The project is done when a stranger can open one URL, press play, watch the air travel
backwards to a set of fires, read a district-level attribution, scroll down, and see a
chart demonstrating the effect holds across a whole season better than the naive baseline —
without ever asking a clarifying question.
