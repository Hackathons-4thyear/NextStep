# Smoke Forensics

**Does Delhi's winter smog come from Punjab's stubble burning? We built a physical
transport model to find out, pre-registered the test, and it said no — or rather,
it said nobody has shown it yet, including us.**

🔗 **Live demo: https://hackathons-4thyear.github.io/NextStep/**

---

## The headline result

We traced the air arriving in Delhi backwards through recorded wind, hour by hour,
and identified the satellite-detected fires it passed over. Then we tested that
attribution against a deliberately fair opponent across an entire burning season.

> On this region and season, **neither** a wind-aware trajectory attribution **nor**
> a naive regional fire count explains day-to-day variation in Delhi's PM2.5.
> The naive baseline's apparent advantage on raw levels (Spearman ρ = 0.573,
> p < 0.0001) is **entirely seasonal co-trending** — it collapses to ρ = 0.052
> (p = 0.71) once we correlate day-over-day changes instead of levels.

This is a null result. It is also the honest one, and getting to it required
killing several findings we wanted to be true.

### The seasonality test that decided it

| Comparison | wind-aware ρ | p | naive ρ | p |
|---|---|---|---|---|
| Raw levels | +0.079 | 0.58 | **+0.573** | **<0.0001** |
| Day-over-day change | +0.048 | 0.74 | **+0.052** | **0.71** |
| Detrended residual (7-day) | +0.032 | 0.82 | −0.061 | 0.67 |

Burning rises and falls across the season; so does Delhi's PM2.5. Any index that
tracks that shared shape scores well on levels without predicting a single day.
The warning sign was visible beforehand: enlarging the fire region lifted the
baseline from ρ = 0.300 to ρ = 0.573 while giving it no new physics at all.

**This is a bounded null, not a proof of no effect.** With 51 day-over-day changes
the 95% interval spans roughly ±0.32, so a strong daily relationship is excluded
and a modest one is not.

### The pre-registered specification grid

Four combinations, fixed in writing *before* the numbers existed. The ventilation
correction is applied to **both** models — if ventilation is what matters, the
baseline is entitled to it too.

| Arrival sampling | Ventilation | wind-aware ρ | p | naive ρ | p | Winner |
|---|---|---|---|---|---|---|
| One 06:00 UTC sample **(primary)** | none | +0.079 | 0.58 | +0.573 | <0.0001 | naive |
| One 06:00 UTC sample | corrected | +0.137 | 0.33 | +0.576 | <0.0001 | naive |
| Mean of four hours | none | +0.221 | 0.12 | +0.650 | <0.0001 | naive |
| Mean of four hours | corrected | +0.257 | 0.066 | +0.648 | <0.0001 | naive |

The wind-aware index reaches significance in none of the four, and beats the
baseline in none of them.

### Why the index fails: it measures wind, not smoke

| Relationship | ρ | p | |
|---|---|---|---|
| Fires crossed ↔ smoke index | +0.943 | <0.0001 | supported |
| Path length ↔ smoke index | +0.555 | <0.0001 | supported |
| Wind speed ↔ smoke index | +0.527 | 0.0001 | supported |
| Fires crossed ↔ PM2.5 | +0.103 | 0.47 | **null** |
| Wind speed ↔ PM2.5 | −0.246 | 0.079 | not significant |

The index is almost entirely the fire count, and the fire count is substantially
set by how fast the air was moving — faster air sweeps over more ground. Meanwhile
the fire count has no detectable relationship with the pollution it is meant to
explain. **The index tracks wind speed better than it tracks smoke.**

Two consecutive days make it concrete:

| | 18 Nov 2024 | 19 Nov 2024 |
|---|---|---|
| PM2.5 at Delhi | **644 µg/m³** | **256 µg/m³** |
| Fires the air crossed | 1,321 | **3,336** |
| Smoke index | 1,918 | **6,078** (season high) |
| Path straightness | 0.85 | 0.96 |

Two and a half times more fires, a straighter path from the same direction — and
less than half the pollution.

---

## How it works

**1. Fires.** NASA FIRMS VIIRS detections (375 m) from both SNPP and NOAA-20
science-quality products across the season. Filtered to nominal/high confidence,
deduplicated, and screened for persistent industrial thermal anomalies by dropping
grid cells that burn on most days — refineries and flares, not fields. 95,055 raw
detections reduce to 85,127 usable ones.

**2. Wind.** Hourly ERA5 reanalysis at 100 m via Open-Meteo, on a 0.5° grid
(27 × 30 points) across the domain. Meteorological direction is converted to
eastward/northward components; getting that sign convention wrong is the single
most likely silent bug in a project like this, so it is pinned by unit tests and
cross-checked against the receptor's known post-monsoon north-westerly regime
(317° measured, 290–330° expected).

**3. Trajectory.** A 48-hour Lagrangian back-trajectory from Delhi, integrated at
15-minute midpoint (RK2) steps through the interpolated wind field — the same class
of method NOAA's HYSPLIT uses. An 8-member ensemble launched from ±0.15° and ±2 h
gives the uncertainty estimate.

**4. Attribution.** Each fire is scored against the path by `frp × exp(−(d/r)²)`
with a 30 km corridor, and only counts if it was detected within ±12 h of the air
actually passing over it. A fire two days stale near the path does not count.

The baseline sums fire power across the whole region over **the same 48-hour
window**, so both models see an identical set of fires and differ only in whether
they know where the wind went. Shrinking that window would have manufactured a win.

---

## Reproduce it

```bash
git clone https://github.com/Hackathons-4thyear/NextStep.git
cd NextStep
pip install -r requirements.txt
cp .env.example .env          # then add your two free API keys
python verify_day1.py         # fetches everything, prints a go/no-go verdict
python -m pipeline.validate   # the season-wide comparison
python -m pipeline.export     # writes docs/data/*.json
python -m tests.test_physics && python -m tests.test_attribution   # 51 checks
```

Keys are free: [FIRMS](https://firms.modaps.eosdis.nasa.gov/api/map_key/) by email,
[OpenAQ](https://explore.openaq.org/register) by registration. Open-Meteo needs none.

The site is static. Serve `docs/` over HTTP and it runs with no server, no keys in
the browser, and no network calls beyond the deck.gl bundle.

---

## Limitations

Stated by us, because they are real.

- **Neither model shows day-to-day skill, and our sample is small.** n = 52 days,
  one receptor city, one season. The null is bounded at roughly ±0.32, not proven.
- **The straightness split is not significant.** The wind-aware correlation flips
  from +0.184 on coherent-transport days to −0.194 on recirculating days, which is
  the direction transport physics predicts, but p = 0.30 and p = 0.44. We report it
  as exploratory and it is not a finding.
- **The negative control is not significant.** Air arriving from the sector with no
  burning was cleaner on average (129.8 vs 171.5 µg/m³, n = 15 vs 37), but
  Mann-Whitney gives p = 0.21. We are not claiming it.
- **A single-particle trajectory is a simplification.** Real plumes disperse; we
  approximate that with a corridor radius and an ensemble rather than modelling
  dispersion. The model is 2-D with no vertical motion between levels.
- **Satellite detections miss fires** under cloud and between overpasses, so the
  fire count is a floor, not a total.
- **Reanalysis wind is ~10 km** and will not resolve terrain-driven local flow.
- **Attribution across a season is evidence about transport, not proof about any
  individual fire.**
- **Source regions are named by nearest towns**, not by a district boundary join.
  A 1° grid cell is labelled from the towns inside it.

## Claims we could have made, and didn't

Each of these is a sentence this project could have written, and several of them
are what we expected to be writing when we started. Each is followed by the
statistic that killed it.

| Claim we didn't make | What killed it |
|---|---|
| "Delhi's smog comes from Punjab's burning." | Our own pre-registered test failed to show it: wind-aware ρ = 0.079, p = 0.58, and it lost in all four specifications. |
| "These 1,384 fires caused the pollution." | Attribution establishes *passage*, not causation. Across the season, fires crossed against PM2.5 is ρ = 0.103, p = 0.47. |
| "Attribution works on coherent-transport days." | ρ = +0.184 on those 34 days, p = 0.30. The sign is right; the evidence isn't there. |
| "Days when the air came from a direction with no fires were cleaner." | 129.8 vs 171.5 µg/m³ looks convincing. Mann-Whitney on n = 15 vs 37 gives **p = 0.21**. |
| "Wind ventilates the city, so it lowers PM2.5." | ρ = −0.246, p = 0.079. Suggestive, and not significant. |
| "We proved the naive fire count is wrong." | Narrower than that: we showed its *levels* correlation is seasonal co-trending (0.573 → 0.052 differenced). It may still be right for reasons we cannot test at n = 52. |
| "There is no relationship between fires and Delhi's air." | Overclaims a null. The 95% interval on the differenced correlation spans about ±0.32 — a strong effect is excluded, a modest one is not. |

The first four are the ones that cost something to give up. The directional
negative control in particular was described in our own working notes as the
strongest surviving evidence, right up until we ran a significance test on it.

## What we would do next

Test the receptor's diurnal cycle properly — a post-hoc sweep suggested the
correlation depends strongly on the hour sampled (ρ = 0.094 at 06:00 UTC vs 0.425
at 18:00 UTC). That is not a result, it is a reason the current specification may
be underpowered, and it deserves a pre-registered test of its own.

---

## Data sources

- **NASA FIRMS** — VIIRS active fire detections (SNPP + NOAA-20, science-quality)
- **Open-Meteo** — ERA5 reanalysis hourly wind, CC BY 4.0
- **OpenAQ v3** — ground reference-monitor PM2.5
- **Natural Earth** — admin-1 boundaries, 1:50m

> We acknowledge the use of data and/or imagery from NASA's Fire Information for
> Resource Management System (FIRMS), part of NASA's Earth Observing System Data
> and Information System (EOSDIS).

## Prior work disclosure

**Nothing in this repository predates the hackathon.** All code, analysis and
design in this repository — the trajectory integrator, the wind field
interpolator, the attribution scoring, the validation framework, the export layer
and the site — was written during the event. The data belongs to NASA, ECMWF via
Open-Meteo, and OpenAQ; deck.gl renders the map.
