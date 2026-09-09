# Video script — 3:30 target

Word count is tuned to roughly 150 words per minute. Read it aloud with a stopwatch
before recording; if you land over 4:00, cut from §3 (How it works) first, never
from §5 (Why it failed).

Every number here is pulled from `docs/data/season.json`. If you re-run the
pipeline and a number moves, fix it here too.

---

## 0:00 – 0:25 · The question

**Shot:** the map, already dark, Delhi marked, nothing else moving. No title card,
no logo, no team introduction.

> "Every winter, Delhi's air turns toxic, and everybody already knows the answer:
> it's the stubble burning up in Punjab.
>
> We wanted to prove it. So we built a physical transport model, wrote down our
> test before we ran it — and it told us something we didn't want to hear."

*(~55 words · 22s)*

---

## 0:25 – 1:15 · The demo

**Shot:** play the animation from the top. Let it run. Say nothing the screen is
not showing, and **stop talking for the last three seconds** so the final frame
lands in silence.

> "This is the air that arrived in Delhi on the morning of the 18th of November,
> when PM2.5 hit seven hundred micrograms — nearly three times the threshold for
> 'severe'.
>
> We're stepping the recorded wind backwards, fifteen minutes at a time, for
> forty-eight hours, to reconstruct where that air came from. The faint lines are
> eight alternative starting points — that spread is our uncertainty.
>
> Every fire that lights up is one this specific air mass passed over, and it only
> lights up once the air actually reaches it.
>
> Five hundred kilometres. One thousand three hundred and eighty-four fires.
> Half of them in one place: Jalandhar and Moga, in Punjab."

*(~125 words · 50s)*

---

## 1:15 – 1:40 · How it works

**Shot:** hold the finished frame, or scrub slowly back and forth.

> "This is a Lagrangian back-trajectory — the same class of method NOAA's HYSPLIT
> model uses. Fire detections are NASA FIRMS at 375 metres. Winds are ERA5
> reanalysis. Air quality is ground reference monitors. Each fire is weighted by
> its radiated power and how close it sat to the path, and it only counts if it
> was burning within twelve hours of the air passing over."

*(~62 words · 25s)*

---

## 1:40 – 2:20 · We pre-registered it, and it lost

**Shot:** scroll to the specification grid. Let the four rows sit on screen.

> "One convincing day is not evidence. So before we ran anything, we wrote down
> the test: four specifications, fixed in advance, scored against a deliberately
> fair opponent — a naive model that just counts all the fire power in the region
> over the same forty-eight hours. Both models see identical fires. The only
> difference is that ours knows where the wind went.
>
> We lost. In all four. The naive fire count beat our physics every single time,
> and our index never reached significance in any of them."

*(~95 words · 38s)*

---

## 2:20 – 3:05 · Why — and what beat the baseline too

**Shot:** the Nov 18 / Nov 19 two-frame comparison, then the scatter chart.

> "Here's why. Look at two consecutive days. On the 19th, the air crossed two and
> a half times more fires than on the 18th, along a straighter path from the same
> direction — and Delhi's air was less than half as polluted.
>
> Our index counts fires along the path. But how many fires you cross depends on
> how far the air travelled, and that depends on wind speed — and wind also blows
> the city clean. We built an index that goes up on exactly the days the pollution
> gets flushed out.
>
> Then we tested the baseline the same way, and it fell apart too. Its correlation
> was point five seven — but that's the burning season and the smog season rising
> together. Correlate day-to-day changes instead of levels, and it drops to point
> zero five. Neither model predicts any individual day."

*(~150 words · 60s)*

---

## 3:05 – 3:30 · What we actually learned

**Shot:** the limitations section, or back to the hero frame.

> "The interesting part wasn't the model. It was the three times we nearly fooled
> ourselves.
>
> We caught a baseline whose reference level was the median of the very window it
> was supposed to precede — circular, and it flattered us. We found our own
> negative control looked convincing at a glance and died the moment we ran an
> actual significance test on it. And we kept the baseline's lookback window
> locked to ours, because shrinking it would have handed us a win we hadn't earned.
>
> We can't tell you Delhi's smog comes from Punjab. We can tell you exactly why
> counting upwind fires won't prove it — and that's worth more than a number we
> couldn't defend."

*(~125 words · 50s)*

**Total: ~610 words ≈ 3:25.**

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
| "There is no relationship between fires and Delhi's air" | Overclaims a null. The interval is ±0.32; we can exclude a strong effect, not a modest one. |
| "We proved the naive baseline is wrong" | We showed its levels correlation is seasonal. That is narrower. |
| "Wind ventilates the city, lowering PM2.5" | ρ = −0.246, p = 0.079. Suggestive, not significant. |

Two lines in the script that are load-bearing and **are** defensible, in case you
are challenged:

- **"We lost in all four."** Verifiable in `season.json → specification_grid`;
  all four `smoke_wins` are false, all four `p_smoke` ≥ 0.066.
- **"It drops to point zero five."** `detrended_comparison.first_differences`,
  naive ρ = 0.052, p = 0.71.

---

## Production notes

- 1080p minimum. Browser at ~110% zoom so the ledger text survives compression.
- Record audio separately. A laptop mic over a playing animation sounds poor.
- No music under narration.
- Rehearse twice. Record the second take and the third; keep the third.
- The animation runs 22 seconds. For §2 you will need roughly two play-throughs,
  or one play plus a slow scrub — plan which before you hit record.
