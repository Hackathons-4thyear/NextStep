# Smoke Forensics — Project Brief

**Hackathon:** NextStep Hacks 2026 (HackAlphaX), theme *Earth Forward*
**Deadline:** Sep 14 2026, 02:30 GMT+5:30 — effective working deadline **Sep 13, evening**

---

## The one-sentence pitch

When a city's air turns toxic, we trace the air backwards through the wind to find the
specific fires it passed over — and prove the connection holds across an entire burning season.

## The problem with every other pollution project

Air quality projects at hackathons show you a map of bad air. That is a measurement, not an
answer. Nobody can act on "the air is bad" — action requires knowing *which sources*, in
*which districts*, on *which days*. Source attribution is the actual unsolved half of the problem.

## What we build instead

A physical transport model. For a chosen city and a chosen pollution episode:

1. Take the hour the pollution spiked.
2. Step backwards through the historical wind field, hour by hour, for 48–72 hours,
   reconstructing the path the arriving air mass travelled. This is a **Lagrangian back-trajectory**,
   the same class of method NOAA's HYSPLIT model uses operationally.
3. Intersect that path with satellite-detected active fires from the same time window,
   weighted by each fire's radiated power.
4. Output a ranked attribution: which districts, how many fires, how many hours upwind.

Then repeat across an entire season and show the relationship is statistically real.

## Why this is not the causal-inference idea we rejected

An earlier idea used causal discovery algorithms on pollution time series. It was abandoned
because **it had no ground truth** — you cannot prove an inferred causal graph is correct,
and a judge asking "how do you know?" would have ended the pitch.

This project replaces statistical inference with physical transport. Fires are *observed events*,
not inferred causes. Wind fields are *measured*, not assumed. The claim being made is physical
and checkable: the air went over there, and there was burning there.

## The headline number (the thing that wins)

Not "we found a correlation." The claim is a **comparison against a naive baseline**:

> A naive model that counts all fires anywhere in the region explains **X%** of the variance
> in observed PM2.5. Our wind-aware trajectory attribution explains **Y%**.
> The difference is the value of modelling the physics.

That single sentence is the project. Everything else exists to support it. Compute it early
(Day 3), because if Y is not meaningfully above X, the scope must change before the visuals
are built.

## Supporting evidence to include

- **Negative control.** Days where the back-trajectory arrived from a direction with no fires.
  If those days show no spike, the mechanism is real rather than coincidental. Almost no student
  project includes a negative control; state it out loud in the video.
- **Lag structure.** Attribution should peak at a physically plausible transport delay
  (roughly 6–24 hours depending on distance), not at zero lag. If the lag is physically sensible,
  say so — it is strong evidence the model is capturing real transport.


## Scope discipline

**In scope:** one region, one season, one city as receptor, one clean statistical result,
one excellent animation.

**Out of scope, permanently:** live/real-time data, multiple cities, forecasting, mobile apps,
user accounts, an LLM chatbot layer, anything requiring a server at judging time.

If a day runs over, cut from the analysis, never from the animation. Design is a sixth of the
score and the animation carries the video.
