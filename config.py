"""
Every tunable constant in the project lives here and nowhere else.

If you find yourself typing a number into a pipeline module, it belongs in this file.
That rule is what makes the sensitivity analysis on Day 3 a five-minute job instead of
a refactor.
"""

from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "docs" / "data"

for _d in (DATA_RAW, DATA_PROCESSED, SITE_DATA):
    _d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# TARGET  --  change these to move the project to a different region
# ---------------------------------------------------------------------------
#
# Default target: crop residue burning in Punjab/Haryana -> Delhi.
#
# Chosen because it is the best-instrumented smoke transport case on Earth:
# very dense VIIRS detections through Oct-Nov, the densest PM2.5 monitoring
# network in India at the receptor, and a well-defined NW->SE transport
# direction over roughly 250-300 km.
#
# Run prompt P1 in 07-prompts.md if you want to target somewhere else.

TARGET_NAME = "punjab-delhi"

# Domain covering both the source region and the receptor, with margin so
# back-trajectories do not immediately exit the box.
# Widened on Day 3: at 48h back, 8 of 52 days (15.4%) hit the old NW corner and
# truncated. Trajectories run upwind toward the northwest, so the box needs
# roughly 900 km of room in that quadrant -- the longest observed path was
# 762 km. Widening changes the fire region too, so it also changes the naive
# baseline's denominator; both models see the same new region.
BBOX = {
    "west": 67.5,
    "south": 24.0,
    "east": 82.0,
    "north": 37.0,
}

# Receptor: the city where pollution is measured.
RECEPTOR = {
    "name": "Delhi",
    "lat": 28.6139,
    "lon": 77.2090,
}

# Season to analyse. Burning season, wide enough for a real correlation.
SEASON_START = "2024-10-10"
SEASON_END = "2024-11-30"

# The hero episode driving the animation. Chosen on Day 1: season-peak PM2.5
# (700 ug/m3) arriving on a near-straight 433 km trajectory from the Punjab
# stubble belt, with 83% of attribution in two adjacent source cells and no
# contribution from Delhi's own cell. Ensemble CV 0.11, the most robust of the
# candidates. See planning/02-data-sources.md on why peak ratio alone is a poor
# selector: 2024-11-12 had a steeper rise but recirculated locally.
EPISODE_ARRIVAL_UTC = datetime(2024, 11, 18, 6, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Wind field
# ---------------------------------------------------------------------------

# Grid spacing in degrees. ERA5 is ~10km (~0.1 deg) so going finer than 0.25
# adds no information, it just interpolates the same underlying cells.
WIND_GRID_SPACING = 0.5

# Altitude of the transport wind.
#   100m  -> boundary layer, correct for smoke from surface burning (default)
#   10m   -> too much surface friction, use only as a sensitivity check
WIND_LEVEL = "100m"

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Locations per Open-Meteo request. The API accepts comma-separated lists.
WIND_BATCH_SIZE = 25


# ---------------------------------------------------------------------------
# Trajectory integration
# ---------------------------------------------------------------------------

TRAJECTORY_HOURS_BACK = 48          # how far back to trace
TRAJECTORY_DT_SECONDS = 900         # 15 min. Hourly steps visibly cut corners.

ENSEMBLE_SIZE = 8                   # members expressing uncertainty
ENSEMBLE_SPATIAL_JITTER_DEG = 0.15  # launch offset around the receptor
ENSEMBLE_TIME_JITTER_HOURS = 2.0    # offset in arrival time

# Earth geometry constants for the degree/metre conversion.
METRES_PER_DEG_LAT = 110_540.0
METRES_PER_DEG_LON_EQUATOR = 111_320.0


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

# Corridor half-width in km. Fires are weighted by a Gaussian falloff on this,
# so it is a soft scale rather than a hard cutoff.
CORRIDOR_RADIUS_KM = 30.0

# Sensitivity sweep reported on Day 3.
CORRIDOR_SENSITIVITY_KM = [20.0, 30.0, 50.0]

# A fire only counts if it was detected within this many hours of the air
# parcel passing over it. Without this, a fire from two days earlier gets
# credited to an episode it had nothing to do with.
FIRE_TIME_TOLERANCE_HOURS = 12.0


# ---------------------------------------------------------------------------
# Fire data
# ---------------------------------------------------------------------------

FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Science-quality products for historical seasons. NRT data is replaced by SP
# after a 2-3 month lag, so for anything older than ~3 months, use SP.
FIRMS_SOURCES = ["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"]

# Fallback if SP is not yet available for your dates.
FIRMS_SOURCES_NRT = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT"]

FIRMS_MAX_DAY_RANGE = 5            # hard API limit

# VIIRS confidence: 'l' low, 'n' nominal, 'h' high.
FIRE_CONFIDENCE_KEEP = ["n", "h"]

# Persistent thermal anomaly mask: steel plants, refineries and gas flares fire
# nearly every day at the same spot. Round coordinates to a grid and drop cells
# that appear on more than this fraction of days in the season.
PERSISTENT_SOURCE_GRID_DEG = 0.01   # ~1 km
PERSISTENT_SOURCE_DAY_FRACTION = 0.6


# ---------------------------------------------------------------------------
# Air quality
# ---------------------------------------------------------------------------

OPENAQ_BASE_URL = "https://api.openaq.org/v3"
OPENAQ_PARAMETER = "pm25"

# Take the median across stations rather than trusting a single one.
OPENAQ_MIN_STATIONS = 3
OPENAQ_SEARCH_RADIUS_DEG = 0.35     # around the receptor


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

LAG_SWEEP_HOURS = list(range(0, 49, 2))

# Lookback window for the naive baseline, in hours. Should match
# TRAJECTORY_HOURS_BACK so both models see the same set of fires and the only
# difference between them is whether they know about the wind. Shrinking this
# would hand the comparison an easy win and make the headline claim worthless.
NAIVE_BASELINE_WINDOW_HOURS = TRAJECTORY_HOURS_BACK

# Negative control, directional form. A day joins the control when the air
# arrived from this bearing sector, which contains no significant burning --
# it tests the mechanism claim (smoke comes from upwind fires) rather than a
# threshold on the model's own output.
#
# The earlier count-based threshold was removed: the minimum fires attributed
# on any day of the season was 20, so no threshold below that selected a
# single day, and the control silently returned an empty set.
NEGATIVE_CONTROL_BEARING_MIN = 45.0
NEGATIVE_CONTROL_BEARING_MAX = 225.0

# Ventilation normalisation. Concentration in a box model goes as emission
# divided by ventilation, so an index that only counts fires crossed will
# inflate on windy days -- exactly the days when the receptor is best flushed.
# Dividing by mean transport speed removes that bias. Applied to BOTH models,
# so it cannot favour either.
VENTILATION_MIN_MS = 0.5    # floor, guards against dividing by a near-calm day

# Arrival hours used by the multi-hour specification, which averages the index
# across the day rather than sampling one hour of a strong diurnal cycle.
VALIDATION_ARRIVAL_HOURS_UTC = [0, 6, 12, 18]

# Window for the detrending check. Both the fire index and PM2.5 ride the same
# seasonal arc, so a correlation on raw levels can be produced entirely by that
# shared trend without either series predicting the other day to day.
# Subtracting a centred rolling mean over this many days removes the arc and
# leaves the day-to-day variation, which is what a useful model has to explain.
DETREND_WINDOW_DAYS = 7

# Resamples for the bootstrap interval on the differenced correlation. The
# analytic Fisher interval assumes bivariate normality, which a heavily skewed
# fire index does not satisfy.
BOOTSTRAP_ITERATIONS = 5000

# Hour of day (UTC) at which the season-wide daily trajectory is launched.
# Fixed rather than chosen per day: picking each day's own PM2.5 peak hour
# would select for the outcome being measured and inflate the correlation.
VALIDATION_ARRIVAL_HOUR_UTC = 6

# Width of the window used to read observed PM2.5 as the response variable,
# centred on the (lagged) arrival time. Averaging over a few hours suppresses
# single-sensor noise. Applied identically to both models, so it cannot favour
# either one.
VALIDATION_PM25_WINDOW_HOURS = 6

# A day is called coherent transport rather than local recirculation when the
# net displacement of its trajectory is at least this fraction of the path
# length travelled. 1.0 is a straight line.
STRAIGHTNESS_TRANSPORT_MIN = 0.5


# ---------------------------------------------------------------------------
# Place names
# ---------------------------------------------------------------------------
#
# Attribution reads as "Jalandhar and Moga" or as "31N, 75E", and only one of
# those tells a viewer anything. Proper admin-2 boundaries would need a
# shapefile join and geopandas; the cut list in 04-build-plan.md says drop that
# and label clusters by their nearest named towns instead, which is what this
# is. Each key is a 1-degree cell from assign_districts (the cell centre, so
# "31N, 75E" spans 30.5-31.5N and 74.5-75.5E) and each value names the towns
# actually inside it.
#
# Unmapped cells fall through to the raw grid reference rather than being
# hidden, so a new region shows up as a coordinate instead of silently
# vanishing.

DISTRICT_NAMES = {
    "32N, 74E": "Gujranwala–Sialkot, Pakistan",
    "32N, 75E": "Amritsar–Gurdaspur, Punjab",
    "31N, 74E": "Fazilka–Firozpur, Punjab",
    "31N, 75E": "Jalandhar–Moga, Punjab",
    "31N, 76E": "Ludhiana–Rupnagar, Punjab",
    "30N, 74E": "Abohar–Sri Ganganagar",
    "30N, 75E": "Bathinda–Barnala, Punjab",
    "30N, 76E": "Patiala–Ambala",
    "30N, 77E": "Karnal–Kurukshetra, Haryana",
    "29N, 76E": "Jind–Rohtak, Haryana",
    "29N, 77E": "Panipat–Sonipat, Haryana",
    "29N, 78E": "Bijnor–Moradabad, Uttar Pradesh",
    "28N, 77E": "Delhi and its own outskirts",
    "28N, 78E": "Bulandshahr–Aligarh, Uttar Pradesh",
    "27N, 78E": "Agra, Uttar Pradesh",
}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

# Animation window shown in the browser, ending at the episode arrival. Tied to
# the trajectory length so the animation cannot show a window the physics did
# not actually cover.
ANIMATION_HOURS = TRAJECTORY_HOURS_BACK

# Trajectory points are decimated before export to keep payload small.
# 15-min steps over 48h = 193 points per member; every 2nd is plenty.
EXPORT_TRAJECTORY_STRIDE = 2

MAX_EXPORT_MB = 8.0

# Decimal places kept on exported coordinates. 4 dp is about 11 m, far finer
# than a 375 m VIIRS pixel or a 10 km reanalysis cell, and it roughly halves
# the JSON against full float repr.
EXPORT_COORD_PRECISION = 4

# Unattributed fires drawn for context, so the corridor is visibly a selection
# out of a wider field rather than the only burning on the map. Capped because
# the widened domain holds 85k detections and all of them would bloat the page.
EXPORT_MAX_CONTEXT_FIRES = 3000

# Hours of PM2.5 shown after the arrival moment, so the gauge can crest and
# fall rather than stopping dead on the peak.
EXPORT_PM25_TRAIL_HOURS = 12

# Natural Earth admin-1 boundaries, clipped to BBOX at export time. Downloaded
# once by hand; see docs in export.py. 1:50m is the right scale here -- the
# 1:10m edition is 38 MB, which no static page should be loading.
TERRAIN_SOURCE = DATA_RAW / "ne_50m_admin_1_states_provinces.geojson"
TERRAIN_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_50m_admin_1_states_provinces.geojson"
)
