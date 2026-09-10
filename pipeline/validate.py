"""
Season-wide validation: does knowing the wind actually help?

Runs the trajectory and attribution machinery across every day of the season,
scores the same days with a wind-blind naive baseline, and compares the two
against observed PM2.5. That comparison is the project's entire technical
claim, so the arithmetic here is deliberately plain and every intermediate is
written out for inspection.

The baseline is not a straw man. It sums FRP over the same lookback window the
trajectory covers, so both models see an identical set of fires and the only
difference between them is whether they know where the air went. Shrinking that
window would manufacture a win and make the headline claim indefensible.

The specification grid
----------------------
A first pass found the wind-aware index losing to the naive baseline, and
diagnosed why: the index counts fires crossed, which scales with how far the
parcel travelled, which scales with wind speed -- and wind also ventilates the
receptor. The index was inflating on exactly the days the city was best flushed.

So the comparison is now run over a pre-registered 2x2:

    ventilation : off | index divided by mean transport speed
    arrival     : one 06:00 UTC sample | mean over four hours vs daily mean PM2.5

All four cells are reported for both models. Ventilation is applied to the
naive baseline as well; if ventilation is what matters, the baseline is
entitled to it too, and the only remaining difference is which fires each
model counts.

    python -m pipeline.validate
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from scipy import stats

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import config
from pipeline.attribution import attribute_fires, naive_baseline
from pipeline.fetch_airquality import fetch_pm25
from pipeline.fetch_fires import assign_districts, clean_fires
from pipeline.fetch_wind import fetch_wind
from pipeline.trajectory import back_trajectory, haversine_km

HOURLY_CSV = config.DATA_PROCESSED / f"validation_hourly_{config.TARGET_NAME}.csv"
DAILY_CSV = config.DATA_PROCESSED / f"validation_daily_{config.TARGET_NAME}.csv"
STATS_JSON = config.DATA_PROCESSED / f"validation_stats_{config.TARGET_NAME}.json"

PRIMARY_HOUR = config.VALIDATION_ARRIVAL_HOUR_UTC


def season_days():
    start = datetime.fromisoformat(config.SEASON_START).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(config.SEASON_END).replace(tzinfo=timezone.utc)
    out, cur = [], start
    while cur <= end:
        out.append(cur.date())
        cur += timedelta(days=1)
    return out


def straightness(traj):
    """
    Net displacement divided by path length.

    Near 1.0 the air ran in a straight line and genuinely came from somewhere
    else. Near 0 it looped and stalled beside the receptor, which is the
    signature of local accumulation rather than transport, however high the
    PM2.5 climbed.
    """
    path_km = traj.total_distance_km()
    if path_km <= 0:
        return 0.0
    o, r = traj.origin(), traj.receptor()
    return float(haversine_km(o.lat, o.lon, r.lat, r.lon) / path_km)


def upwind_bearing(traj):
    """Compass bearing from the receptor back toward where the air came from."""
    o, r = traj.origin(), traj.receptor()
    dlat = o.lat - r.lat
    dlon = (o.lon - r.lon) * np.cos(np.deg2rad((o.lat + r.lat) / 2.0))
    return float(np.rad2deg(np.arctan2(dlon, dlat)) % 360.0)


def mean_transport_speed(wind, traj):
    """
    Mean wind speed along the path: the ventilation term.

    Preferred over raw path length because a trajectory truncated at the domain
    edge has a short path for reasons that have nothing to do with wind speed,
    which would inject exactly the artefact the normalisation exists to remove.
    """
    sp = [float(np.hypot(*wind.interpolate(p.lat, p.lon, p.time))) for p in traj.points]
    return max(float(np.mean(sp)), config.VENTILATION_MIN_MS)


def pm25_response(pm_series, when, lag_hours=0.0):
    """
    Observed PM2.5 around a (lagged) arrival time.

    Averaged over a window so a single noisy station-hour cannot swing a day.
    The same window is applied to both models, so it cannot favour either.
    """
    half = pd.to_timedelta(config.VALIDATION_PM25_WINDOW_HOURS / 2.0, unit="h")
    centre = pd.Timestamp(when) + pd.to_timedelta(lag_hours, unit="h")
    window = pm_series.loc[centre - half: centre + half]
    return float(window.mean()) if len(window) else np.nan


def _spearman(x, y):
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
        return np.nan, np.nan
    rho, p = stats.spearmanr(x[ok], y[ok])
    return float(rho), float(p)


def _r2(x, y):
    """R-squared of the least-squares line of y on x."""
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
        return np.nan
    r = np.corrcoef(x[ok], y[ok])[0, 1]
    return float(r * r)


def run_season(wind, fires, pm_series, verbose=True):
    """
    One row per (day, arrival hour).

    Only the primary trajectory is integrated. attribute_ensemble reports the
    primary member's index anyway and uses the other members solely for the
    spread figure, so this is identical arithmetic at a fraction of the cost.
    """
    days = season_days()
    hours = config.VALIDATION_ARRIVAL_HOURS_UTC
    rows = []

    if verbose:
        print(f"running {len(days)} days x {len(hours)} arrival hours "
              f"({config.TRAJECTORY_HOURS_BACK}h back)")

    for i, day in enumerate(days, 1):
        for hour in hours:
            arrival = datetime(day.year, day.month, day.day, hour,
                               tzinfo=timezone.utc)
            traj = back_trajectory(
                wind, config.RECEPTOR["lat"], config.RECEPTOR["lon"],
                arrival, is_primary=True,
            )
            res = attribute_fires(traj, fires)
            vent = mean_transport_speed(wind, traj)

            row = {
                "date": day.isoformat(),
                "hour_utc": hour,
                "arrival_utc": arrival.isoformat(),
                "pm25": pm25_response(pm_series, arrival),
                "smoke_index": res.smoke_index,
                "naive_index": naive_baseline(fires, arrival),
                "ventilation_ms": vent,
                "fires_attributed": res.fire_count,
                "attributed_frp": res.total_frp,
                "mean_hours_upwind": res.mean_hours_upwind,
                "straightness": straightness(traj),
                "upwind_bearing": upwind_bearing(traj),
                "origin_lat": traj.origin().lat,
                "origin_lon": traj.origin().lon,
                "path_km": traj.total_distance_km(),
                "exited_domain": bool(traj.exited_domain),
                "traj_points": len(traj),
            }

            # Corridor sensitivity is only meaningful on the primary spec, and
            # re-attributing at every hour would triple the run for nothing.
            if hour == PRIMARY_HOUR:
                for radius in config.CORRIDOR_SENSITIVITY_KM:
                    r = attribute_fires(traj, fires, corridor_radius_km=radius)
                    row[f"smoke_index_r{int(radius)}"] = r.smoke_index
                    row[f"fires_r{int(radius)}"] = r.fire_count

            rows.append(row)

        if verbose and (i % 10 == 0 or i == len(days)):
            print(f"  {i}/{len(days)} days")

    return pd.DataFrame(rows)


def build_specifications(hourly, pm_series):
    """
    The pre-registered 2x2. Returns one tidy frame per cell.

    Ventilation is applied per arrival hour before any averaging, because each
    hour's index has its own transport speed. Averaging first and dividing
    afterwards would smear a fast hour's dilution onto a slow one.
    """
    h = hourly.copy()
    h["smoke_vent"] = h["smoke_index"] / h["ventilation_ms"]
    h["naive_vent"] = h["naive_index"] / h["ventilation_ms"]

    single = h[h["hour_utc"] == PRIMARY_HOUR].reset_index(drop=True)

    daily_pm = (
        pm_series.groupby(pm_series.index.date).mean().rename("pm25_daily")
    )
    multi = (
        h.groupby("date")
        .agg(smoke_index=("smoke_index", "mean"),
             naive_index=("naive_index", "mean"),
             smoke_vent=("smoke_vent", "mean"),
             naive_vent=("naive_vent", "mean"))
        .reset_index()
    )
    multi["pm25"] = [
        float(daily_pm.get(pd.Timestamp(d).date(), np.nan)) for d in multi["date"]
    ]

    return {
        ("single", "off"): (single, "smoke_index", "naive_index"),
        ("single", "on"): (single, "smoke_vent", "naive_vent"),
        ("multi", "off"): (multi, "smoke_index", "naive_index"),
        ("multi", "on"): (multi, "smoke_vent", "naive_vent"),
    }


def specification_grid(hourly, pm_series):
    cells = []
    for (arrival, vent), (frame, smoke_col, naive_col) in \
            build_specifications(hourly, pm_series).items():
        pm = frame["pm25"].to_numpy(dtype=float)
        sm = frame[smoke_col].to_numpy(dtype=float)
        nv = frame[naive_col].to_numpy(dtype=float)

        rho_s, p_s = _spearman(sm, pm)
        rho_n, p_n = _spearman(nv, pm)
        cells.append({
            "arrival": arrival,
            "ventilation": vent,
            "n": int(np.isfinite(pm).sum()),
            "rho_smoke": rho_s, "p_smoke": p_s, "r2_smoke": _r2(sm, pm),
            "rho_naive": rho_n, "p_naive": p_n, "r2_naive": _r2(nv, pm),
            "smoke_wins": bool(np.isfinite(rho_s) and np.isfinite(rho_n)
                               and rho_s > rho_n),
        })
    return pd.DataFrame(cells)


def lag_sweep(single, pm_series):
    """
    Spearman correlation of each model against PM2.5 observed `lag` hours
    after arrival, on the primary specification.
    """
    arrivals = pd.to_datetime(single["arrival_utc"], utc=True)
    smoke = single["smoke_index"].to_numpy(dtype=float)
    naive = single["naive_index"].to_numpy(dtype=float)

    out = []
    for lag in config.LAG_SWEEP_HOURS:
        pm = np.array([pm25_response(pm_series, t, lag) for t in arrivals])
        rho_s, _ = _spearman(smoke, pm)
        rho_n, _ = _spearman(naive, pm)
        out.append({"lag_h": int(lag), "rho_smoke": rho_s, "rho_naive": rho_n})
    return pd.DataFrame(out)


def differenced_comparison(single):
    """
    Does either model have day-to-day skill, or do both just ride the season?

    A correlation on raw levels can be manufactured entirely by shared
    seasonality: burning rises and falls across the season, PM2.5 rises and
    falls across the season, and a model that knows only the seasonal shape
    scores well without predicting any individual day. Enlarging the fire
    region raised the naive baseline's levels correlation from 0.300 to 0.573
    without giving it any new physics, which is what that failure mode looks
    like from the outside.

    Two standard ways of removing the shared trend, reported together because
    neither is definitive alone:

      first differences  -- correlate day-over-day changes
      detrended residuals -- subtract a centred rolling mean from each series

    If a model's correlation survives both, it is explaining real day-to-day
    variation. If it collapses, it was tracking the calendar.
    """
    d = single.sort_values("date").reset_index(drop=True)
    pm = d["pm25"].astype(float)
    sm = d["smoke_index"].astype(float)
    nv = d["naive_index"].astype(float)

    win = config.DETREND_WINDOW_DAYS
    roll = dict(window=win, center=True, min_periods=1)

    out = {"n_days": int(len(d)), "detrend_window_days": win}

    rho_s, p_s = _spearman(sm.to_numpy(), pm.to_numpy())
    rho_n, p_n = _spearman(nv.to_numpy(), pm.to_numpy())
    out["levels"] = {"rho_smoke": rho_s, "p_smoke": p_s,
                     "rho_naive": rho_n, "p_naive": p_n}

    dpm, dsm, dnv = pm.diff(), sm.diff(), nv.diff()
    rho_s, p_s = _spearman(dsm.to_numpy(), dpm.to_numpy())
    rho_n, p_n = _spearman(dnv.to_numpy(), dpm.to_numpy())
    out["first_differences"] = {"rho_smoke": rho_s, "p_smoke": p_s,
                                "rho_naive": rho_n, "p_naive": p_n}

    rpm = (pm - pm.rolling(**roll).mean()).to_numpy()
    rsm = (sm - sm.rolling(**roll).mean()).to_numpy()
    rnv = (nv - nv.rolling(**roll).mean()).to_numpy()
    rho_s, p_s = _spearman(rsm, rpm)
    rho_n, p_n = _spearman(rnv, rpm)
    out["detrended"] = {"rho_smoke": rho_s, "p_smoke": p_s,
                        "rho_naive": rho_n, "p_naive": p_n}

    return out


def differenced_lag_sweep(single, pm_series):
    """
    Lag sweep on the differenced series, closing a known gap.

    Our headline test correlates day-over-day changes, which strips the shared
    seasonal trend — but differencing also suppresses relationships that operate
    with a delay, and transport is a delayed process. The original lag sweep ran
    on levels only, so the primary result was structurally blind to a lagged
    day-to-day relationship.

    This sweeps the same lags against differenced PM2.5. If a real lagged
    relationship exists, it should appear here as a peak away from zero.
    """
    arrivals = pd.to_datetime(single["arrival_utc"], utc=True)
    dsmoke = single["smoke_index"].astype(float).diff()
    dnaive = single["naive_index"].astype(float).diff()

    out = []
    for lag in config.LAG_SWEEP_HOURS:
        pm = pd.Series([pm25_response(pm_series, t, lag) for t in arrivals]).diff()
        rho_s, p_s = _spearman(dsmoke.to_numpy(), pm.to_numpy())
        rho_n, p_n = _spearman(dnaive.to_numpy(), pm.to_numpy())
        out.append({"lag_h": int(lag), "rho_smoke": rho_s, "p_smoke": p_s,
                    "rho_naive": rho_n, "p_naive": p_n})
    return pd.DataFrame(out)


def bootstrap_differenced(single, n_boot=None, seed=0):
    """
    Bootstrap confidence interval on the differenced correlation.

    The analytic Fisher interval assumes bivariate normality, which a heavily
    skewed fire index does not satisfy. Resampling days with replacement makes
    no such assumption and also answers a second question: whether the near-zero
    correlation is stable, or an average over a few influential days.
    """
    n_boot = n_boot or config.BOOTSTRAP_ITERATIONS
    d = single.sort_values("date").reset_index(drop=True)
    dpm = d["pm25"].astype(float).diff().to_numpy()
    ds = d["smoke_index"].astype(float).diff().to_numpy()
    dn = d["naive_index"].astype(float).diff().to_numpy()

    ok = np.isfinite(dpm) & np.isfinite(ds) & np.isfinite(dn)
    dpm, ds, dn = dpm[ok], ds[ok], dn[ok]
    n = len(dpm)
    rng = np.random.default_rng(seed)

    boot_s, boot_n = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        rs, _ = _spearman(ds[idx], dpm[idx])
        rn, _ = _spearman(dn[idx], dpm[idx])
        if np.isfinite(rs):
            boot_s.append(rs)
        if np.isfinite(rn):
            boot_n.append(rn)

    def summarise(obs, boots):
        b = np.array(boots, dtype=float)
        return {
            "observed": float(obs),
            "ci_low": float(np.percentile(b, 2.5)),
            "ci_high": float(np.percentile(b, 97.5)),
            "sd": float(b.std()),
            "frac_positive": float((b > 0).mean()),
        }

    obs_s, _ = _spearman(ds, dpm)
    obs_n, _ = _spearman(dn, dpm)
    return {
        "n_pairs": int(n),
        "n_boot": int(n_boot),
        "smoke": summarise(obs_s, boot_s),
        "naive": summarise(obs_n, boot_n),
    }


def confound_correlations(single):
    """
    The diagnosis of *why* the wind-aware index fails.

    Each row is a Spearman correlation between two columns of the daily table.
    Together they say the index is essentially a fire count, the fire count is
    substantially set by transport speed, and the fire count does not track the
    pollution it is supposed to explain.
    """
    pairs = [
        ("path_km", "smoke_index", "Path length ↔ smoke index"),
        ("ventilation_ms", "smoke_index", "Wind speed ↔ smoke index"),
        ("fires_attributed", "smoke_index", "Fires crossed ↔ smoke index"),
        ("fires_attributed", "pm25", "Fires crossed ↔ PM2.5"),
        ("ventilation_ms", "pm25", "Wind speed ↔ PM2.5"),
    ]
    out = []
    for a, b, label in pairs:
        rho, p = _spearman(single[a].to_numpy(dtype=float),
                           single[b].to_numpy(dtype=float))
        out.append({"pair": label, "rho": rho, "p": p,
                    "significant": bool(np.isfinite(p) and p < 0.05)})
    return out


def straightness_split(single):
    """
    Split the season by trajectory coherence.

    This is the reframed claim and it needs its own statistic. Attribution
    presupposes the air came from somewhere: on days when the parcel ran a
    straight line, upwind fires are a candidate explanation, and on days when
    it looped beside the receptor the pollution is local and upwind burning is
    irrelevant. Reporting only the group means would not test that -- the
    correlation within each group is what says whether the model has anything
    to work with.
    """
    thr = config.STRAIGHTNESS_TRANSPORT_MIN
    s = single["straightness"].astype(float)
    out = {"threshold": thr}

    for label, mask in [("coherent", s >= thr), ("recirculating", s < thr)]:
        g = single[mask]
        pm = g["pm25"].to_numpy(dtype=float)
        rho_s, p_s = _spearman(g["smoke_index"].to_numpy(dtype=float), pm)
        rho_n, p_n = _spearman(g["naive_index"].to_numpy(dtype=float), pm)
        out[label] = {
            "n_days": int(len(g)),
            "mean_pm25": float(np.nanmean(pm)) if len(g) else np.nan,
            "rho_smoke": rho_s, "p_smoke": p_s,
            "rho_naive": rho_n, "p_naive": p_n,
        }
    return out


def negative_control(single):
    """
    Directional negative control.

    Days when the air arrived from the sector containing no significant
    burning. If those days are not measurably cleaner, the association is
    coincidence rather than mechanism. This tests the mechanism claim directly,
    unlike a threshold on the model's own output, which would only tell us the
    model is self-consistent.
    """
    b = single["upwind_bearing"].to_numpy(dtype=float)
    quiet = (b > config.NEGATIVE_CONTROL_BEARING_MIN) & \
            (b < config.NEGATIVE_CONTROL_BEARING_MAX)

    q = single.loc[quiet, "pm25"].dropna()
    o = single.loc[~quiet, "pm25"].dropna()

    res = {
        "definition": (f"upwind bearing in "
                       f"({config.NEGATIVE_CONTROL_BEARING_MIN:.0f}, "
                       f"{config.NEGATIVE_CONTROL_BEARING_MAX:.0f}) degrees"),
        "n_control_days": int(len(q)),
        "n_other_days": int(len(o)),
        "mean_pm25_control": float(q.mean()) if len(q) else np.nan,
        "mean_pm25_other": float(o.mean()) if len(o) else np.nan,
        "median_pm25_control": float(q.median()) if len(q) else np.nan,
        "median_pm25_other": float(o.median()) if len(o) else np.nan,
        "dates": single.loc[quiet, "date"].tolist(),
    }
    if len(q) >= 3 and len(o) >= 3:
        u, p = stats.mannwhitneyu(q, o, alternative="less")
        res["mannwhitney_u"] = float(u)
        res["mannwhitney_p"] = float(p)
    return res


def corridor_sensitivity(single):
    pm = single["pm25"].to_numpy(dtype=float)
    out = []
    for radius in config.CORRIDOR_SENSITIVITY_KM:
        idx = single[f"smoke_index_r{int(radius)}"].to_numpy(dtype=float)
        rho, p = _spearman(idx, pm)
        out.append({
            "radius_km": radius, "spearman": rho, "spearman_p": p,
            "r2": _r2(idx, pm),
            "mean_fires": float(single[f"fires_r{int(radius)}"].mean()),
        })
    return pd.DataFrame(out)


def compute_stats(single, grid):
    exits = int(single["exited_domain"].sum())
    primary = grid[(grid["arrival"] == "single") & (grid["ventilation"] == "off")]
    p = primary.iloc[0]

    return {
        "n_days": int(len(single)),
        "bbox": dict(config.BBOX),
        "trajectory_hours_back": config.TRAJECTORY_HOURS_BACK,
        "naive_window_hours": config.NAIVE_BASELINE_WINDOW_HOURS,
        "corridor_radius_km": config.CORRIDOR_RADIUS_KM,
        "primary_spearman_smoke": float(p["rho_smoke"]),
        "primary_spearman_naive": float(p["rho_naive"]),
        "primary_r2_smoke": float(p["r2_smoke"]),
        "primary_r2_naive": float(p["r2_naive"]),
        "mean_hours_upwind": float(single["mean_hours_upwind"].mean()),
        "mean_straightness": float(single["straightness"].mean()),
        "mean_ventilation_ms": float(single["ventilation_ms"].mean()),
        "transport_days": int(
            (single["straightness"] >= config.STRAIGHTNESS_TRANSPORT_MIN).sum()
        ),
        "days_exiting_domain": exits,
        "pct_exiting_domain": 100.0 * exits / len(single) if len(single) else 0.0,
    }


def main(verbose=True):
    wind = fetch_wind(verbose=verbose)
    fires = assign_districts(clean_fires(verbose=verbose))
    pm = fetch_pm25(verbose=verbose)

    pm_series = (
        pm.set_index(pd.to_datetime(pm["datetime"], utc=True))["pm25"].sort_index()
    )

    hourly = run_season(wind, fires, pm_series, verbose=verbose)
    single = hourly[hourly["hour_utc"] == PRIMARY_HOUR].reset_index(drop=True)

    grid = specification_grid(hourly, pm_series)
    sweep = lag_sweep(single, pm_series)
    control = negative_control(single)
    sens = corridor_sensitivity(single)
    detrend = differenced_comparison(single)
    split = straightness_split(single)
    confound = confound_correlations(single)
    dlag = differenced_lag_sweep(single, pm_series)
    boot = bootstrap_differenced(single)
    st = compute_stats(single, grid)

    hourly.to_csv(HOURLY_CSV, index=False)
    single.to_csv(DAILY_CSV, index=False)
    payload = {
        "stats": st,
        "specification_grid": grid.to_dict(orient="records"),
        "lag_sweep": sweep.to_dict(orient="records"),
        "negative_control": control,
        "corridor_sensitivity": sens.to_dict(orient="records"),
        "detrended_comparison": detrend,
        "straightness_split": split,
        "confound": confound,
        "differenced_lag_sweep": dlag.to_dict(orient="records"),
        "bootstrap_differenced": boot,
    }
    STATS_JSON.write_text(json.dumps(payload, indent=2, default=str))

    if verbose:
        _report(single, grid, sweep, control, sens, detrend, st)
    return hourly, payload


def _report(single, grid, sweep, control, sens, detrend, st):
    line = "=" * 78
    print(f"\n{line}\nSEASON VALIDATION  --  {config.TARGET_NAME}\n{line}")
    print(f"days {st['n_days']}   trajectory {st['trajectory_hours_back']}h   "
          f"naive window {st['naive_window_hours']}h   "
          f"corridor {st['corridor_radius_km']:.0f} km")
    b = st["bbox"]
    print(f"domain {b['west']}W {b['south']}S {b['east']}E {b['north']}N   "
          f"exits {st['days_exiting_domain']}/{st['n_days']} "
          f"({st['pct_exiting_domain']:.1f}%)")

    print(f"\n{line}\nPRE-REGISTERED SPECIFICATION GRID\n{line}")
    print(f"{'arrival':>8} {'vent':>5} {'n':>4} | "
          f"{'smoke rho':>10} {'p':>8} {'smoke R2':>9} | "
          f"{'naive rho':>10} {'p':>8} {'naive R2':>9} | winner")
    print("-" * 78)
    for _, r in grid.iterrows():
        winner = "SMOKE" if r["smoke_wins"] else "naive"
        star = "  <- PRIMARY" if (r["arrival"] == "single"
                                  and r["ventilation"] == "off") else ""
        print(f"{r['arrival']:>8} {r['ventilation']:>5} {int(r['n']):>4} | "
              f"{r['rho_smoke']:>10.3f} {r['p_smoke']:>8.4f} {r['r2_smoke']:>9.3f} | "
              f"{r['rho_naive']:>10.3f} {r['p_naive']:>8.4f} {r['r2_naive']:>9.3f} | "
              f"{winner}{star}")

    print(f"\n{line}\nSEASONALITY CHECK: DOES EITHER MODEL HAVE DAY-TO-DAY SKILL?\n{line}")
    print(f"  detrend window {detrend['detrend_window_days']} days")
    print(f"  {'':<20}{'smoke rho':>11}{'p':>9}{'naive rho':>11}{'p':>9}")
    for key, label in [("levels", "levels (raw)"),
                       ("first_differences", "first differences"),
                       ("detrended", "detrended resid.")]:
        s = detrend[key]
        print(f"  {label:<20}{s['rho_smoke']:>11.3f}{s['p_smoke']:>9.4f}"
              f"{s['rho_naive']:>11.3f}{s['p_naive']:>9.4f}")

    print(f"\n{line}\nNEGATIVE CONTROL (directional)\n{line}")
    print(f"  {control['definition']}")
    print(f"  control days {control['n_control_days']}  vs  "
          f"{control['n_other_days']} other days")
    print(f"  mean PM2.5   {control['mean_pm25_control']:.1f}  vs  "
          f"{control['mean_pm25_other']:.1f}")
    print(f"  median PM2.5 {control['median_pm25_control']:.1f}  vs  "
          f"{control['median_pm25_other']:.1f}")
    if "mannwhitney_p" in control:
        print(f"  Mann-Whitney U {control['mannwhitney_u']:.1f}, "
              f"p = {control['mannwhitney_p']:.4g}  (one-sided: control cleaner)")

    print(f"\n{line}\nCORRIDOR SENSITIVITY\n{line}")
    print(f"{'radius_km':>10}{'Spearman':>12}{'R2':>10}{'mean fires':>12}")
    for _, r in sens.iterrows():
        print(f"{r['radius_km']:>10.0f}{r['spearman']:>12.3f}"
              f"{r['r2']:>10.3f}{r['mean_fires']:>12.1f}")

    best = sweep.loc[sweep["rho_smoke"].idxmax()]
    bestn = sweep.loc[sweep["rho_naive"].idxmax()]
    print(f"\n{line}\nLAG SWEEP (primary spec)\n{line}")
    print(f"  best smoke lag {int(best['lag_h']):>3}h  rho {best['rho_smoke']:.3f}")
    print(f"  best naive lag {int(bestn['lag_h']):>3}h  rho {bestn['rho_naive']:.3f}")

    print(f"\n{line}\nTRAJECTORY DIAGNOSTICS\n{line}")
    print(f"mean straightness    {st['mean_straightness']:.2f}")
    print(f"coherent transport   {st['transport_days']} of {st['n_days']} days")
    print(f"mean ventilation     {st['mean_ventilation_ms']:.2f} m/s")
    print(f"mean hours upwind    {st['mean_hours_upwind']:.1f} h")

    print(f"\nwrote {HOURLY_CSV.name}, {DAILY_CSV.name}, {STATS_JSON.name}")


if __name__ == "__main__":
    main()
