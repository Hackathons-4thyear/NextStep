"""
Gridded wind field with interpolation in space and time.

The class deliberately takes raw arrays in its constructor rather than reading
files. That means it can be built from a synthetic analytic field in tests,
where the correct trajectory is known in advance, as well as from cached
Open-Meteo data in the real pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from scipy.interpolate import RegularGridInterpolator


class WindField:
    """
    Hourly gridded u/v wind, interpolated bilinearly in space and linearly in time.

    Parameters
    ----------
    lats, lons
        1-D ascending coordinate arrays defining the grid.
    times
        1-D array of timezone-aware datetimes, ascending, evenly spaced.
    u, v
        Arrays shaped (n_time, n_lat, n_lon) in metres per second.
        u is the eastward component, v is the northward component.
    """

    def __init__(self, lats, lons, times, u, v):
        self.lats = np.asarray(lats, dtype=float)
        self.lons = np.asarray(lons, dtype=float)
        self.times = list(times)

        self.u = np.asarray(u, dtype=float)
        self.v = np.asarray(v, dtype=float)

        expected = (len(self.times), len(self.lats), len(self.lons))
        if self.u.shape != expected or self.v.shape != expected:
            raise ValueError(
                f"u/v must be shaped {expected}, got {self.u.shape} and {self.v.shape}"
            )

        if not np.all(np.diff(self.lats) > 0):
            raise ValueError("lats must be strictly ascending")
        if not np.all(np.diff(self.lons) > 0):
            raise ValueError("lons must be strictly ascending")

        # Interpolate against epoch seconds so time is just another numeric axis.
        self._t0 = self.times[0]
        self._t_secs = np.array(
            [(t - self._t0).total_seconds() for t in self.times], dtype=float
        )
        if not np.all(np.diff(self._t_secs) > 0):
            raise ValueError("times must be strictly ascending")

        grid = (self._t_secs, self.lats, self.lons)
        opts = dict(bounds_error=False, fill_value=None)  # None -> extrapolate at edges
        self._iu = RegularGridInterpolator(grid, self.u, **opts)
        self._iv = RegularGridInterpolator(grid, self.v, **opts)

    # -- construction ------------------------------------------------------

    @staticmethod
    def uv_from_speed_direction(speed, direction_deg):
        """
        Convert meteorological speed/direction to eastward/northward components.

        Meteorological wind direction is the direction the wind blows *FROM*,
        measured clockwise from north. A 270 degree wind is a westerly: it comes
        from the west and blows toward the east, so u is positive.

        Getting this sign wrong sends every trajectory in exactly the wrong
        direction, which is the single most likely silent bug in this project.
        The self-test in tests/test_physics.py pins it down.
        """
        speed = np.asarray(speed, dtype=float)
        rad = np.deg2rad(np.asarray(direction_deg, dtype=float))
        u = -speed * np.sin(rad)
        v = -speed * np.cos(rad)
        return u, v

    @classmethod
    def from_npz(cls, path):
        """Load a wind field cached by pipeline.fetch_wind."""
        blob = np.load(path, allow_pickle=False)
        times = [
            datetime.fromtimestamp(float(ts), tz=timezone.utc)
            for ts in blob["time_epoch"]
        ]
        return cls(blob["lats"], blob["lons"], times, blob["u"], blob["v"])

    def to_npz(self, path):
        np.savez_compressed(
            path,
            lats=self.lats,
            lons=self.lons,
            time_epoch=np.array([t.timestamp() for t in self.times], dtype=float),
            u=self.u,
            v=self.v,
        )

    # -- queries -----------------------------------------------------------

    def interpolate(self, lat, lon, when):
        """
        Wind at a point and time.

        Returns (u, v) in m/s. Queries outside the grid are linearly
        extrapolated rather than raising, because a trajectory that grazes the
        domain edge should degrade gracefully. Use `contains` to check
        explicitly when it matters.
        """
        t = (when - self._t0).total_seconds()
        pt = np.array([[t, lat, lon]], dtype=float)
        return float(self._iu(pt)[0]), float(self._iv(pt)[0])

    def contains(self, lat, lon, when=None):
        inside = (
            self.lats[0] <= lat <= self.lats[-1]
            and self.lons[0] <= lon <= self.lons[-1]
        )
        if when is not None:
            t = (when - self._t0).total_seconds()
            inside = inside and (self._t_secs[0] <= t <= self._t_secs[-1])
        return inside

    # -- diagnostics -------------------------------------------------------

    def prevailing_direction(self):
        """
        Mean direction the wind blows FROM, over the whole field, in degrees.

        This is the sanity check that catches an inverted sign convention.
        Compare it against what you know of the region's climate before
        trusting a single trajectory. For Punjab-to-Delhi in the burning
        season, expect something broadly northwesterly, so roughly 290-330.
        """
        mu = float(np.nanmean(self.u))
        mv = float(np.nanmean(self.v))
        # Invert the vector to recover the "from" direction.
        return float((np.rad2deg(np.arctan2(-mu, -mv))) % 360.0)

    def mean_speed(self):
        return float(np.nanmean(np.sqrt(self.u**2 + self.v**2)))

    def summary(self):
        return (
            f"WindField grid={len(self.lats)}x{len(self.lons)} "
            f"times={len(self.times)} "
            f"({self.times[0]:%Y-%m-%d %H:%M} to {self.times[-1]:%Y-%m-%d %H:%M} UTC)\n"
            f"  mean speed        {self.mean_speed():.2f} m/s\n"
            f"  prevailing (from) {self.prevailing_direction():.1f} deg"
        )
