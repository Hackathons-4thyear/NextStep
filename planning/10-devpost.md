# Devpost entry

Paste-ready. Matches the video's voice: the question, not a boast.

---

## Name

**Smoke Forensics**

## Tagline

> Does Delhi's smog come from Punjab's burning? We built the model to prove it,
> pre-registered the test, and published what it actually said.

## Elevator pitch (first paragraph — many judges read only this)

Blaming Delhi's winter smog on Punjab's stubble burning is not an academic debate.
It drives enforcement, court directives and fines on individual farmers every
winter, and the obvious way to make that attribution is to count fires burning
upwind. **We built a physical transport model to test whether that reasoning
holds — and it doesn't hold the way it is usually assumed to.** We step recorded
wind backwards from Delhi, fifteen minutes at a time, to reconstruct where the
arriving air came from and which satellite-detected fires it crossed, then test it
across a full season against a deliberately fair baseline. It lost in all four
pre-registered specifications. And when we applied the same scrutiny to the
baseline, that fell apart too — its apparent correlation was the burning season and
the smog season rising together, and it vanished under first differencing.

We are careful about what this licenses. We have **not** shown that enforcement was
misdirected on any particular day. We have shown something narrower: a fire count
cannot tell apart the days when the arriving air actually made that journey from the
days when it did not. On 15 of our 52 days our reconstruction puts the incoming air
arriving from the east rather than the burning belt, and a fire count would have
scored those days identically. Knowing when a method cannot support a conclusion is
what stops it being used to reach one — and that is why a null result was worth
publishing rather than burying.

---

## Inspiration

Air quality projects show you a map of bad air. That is a measurement, not an answer.
Nobody can act on "the air is bad" — action needs to know *which sources*, on *which
days*. Source attribution is the unsolved half of the problem, and unlike a causal
graph inferred from time series, a transport model makes a physical, checkable claim:
the air went over there, and there was burning there.

## What it does

For a chosen city and a pollution episode, it integrates backwards through an ERA5
wind field for 48 hours to reconstruct the path the arriving air travelled, then
intersects that path with NASA FIRMS fire detections — weighted by radiated power,
by distance from the path, and gated on whether the fire was burning within ±12 hours
of the air actually passing over it. Then it does that for every day of the season and
compares the result against a wind-blind baseline.

The site animates one episode — 18 November 2024, when Delhi hit 700 µg/m³ — with a
505 km trajectory, 1,384 attributed fires, and an attribution ledger that fills in as
the air crosses each source region. Fires ignite only once the reconstructed air
reaches them, never before.

## How we built it

Python computes everything offline and writes static JSON; the site is vanilla JS plus
deck.gl from a CDN with no build step, no server, and no API keys in the browser, so
nothing can rate-limit or expire while a judge is watching. Terrain is local Natural
Earth GeoJSON rather than tiles, for the same reason.

The physics is a midpoint (RK2) integrator over a bilinearly interpolated 0.5° wind
grid, with an 8-member ensemble for uncertainty. It is covered by 51 unit tests against
analytic fields with hand-computable answers, because the failure modes here are silent:
an inverted sign convention or a missing `cos(latitude)` term produces trajectories that
look completely plausible on a map and are completely wrong.

## Challenges we ran into

**The FIRMS API's documented day-range limit was wrong.** Every 10-day request returned
HTTP 400. The API's own error message said the real cap was 5. Our first fetch silently
returned 894 detections from a 2-day window and the verification script still called the
target viable — the count cleared its threshold, so the truncation only registered as a
warning.

**Our baseline reference level was circular.** The animation's "before" number was the
median of the very window the episode occurs in, so the episode was inflating the
baseline it was meant to be compared against. Same class of error as shrinking a
baseline's lookback window to make your own model look better.

**The hero frame was broken and it was invisible in code.** The trajectory used a
5-hour trail on a 48-hour path, so the finished frame showed about a tenth of the
journey — 505 km rendered as a white smudge beside the city. It only surfaced when we
started taking real browser screenshots instead of reasoning about the code.

## Accomplishments we're proud of

Pre-registering the specification grid before running it, and publishing all four cells
including the ones that lost. Applying the ventilation correction to the baseline as
well as to our own model, because if ventilation is what matters the baseline is
entitled to it too. And running a significance test on our own negative control, which
killed it — it looked convincing at a glance (129.8 vs 171.5 µg/m³) and gave p = 0.21.

## What we learned

Neither of us had touched atmospheric transport modelling before this. The hardest part
was not the integrator — it was building enough scaffolding to catch ourselves being
wrong. Every substantive finding in this project came from a test we ran hoping it would
confirm something, and it didn't.

Specifically: a correlation on raw levels between two seasonal series is nearly
meaningless, and the tell was visible before we tested it — enlarging our bounding box
lifted the baseline's correlation from 0.300 to 0.573 while giving it no new physics.

## What's next

The correlation appears to depend strongly on which hour of the day is sampled
(ρ = 0.094 at 06:00 UTC versus 0.425 at 18:00 UTC), which fits the diurnal boundary
layer — shallow at night, so transported smoke concentrates instead of dispersing. We
found that by sweeping after the fact, so it is not a result. It is the pre-registered
test we would run next, with more than one receptor and more than one season.

## Built with

`python` · `numpy` · `pandas` · `scipy` · `deck.gl` · `nasa-firms` · `open-meteo` ·
`openaq` · `era5` · `natural-earth` · `github-pages`

---

## Prior work disclosure

**No code in this project predates the hackathon.** The trajectory integrator, wind
field interpolator, attribution scoring, validation framework, export layer and site
were all written during the event. Data belongs to NASA (FIRMS), ECMWF via Open-Meteo
(ERA5), and OpenAQ. deck.gl renders the map.

---

## Required acknowledgement

> We acknowledge the use of data and/or imagery from NASA's Fire Information for
> Resource Management System (FIRMS), part of NASA's Earth Observing System Data and
> Information System (EOSDIS).
