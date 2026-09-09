# Findings

Named results from the analysis, kept separate from the plan so they can be
quoted directly into the video script and the Devpost entry.

---

## What is, and is not, statistically supported

Everything the site and the video claim must come from the first list. The
second list exists so that nothing in it gets promoted by accident.

**Supported** (n = 52 days, Spearman, α = 0.05):

1. The naive regional fire count correlates with Delhi PM2.5 **on raw levels**:
   ρ = 0.573, p < 0.0001, 95% CI (+0.355, +0.731).
2. That correlation **does not survive detrending**. First differences give
   ρ = 0.052, p = 0.72, CI (−0.226, +0.323); a 7-day detrended residual gives
   ρ = −0.061, p = 0.67. Both CIs contain zero.
3. Consequently **neither model shows detectable day-to-day skill**. This is a
   *bounded* null, not a proof of no effect: with n = 51 differences the
   interval spans roughly ±0.32, so a strong day-to-day relationship is
   excluded and a modest one is not.
4. The wind-aware smoke index is largely a function of transport speed
   (ρ = 0.527 with mean wind speed, p = 0.0001) and of raw fire count
   (ρ = 0.943, p < 0.0001), while that fire count has no detectable
   relationship with PM2.5 (ρ = 0.103, p = 0.47).

**Not supported — must never be phrased as a finding:**

- That wind-aware attribution beats the naive baseline. It does not, in any of
  the four pre-registered specifications (all p ≥ 0.066).
- The directional negative control. Air from the east/south-east sector was
  cleaner on average (129.8 vs 171.5 µg/m³) but Mann-Whitney gives p = 0.21.
- The straightness split. The wind-aware correlation changes sign between
  coherent (+0.184) and recirculating (−0.194) days, which is the direction
  transport physics predicts, but p = 0.30 and p = 0.44 respectively.
- That ventilation lowers PM2.5 (ρ = −0.246, p = 0.079).

The last three are **exploratory observations**. They are worth showing, and
worth saying out loud that they are underpowered at 52 days, but they are not
results.

---

## The Ventilation Paradox

**Two consecutive days, November 2024, same receptor, same burning season.**

| | 18 Nov 2024 | 19 Nov 2024 |
|---|---|---|
| Observed PM2.5 at Delhi | **644 µg/m³** | **256 µg/m³** |
| Wind-aware smoke index | 1,918 | **6,078** — the season's highest |
| Fires crossed by the trajectory | 1,321 | **3,336** |
| Trajectory straightness | 0.85 | 0.96 |
| Upwind bearing | 327° (NW) | 310° (NW) |

On 19 November the arriving air crossed **two and a half times more fires**
than on the 18th, along a straighter path from the same direction — and Delhi's
air was **less than half as polluted**.

### Why this happens

The smoke index counts fires the air passed over during 48 hours of travel. How
many fires it passes over depends on how far it travels, which depends on wind
speed. But wind speed also ventilates the receptor. So the index rises on
exactly the days the city is being flushed out most effectively.

Measured across the season (n = 52, Spearman):

| Pair | ρ | p | |
|---|---|---|---|
| Path length ↔ smoke index | **+0.555** | <0.0001 | supported |
| Ventilation (mean speed) ↔ smoke index | **+0.527** | 0.0001 | supported |
| Fires attributed ↔ smoke index | **+0.943** | <0.0001 | supported |
| Fires attributed ↔ PM2.5 | +0.103 | 0.47 | **null** |
| Ventilation ↔ PM2.5 | −0.246 | 0.079 | not significant |

Read the supported rows together and the problem is precise: the index is
almost entirely determined by how many fires were crossed (ρ = 0.94), and how
many fires get crossed is substantially determined by how fast the air was
moving (ρ = 0.53). Meanwhile the fire count carries no detectable relationship
with the pollution it is meant to explain (ρ = 0.10, p = 0.47).

**The index tracks wind speed better than it tracks pollution.** That statement
is supported. The tempting further claim — that ventilation actively *lowers*
PM2.5 — is only suggestive here (ρ = −0.246, p = 0.079) and is not asserted.

### Why it matters beyond this project

This is the failure mode any "count the upwind fires" attribution will hit, and
it is invisible unless a baseline is run alongside. It is also the reason the
first season-wide comparison lost to a wind-blind baseline: the naive model,
knowing nothing about wind, was not penalised by it.

### Why it belongs in the video

It is a two-frame argument. Two consecutive days, same season, same wind
direction, more fires on the cleaner day. It states the problem, motivates the
physics of the correction, and demonstrates that the project checked its own
work rather than reporting the first correlation it found — without needing a
single equation on screen.

---

## Neither model has day-to-day skill

The naive baseline appeared to win the season-wide comparison decisively —
Spearman 0.573 against the wind-aware index's 0.079. That apparent win does not
survive the removal of the seasonal trend.

| Comparison | wind-aware ρ | p | naive ρ | p |
|---|---|---|---|---|
| **Levels (raw)** | 0.079 | 0.58 | **0.573** | <0.0001 |
| **First differences** | 0.048 | 0.74 | **0.052** | 0.72 |
| **Detrended residuals** (7-day) | 0.032 | 0.82 | **−0.061** | 0.67 |

Both models collapse to zero. The naive baseline's ρ falls from 0.573 to 0.052
once day-over-day changes are used instead of levels, and to −0.061 against a
7-day detrended residual.

### What this means

The naive baseline was never predicting individual days. Burning rises and
falls across the season; Delhi's PM2.5 rises and falls across the season; any
index that tracks the seasonal shape scores well on raw levels without
forecasting a single day correctly. That is the whole of its apparent
advantage.

The tell was visible before the test: enlarging the fire region lifted naive's
levels correlation from 0.300 to 0.573 while giving it no new physics at all.
A model gaining a third of its correlation from a box redefinition is tracking
a calendar, not a mechanism.

### Why this is the stronger result

The honest claim is no longer "our physics lost to a simple baseline." It is:

> On this region and season, **neither** a wind-aware trajectory attribution
> **nor** a naive regional fire count explains day-to-day variation in Delhi's
> PM2.5. The naive baseline's apparent advantage is entirely seasonal
> co-trending and disappears under first differencing.

That is a real negative result about the difficulty of daily source
attribution, and it is only visible because the baseline was kept honest and
then stress-tested. A project that reported the levels correlation and stopped
would have published a number with no day-to-day content in it.

---

## The domain-truncation trap

At 72 hours back, most trajectories from Delhi ran off the original
72–80°E / 26–33.5°N box before finishing. Reducing the integration to 48 hours
brought that down to 8 of 52 days (15.4%), and widening the box to
67.5–82°E / 24–37°N was the second half of the fix.

A truncated trajectory fails silently: it returns a valid, shorter path and an
attribution computed over the part that fitted inside the box. Nothing errors.
The only symptom is a point count below the expected `hours_back × 3600 / dt`,
which is why `exited_domain` is carried on every `Trajectory` and reported per
day in the validation output.
