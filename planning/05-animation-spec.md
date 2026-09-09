# Animation & Design Spec

Design is one of six judging criteria, and the animation is what the video is made of.
Treat this file as a specification, not a suggestion.

---

## Design direction

The subject is atmospheric forensics: tracing invisible air back to visible fire. The whole
design rests on one contrast — **cool moving air against hot static sources**. Air is pale,
luminous and in motion. Fire is warm, sharp and fixed to the ground. Every colour decision
serves that opposition, and nothing else gets to be colourful.

The one deliberate borrowing from the real domain is the **AQI colour ramp**, used for the
PM2.5 readout. It is not invented — it is the scale printed on every government air quality
board, so it arrives pre-understood and roots the interface in its actual field rather than
in generic dashboard vocabulary.

### Palette

```css
--ground:      #16202E;  /* night terrain — blue-slate, deliberately not near-black */
--ground-line: #24334A;  /* district boundaries, rivers, coastline */
--air:         #9FD9F2;  /* the trajectory: pale, luminous, cold */
--air-lead:    #FFFFFF;  /* leading edge of the moving air mass */
--fire:        #FF8A3D;  /* fire detections, scaled toward #FFF6E8 at high FRP */
--ink:         #E8EDF2;  /* primary text */
--ink-quiet:   #8C9AAB;  /* secondary text, axis labels */
```

AQI ramp for the PM2.5 gauge only (CPCB scale):
`#55A84B · #A3C853 · #FFF833 · #F29C33 · #E93F33 · #AF2D24`

Nothing outside this list. Resist adding an accent colour for buttons.

### Typography

**IBM Plex Sans** throughout. It carries genuine technical provenance, has proper tabular
figures, and is free on Google Fonts.

**IBM Plex Mono** for one purpose only: numerals that change during the animation
(the clock, the PM2.5 value, the fire counter). Proportional digits visibly jitter as
they tick, and tabular mono figures do not. This is a functional fix, not a style choice —
do not extend mono to static labels, which reads as decoration.

Set labels in sentence case. Do not use all-caps eyebrow labels above sections.

### Layout

The map is the hero and runs full-bleed. Panels are anchored flush to the viewport edges
and share the map's background, so they read as instrument surfaces rather than as a set of
identical floating cards.

```
┌──────────────────────────────────────────────────────────────┐
│                                                    ┌────────┐│
│                                                    │ PM2.5  ││
│   ATTRIBUTION LEDGER          [ map + animation ]  │  gauge ││
│   ┌──────────────┐                                 │        ││
│   │ District  ▓▓ │                                  └────────┘│
│   │ District  ▓  │                                            │
│   │ District  ▒  │                                            │
│   └──────────────┘                                            │
│                                                               │
│  ── timeline scrubber ──────────────────────────●─────────    │
│  Wed 06:00              ← air travelling backwards in time    │
└──────────────────────────────────────────────────────────────┘
                          ↓ scroll
┌──────────────────────────────────────────────────────────────┐
│  Does this hold up across the whole season?                   │
│  [ scatter: smoke index vs PM2.5 ]  [ naive baseline, greyed ]│
│  R² 0.52 vs 0.18                                              │
└──────────────────────────────────────────────────────────────┘
```

Left-align everything. Centred text in a data interface slows reading and reads as marketing.

### Motion discipline

The play-through is the only motion in the product. No fade-and-slide-up on scroll, no hover
transitions on panels, no pulsing buttons. One orchestrated sequence, executed well, reads as
designed; scattered ambient effects read as generated.

---

## Skip the basemap tiles

Do **not** load Mapbox or a raster tile basemap. Instead render terrain from a small local
GeoJSON — Natural Earth admin boundaries, coastline and rivers — with deck.gl's `GeoJsonLayer`
in `--ground-line` on a flat `--ground` fill.

Three reasons, all of which matter here: it needs no token and no account; it keeps the site
genuinely self-contained so it cannot break during judging; and it looks markedly more
distinctive than the dark Mapbox style every other geospatial project uses.

---

## Storyboard

The full sequence runs **22 seconds**, then holds on the final state. Time is animation time,
not data time.

**0.0–1.5s · Establish.** Terrain fades up. The receptor city sits alone as a small ring.
The PM2.5 gauge reads the calm baseline in AQI green. Nothing else on screen.

**1.5–3.0s · The problem.** The gauge climbs sharply to the episode peak, sweeping up through
the AQI ramp into deep red. The clock jumps to the episode hour. One line of copy appears:
*"On this morning, PM2.5 hit 412. Where did it come from?"*

**3.0–14.0s · The trace.** The trajectory draws itself across the map from source region toward
the city, leading edge bright white, trail falling back to `--air` and fading behind. The clock
counts *backwards* through the hours as it draws. The ensemble members trail faintly behind the
primary path, spreading as they go — visible honesty about uncertainty.

**As the path passes over each fire location**, that fire ignites: a point scaled by FRP, warm
amber, brief bloom then settling. Fires never appear before the air reaches them. This is the
whole idea made visible, and it must be exact — the causal reading depends entirely on the
ignition being *triggered by* the passage, not merely coincident with it.

The attribution ledger on the left fills in progressively as districts accumulate fires,
bars growing in place.

**14.0–17.0s · The count.** Path complete. Attributed fires pulse once together. The headline
resolves: *"340 fires. Three districts. 14 hours upwind."*

**17.0–22.0s · Hold.** Everything settles to a readable static frame. The scrubber becomes
interactive. This frame is the one that will end up as the Devpost thumbnail, so compose it
deliberately.

---

## Implementation notes

Load deck.gl from CDN — no build step:

```html
<script src="https://unpkg.com/deck.gl@^9.0.0/dist.min.js"></script>
```

Layers, back to front: `GeoJsonLayer` (terrain) → `ScatterplotLayer` (fires, filtered by
current time) → `TripsLayer` (trajectory) → `ScatterplotLayer` (receptor).

The animation loop:

```js
function frame() {
  currentTime = (currentTime + SPEED) % LOOP_LENGTH;
  deckInstance.setProps({ layers: buildLayers(currentTime) });
  requestAnimationFrame(frame);
}
```

TripsLayer props that matter: `currentTime` is the playhead, `trailLength` controls how long
the trail takes to fade, and `getTimestamps` must be in the same units as `currentTime`.

**The precision trap.** TripsLayer stores timestamps as float32. Passing epoch milliseconds
overflows that precision and produces juddering, misplaced trails — a bug that looks like
broken physics but is purely a rendering artefact. Timestamps are already exported as small
elapsed-seconds values by the Python side (see `03-architecture.md`); keep them that way.

**Fire visibility** is a filter on animation time, not a separate animation:
`d.t <= currentTime`, with a brief scale bloom for fires whose `t` is within the last
second of playhead time.

## Quality floor

- `prefers-reduced-motion` honoured: render the completed final state immediately, no autoplay
- The scrubber is keyboard-operable with visible focus
- Never rely on colour alone — attributed fires differ in size and label, not just hue
- Readable at 1280px, since that is the screen judges will use
- One `<h1>`, real alt text, sensible contrast throughout

## Copy rules

Write plain sentences. "340 fires, 14 hours upwind" rather than "Attribution Analysis Results."
Name things as a person would understand them. Let each label do exactly one job, and delete
any label that is explaining a design decision rather than the data.
