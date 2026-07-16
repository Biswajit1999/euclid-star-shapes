"""Run the Euclid Q1 VIS PSF and astrometry audit: either the synthetic
--demo smoke path, or the real-data pipeline over data/source_catalog.csv +
data/raw/ + a live Gaia DR3 cross-match.

Peak memory is measured with the stdlib `tracemalloc` (Python-level
allocations) rather than a full process-RSS profiler such as psutil, which
is not part of this project's pinned dependency set.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np

from euclid_q1_vis_psf_astrometry_audit import __version__
from euclid_q1_vis_psf_astrometry_audit.config import load_config
from euclid_q1_vis_psf_astrometry_audit.core import demo_series, read_source_catalog, robust_summary, run_pipeline
from euclid_q1_vis_psf_astrometry_audit.exceptions import ProjectError
from euclid_q1_vis_psf_astrometry_audit.gaia_match import fetch_gaia_reference_catalog
from euclid_q1_vis_psf_astrometry_audit.logging_utils import get_logger
from euclid_q1_vis_psf_astrometry_audit.provenance import get_git_commit, sha256_config
from euclid_q1_vis_psf_astrometry_audit.results_io import Metric, write_summary

LOGGER = get_logger(__name__)
GAIA_MATCH_RADIUS_DEG = 0.02  # search box around the field center for the live Gaia query


def _write_benchmark(path: Path, label: str, wall_time_s: float, peak_memory_mib: float, dataset_size: int) -> None:
    payload = {
        "label": label,
        "wall_time_seconds": wall_time_s,
        "peak_memory_mib": peak_memory_mib,
        "peak_memory_method": "tracemalloc (Python-level allocations, not full process RSS)",
        "dataset_size": dataset_size,
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "package_version": __version__,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    existing.append(payload)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def run_demo() -> None:
    tracemalloc.start()
    start = time.perf_counter()

    values = demo_series()
    summary = robust_summary(values)

    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    out = Path("results")
    out.mkdir(exist_ok=True)
    metrics = [
        Metric(name="median", estimate=summary.median, units="dimensionless", sample_size=summary.count),
        Metric(name="median_absolute_deviation", estimate=summary.mad, units="dimensionless", sample_size=summary.count),
    ]
    payload = write_summary(
        out / "summary.json",
        project="Euclid Q1 VIS PSF and Astrometry Audit (demo smoke test)",
        data_kind="synthetic_smoke_test",
        metrics=metrics,
        provenance={
            "config_sha256": None,
            "git_commit": get_git_commit(Path(__file__).resolve().parents[1]),
            "package_version": __version__,
        },
        warnings=[],
    )
    print(json.dumps(payload, indent=2))
    _write_benchmark(out / "benchmarks.json", "demo", elapsed, peak / (1024 * 1024), values.size)


def run_real_data(config_path: Path, source_catalog_path: Path, raw_dir: Path, results_dir: Path) -> None:
    config = load_config(config_path)
    try:
        catalog_entries = read_source_catalog(source_catalog_path)
    except ProjectError as exc:
        raise SystemExit(
            f"Cannot run the real-data pipeline: {exc}. Run scripts/fetch_data.py "
            "(with explicit operator authorization) first."
        ) from exc

    field_ra = float(np.mean([e.ra for e in catalog_entries]))
    field_dec = float(np.mean([e.dec for e in catalog_entries]))
    LOGGER.info("Fetching live Gaia DR3 reference catalog around (%.4f, %.4f)", field_ra, field_dec)
    gaia_ra, gaia_dec, gaia_source_id = fetch_gaia_reference_catalog(field_ra, field_dec, GAIA_MATCH_RADIUS_DEG)

    tracemalloc.start()
    start = time.perf_counter()

    result = run_pipeline(catalog_entries, raw_dir, config, gaia_ra, gaia_dec, gaia_source_id)

    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    fwhm_values = [m.fwhm_measured for m in result.measurements]
    ellip_values = [m.ellipticity_measured for m in result.measurements]
    metrics = [
        Metric(name="median_fwhm", estimate=float(np.median(fwhm_values)), units="pixels", sample_size=len(fwhm_values)),
        Metric(name="median_ellipticity", estimate=float(np.median(ellip_values)), units="dimensionless", sample_size=len(ellip_values)),
        Metric(
            name="gaia_astrometric_rms_residual",
            estimate=result.gaia_rms_residual_arcsec if result.gaia_rms_residual_arcsec is not None else float("nan"),
            units="arcsec",
            sample_size=result.gaia_n_matched,
        ),
    ]
    for cut in result.quality_cuts:
        metrics.append(
            Metric(name=f"fwhm_median_{cut.cut_name}_cut", estimate=cut.fwhm_median, units="pixels", sample_size=cut.n_sources)
        )
        metrics.append(
            Metric(name=f"ellipticity_median_{cut.cut_name}_cut", estimate=cut.ellipticity_median, units="dimensionless", sample_size=cut.n_sources)
        )
    for label, binning in (("fwhm", result.fwhm_by_magnitude), ("ellipticity", result.ellipticity_by_magnitude)):
        for i, b in enumerate(binning.bins):
            metrics.append(
                Metric(
                    name=f"{label}_by_magnitude_bin_{i}_[{b.bin_low:.3g},{b.bin_high:.3g})",
                    estimate=b.mean, units="pixels" if label == "fwhm" else "dimensionless", sample_size=b.n_members,
                )
            )

    provenance = {
        "config_sha256": sha256_config(config_path),
        "git_commit": get_git_commit(Path(__file__).resolve().parents[1]),
        "package_version": __version__,
        "n_sources": len(result.measurements),
        "gaia_reference_size": len(gaia_ra),
    }

    results_dir.mkdir(exist_ok=True)
    write_summary(
        results_dir / "summary.json",
        project=config.project.title,
        data_kind=config.input.data_mode,
        metrics=metrics,
        provenance=provenance,
        warnings=result.warnings,
    )
    (results_dir / "warnings.json").write_text(json.dumps(result.warnings, indent=2), encoding="utf-8")
    _write_benchmark(results_dir / "benchmarks.json", "real_data", elapsed, peak / (1024 * 1024), len(catalog_entries))
    print(f"Wrote {results_dir / 'summary.json'} ({len(metrics)} metrics, {len(result.warnings)} warnings)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Run synthetic smoke data only")
    parser.add_argument("--config", type=Path, default=Path("config/analysis.yml"))
    parser.add_argument("--source-catalog", type=Path, default=Path("data/source_catalog.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    args = parser.parse_args()

    if args.demo:
        run_demo()
        return

    run_real_data(args.config, args.source_catalog, args.raw_dir, args.results_dir)


if __name__ == "__main__":
    main()
