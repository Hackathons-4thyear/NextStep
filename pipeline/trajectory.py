"""
Lagrangian back-trajectory integration.

Given a receptor and an arrival time, step backwards through the wind field to
reconstruct the path the arriving air travelled. This is the same class of
method NOAA's HYSPLIT model uses operationally, reduced to its core: a single
air parcel advected by the interpolated wind, with no dispersion or vertical
motion.

Simplifications we make, and state openly in the README:
  - single particle, no turbulent dispersion (approximated later by the
    corridor radius in attribution.py and by the ensemble spread here)
  - two-dimensional, no vertical motion between levels
  - reanalysis wind at ~10km, so terrain-driven local flow is not resolved
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np

import config


@dataclass
class TrajectoryPoint:
    lat: float
    lon: float
    time: object          # timezone-aware datetime
    hours_before: float   # hours before arrival at the receptor

    def as_tuple(self):
        return (self.lat, self.lon, self.time)


@dataclass
class Trajectory:
    points: list
    member: int = 0
    is_primary: bool = False
    exited_domain: bool = False

    def __len__(self):
        return len(self.points)

    @property
    def lats(self):
        return np.array([p.lat for p in self.points])

    @property
    def lons(self):
        return np.array([p.lon for p in self.points])

    @property
    def times(self):
        return [p.time for p in self.points]

    def origin(self):
        """Where the air came from: the earliest point on the path."""
        return self.points[0]

    def receptor(self):
        """Where the air arrived: the latest point on the path."""
        return self.points[-1]

    def total_distance_km(self):
        d = 0.0
        for a, b in zip(self.points[:-1], self.points[1:]):
            d += haversine_km(a.lat, a.lon, b.lat, b.lon)
        return d


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Scalar or array."""
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = np.radians(np.asarray(lat2) - np.asarray(lat1))
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def back_trajectory(
    windfield,
    lat,
    lon,
    arrival_time,
    hours_back=None,
    dt_seconds=None,
    member=0,
    is_primary=False,
):
    """
    Integrate backwards from (lat, lon, arrival_time).

    Returns a Trajectory whose points run *forward* in time, so points[0] is
    where the air came from and points[-1] is the receptor. That ordering is
    what the animation wants: air flowing from the fires toward the city reads
    far more naturally than the reverse.

    Uses a midpoint (RK2) step rather than plain Euler. Euler consistently cuts
    corners on curved flow, which accumulates into a real position error over
    72 hours; the midpoint correction costs one extra interpolation per step
    and removes most of it.
    """
    hours_back = hours_back or config.TRAJECTORY_HOURS_BACK
    dt = dt_seconds or config.TRAJECTORY_DT_SECONDS

    n_steps = int(round(hours_back * 3600 / dt))

    cur_lat, cur_lon, cur_time = float(lat), float(lon), arrival_time
    exited = False

    collected = [TrajectoryPoint(cur_lat, cur_lon, cur_time, 0.0)]

    for step in range(1, n_steps + 1):
        u1, v1 = windfield.interpolate(cur_lat, cur_lon, cur_time)

        # Midpoint: probe half a step back, then apply that wind for the full step.
        half_lat, half_lon = _displace(cur_lat, cur_lon, u1, v1, -dt / 2.0)
        half_time = cur_time - timedelta(seconds=dt / 2.0)
        u2, v2 = windfield.interpolate(half_lat, half_lon, half_time)

        new_lat, new_lon = _displace(cur_lat, cur_lon, u2, v2, -dt)
        new_time = cur_time - timedelta(seconds=dt)

        if not windfield.contains(new_lat, new_lon):
            exited = True
            break

        cur_lat, cur_lon, cur_time = new_lat, new_lon, new_time
        collected.append(
            TrajectoryPoint(cur_lat, cur_lon, cur_time, step * dt / 3600.0)
        )

    collected.reverse()  # so the path reads forward in time
    return Trajectory(
        points=collected, member=member, is_primary=is_primary, exited_domain=exited
    )


def _displace(lat, lon, u, v, dt_seconds):
    """
    Move a point by a wind vector for dt seconds.

    Negative dt steps backwards. The cos(latitude) term on longitude is
    required: without it, east-west displacement is wrong everywhere except
    the equator, and the error grows with latitude.
    """
    dlat = (v * dt_seconds) / config.METRES_PER_DEG_LAT
    denom = config.METRES_PER_DEG_LON_EQUATOR * np.cos(np.deg2rad(lat))
    denom = max(abs(denom), 1.0)  # guard against the pole singularity
    dlon = (u * dt_seconds) / denom
    return lat + dlat, lon + dlon


def ensemble_trajectories(
    windfield,
    lat,
    lon,
    arrival_time,
    n_members=None,
    spatial_jitter=None,
    time_jitter_hours=None,
    **kwargs,
):
    """
    An ensemble of perturbed trajectories.

    The spread between members is the uncertainty estimate. It is not decoration:
    a tight bundle means the attribution is robust, a fan means it is not, and
    showing that honestly is worth more than a single confident line.

    Member 0 is always the unperturbed primary.
    """
    n = n_members or config.ENSEMBLE_SIZE
    jitter = spatial_jitter if spatial_jitter is not None else config.ENSEMBLE_SPATIAL_JITTER_DEG
    t_jitter = (
        time_jitter_hours
        if time_jitter_hours is not None
        else config.ENSEMBLE_TIME_JITTER_HOURS
    )

    out = [
        back_trajectory(
            windfield, lat, lon, arrival_time, member=0, is_primary=True, **kwargs
        )
    ]

    for i in range(1, n):
        angle = 2 * np.pi * (i - 1) / max(n - 1, 1)
        dlat = jitter * np.sin(angle)
        dlon = jitter * np.cos(angle)
        dt_h = t_jitter * np.sin(angle)

        out.append(
            back_trajectory(
                windfield,
                lat + dlat,
                lon + dlon,
                arrival_time + timedelta(hours=float(dt_h)),
                member=i,
                is_primary=False,
                **kwargs,
            )
        )

    return out


def ensemble_spread_km(trajectories):
    """
    Mean distance of ensemble members from the primary, at matched hours-before.

    A single number for how confident the trace is. Report it in the video.
    """
    primary = next((t for t in trajectories if t.is_primary), trajectories[0])
    ref = {round(p.hours_before, 3): p for p in primary.points}

    dists = []
    for traj in trajectories:
        if traj is primary:
            continue
        for p in traj.points:
            match = ref.get(round(p.hours_before, 3))
            if match is not None:
                dists.append(haversine_km(match.lat, match.lon, p.lat, p.lon))

    return float(np.mean(dists)) if dists else 0.0
