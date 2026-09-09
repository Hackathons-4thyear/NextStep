# Build Plan — 7 days

Today is **Sun 7 Sep**. Submission deadline is **14 Sep 02:30 IST**, which means the real
deadline is the evening of **13 Sep**. Do not plan to be working at 2am on the 14th.

Each day has a **gate**. If the gate fails, the response is written down in advance so that
a tired brain at 11pm does not have to invent one.

---

## Day 1 — Sun 7 Sep · Prove the data exists

**Do nothing but fetch and inspect.** No modelling, no visuals, no repo polish.

1. Register both keys (FIRMS by email, OpenAQ at explore.openaq.org/register).
2. Pick a candidate region, season and receptor city.
3. Work through the full Day 1 checklist in `02-data-sources.md`.
4. Plot three things in a notebook: PM2.5 over the season, fire counts per day,
   and a wind rose for the receptor.
5. Pick **one specific episode day** — a large, clean, unambiguous PM2.5 spike.

**Gate:** the receptor city has near-continuous hourly PM2.5 across the season, the season
has thousands of fire detections, and at least three clear spike episodes exist.

**If the gate fails:** change the city, or the season, or the region — today. This is a
cheap change now and a project-ending one on Day 4. Do not proceed on the hope that
the gaps will not matter.

---

## Day 2 — Mon 8 Sep · The physics

1. Build the wind grid fetch and cache it.
2. Write `windfield.py` with the interpolator.
3. **Validate the u/v sign convention** by checking the prevailing direction against what
   is known about the region's climate. Getting this backwards is the most likely silent
   bug in the whole project.
4. Write `trajectory.py` and run a single back-trajectory from the chosen episode.
5. Plot it on a simple matplotlib map with the fires overlaid.

**Gate:** you are looking at one trajectory that ends somewhere physically plausible,
and fires visibly cluster near it.

**If the gate fails:** check the sign convention first, then units (m/s vs km/h),
then the timezone alignment. It will be one of those three.

---

## Day 3 — Mon 9 Sep · The number that wins

The most important day. Everything after this is presentation.

1. Write `attribution.py` — corridor matching, FRP weighting, district rollup.
2. Run the trajectory + attribution across every day of the season.
3. Compute the naive baseline.
4. Compute: Spearman correlation for both, R² for both, the lag sweep, the negative control.
5. Write the headline sentence down, with the real numbers in it.

**Gate:** the wind-aware index beats the naive baseline by a clear, defensible margin,
and the best lag is physically plausible rather than zero.

**If the gate fails:** in order — widen the corridor radius; check the time-window tolerance;
try 10 m winds instead of 100 m; try a different episode-heavy sub-period. If after all that
the margin is genuinely small, **do not fake it**. Reframe the project honestly as
"when does wind-aware attribution help, and when does it not?" — a real negative result,
clearly presented, still scores well on Technology and Learning, and scores far better than
a claim that collapses when a judge asks one question.

---

## Day 4 — Wed 10 Sep · Motion on screen

1. Write `export.py`, produce `episode.json` and `season.json`.
2. Set up `docs/index.html` with deck.gl from CDN and a dark basemap.
3. Get the TripsLayer animating the trajectory.
4. Get fires appearing in time with the trajectory passage.

**Gate:** the animation plays end to end in a browser, even if it is ugly.

**If the gate fails:** check the timestamp precision issue in `03-architecture.md` first —
that is the classic TripsLayer bug. If deck.gl is fighting you by late evening, fall back
to a 2D canvas animation. Something moving beats nothing perfect.

---

## Day 5 — Thu 11 Sep · Make it beautiful

Follow `05-animation-spec.md` closely. This is a full day on visuals and that is correct:
Design is a sixth of the score and the animation carries the entire video.

1. Palette, typography, layout.
2. The PM2.5 gauge and the attribution panel filling in as the animation plays.
3. The scrub control and reduced-motion fallback.
4. The season validation view below the fold.
5. Copy — every label rewritten as plain language.

**Gate:** show it to someone who knows nothing about the project. If they cannot say what
is happening within ten seconds without help, the visual has failed, not them. Fix it.

---

## Day 6 — Fri 12 Sep · Ship and record

1. Deploy to GitHub Pages. Test on a different device and a different browser.
2. Write the README (see `06-submission-kit.md`).
3. Write the Devpost entry, including the prior-work disclosure if any code predates 21 Aug.
4. Write the video script, rehearse twice, record.

**Gate:** a link exists that a stranger can open and that works.

---

## Day 7 — Sat 13 Sep · Buffer, then submit

Reserved for the thing that will go wrong. If nothing does, re-record the video — the
second take is always better than the first.

**Submit by evening.** Not at 2am. Late submissions to a deadline in an unfamiliar timezone
are a genuinely common way to lose a hackathon you had already won.

---

## Cut list, in order

When a day runs long, cut from the top of this list. Never cut from the bottom.

1. District boundary shapefiles → cluster fires and name by nearest town instead
2. Ensemble trajectories → ship the single primary trajectory
3. Sensitivity analysis across corridor radii
4. The lag sweep chart → keep the number, drop the chart
5. Multiple episodes → one is enough
6. — everything below this line is untouchable —
7. The negative control
8. The naive baseline comparison
9. The animation
10. The video
