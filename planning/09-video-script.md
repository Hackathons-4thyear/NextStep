# Video script — 638 words, 4:54 at recording pace

Timed at **130 words per minute**, which is what people actually do on camera —
not the 150 wpm a silent read suggests. Measured, not estimated:

| Pace | Runtime |
|---|---|
| 120 wpm (slow, nervous) | 5:19 — **over the ceiling** |
| **130 wpm (realistic)** | **4:54** |
| 140 wpm (confident) | 4:33 |

Six seconds of headroom at the realistic pace. If a rehearsal runs over 5:00,
`11-shot-list.md` lists the two lines to cut and the four that must survive.

Shot directions and the read-aloud stumble list are in `11-shot-list.md`.

Every number is pulled from `docs/data/`. If you re-run the pipeline and a
number moves, fix it here too.

---

## 0:00 – 0:20 · The question

**Shot:** the map, already dark, Delhi marked, nothing moving. No title card, no
logo, no team introduction.

> "Every winter Delhi's air turns toxic, and everybody already knows the answer:
> it's the stubble burning up in Punjab.
>
> We wanted to prove it. So we built a physical transport model, wrote down our
> test before we ran it — and it told us something we didn't want to hear."

---

## 0:20 – 1:00 · The demo

**Shot:** one play-through at full speed, then scrub back and hold on the count
frame while you finish. The scrub doubles as proof the timeline is interactive.
**Stop talking for the last three seconds of the play-through** so the final
frame lands in silence.

> "This is the air that arrived in Delhi on the morning of the 18th of November,
> when PM2.5 hit seven hundred micrograms.
>
> We're stepping the recorded wind backwards, fifteen minutes at a time, for
> forty-eight hours. The faint lines are seven alternative starting points —
> that's our uncertainty. Every fire lights up only once the air reaches it.
>
> Five hundred kilometres. One thousand three hundred and eighty-four fires.
> Nearly half the weight in one place: Jalandhar and Moga, in Punjab."

---

## 1:00 – 1:40 · Why this matters

**Shot:** hold on the finished frame, path from Punjab to Delhi still on screen.
Do not scroll yet. **This beat is the reason the project exists and it has to
land before any result does.** Do not cut it.

> "This question isn't academic. Blaming Delhi's smog on Punjab's burning isn't a
> debate that happens in journals — it drives enforcement, court directives,
> fines on individual farmers, every winter.
>
> So the accuracy of the attribution is somebody's livelihood. And counting fires
> is the obvious way to do it: lots of burning upwind, therefore the smoke is
> theirs.
>
> We wanted to know whether that reasoning holds. Because if it doesn't, the cost
> isn't a wrong number in a paper — it's blame landing on the wrong people, on
> the wrong day."

---

## 1:40 – 1:52 · How it works

**Shot:** scrub slowly across the path.

> "Underneath, it's a Lagrangian back-trajectory — the method NOAA's HYSPLIT
> uses. Fires from NASA FIRMS, winds from ERA5 reanalysis."

---

## 1:52 – 2:38 · We pre-registered it, and it lost

**Shot:** scroll to the specification grid. Let the four rows sit on screen.

> "One convincing day isn't evidence. So we wrote down what would count as
> success *before* we ran it — four specifications, fixed in advance. That's
> called pre-registering: it means you can't quietly go looking for the version
> that works.
>
> Our opponent was deliberately fair — a naive model that just counts all the
> fire power in the region over the same forty-eight hours. Both see identical
> fires. Ours also knows where the wind went.
>
> And by that standard, all four specifications failed. Our index never reached
> significance in any of them.
>
> That's not a failed project. Knowing a method doesn't work, and why, is a
> result."

---

## 2:38 – 3:50 · Why — and what it means for the people being blamed

**Shot:** the Nov 18 / Nov 19 paired bars, then the scatter chart.

> "Here's why. Two consecutive days. On the 19th the air crossed two and a half
> times more fires than on the 18th, along a straighter path from the same
> direction — and Delhi's air was less than half as polluted.
>
> Our index counts fires along the path. But how many you cross depends on how
> far the air travelled, which depends on wind speed — and wind also blows the
> city clean. We built an index that rises on the days the pollution gets flushed
> out.
>
> The baseline fell apart too. Its correlation was point five seven. But burning
> and smog both rise and fall across the season — two things following the
> calendar track each other without either causing the other. Ask whether a
> *change* in burning predicts a *change* in pollution, and it drops to point
> zero five.
>
> And this comes back to the farmers. On fifteen of our fifty-two days, our
> reconstruction says the arriving air hadn't come from the burning belt at all.
> We're not telling you enforcement was wrong. We're telling you a fire count
> could never have told you it was right."

---

## 3:50 – 4:30 · What we actually learned

**Shot:** the limitations section, then back to the hero frame for the last line.

> "The interesting part wasn't the model. It was the three times we nearly fooled
> ourselves. A baseline whose reference level was the median of the window it was
> meant to precede — circular, and it flattered us. A negative control that looked
> convincing, and died when we significance-tested it. And that point five seven,
> which looked like a finding until we asked whether it survived removing the
> season.
>
> That last one is the result. We didn't just fail to find something — we showed
> the obvious method's apparent skill was an artefact. The calendar, not the
> physics.
>
> We can't tell you Delhi's smog comes from Punjab. We can tell you why counting
> upwind fires won't prove it."

---

## Sentences to check before you record

Things I would push back on if a judge asked. None of these are in the script
above — they are the versions we deliberately did **not** write.

| Do not say | Why it fails |
|---|---|
| "Delhi's smog comes from Punjab" | We did not show this. Our own test failed to. |
| "These 1,384 fires caused the pollution" | Attribution is passage, not causation. Say "the air passed over". |
| "Our model shows attribution works on transport days" | p = 0.30. Not significant. |
| "Days with no upwind fires were cleaner" | p = 0.21. Not significant. Do not state it as fact. |
| "On stagnation days the pollution is local" | The straightness split is p = 0.30 / 0.44. Say where the air *came from*, which we reconstruct, not what caused the pollution, which we did not establish. |
| "There is no relationship between fires and Delhi's air" | Overclaims a null. The interval is ±0.32; we can exclude a strong effect, not a modest one. |
| "We proved the naive baseline is wrong" | We showed its levels correlation is seasonal. That is narrower. |
| "Wind ventilates the city, lowering PM2.5" | ρ = −0.246, p = 0.079. Suggestive, not significant. |

### Every number in the script, and where it comes from

Checked line by line against `docs/data/`. If a judge challenges one, this is
where to point.

| Spoken | Value | Source |
|---|---|---|
| "seven hundred micrograms" | 700.0 | `episode.pm25_peak` |
| "nearly three times the threshold for severe" | 700 ÷ 250 = 2.8× | CPCB severe band is >250 µg/m³ |
| "fifteen minutes at a time" | 900 s | `config.TRAJECTORY_DT_SECONDS` |
| "forty-eight hours" | 48 | `config.TRAJECTORY_HOURS_BACK` |
| "seven alternative starting points" | 8 members, 1 unperturbed | `config.ENSEMBLE_SIZE` |
| "five hundred kilometres" | 504.9 km | `episode.path_km` |
| "one thousand three hundred and eighty-four fires" | 1,384 | `episode.fires_attributed` |
| "nearly half the attributed weight… Jalandhar and Moga" | 48.9% of weight | `episode.attribution[0].share` |
| "375 metres" | VIIRS resolution | NASA FIRMS |
| "twelve hours" | ±12 h | `config.FIRE_TIME_TOLERANCE_HOURS` |
| "we lost in all four" | all `smoke_wins` false, all `p_smoke` ≥ 0.066 | `specification_grid` |
| "two and a half times more fires" | 3,336 ÷ 1,321 = 2.53× | `ventilation_paradox` |
| "less than half as polluted" | 255.8 ÷ 644.0 = 40% | `ventilation_paradox` |
| "point five seven" | 0.573 | `detrended_comparison.levels.rho_naive` |
| "point zero five" | 0.052 | `detrended_comparison.first_differences.rho_naive` |
| "fifteen of our fifty-two days… came in from the east" | 15 of 52 | `negative_control.n_control_days`, bearing sector 45–225° |
| "it drives enforcement, court directives, fines" | background, not our data | **See the flag below — the one claim in the script not backed by this project.** |
| "four hundred kilometres in the wrong direction" | 505 km path, NW origin | `episode.path_km`, `episode.origin` |

**Three errors were caught in the first draft of this script** and are fixed
above. Recording the draft version would have put false numbers in the video:

1. *"Eight alternative starting points"* — there are eight ensemble members, but
   one is the unperturbed primary, so only **seven** are alternatives.
2. *"1,384 fires… half of them in one place"* — Jalandhar–Moga is 48.9% of the
   **weighted** attribution but only 349 fires, or **25%** of the count. Saying
   "half of them" straight after the fire count asserts something false.
3. *"The three times we nearly fooled ourselves"* originally listed keeping the
   baseline window coupled. That was a trap **avoided by design**, not a
   near-miss, so it was replaced with the seasonal correlation — which genuinely
   did look like a finding until it was differenced.

---

## Production notes

- 1080p minimum. Browser at ~110% zoom so the ledger text survives compression.
- Record audio separately. A laptop mic over a playing animation sounds poor.
- No music under narration.
- Rehearse twice. Record the second take and the third; keep the third.
- The animation runs 22 seconds. For §2 you will need roughly two play-throughs,
  or one play plus a slow scrub — plan which before you hit record.

---

## The one claim in this script that our data does not support

> *"It drives enforcement, court directives, fines on individual farmers, every
> winter."*

This is background context about how stubble-burning attribution is used in
India. **We did not measure it, and nothing in this repository evidences it.**
It is included because it is the reason the accuracy of the method matters, and
it is widely reported — but if a judge asks "how do you know that?", the honest
answer is "that's context, not our finding; our finding starts at the next
sentence."

Two guards keep the rest of the beat defensible:

- We say **"our reconstruction says"** the air came from the east on 15 of 52
  days — attributing it to the model, not asserting it as ground truth.
- We explicitly say **"we're not telling you enforcement was wrong on those
  days."** The claim is bounded to what a fire count can and cannot support.
  Do not let this drift in the recording into "enforcement is misdirected."

If you would rather not carry the background claim at all, the beat still works
with it removed — cut to *"a fire count is the obvious way to do it"* and the
argument survives, just with less weight behind why accuracy matters.
