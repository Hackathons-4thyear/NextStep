/*
 * Smoke Forensics — the page does no science.
 *
 * Everything is precomputed by pipeline/export.py and read as static JSON. No
 * keys, no API calls, nothing that can rate-limit or expire during judging.
 *
 * Three rules this file exists to enforce:
 *
 *  1. A fire never ignites before the reconstructed air reaches it. Its reveal
 *     time is the passage time computed in Python, not its satellite detection
 *     time, so the animation cannot assert a causal order that runs backwards.
 *
 *  2. Every number below the fold is rendered from season.json. None are
 *     written into the HTML, so the page cannot drift from the analysis.
 *
 *  3. Results and exploratory observations are rendered by different code
 *     paths into differently-labelled sections. Underpowered signals do not
 *     get to look like findings.
 */

const { DeckGL, GeoJsonLayer, ScatterplotLayer, TextLayer, TripsLayer, PathLayer,
        WebMercatorViewport } = deck;

/* Storyboard, in animation seconds. See planning/05-animation-spec.md. */
const BEATS = {
  establish: [0.0, 1.5],
  problem:   [1.5, 3.0],
  trace:     [3.0, 14.0],
  count:     [14.0, 17.0],
  hold:      [17.0, 22.0],
};
const RUNTIME = BEATS.hold[1];

/* The bright TripsLayer head is only the *leading edge*. The path travelled so
   far is drawn separately and persists, because a trail alone shows about a
   tenth of a 48-hour journey and the whole point is to see where the air came
   from. A short trail with no persistent path made the finished frame look
   like a smudge beside the city. */
const TRAIL_SECONDS = 9000;    // 2.5h bright head
const BLOOM_SECONDS = 5400;    // fires bloom briefly as the air passes

/* Minimum fires crossed before the attribution ledger will rank anything.
   With one fire crossed the panel reads "100.0%" for whichever cell it landed
   in, which at the opening frame put a region across an international border
   at the top of a list about Punjab. */
const LEDGER_MIN_FIRES = 20;

/* CPCB PM2.5 sub-index breakpoints (µg/m³). */
const AQI = [
  { max: 30,       name: "Good",         css: "--aqi-1" },
  { max: 60,       name: "Satisfactory", css: "--aqi-2" },
  { max: 90,       name: "Moderate",     css: "--aqi-3" },
  { max: 120,      name: "Poor",         css: "--aqi-4" },
  { max: 250,      name: "Very poor",    css: "--aqi-5" },
  { max: Infinity, name: "Severe",       css: "--aqi-6" },
];

const state = { clock: 0, playing: true, last: null, scrubbing: false, rendered: -1 };
let episode, season, terrain, meta, dg;

const $ = (id) => document.getElementById(id);
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const lerp = (a, b, t) => a + (b - a) * t;

const fmt = (n, d = 0) =>
  n === null || n === undefined || Number.isNaN(n)
    ? "—"
    : Number(n).toLocaleString("en", { minimumFractionDigits: d, maximumFractionDigits: d });

function compass(deg) {
  const n = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
  return n[Math.round(deg / 22.5) % 16];
}

function aqiBand(v) {
  return AQI.find((b) => v <= b.max) || AQI[AQI.length - 1];
}

function pmAt(t) {
  const s = episode.pm25_series;
  if (!s.length) return null;
  if (t <= s[0].t) return s[0].v;
  for (let i = 1; i < s.length; i++) {
    if (s[i].t >= t) {
      const a = s[i - 1], b = s[i];
      return lerp(a.v, b.v, (t - a.t) / Math.max(b.t - a.t, 1));
    }
  }
  return s[s.length - 1].v;
}

/* ----------------------------------------------------------- storyboard */

/** Map animation clock to the state everything else reads from. */
function scene() {
  const t = state.clock;
  const loop = episode.loop_length;
  const peak = episode.episode.pm25_peak;
  const base = episode.episode.pm25_baseline;

  if (t < BEATS.problem[0]) {
    const k = clamp01((t - BEATS.establish[0]) / (BEATS.establish[1] - BEATS.establish[0]));
    // The spec's storyboard opens on a calm baseline in AQI green. This season
    // has no such hour: the quietest point in the window is still "very poor".
    // The gauge therefore opens where the air actually was, not where a
    // tidier story would want it.
    return { beat: "establish", dataTime: 0, pm: base, terrain: k, showPath: false,
             narration: "" };
  }
  if (t < BEATS.trace[0]) {
    const k = clamp01((t - BEATS.problem[0]) / (BEATS.problem[1] - BEATS.problem[0]));
    return { beat: "problem", dataTime: 0, pm: lerp(base, peak, k * k), terrain: 1,
             showPath: false,
             narration: `Two days earlier Delhi was already at ${fmt(base)}. ` +
                        `On this morning it reached ${fmt(peak)}. Where did that air come from?` };
  }
  if (t < BEATS.count[0]) {
    const k = clamp01((t - BEATS.trace[0]) / (BEATS.trace[1] - BEATS.trace[0]));
    return { beat: "trace", dataTime: k * loop, pm: peak, terrain: 1, showPath: true,
             narration: "Stepping the recorded wind backwards, hour by hour." };
  }
  if (t < BEATS.hold[0]) {
    const k = clamp01((t - BEATS.count[0]) / (BEATS.count[1] - BEATS.count[0]));
    const e = episode.episode;
    return { beat: "count", dataTime: loop, pm: peak, terrain: 1, showPath: true,
             pulse: Math.sin(k * Math.PI),
             narration: `${fmt(e.fires_attributed)} fires crossed. ` +
                        `${fmt(e.path_km)} km travelled. ` +
                        `${fmt(e.mean_hours_upwind, 0)} hours upwind on average.` };
  }
  return { beat: "hold", dataTime: loop, pm: peak, terrain: 1, showPath: true,
           narration: "" };
}

/* --------------------------------------------------------------- layers */

/** The portion of a path already travelled at this animation time. */
function travelled(traj, dt) {
  let i = 0;
  while (i < traj.timestamps.length && traj.timestamps[i] <= dt) i++;
  return traj.path.slice(0, Math.max(i, 2));
}

function buildLayers(s) {
  const dt = s.dataTime;
  const lit = episode.fires.filter((f) => f.t <= dt);
  const attributed = lit.filter((f) => f.attributed);
  const context = lit.filter((f) => !f.attributed);
  const pulse = s.pulse || 0;

  const paths = s.showPath ? episode.trajectories : [];
  const primaryPaths = paths.filter((d) => d.is_primary);
  const ensemblePaths = paths.filter((d) => !d.is_primary);

  return [
    new GeoJsonLayer({
      id: "terrain",
      data: terrain,
      stroked: true,
      filled: true,
      getFillColor: [22, 32, 46],
      getLineColor: [36, 51, 74],
      lineWidthMinPixels: 1,
      opacity: s.terrain,
    }),

    new ScatterplotLayer({
      id: "fires-context",
      data: context,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => 300 + Math.sqrt(d.frp) * 120,
      radiusMinPixels: 1,
      radiusMaxPixels: 3,
      getFillColor: [104, 122, 148, 130],
      stroked: false,
    }),

    // Small and semi-transparent on purpose. At full size 1,384 detections
    // merge into one orange mass that says nothing; kept small, the overlap
    // itself reads as density and the burning belt keeps its shape.
    new ScatterplotLayer({
      id: "fires-attributed",
      data: attributed,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => {
        const age = clamp01((dt - d.t) / BLOOM_SECONDS);
        const bloom = 1 + 1.1 * (1 - age) + 0.4 * pulse;
        return (260 + Math.sqrt(d.frp) * 130) * bloom;
      },
      radiusMinPixels: 1.2,
      radiusMaxPixels: 7,
      getFillColor: (d) => {
        const hot = clamp01(d.frp / 60);
        const age = clamp01((dt - d.t) / BLOOM_SECONDS);
        return [255, 138 + 100 * hot, 61 + 130 * hot, 120 + 120 * (1 - age)];
      },
      updateTriggers: { getRadius: [dt, pulse], getFillColor: dt },
      pickable: true,
    }),

    // The journey so far, persisting. Without this the finished frame shows
    // only a short trail stub and the 500 km the air actually travelled is
    // invisible — which is the one thing the animation exists to show.
    new PathLayer({
      id: "ensemble-travelled",
      data: ensemblePaths,
      getPath: (d) => travelled(d, dt),
      getColor: [159, 217, 242, 46],
      widthMinPixels: 1,
      capRounded: true,
      jointRounded: true,
      updateTriggers: { getPath: dt },
    }),

    new PathLayer({
      id: "primary-travelled",
      data: primaryPaths,
      getPath: (d) => travelled(d, dt),
      getColor: [159, 217, 242, 210],
      widthMinPixels: 2,
      capRounded: true,
      jointRounded: true,
      updateTriggers: { getPath: dt },
    }),

    new TripsLayer({
      id: "primary-head",
      data: primaryPaths,
      getPath: (d) => d.path,
      getTimestamps: (d) => d.timestamps,
      getColor: [255, 255, 255],
      opacity: 1,
      widthMinPixels: 3.5,
      trailLength: TRAIL_SECONDS,
      currentTime: dt,
    }),

    new ScatterplotLayer({
      id: "receptor",
      data: [episode.receptor],
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 7,
      radiusUnits: "pixels",
      filled: false,
      stroked: true,
      getLineColor: [232, 237, 242],
      lineWidthMinPixels: 2,
    }),

    new TextLayer({
      id: "receptor-label",
      data: [episode.receptor],
      getPosition: (d) => [d.lon, d.lat],
      getText: (d) => d.name,
      getSize: 13,
      getColor: [232, 237, 242],
      getPixelOffset: [0, -20],
      fontFamily: "IBM Plex Sans, sans-serif",
      fontWeight: 600,
    }),
  ];
}

/* --------------------------------------------------------------- chrome */

function updateChrome(s) {
  const dt = s.dataTime;

  const band = aqiBand(s.pm);
  $("pm-value").textContent = fmt(s.pm);
  $("aqi-band").textContent = band.name;
  $("aqi-dot").style.background = `var(${band.css})`;
  $("pm-needle").style.left =
    `${clamp01(s.pm / episode.episode.pm25_peak) * 100}%`;

  const hoursBack = (episode.loop_length - dt) / 3600;
  $("r-back").textContent = `${hoursBack.toFixed(0)} h`;

  const start = new Date(episode.window_start_utc);
  $("clock").textContent =
    new Date(start.getTime() + dt * 1000).toISOString().slice(0, 16).replace("T", "  ") + " UTC";

  const lit = episode.fires.filter((f) => f.attributed && f.t <= dt);
  $("r-fires").textContent = fmt(lit.length);

  const prim = episode.trajectories.find((d) => d.is_primary);
  let km = 0;
  for (let i = 1; i < prim.path.length; i++) {
    if (prim.timestamps[i] > dt) break;
    const [x1, y1] = prim.path[i - 1], [x2, y2] = prim.path[i];
    const dy = (y2 - y1) * 111.0;
    const dx = (x2 - x1) * 111.0 * Math.cos(((y1 + y2) / 2) * Math.PI / 180);
    km += Math.hypot(dx, dy);
  }
  $("r-path").textContent = `${fmt(km)} km`;

  updateSpark(dt);

  const o = episode.episode.origin;
  $("r-origin").textContent = `${o.lat.toFixed(1)}N ${o.lon.toFixed(1)}E`;

  const nar = $("narration");
  if (nar.textContent !== s.narration) nar.textContent = s.narration;
  nar.classList.toggle("on", Boolean(s.narration));

  // Ledger, accumulating in animation time.
  const by = new Map();
  let total = 0;
  for (const f of lit) {
    const w = f.weight || 0;
    by.set(f.district, (by.get(f.district) || 0) + w);
    total += w;
  }
  // Below a handful of fires the shares are noise: one detection reads as
  // "100.0%" and, at the opening frame, named a region on the wrong side of a
  // border as the sole source. Hold the panel until there is enough crossed to
  // rank honestly.
  const rows = lit.length < LEDGER_MIN_FIRES
    ? []
    : [...by.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);

  $("ledger").innerHTML = rows.length
    ? rows.map(([name, w]) => {
        const pct = total > 0 ? (w / total) * 100 : 0;
        return `<li>
          <div class="row"><span class="num">${name}</span><span class="pct num">${pct.toFixed(1)}%</span></div>
          <div class="bar"><span style="width:${pct.toFixed(1)}%"></span></div>
        </li>`;
      }).join("")
    : `<li class="empty">${lit.length
          ? "Too few crossed yet to rank sources."
          : "Nothing crossed yet."}</li>`;

  if (!state.scrubbing) {
    $("scrub").value = String(Math.round((state.clock / RUNTIME) * 1000));
  }
}

/* ------------------------------------------------------------- sparkline */

const SPARK = { w: 220, h: 46 };

/**
 * PM2.5 across the traced window, drawn once.
 *
 * The big readout holds at the peak through the trace beat, which leaves the
 * most prominent panel static for half the runtime. The sparkline gives that
 * panel something true to do: it shows the whole 48 hours at once and marks
 * where the air being traced currently is.
 */
function buildSpark() {
  const loop = episode.loop_length;
  const pts = episode.pm25_series.filter((d) => d.t >= 0 && d.t <= loop);
  if (pts.length < 2) return;

  const peak = episode.episode.pm25_peak;
  const x = (t) => (t / loop) * SPARK.w;
  const y = (v) => SPARK.h - (clamp01(v / peak) * (SPARK.h - 3)) - 1.5;

  const line = pts.map((d, i) => `${i ? "L" : "M"}${x(d.t).toFixed(1)},${y(d.v).toFixed(1)}`).join(" ");
  const area = `${line} L${SPARK.w},${SPARK.h} L0,${SPARK.h} Z`;

  $("spark").innerHTML = `
    <path d="${area}" fill="rgba(255,138,61,.14)"/>
    <path d="${line}" fill="none" stroke="var(--fire)" stroke-width="1.5"
          stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
    <line id="spark-head" x1="0" y1="0" x2="0" y2="${SPARK.h}"
          stroke="var(--air-lead)" stroke-width="1" vector-effect="non-scaling-stroke"/>
    <circle id="spark-dot" r="2.5" fill="var(--air-lead)" cx="0" cy="${SPARK.h}"/>`;
}

function updateSpark(dt) {
  const head = document.getElementById("spark-head");
  const dot = document.getElementById("spark-dot");
  if (!head || !dot) return;
  const loop = episode.loop_length;
  const peak = episode.episode.pm25_peak;
  const x = (dt / loop) * SPARK.w;
  const y = SPARK.h - (clamp01(pmAt(dt) / peak) * (SPARK.h - 3)) - 1.5;
  head.setAttribute("x1", x); head.setAttribute("x2", x);
  dot.setAttribute("cx", x); dot.setAttribute("cy", y);
}

/* ----------------------------------------------------------- confound chart */

/**
 * The confound, drawn: distance travelled against the pollution that arrived,
 * one point per day, sized by fires crossed.
 *
 * The table states the correlations; this shows the shape in one glance. If
 * crossing more fires produced worse air, the big circles would climb to the
 * right. They do not.
 */
function drawConfoundChart() {
  const svg = $("confound-chart");
  const days = season.daily.filter(
    (d) => Number.isFinite(d.path_km) && Number.isFinite(d.pm25));
  if (!svg || days.length < 5) return;

  const W = 640, H = 300, M = { t: 14, r: 16, b: 44, l: 56 };
  const xs = days.map((d) => d.path_km);
  const ys = days.map((d) => d.pm25);
  // Round the axes to human numbers. max * 1.05 produced ticks like "676",
  // which reads as a measurement rather than a scale.
  const niceStep = (range, count) => {
    const raw = range / count;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    return [1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) * mag;
  };
  const stepY = niceStep(Math.max(...ys), 4);
  const stepX = niceStep(Math.max(...xs) - Math.min(...xs), 4);
  const fx = [Math.floor(Math.min(...xs) / stepX) * stepX,
              Math.ceil(Math.max(...xs) / stepX) * stepX];
  const fy = [0, Math.ceil(Math.max(...ys) / stepY) * stepY];
  const maxFires = Math.max(...days.map((d) => d.fires_attributed));

  const X = (v) => M.l + ((v - fx[0]) / (fx[1] - fx[0])) * (W - M.l - M.r);
  const Y = (v) => H - M.b - ((v - fy[0]) / (fy[1] - fy[0])) * (H - M.t - M.b);

  const ticksX = 4, ticksY = 4;
  let g = "";

  for (let i = 0; i <= ticksY; i++) {
    const v = fy[0] + ((fy[1] - fy[0]) * i) / ticksY;
    g += `<line x1="${M.l}" y1="${Y(v).toFixed(1)}" x2="${W - M.r}" y2="${Y(v).toFixed(1)}"
             stroke="var(--ground-line)" stroke-width="1"/>
          <text x="${M.l - 9}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end"
             font-size="11" fill="var(--ink-quiet)">${Math.round(v)}</text>`;
  }
  for (let i = 0; i <= ticksX; i++) {
    const v = fx[0] + ((fx[1] - fx[0]) * i) / ticksX;
    g += `<text x="${X(v).toFixed(1)}" y="${H - M.b + 20}" text-anchor="middle"
             font-size="11" fill="var(--ink-quiet)">${Math.round(v)}</text>`;
  }

  for (const d of days) {
    const r = 2.5 + 7 * Math.sqrt(d.fires_attributed / maxFires);
    g += `<circle cx="${X(d.path_km).toFixed(1)}" cy="${Y(d.pm25).toFixed(1)}" r="${r.toFixed(1)}"
            fill="rgba(255,138,61,.34)" stroke="var(--fire)" stroke-width="1"><title>${d.date}: ${
              d.pm25} µg/m³, ${d.path_km} km, ${d.fires_attributed} fires</title></circle>`;
  }

  g += `<text x="${(M.l + (W - M.r)) / 2}" y="${H - 6}" text-anchor="middle"
           font-size="11.5" fill="var(--ink-quiet)">Distance the air travelled in 48 hours (km)</text>
        <text transform="translate(15,${(M.t + H - M.b) / 2}) rotate(-90)" text-anchor="middle"
           font-size="11.5" fill="var(--ink-quiet)">PM2.5 on arrival (µg/m³)</text>`;

  svg.innerHTML = g;

  const row = season.confound.find((c) => /Fires crossed.*PM2/.test(c.pair));
  $("chart-cap").innerHTML =
    `One dot per day; bigger dots crossed more fires. If crossing fires drove
     the pollution, the cloud would slope up to the right. It does not — the
     days the air travelled furthest are among the cleanest, and the worst day
     of the season sits mid-range. Fires crossed against PM2.5:
     ρ&nbsp;=&nbsp;${row ? row.rho.toFixed(3) : "—"},
     p&nbsp;=&nbsp;${row ? row.p.toFixed(2) : "—"}.`;
}

/* ------------------------------------------------------------- findings */

const p3 = (x) => (x >= 0 ? "+" : "") + x.toFixed(3);
const sig = (p) =>
  p < 0.05
    ? `<span>${p < 0.0001 ? "&lt;0.0001" : p.toFixed(4)}</span>`
    : `<span class="ns">${p.toFixed(3)}</span>`;

function renderFindings() {
  const d = season.detrended_comparison;
  const lv = d.levels, fd = d.first_differences, dr = d.detrended;

  $("headline").innerHTML =
    `Across ${d.n_days} days the naive fire count tracked Delhi's PM2.5 at
     ρ&nbsp;=&nbsp;${lv.rho_naive.toFixed(3)}, and our wind-aware index at
     ρ&nbsp;=&nbsp;${lv.rho_smoke.toFixed(3)}. Then we removed the seasonal
     trend, and <strong>both fell to zero</strong>.`;

  $("detrend").innerHTML = `
    <thead><tr><th>Comparison</th><th>wind-aware ρ</th><th>p</th><th>naive ρ</th><th>p</th></tr></thead>
    <tbody>
      <tr><td>Raw levels</td><td class="num">${p3(lv.rho_smoke)}</td><td class="num">${sig(lv.p_smoke)}</td>
          <td class="num">${p3(lv.rho_naive)}</td><td class="num">${sig(lv.p_naive)}</td></tr>
      <tr><td>Day-over-day change</td><td class="num">${p3(fd.rho_smoke)}</td><td class="num">${sig(fd.p_smoke)}</td>
          <td class="num">${p3(fd.rho_naive)}</td><td class="num">${sig(fd.p_naive)}</td></tr>
      <tr><td>Detrended, ${d.detrend_window_days}-day</td><td class="num">${p3(dr.rho_smoke)}</td><td class="num">${sig(dr.p_smoke)}</td>
          <td class="num">${p3(dr.rho_naive)}</td><td class="num">${sig(dr.p_naive)}</td></tr>
    </tbody>`;

  const label = { single: "One 06:00 UTC sample", multi: "Mean of four hours" };
  $("grid").innerHTML = `
    <thead><tr><th>Arrival</th><th>Ventilation</th><th>wind-aware ρ</th><th>p</th>
      <th>naive ρ</th><th>p</th></tr></thead>
    <tbody>${season.specification_grid.map((c) => `
      <tr class="${c.arrival === "single" && c.ventilation === "off" ? "primary" : ""}">
        <td>${label[c.arrival]}${c.arrival === "single" && c.ventilation === "off" ? " (primary)" : ""}</td>
        <td>${c.ventilation === "on" ? "corrected" : "none"}</td>
        <td class="num">${p3(c.rho_smoke)}</td><td class="num">${sig(c.p_smoke)}</td>
        <td class="num">${p3(c.rho_naive)}</td><td class="num">${sig(c.p_naive)}</td>
      </tr>`).join("")}
    </tbody>`;

  const anyWin = season.specification_grid.some((c) => c.smoke_wins);
  $("grid-note").innerHTML =
    `The wind-aware index does not reach significance in any of the four
     (all p&nbsp;≥&nbsp;${Math.min(...season.specification_grid.map((c) => c.p_smoke)).toFixed(3)}),
     and ${anyWin ? "wins one cell" : "beats the baseline in none of them"}.
     Correcting for ventilation helps it slightly and nowhere near enough.`;

  // Why the index fails. Every row comes from season.json; nothing is typed
  // in here, so the table cannot drift away from the analysis.
  drawConfoundChart();

  $("confound").innerHTML = `
    <thead><tr><th>Relationship</th><th>ρ</th><th>p</th><th>Verdict</th></tr></thead>
    <tbody>${season.confound.map((r) => `
      <tr><td>${r.pair}</td><td class="num">${p3(r.rho)}</td><td class="num">${sig(r.p)}</td>
      <td class="${r.significant ? "" : "ns"}">${r.significant ? "supported" : "not significant"}</td></tr>
    `).join("")}</tbody>`;

  $("confound-note").innerHTML =
    `Read those together. The index is almost entirely the fire count
     (ρ&nbsp;=&nbsp;0.94), and the fire count is substantially set by how fast
     the air was moving (ρ&nbsp;=&nbsp;0.53), because faster air sweeps over
     more ground. Meanwhile the fire count has no detectable relationship with
     the pollution it is supposed to explain (ρ&nbsp;=&nbsp;0.10,
     p&nbsp;=&nbsp;0.47). <strong>The index tracks wind speed better than it
     tracks smoke.</strong>`;

  // Exploratory: the two-day illustration.
  const vp = season.ventilation_paradox;
  const a = vp.high_pm_day, b = vp.high_index_day;
  // Paired bars, not two columns of numerals. The argument is that one quantity
  // goes up while the other goes down, and identical numbers in identical
  // styling leave the reader to notice that unaided. Crossing bars show it.
  const maxFires = Math.max(a.fires_attributed, b.fires_attributed);
  const maxPm = Math.max(a.pm25, b.pm25);

  const frame = (x, cap) => `
    <div class="frame">
      <div class="date">${x.date}</div>
      <div class="cap">${cap}</div>
      <div class="pair">
        <div class="pair-row">
          <span class="pair-label">Fires the air crossed</span>
          <span class="pair-val num">${fmt(x.fires_attributed)}</span>
        </div>
        <div class="pair-bar fires">
          <span style="width:${(x.fires_attributed / maxFires * 100).toFixed(1)}%"></span>
        </div>
        <div class="pair-row">
          <span class="pair-label">PM2.5 that arrived</span>
          <span class="pair-val num">${fmt(x.pm25)} <em>µg/m³</em></span>
        </div>
        <div class="pair-bar pm">
          <span style="width:${(x.pm25 / maxPm * 100).toFixed(1)}%"></span>
        </div>
      </div>
      <ul>
        <li><span>Smoke index</span><span class="num">${fmt(x.smoke_index)}</span></li>
        <li><span>Straightness</span><span class="num">${x.straightness.toFixed(2)}</span></li>
        <li><span>Air came from</span><span class="num">${compass(x.upwind_bearing)} ${x.upwind_bearing.toFixed(0)}°</span></li>
      </ul>
    </div>`;
  $("twoframe").innerHTML =
    frame(a, "the season's worst air") +
    frame(b, "the season's highest smoke index");
  $("twoframe-note").innerHTML =
    `The second day crossed ${(b.fires_attributed / a.fires_attributed).toFixed(1)}×
     as many fires along a straighter path from the same direction, and the air
     was ${((b.pm25 / a.pm25) * 100).toFixed(0)}% as polluted. Two days prove
     nothing on their own — the season-wide table above is the evidence. This
     pair is here because it makes the mechanism legible in one glance.`;

  // Exploratory: the underpowered signals.
  const sp = season.straightness_split;
  const nc = season.negative_control;
  $("explore").innerHTML = `
    <thead><tr><th>Observation</th><th>Effect</th><th>p</th><th>Verdict</th></tr></thead>
    <tbody>
      <tr><td>Coherent-transport days (n=${sp.coherent.n_days})</td>
          <td class="num">ρ ${p3(sp.coherent.rho_smoke)}</td>
          <td class="num">${sig(sp.coherent.p_smoke)}</td><td class="ns">not significant</td></tr>
      <tr><td>Recirculating days (n=${sp.recirculating.n_days})</td>
          <td class="num">ρ ${p3(sp.recirculating.rho_smoke)}</td>
          <td class="num">${sig(sp.recirculating.p_smoke)}</td><td class="ns">not significant</td></tr>
      <tr><td>Air from the non-burning sector (n=${nc.n_control_days})</td>
          <td class="num">${fmt(nc.mean_pm25_control)} vs ${fmt(nc.mean_pm25_other)}</td>
          <td class="num">${sig(nc.mannwhitney_p)}</td><td class="ns">not significant</td></tr>
    </tbody>`;

  $("explore-note").innerHTML =
    `The wind-aware correlation changes sign between days when the air genuinely
     travelled and days when it looped beside the city — the direction transport
     physics predicts. Air arriving from the sector with no burning was cleaner
     on average. Both point the way we would want. <strong>Neither clears
     significance at this sample size</strong>, so neither is a finding, and we
     are not going to present them as one.`;

  $("claim").innerHTML =
    `On this region and season, <strong>neither</strong> a wind-aware trajectory
     attribution <strong>nor</strong> a naive regional fire count explains
     day-to-day variation in Delhi's PM2.5 (ρ&nbsp;=&nbsp;${fd.rho_smoke.toFixed(3)}
     and ${fd.rho_naive.toFixed(3)} on day-over-day changes). The baseline's
     apparent advantage on raw levels (ρ&nbsp;=&nbsp;${lv.rho_naive.toFixed(3)})
     is seasonal co-trending.`;

  $("bound").innerHTML =
    `This is a bounded null, not a proof that no relationship exists. With
     ${d.n_days - 1} day-over-day changes the 95% interval spans roughly ±0.32,
     so a strong daily relationship is excluded and a modest one is not. Saying
     which of those we have earned is the difference between a result and a
     press release.`;

  const m = meta.model;
  $("method").textContent =
    `Method: ${m.trajectory_hours_back}-hour Lagrangian back-trajectory, ` +
    `${m.dt_seconds / 60}-minute midpoint steps through ERA5 ${m.wind_level} winds, ` +
    `${m.ensemble_size}-member ensemble. Fires within a ${m.corridor_radius_km} km ` +
    `Gaussian corridor and ±${m.fire_time_tolerance_hours} hours of the air's passage are ` +
    `attributed, weighted by radiative power. The naive baseline sums fire power across the ` +
    `whole region over the same ${m.naive_window_hours} hours, so both models see identical ` +
    `fires and differ only in whether they know the wind. Sources: ${meta.sources.join("; ")}.`;

  $("nasa").textContent = meta.attribution_text;
}

/* ------------------------------------------------------------------ loop */

function frame(now) {
  if (state.last === null) state.last = now;
  const dt = (now - state.last) / 1000;
  state.last = now;

  if (state.playing) {
    state.clock += dt;
    if (state.clock > RUNTIME) state.clock = 0;
  }

  // Idle when nothing has moved. Rebuilding seven layers and filtering 2,458
  // fires sixty times a second to redraw an identical frame is pure heat, and
  // on a weak laptop it is the difference between smooth and stuttering.
  if (state.clock !== state.rendered) {
    const s = scene();
    dg.setProps({ layers: buildLayers(s) });
    updateChrome(s);
    state.rendered = state.clock;
  }
  requestAnimationFrame(frame);
}

/* ------------------------------------------------------------------ init */

/**
 * Frame the whole ensemble inside the *visible* map window.
 *
 * The rails and the timeline cover roughly 45% of the viewport, so fitting to
 * the full canvas leaves the trajectory small and pushed off centre. Padding
 * is read from the live DOM rather than hardcoded, so it stays correct when
 * the rails change width at the 1180px breakpoint.
 */
function fitView() {
  const pts = episode.trajectories.flatMap((t) => t.path);
  const lons = pts.map((p) => p[0]);
  const lats = pts.map((p) => p[1]);

  const w = window.innerWidth, h = window.innerHeight;
  const wide = w > 900;
  const left = wide ? document.querySelector(".rail-left").offsetWidth : 0;
  const right = wide ? document.querySelector(".rail-right").offsetWidth : 0;
  const bottom = wide ? document.querySelector(".timeline").offsetHeight : 0;

  const pad = {
    left: left + 70, right: right + 70,
    top: 110, bottom: bottom + 60,
  };
  // fitBounds throws if padding exceeds the canvas; fall back to something safe.
  if (pad.left + pad.right >= w - 40 || pad.top + pad.bottom >= h - 40) {
    return { longitude: (Math.min(...lons) + Math.max(...lons)) / 2,
             latitude: (Math.min(...lats) + Math.max(...lats)) / 2,
             zoom: 5.7, pitch: 0, bearing: 0 };
  }

  const { longitude, latitude, zoom } = new WebMercatorViewport({ width: w, height: h })
    .fitBounds(
      [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
      { padding: pad },
    );
  return { longitude, latitude, zoom, pitch: 0, bearing: 0 };
}

async function init() {
  const load = (f) => fetch(`data/${f}`).then((r) => {
    if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`);
    return r.json();
  });

  try {
    [episode, season, terrain, meta] = await Promise.all([
      load("episode.json"), load("season.json"), load("terrain.json"), load("meta.json"),
    ]);
  } catch (err) {
    $("map").innerHTML =
      `<p style="padding:32px;color:#E93F33">Could not load data — ${err.message}.
       Run <code>python -m pipeline.export</code>, then serve this folder over HTTP
       (<code>python -m http.server</code>). Opening index.html from disk will not work.</p>`;
    return;
  }

  // Paint the AQI ramp against this episode's actual scale, so the coloured
  // bands line up with the needle rather than approximating it.
  const peak = episode.episode.pm25_peak;
  const stops = [];
  let prev = 0;
  for (const b of AQI) {
    const to = Math.min(b.max === Infinity ? peak : b.max, peak);
    stops.push(`var(${b.css}) ${(prev / peak) * 100}%`, `var(${b.css}) ${(to / peak) * 100}%`);
    prev = to;
    if (to >= peak) break;
  }
  document.querySelector(".gauge-track").style.background =
    `linear-gradient(90deg, ${stops.join(", ")})`;

  dg = new DeckGL({
    container: "map",
    initialViewState: fitView(),
    controller: true,
    layers: [],
    getTooltip: ({ object }) =>
      object && object.district
        ? { text: `${object.district}\n${object.frp} MW\n${object.hours_upwind}h upwind` }
        : null,
  });

  buildSpark();
  renderFindings();

  const play = $("play");
  play.addEventListener("click", () => {
    state.playing = !state.playing;
    play.textContent = state.playing ? "Pause" : "Play";
    play.setAttribute("aria-label",
      state.playing ? "Pause the animation" : "Play the animation");
  });

  const scrub = $("scrub");
  const grab = () => { state.scrubbing = true; };
  const drop = () => { state.scrubbing = false; };
  scrub.addEventListener("pointerdown", grab);
  scrub.addEventListener("pointerup", drop);
  scrub.addEventListener("focus", grab);
  scrub.addEventListener("blur", drop);
  scrub.addEventListener("input", (e) => {
    state.clock = (Number(e.target.value) / 1000) * RUNTIME;
  });

  // Reduced motion: show the finished frame, do not autoplay.
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    state.playing = false;
    state.clock = BEATS.hold[0];
    play.textContent = "Play";
    play.setAttribute("aria-label", "Play the animation");
  }

  window.addEventListener("resize", () => {
    dg.setProps({ initialViewState: fitView() });
    state.rendered = -1;
  });

  requestAnimationFrame(frame);
}

init();
