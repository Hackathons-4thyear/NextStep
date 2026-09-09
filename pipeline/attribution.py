"""
Attribute fires to a trajectory.

A fire counts toward an episode only if the air parcel passed close to it in
space AND near it in time. The time condition is what separates this from a
plain proximity join: a fire detected 30 hours before the air went over that
spot did not contribute to this episode, however close it sits to the path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config
from pipeline.trajectory import haversine_km


@dataclass
class AttributionResult:
    smoke_index: float
    fire_count: int
    total_frp: float
    fires: pd.DataFrame                 # attributed fires with weights attached
    by_district: pd.DataFrame
    mean_hours_upwind: float = 0.0
    corridor_radius_km: float = 0.0
    meta: dict = field(default_factory=dict)

    def summary(self):
        lines = [
            f"smoke index      {self.smoke_index:,.1f}",
            f"fires attributed {self.fire_count:,}",
            f"total FRP        {self.total_frp:,.1f} MW",
            f"mean upwind lag  {self.mean_hours_upwind:.1f} h",
        ]
        if not self.by_district.empty:
            lines.append("top districts:")
            for _, r in self.by_district.head(5).iterrows():
                lines.append(
                    f"  {r['district']:<28} {int(r['fire_count']):>5} fires"
                    f"  {r['share']*100:>5.1f}%"
                )
        return "\n".join(lines)


def attribute_fires(
    trajectory,
    fires,
    corridor_radius_km=None,
    time_tolerance_hours=None,
    district_col="district",
):
    """
    Score fires against one trajectory.

    Parameters
    ----------
    trajectory : Trajectory
    fires : DataFrame with columns lat, lon, datetime (tz-aware UTC), frp
    corridor_radius_km : soft corridor half-width; Gaussian falloff, not a cutoff
    time_tolerance_hours : max |fire time - parcel passage time|

    The weight for each fire is

        frp * exp(-(distance / corridor_radius)^2)

    so a fire directly beneath the path counts fully and one at the corridor
    edge counts little. The smooth falloff avoids an arbitrary hard boundary
    where a fire 100 m further away suddenly counts for nothing.
    """
    radius = corridor_radius_km or config.CORRIDOR_RADIUS_KM
    tol_h = time_tolerance_hours or config.FIRE_TIME_TOLERANCE_HOURS

    empty = _empty_result(radius)
    if fires is None or len(fires) == 0 or len(trajectory) == 0:
        return empty

    traj_lat = trajectory.lats
    traj_lon = trajectory.lons
    traj_time = np.array([p.time.timestamp() for p in trajectory.points])
    traj_hours = np.array([p.hours_before for p in trajectory.points])

    f = fires.copy()
    fire_lat = f["lat"].to_numpy(dtype=float)
    fire_lon = f["lon"].to_numpy(dtype=float)
    fire_time = np.array([t.timestamp() for t in f["datetime"]])
    fire_frp = f["frp"].to_numpy(dtype=float)

    # Coarse bounding-box prefilter. Distance is the expensive part and most
    # fires in a regional dataset are nowhere near any given path.
    margin = radius / 100.0 + 0.5  # generous degrees
    in_box = (
        (fire_lat >= traj_lat.min() - margin)
        & (fire_lat <= traj_lat.max() + margin)
        & (fire_lon >= traj_lon.min() - margin)
        & (fire_lon <= traj_lon.max() + margin)
    )
    if not in_box.any():
        return empty

    idx = np.flatnonzero(in_box)

    # Distance from every candidate fire to every trajectory point.
    # (n_fires, n_points) - fine at this scale.
    d = haversine_km(
        fire_lat[idx][:, None], fire_lon[idx][:, None],
        traj_lat[None, :], traj_lon[None, :],
    )

    dt_h = np.abs(fire_time[idx][:, None] - traj_time[None, :]) / 3600.0

    # A trajectory point only qualifies if it is within the time tolerance.
    # Mask the rest to infinity so the nearest *valid* passage is selected.
    d_valid = np.where(dt_h <= tol_h, d, np.inf)

    nearest = np.argmin(d_valid, axis=1)
    min_dist = d_valid[np.arange(len(idx)), nearest]

    hit = np.isfinite(min_dist) & (min_dist <= radius * 3.0)
    if not hit.any():
        return empty

    sel = idx[hit]
    dist_km = min_dist[hit]
    hours_upwind = traj_hours[nearest[hit]]

    weight = fire_frp[sel] * np.exp(-((dist_km / radius) ** 2))

    out = f.iloc[sel].copy()
    out["distance_km"] = dist_km
    out["hours_upwind"] = hours_upwind
    out["weight"] = weight
    out["attributed"] = True

    by_district = _rollup(out, district_col)

    return AttributionResult(
        smoke_index=float(weight.sum()),
        fire_count=int(len(out)),
        total_frp=float(out["frp"].sum()),
        fires=out,
        by_district=by_district,
        mean_hours_upwind=float(np.average(hours_upwind, weights=np.maximum(weight, 1e-9))),
        corridor_radius_km=radius,
    )


def attribute_ensemble(trajectories, fires, **kwargs):
    """
    Attribute across an ensemble.

    The primary member's attribution is reported. The ensemble is used for the
    stability figure: how much the smoke index varies across members. A low
    coefficient of variation means the attribution does not hinge on the exact
    launch point, which is the honest way to claim robustness.
    """
    results = [attribute_fires(t, fires, **kwargs) for t in trajectories]
    primary_i = next(
        (i for i, t in enumerate(trajectories) if t.is_primary), 0
    )
    primary = results[primary_i]

    indices = np.array([r.smoke_index for r in results], dtype=float)
    mean = float(indices.mean())
    primary.meta["ensemble_mean_index"] = mean
    primary.meta["ensemble_std_index"] = float(indices.std())
    primary.meta["ensemble_cv"] = float(indices.std() / mean) if mean > 0 else 0.0
    primary.meta["ensemble_n"] = len(results)
    return primary


def naive_baseline(fires, arrival_time, window_hours=None, region_bbox=None):
    """
    The baseline this project has to beat: total fire radiative power anywhere
    in the region over the preceding window, ignoring wind entirely.

    The window matters, and getting it wrong is how a comparison becomes
    dishonest. Smoke takes something like 8-32 hours to travel from source to
    receptor, so a baseline restricted to the arrival calendar day would miss
    most of the relevant burning and lose for the wrong reason. Beating a
    crippled opponent proves nothing.

    Matching the window to the trajectory duration is what makes this a fair
    fight: both models see exactly the same fires, and the only difference is
    that one knows where the wind was going.
    """
    if fires is None or len(fires) == 0:
        return 0.0

    window = window_hours or config.NAIVE_BASELINE_WINDOW_HOURS

    arrival = pd.Timestamp(arrival_time)
    if arrival.tzinfo is None:
        arrival = arrival.tz_localize("UTC")
    start = arrival - pd.Timedelta(hours=window)

    t = pd.to_datetime(fires["datetime"], utc=True)
    sel = fires.loc[(t > start) & (t <= arrival)]

    if region_bbox is not None:
        sel = sel[
            sel["lat"].between(region_bbox["south"], region_bbox["north"])
            & sel["lon"].between(region_bbox["west"], region_bbox["east"])
        ]

    return float(sel["frp"].sum())


def _rollup(attributed, district_col):
    if district_col not in attributed.columns:
        return pd.DataFrame(columns=["district", "fire_count", "frp_sum", "weight_sum", "share"])

    g = (
        attributed.groupby(district_col)
        .agg(fire_count=("frp", "size"), frp_sum=("frp", "sum"), weight_sum=("weight", "sum"))
        .reset_index()
        .rename(columns={district_col: "district"})
    )
    total = g["weight_sum"].sum()
    g["share"] = g["weight_sum"] / total if total > 0 else 0.0
    return g.sort_values("weight_sum", ascending=False).reset_index(drop=True)


def _empty_result(radius):
    return AttributionResult(
        smoke_index=0.0,
        fire_count=0,
        total_frp=0.0,
        fires=pd.DataFrame(
            columns=["lat", "lon", "datetime", "frp", "distance_km", "hours_upwind", "weight"]
        ),
        by_district=pd.DataFrame(
            columns=["district", "fire_count", "frp_sum", "weight_sum", "share"]
        ),
        corridor_radius_km=radius,
    )
