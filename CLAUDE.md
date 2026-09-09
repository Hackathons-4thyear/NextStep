# Smoke Forensics — working context

Hackathon project. **Deadline: evening of 13 Sep 2026.** Every decision is
constrained by that.

Full planning documents are in `planning/`. Read `planning/00-brief.md` and
`planning/04-build-plan.md` before making structural suggestions.

## What this is

Traces city air pollution back to the fires that caused it. Integrates
backwards through an ERA5 wind field from a receptor city at a pollution peak,
reconstructs the path the arriving air travelled over 72 hours, and identifies
which satellite-detected fires it passed over.

The claim that wins the hackathon is one sentence:

> A naive model counting all fires in the region explains X% of PM2.5 variance.
> Wind-aware trajectory attribution explains Y%.

Everything in this repo exists to support that sentence or to show it on screen.

## Current state — complete and deployed

| Component | State |
|---|---|
| `pipeline/windfield.py`, `pipeline/trajectory.py` | Done. 26/26 tests pass. |
| `pipeline/attribution.py` | Done. 25/25 tests pass. |
| `pipeline/fetch_*.py` | Done. All three sources fetched and cached. |
| `verify_day1.py` | Run. 14 passed, 0 warnings, 0 blocking. |
| `pipeline/validate.py` | Done. Season-wide comparison + specification grid. |
| `pipeline/export.py` | Done. Writes `docs/data/*.json`. |
| `pipeline/run_all.py` | Done. Thin orchestrator over all five stages. |
| `docs/` site + animation | Done and deployed to GitHub Pages. |

**Live:** https://hackathons-4thyear.github.io/NextStep/

## The result, so nobody re-derives it

The headline is a **null**, and it is deliberate. Neither the wind-aware
trajectory index nor the naive fire count explains day-to-day variation in
Delhi's PM2.5. The naive baseline's apparent levels correlation (ρ = 0.573)
is seasonal co-trending and collapses to ρ = 0.052 under first differencing.

Do not "fix" this by searching for a specification that wins. The four-cell
grid was pre-registered and all four are reported. See `planning/08-findings.md`
for what is and is not statistically supported, and the README section
"Claims we could have made, and didn't".

## Rules for this repo

**Do not write `validate.py` or `export.py` until `verify_day1.py` has run
successfully.** Both must match the actual shape of the fetched data. Writing
them against a guess produces code that looks correct and fits nothing.

**Every constant goes in `config.py`.** No magic numbers in pipeline modules.
This is what makes the Day 3 sensitivity analysis a five-minute job.

**All datetimes are timezone-aware UTC** until the final display layer. FIRMS
`acq_time` is UTC. A naive datetime crossing a module boundary silently means
"local time" somewhere downstream and shifts the whole analysis. The trajectory
integrator raises `TypeError` on naive datetimes — keep it that way.

**Run the tests after touching physics or attribution:**
```
python -m tests.test_physics
python -m tests.test_attribution
```
They need no network and no keys. They test against analytic fields with
hand-computable answers, because the failure modes here are silent — an
inverted sign convention or a missing `cos(latitude)` term produces
trajectories that look plausible on a map and are completely wrong.

**Do not weaken the naive baseline.** It sums FRP over the same 72-hour window
the trajectory covers, so both models see identical fires and the only
difference is wind knowledge. Shrinking that window would hand the comparison
a fake win and make the headline claim worthless.

**Scope is fixed.** No real-time data, no forecasting, no multiple cities, no
ML model, no chatbot. If a day runs long, cut from the list in
`planning/04-build-plan.md`, and cut analysis before cutting the animation —
Design is a sixth of the judging score.

## Stack decisions, already made

- Python does all computation offline and writes static JSON to `docs/data/`.
- The site is vanilla JS + deck.gl from CDN. **No build step, no bundler, no
  npm install.** A broken build on Day 6 loses the hackathon.
- Deployed to GitHub Pages from `docs/`. No server, no API keys in the browser.
- No basemap tiles. Terrain renders from local Natural Earth GeoJSON, so the
  site is self-contained and cannot break while a judge is watching.

## Next action

Run `python verify_day1.py`. It fetches all three sources and prints a go/no-go
verdict. Two numbers matter most:

- **Prevailing wind direction** — if it is ~180° off from the region's known
  climate, the sign convention is inverted and everything downstream is wrong.
- **PM2.5 coverage** — below 70%, change receptor city *today*. On Day 4 that
  change costs the project.
