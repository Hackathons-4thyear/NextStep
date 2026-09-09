# Smoke Forensics — build documentation

Planning and build documents for a NextStep Hacks 2026 entry. Read `00-brief.md` first,
then start at `07-prompts.md` and work through in order.

| File | What it's for |
|---|---|
| `00-brief.md` | The concept, the winning claim, and how it maps to the six judging criteria |
| `01-requirements.md` | Functional and technical requirements, non-goals, definition of done |
| `02-data-sources.md` | Verified API endpoints, parameters, gotchas, Day 1 checklist |
| `03-architecture.md` | System design, repo layout, JSON contracts, the trajectory algorithm |
| `04-build-plan.md` | Day-by-day plan with go/no-go gates and a cut list |
| `05-animation-spec.md` | Design system and the 22-second animation storyboard |
| `06-submission-kit.md` | Video script, README structure, Devpost copy, judge Q&A prep |
| `07-prompts.md` | 24 sequenced prompts to drive the build from empty repo to submission |

## The three things that decide this project

**Day 1 is a data verification day, not a coding day.** The most expensive failure available
is discovering on Day 4 that the receptor city has gaps in its PM2.5 record. Changing city on
Day 1 costs an hour; on Day 4 it costs the hackathon.

**Day 3 is the gate.** If wind-aware attribution doesn't beat the naive baseline, that has to
be known before two days go into visuals. The honest reframe is in the build plan.

**Design is a sixth of the score.** Two full days on the animation is the correct allocation,
not an indulgence. The animation is what the video is made of, and the video is what judges
watch first.

## What isn't decided yet

The region, season and receptor city. Prompt P1 works that out — it depends on where you are
and which local environmental problem you actually care about, and the theme statement
explicitly rewards local grounding.
