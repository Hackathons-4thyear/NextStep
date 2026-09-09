# Submission Kit

The video is the highest-leverage artefact in this project. Judges watch it before they open
the repo, and many decide there. Budget real time for it.

---

## Video script — target 3:30, hard ceiling 5:00

Shorter is better. A tight 3:30 beats a rambling 4:50, and going over five minutes risks
disqualification on a stated requirement.

### 0:00–0:20 · The question, immediately

No logo, no title card, no "hi we're team X." Open on the map, already dark, city marked.

> "On the 8th of November, air quality here hit 412 micrograms. That's severe. Every air
> quality app in the world can tell you that. None of them can tell you where it came from."

### 0:20–1:20 · The demo, running

Play the animation. Narrate it as it happens, and say nothing that the screen is not showing.

> "So we ran the wind backwards. This is the actual air that arrived in the city that morning,
> traced back through the historical wind field, fifteen minutes at a time, for three days.
> Every fire that lights up is a fire that specific air mass passed directly over. The faint
> paths are our uncertainty ensemble.
> Three hundred and forty fires. Three districts. Fourteen hours upwind."

Let the animation breathe. Do not talk over the final beat.

### 1:20–2:00 · How it works

> "This is a Lagrangian back-trajectory — the same class of method NOAA's HYSPLIT model uses
> operationally. Satellite fire detections come from NASA FIRMS at 375 metre resolution.
> Winds are ERA5 reanalysis. Air quality is from ground reference monitors. Every fire is
> weighted by its radiated power and by how close it sat to the path."

### 2:00–3:00 · The evidence

This is the section that wins. Slow down here.

> "One day proves nothing, so we ran it across the whole season.
> A naive model that just counts fires anywhere in the region explains 18% of the variance
> in observed PM2.5. Ours, which follows the wind, explains 52%.
> The correlation peaks at a 14-hour lag — which is roughly how long the air actually takes
> to make that journey. We didn't tune that. It fell out of the physics.
> And on the eighteen days where the wind came from a direction with no fires, the spikes
> don't happen. That's our negative control."

*(Replace every number with your real ones. If a number is worse than you hoped, say the real
one anyway — see the honesty note below.)*

### 3:00–3:30 · What it's for, and what you learned

> "Knowing that the air is bad changes nothing. Knowing which districts, on which days, and
> how many hours ahead of time, is what makes enforcement and early warning possible.
> Neither of us had touched atmospheric transport modelling before this week. The hardest
> part wasn't the model — it was discovering our trajectories ran backwards for a full day
> because of a sign convention in how meteorologists define wind direction."

That last line does real work. The **Learning** criterion explicitly asks whether the team
stretched themselves, and a specific, honest failure is far more convincing than a claim
of having learned a lot.

### Production notes

- Screen recording at 1080p minimum. Zoom the browser to ~110% so text is legible when compressed.
- Record audio separately if you can; laptop mic over a playing animation sounds poor.
- Rehearse twice before recording. The second take is always better.
- No background music under narration.

---

## README structure

1. One-sentence description, then the live link, then a GIF of the animation.
   Put the GIF above everything. Many judges will not scroll.
2. The headline result, stated as a number, in the first screen.
3. How it works — the four pipeline stages, one paragraph each.
4. Data sources with links, and the required NASA FIRMS acknowledgement.
5. Reproduce it: clone, `pip install -r requirements.txt`, add keys to `.env`,
   `python -m pipeline.run_all`.
6. Limitations, honestly stated. See below.
7. What was built before vs during the hackathon, if any code predates 21 August.

---

## Limitations to state yourself

Naming your own weaknesses before a judge finds them converts a vulnerability into evidence
of rigour. It also makes every other claim more credible.

- A single-particle trajectory is a simplification. Real smoke plumes disperse; we approximate
  that with a corridor radius and an ensemble rather than modelling dispersion properly.
- Satellite detections miss fires under cloud cover and small fires between overpasses,
  so the fire count is a floor, not a total.
- Correlation across a season is evidence of transport, not proof of attribution for any
  individual fire.
- Reanalysis wind is ~10 km resolution and will miss local terrain-driven flow.
- We validate against one receptor city in one season.

---

## Devpost entry

Reuse the video's opening line as the tagline. Include the animation GIF. State the headline
number in the first paragraph. Add the prior-work disclosure if applicable — the rules require
it and omitting it is an unforced disqualification risk.

---

## Judge questions to prepare for

**"What's a back-trajectory, in one sentence?"**
Follow the wind backwards from the city and see what the air crossed on its way in.

**"How is this different from correlating fires and pollution?"**
Correlation asks whether fires and pollution happen on the same day. This asks whether *this
specific air* passed over *those specific fires*, which is why it works even when there are
fires everywhere and only some of them matter.

**"How do you know your trajectories are right?"**
We don't, individually. That's why the claim is statistical: across 61 days, wind-aware
attribution explains three times the variance of the naive baseline, and the effect peaks
at a physically sensible lag we didn't tune for.

**"Could you do this in real time?"**
Yes — the wind data has a forecast endpoint, so the same model runs forwards to predict where
today's smoke lands tomorrow. We scoped to historical validation because a forecast you can't
check isn't evidence.

**"What did you actually build versus what did you use?"**
The trajectory integrator, the wind field interpolator, the attribution scoring and the whole
validation framework are ours. The data is NASA's and ECMWF's. deck.gl renders it.

---

## A note on honesty

If your real numbers are weaker than the placeholders in this script, use the real numbers.
An overstated claim that collapses under a single question is one of the most common ways a
strong hackathon project loses, and student judges ask that question more often than people
expect. A modest, defended, honestly-bounded result beats an impressive one you cannot support.
