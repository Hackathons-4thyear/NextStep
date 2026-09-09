"""
Run the whole pipeline end to end.

A thin orchestrator, deliberately. Every stage below already works standalone
and caches its own output, so this exists to give one reproducible command
rather than to add logic of its own. Re-running it is cheap: fetches hit the
cache unless --force is passed.

    python -m pipeline.run_all
    python -m pipeline.run_all --force     # re-fetch everything from the APIs

Needs FIRMS_MAP_KEY and OPENAQ_API_KEY in .env for the fetch stages. Open-Meteo
needs no key. Once the caches exist, the modelling stages run offline.
"""

from __future__ import annotations

import argparse
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import config


def _stage(n, total, title):
    print(f"\n{'=' * 70}\n[{n}/{total}] {title}\n{'=' * 70}")


def main(force=False, verbose=True):
    from pipeline.fetch_airquality import fetch_pm25
    from pipeline.fetch_fires import assign_districts, clean_fires, fetch_fires
    from pipeline.fetch_wind import fetch_wind

    total = 5
    t0 = time.time()

    print(f"Smoke Forensics — full pipeline for {config.TARGET_NAME}")
    print(f"  domain {config.BBOX['west']}W {config.BBOX['south']}S "
          f"{config.BBOX['east']}E {config.BBOX['north']}N")
    print(f"  season {config.SEASON_START} to {config.SEASON_END}")
    print(f"  receptor {config.RECEPTOR['name']}")

    _stage(1, total, "Fire detections (NASA FIRMS)")
    raw = fetch_fires(force=force, verbose=verbose)
    fires = assign_districts(clean_fires(raw, force=force, verbose=verbose))
    print(f"  {len(fires):,} usable detections")

    _stage(2, total, "Wind field (Open-Meteo ERA5)")
    wind = fetch_wind(force=force, verbose=verbose)
    print(f"  {len(wind.times):,} hourly steps on a "
          f"{len(wind.lats)}x{len(wind.lons)} grid")

    _stage(3, total, "Ground PM2.5 (OpenAQ v3)")
    pm = fetch_pm25(force=force, verbose=verbose)
    print(f"  {len(pm):,} hourly observations")

    _stage(4, total, "Season-wide validation")
    from pipeline.validate import main as validate_main
    validate_main(verbose=verbose)

    _stage(5, total, "Export site JSON")
    from pipeline.export import main as export_main
    export_main(verbose=verbose)

    mins = (time.time() - t0) / 60
    print(f"\n{'=' * 70}")
    print(f"Done in {mins:.1f} min. Site data written to {config.SITE_DATA}")
    print("Serve it with:  cd docs && python -m http.server")
    print("=" * 70)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="ignore caches and re-fetch from every API")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    try:
        main(force=args.force, verbose=not args.quiet)
    except RuntimeError as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        sys.exit(1)
