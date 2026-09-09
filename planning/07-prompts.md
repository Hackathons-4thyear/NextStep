# Prompts — scratch to submission

> **What this file is.** This project was built with AI assistance (Claude), and
> this is the working prompt sequence we used, kept in the repo as part of the
> process record rather than tidied away. The physics, the statistics and every
> decision about what to claim were reviewed and argued over by us; the analysis
> that produced the headline null is reproducible from `pipeline/run_all.py` and
> pinned by 51 unit tests. We would rather show the method than imply there
> wasn't one.

Copy these in order. Each one produces a specific artefact and has a check attached.
Do not run ahead: several prompts depend on real numbers from the previous step, and
guessing them will produce code that fits data you do not have.

## How to use this file

**Upload `00-brief.md` through `06-submission-kit.md` at the start of each session.**
Chats lose context; the documents are the memory. Re-attach after any gap.

**Paste real output back.** When a prompt says to paste results, paste the actual output —
errors, row counts, plots, all of it. Debugging without the real error is guesswork.

**One prompt, one artefact.** Resist bundling. "Write the whole pipeline" produces code
that looks right and fails everywhere at once.

**Work in Claude Code if you can.** It edits files in your repo directly instead of
round-tripping code through chat, which for a project this size saves hours.

---

# Day 1 — Prove the data exists

### P1 · Choose the target
```
I'm building the Smoke Forensics project in the attached docs. Help me choose the
region, season and receptor city.

About me: [country/region you know well, and any local pollution problem you care about].

Give me 3 candidate combinations of (fire source region, receptor city, season date range).
For each: why fire activity should be high, why that city likely has good PM2.5 coverage,
the typical wind direction in that season, and the rough source-to-receptor distance.
Then recommend one and tell me exactly what to check first.
```
**Check:** you have one primary and one backup target before writing any code.

### P2 · Verification script
```
Write me a single Python script that runs the entire Day 1 checklist from 02-data-sources.md
for my chosen target: [paste target and bbox].

It should fetch FIRMS fires, Open-Meteo winds for a coarse grid, and OpenAQ PM2.5 for the
receptor, then print a verdict for each checklist item — pass or fail with the number that
decides it. Cache everything to data/raw/. Use the exact endpoints in the doc; note that
OpenAQ v3 needs the locations → sensors → measurements chain, and FIRMS caps day_range at 10.

Don't build anything else yet.
```
**Check:** the script runs and prints a verdict per item.

### P3 · Read the verdict
```
Here's the output: [paste everything, including any errors].

Walk through each checklist item. Is my target viable? If any item failed, tell me whether
to fix it or switch targets — and be blunt. I'd rather change city today than on Day 4.
```
**Check:** an explicit go or no-go. If no-go, return to P1. This is not a delay, it is the
cheapest decision in the project.

### P4 · Pick the episode
```
Here are the season's daily PM2.5 values and daily fire counts: [paste or attach CSV].

Plot PM2.5 over the season and pick the 3 strongest, cleanest spike episodes. For each,
tell me the exact peak hour in UTC, the baseline level before it, and whether the shape
looks like transport (sharp rise, slow decay) or something local.

Recommend one episode as the hero for the animation.
```
**Check:** one specific UTC datetime written down. Everything downstream points at it.

---

# Day 2 — The physics

### P5 · Repo skeleton
```
Set up the repo exactly as laid out in 03-architecture.md: folders, requirements.txt,
.env.example, .gitignore, and a config.py holding every tunable constant with my values:
[bbox, season dates, receptor lat/lon, episode datetime].

Empty stub files with docstrings for the pipeline modules. No implementation yet.
```

### P6 · Wind field
```
Implement pipeline/fetch_wind.py and pipeline/windfield.py.

fetch_wind builds a lat/lon grid at [0.25 or 0.5]° over the bbox, fetches hourly
wind_speed_100m and wind_direction_100m from the Open-Meteo archive API for the full season
using comma-separated multi-location requests, converts to u/v using the sign convention
in 02-data-sources.md, and caches as a numpy array shaped (n_time, n_lat, n_lon, 2).

windfield.py wraps it in a class with interpolate(lat, lon, datetime) -> (u, v), using
RegularGridInterpolator, bilinear in space and linear in time.

Include a self-test that prints the mean wind direction over the season so I can sanity-check
it against the region's known prevailing wind.
```
**Check:** the printed prevailing direction matches what you know about the region.
If it is 180° off, the sign convention is inverted. Fix it now, not later.

### P7 · The trajectory engine
```
Implement pipeline/trajectory.py following the pseudocode in 03-architecture.md.

back_trajectory(lat, lon, arrival_time, hours_back, dt_seconds) returning a list of
(lat, lon, datetime). dt default 900s. Include the cos(latitude) correction on longitude
displacement, stop if the parcel exits the domain, and return the path reversed so it
reads forward in time.

Also ensemble_trajectories(...) launching N members from small spatial and temporal offsets.

Then a script that runs the hero episode and plots the trajectory over a simple map with
that day's fires, saved to PNG.
```
**Check:** the trajectory ends somewhere plausible and fires cluster near it. Paste the PNG back.

### P8 · Debug the physics
```
Here's the trajectory plot: [attach PNG].

Does this look physically correct? Check for: trajectory running the wrong direction,
unrealistic speed, straight lines where flow should curve, or the path leaving the domain
immediately. If something's wrong, tell me which of the three usual causes it is —
sign convention, units, or timezone.
```

---

# Day 3 — The number that wins

### P9 · Fire cleaning
```
Implement pipeline/fetch_fires.py.

FIRMS area endpoint, chunked into 10-day requests across the season, both VIIRS platforms,
science-quality product. Cache raw CSVs.

Then cleaning: parse acq_date + acq_time as UTC datetimes, filter confidence to n and h,
and build the persistent-source mask described in 02-data-sources.md to strip industrial
thermal anomalies. Print how many detections each filter removed.
```
**Check:** the industrial mask removes a small but non-zero number. Spot-check a few
removed coordinates on a map — they should be plants, not fields.

### P10 · Attribution
```
Implement pipeline/attribution.py per 03-architecture.md.

For a trajectory and the fire set: find fires within corridor_radius of any trajectory point
whose timestamp is within the time tolerance of that fire's detection, weight each by
frp * exp(-(dist/corridor_radius)^2), sum to a smoke index, and roll up by district
(or spatial cluster if I'm skipping shapefiles).

Run it on the hero episode and print the attribution table.
```

### P11 · Season validation — the gate
```
Implement pipeline/validate.py.

Run trajectory + attribution for every day of the season. Compute:
- the wind-aware smoke index per day
- the naive baseline: total FRP of all fires in the region that day, ignoring wind
- Spearman correlation and R² of each against observed PM2.5
- a lag sweep from 0 to 48 hours, showing which lag maximises correlation
- the negative control: days with no fires upwind, and their PM2.5 versus other days
- sensitivity of the result to corridor_radius at 20/30/50 km

Print everything as a clean summary table.
```

### P12 · Read the result honestly
```
Here are the validation results: [paste the full table].

Three questions, and I want the real answer not the encouraging one:
1. Does the wind-aware index beat the naive baseline by a margin worth claiming?
2. Is the best lag physically plausible for my source-receptor distance, or suspiciously zero?
3. Is the negative control convincing?

Then write my headline sentence with the real numbers in it. If the result is weak,
tell me directly and give me the honest reframe from Day 3 of the build plan instead of
helping me dress it up.
```
**Check:** you have one sentence with real numbers. That sentence is the project.

---

# Day 4 — Motion on screen

### P13 · Export
```
Implement pipeline/export.py, producing episode.json and season.json exactly matching the
schemas in 03-architecture.md, written to docs/data/.

Critical: trajectory timestamps must be small elapsed-seconds integers from the animation
window start, never epoch milliseconds — TripsLayer stores them as float32 and epoch values
lose precision.

Print the file sizes so I can confirm we're under the payload budget.
```

### P14 · The map
```
Build docs/index.html and docs/app.js.

deck.gl 9 from CDN, no build step. No basemap tiles — render terrain from a local
Natural Earth GeoJSON with GeoJsonLayer as described in 05-animation-spec.md. Tell me
exactly which Natural Earth files to download and where to put them.

Layers: terrain, fires (ScatterplotLayer filtered by current time, radius scaled by FRP),
trajectory (TripsLayer), receptor marker. requestAnimationFrame loop driving currentTime.

Plain unstyled version first — I just want it moving.
```

### P15 · Fix the animation
```
Current state: [describe what you see, attach a screenshot or screen recording].

[If broken: what's wrong?]
[If working: it plays but looks wrong — trails judder / fires appear too early / timing is off.]

Diagnose and fix.
```
**Check:** it plays end to end. Ugly is fine today.

---

# Day 5 — Make it beautiful

### P16 · Apply the design
```
Now style it to 05-animation-spec.md exactly: palette, IBM Plex typography, edge-anchored
panels rather than floating cards, left alignment throughout.

Build the PM2.5 gauge using the CPCB AQI ramp, the attribution ledger that fills in as the
animation plays, and the timeline scrubber.

Follow the 22-second storyboard beat for beat. The critical detail: fires must ignite when
the trajectory passes over them, never before — the causal reading depends on it.
```

### P17 · The validation view
```
Add the section below the fold: scatter of smoke index versus observed PM2.5 with the naive
baseline shown greyed behind it, the R² comparison stated large and plainly, the lag sweep,
and the negative control.

Same palette. No new colours, no chart library — draw it with deck.gl or plain SVG.
This section has to make the headline number unmissable in a screenshot.
```

### P18 · Design critique
```
Here's the finished interface: [attach screenshots of the hero frame and the validation view].

Critique it as a designer would. Where does it read as templated? Is the hero frame strong
enough to be the Devpost thumbnail? Would someone who knows nothing about this understand
what's happening within ten seconds?

Be harsh. I have one day left to fix it.
```

### P19 · Quality floor
```
Add the accessibility and robustness items from 05-animation-spec.md: prefers-reduced-motion
rendering the final state without autoplay, keyboard-operable scrubber with visible focus,
attributed fires distinguished by more than colour, and a graceful message if a JSON file
fails to load.

Also confirm the site works with no network connection once loaded.
```

---

# Day 6 — Ship and record

### P20 · Deploy and document
```
Walk me through deploying docs/ to GitHub Pages. Then write the README per
06-submission-kit.md, using my real numbers: [paste headline stats].

Include the NASA FIRMS acknowledgement and the limitations section — I want to name my own
weaknesses before a judge does.
```

### P21 · The script
```
Write my final video script from the template in 06-submission-kit.md, with my real numbers
and my real learning moment: [describe the hardest bug or concept you hit this week].

Target 3:30. Mark where I pause for the animation. Flag any sentence that's more than I can
actually defend — I'd rather cut a claim than have it collapse under a question.
```

### P22 · Devpost
```
Write my Devpost entry: tagline, inspiration, what it does, how we built it, challenges,
accomplishments, what we learned, what's next.

[If any code predates 21 August: I need the prior-work disclosure. Before the hackathon I had:
... During the hackathon I built: ...]

Match the voice of the video script. No hype adjectives.
```

---

# Day 7 — Buffer

### P23 · Pre-submission review
```
Final check. Live site: [URL]. Repo: [URL]. Video: [link].

Review against the NextStep Hacks requirements and the six judging criteria. Where would I
lose points? What would a judge ask that I can't currently answer? Is anything missing from
the submission?
```

### P24 · Q&A drill
```
Play a skeptical judge. Ask me the ten hardest questions about this project, one at a time,
starting with the one most likely to expose a weakness. Tell me after each answer whether
it would satisfy you.
```

---

## If a day slips

```
I'm behind — it's [day] and I've only got as far as [state]. Time left: [hours].

Using the cut list in 04-build-plan.md, tell me exactly what to drop and what the minimum
viable submission looks like from here. Don't be optimistic about what I can finish.
```

Ask this early rather than at midnight. The cut list exists precisely so that a tired
person does not have to make this decision from scratch.
