"""Pipeline orchestration composing the reusable scientific modules.

`run_pipeline` is the single non-notebook entry point for the real-data
analysis. It is deliberately network-free (Gaia and cutout fetching happen in
scripts/fetch_data.py and scripts/run_analysis.py) so it can be exercised in
tests against synthetic cutouts and a synthetic Gaia catalog.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from euclid_q1_vis_psf_astrometry_audit.config import AnalysisConfig
from euclid_q1_vis_psf_astrometry_audit.detection import refine_centroid, sky_to_pixel
from euclid_q1_vis_psf_astrometry_audit.exceptions import ConvergenceError, DataSchemaError, InsufficientDataError
from euclid_q1_vis_psf_astrometry_audit.gaia_match import fit_affine_alignment, match_to_gaia, sky_to_tangent_plane
from euclid_q1_vis_psf_astrometry_audit.io import load_cutout
from euclid_q1_vis_psf_astrometry_audit.logging_utils import get_logger
from euclid_q1_vis_psf_astrometry_audit.psf_metrics import compare_gaussian_moffat
from euclid_q1_vis_psf_astrometry_audit.spatial_stats import (
    QualityCutResult,
    ScalarBinningResult,
    apply_quality_cuts,
    bin_scalar_statistic,
)

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class Summary:
    count: int
    median: float
    mad: float


def validate_numeric(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError("values must be one-dimensional")
    if arr.size == 0:
        raise ValueError("values must not be empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError("values contain non-finite entries")
    return arr


def robust_summary(values: np.ndarray) -> Summary:
    arr = validate_numeric(values)
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    return Summary(count=int(arr.size), median=median, mad=mad)


def demo_series(seed: int = 20260713, size: int = 128) -> np.ndarray:
    """Return deterministic synthetic data labelled only for smoke testing."""
    if size < 8:
        raise ValueError("size must be at least 8")
    rng = np.random.default_rng(seed)
    return rng.normal(loc=0.0, scale=1.0, size=size)


@dataclass(frozen=True)
class SourceCatalogEntry:
    object_id: int
    product_id: str
    ra: float
    dec: float
    fwhm_catalog: float
    ellipticity_catalog: float | None
    mag_stargal_sep: float | None
    point_like_prob: float
    gaia_id: int | None
    tileid: int


def _parse_optional_float(value: str) -> float | None:
    return float(value) if value not in ("", None) else None


def read_source_catalog(path: str | Path) -> list[SourceCatalogEntry]:
    """Read the companion source catalog written by scripts/fetch_data.py."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise InsufficientDataError(f"source catalog not found: {csv_path}")
    entries = []
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            entries.append(
                SourceCatalogEntry(
                    object_id=int(row["object_id"]),
                    product_id=row["product_id"],
                    ra=float(row["ra"]),
                    dec=float(row["dec"]),
                    fwhm_catalog=float(row["fwhm_catalog"]),
                    ellipticity_catalog=_parse_optional_float(row["ellipticity_catalog"]),
                    mag_stargal_sep=_parse_optional_float(row["mag_stargal_sep"]),
                    point_like_prob=float(row["point_like_prob"]),
                    gaia_id=int(row["gaia_id"]) if row["gaia_id"] not in ("", None) else None,
                    tileid=int(row["tileid"]),
                )
            )
    if not entries:
        raise InsufficientDataError(f"source catalog {csv_path} has no rows")
    return entries


@dataclass(frozen=True)
class SourceMeasurement:
    object_id: int
    product_id: str
    ra: float
    dec: float
    mag_stargal_sep: float | None
    point_like_prob: float
    fwhm_measured: float
    ellipticity_measured: float
    better_model: str
    gaussian_reduced_chi2: float | None
    moffat_reduced_chi2: float | None
    centroid_ra: float
    centroid_dec: float


def _measure_one(entry: SourceCatalogEntry, raw_dir: Path, box_size: int) -> SourceMeasurement:
    cutout = load_cutout(raw_dir / f"{entry.product_id}.fits")
    x_guess, y_guess = sky_to_pixel(cutout.wcs, entry.ra, entry.dec)
    centroid = refine_centroid(cutout.science_array, x_guess, y_guess, box_size=11)

    half = box_size // 2
    ny, nx = cutout.science_array.shape
    xi, yi = int(round(centroid.x)), int(round(centroid.y))
    x0, x1 = max(0, xi - half), min(nx, xi + half + 1)
    y0, y1 = max(0, yi - half), min(ny, yi + half + 1)
    box = cutout.science_array[y0:y1, x0:x1] - centroid.background_median
    if box.shape[0] < 10 or box.shape[1] < 10:
        raise InsufficientDataError(f"{entry.product_id}: fitting box too small near cutout edge {box.shape}")

    comparison = compare_gaussian_moffat(box)
    best = comparison.gaussian if comparison.better_model == "gaussian" else comparison.moffat

    centroid_ra, centroid_dec = cutout.wcs.all_pix2world(x0 + best.x0, y0 + best.y0, 0)

    return SourceMeasurement(
        object_id=entry.object_id,
        product_id=entry.product_id,
        ra=entry.ra,
        dec=entry.dec,
        mag_stargal_sep=entry.mag_stargal_sep,
        point_like_prob=entry.point_like_prob,
        fwhm_measured=best.fwhm,
        ellipticity_measured=best.ellipticity,
        better_model=comparison.better_model,
        gaussian_reduced_chi2=comparison.gaussian.convergence.reduced_chi_square,
        moffat_reduced_chi2=comparison.moffat.convergence.reduced_chi_square,
        centroid_ra=float(centroid_ra),
        centroid_dec=float(centroid_dec),
    )


@dataclass(frozen=True)
class PipelineResult:
    measurements: list[SourceMeasurement]
    fwhm_by_magnitude: ScalarBinningResult
    ellipticity_by_magnitude: ScalarBinningResult
    quality_cuts: tuple[QualityCutResult, ...]
    gaia_n_matched: int
    gaia_n_unmatched: int
    gaia_rms_residual_arcsec: float | None
    warnings: list[str] = field(default_factory=list)


def run_pipeline(
    catalog_entries: list[SourceCatalogEntry],
    raw_dir: str | Path,
    config: AnalysisConfig,
    gaia_ra: np.ndarray,
    gaia_dec: np.ndarray,
    gaia_source_id: np.ndarray,
    box_size: int = 15,
    n_magnitude_bins: int = 3,
) -> PipelineResult:
    """Run the full VIS PSF + Gaia astrometry audit over real (or synthetic-test) cutouts.

    `gaia_ra`/`gaia_dec`/`gaia_source_id` are passed in rather than fetched
    here, keeping this function network-free and testable with a synthetic
    Gaia catalog.
    """
    raw_dir = Path(raw_dir)
    all_warnings: list[str] = []
    measurements: list[SourceMeasurement] = []

    for entry in catalog_entries:
        try:
            measurements.append(_measure_one(entry, raw_dir, box_size))
        except (InsufficientDataError, ConvergenceError, DataSchemaError) as exc:
            # Per-source failures (missing/malformed cutout file, poor S/N,
            # non-converging fit) are expected and must not abort the whole
            # pipeline; they are recorded, not silently dropped, per
            # docs/ERROR_HANDLING.md.
            all_warnings.append(f"{entry.product_id}: skipped: {exc}")

    if not measurements:
        raise InsufficientDataError("no usable PSF measurements across any source")

    fwhm = np.array([m.fwhm_measured for m in measurements])
    ellipticity = np.array([m.ellipticity_measured for m in measurements])
    point_like_prob = np.array([m.point_like_prob for m in measurements])
    magnitudes = np.array([m.mag_stargal_sep if m.mag_stargal_sep is not None else np.nan for m in measurements])

    valid_mag = np.isfinite(magnitudes)
    if valid_mag.sum() >= 2:
        mag_edges = np.quantile(magnitudes[valid_mag], np.linspace(0, 1, n_magnitude_bins + 1))
        mag_edges[-1] += 1e-6
        fwhm_by_mag = bin_scalar_statistic(
            magnitudes[valid_mag], fwhm[valid_mag], mag_edges, config.validation.minimum_sample_size
        )
        ellip_by_mag = bin_scalar_statistic(
            magnitudes[valid_mag], ellipticity[valid_mag], mag_edges, config.validation.minimum_sample_size
        )
        all_warnings.extend(fwhm_by_mag.warnings)
        all_warnings.extend(ellip_by_mag.warnings)
    else:
        fwhm_by_mag = ScalarBinningResult(bins=[], warnings=["insufficient valid magnitudes to bin"])
        ellip_by_mag = ScalarBinningResult(bins=[], warnings=["insufficient valid magnitudes to bin"])
        all_warnings.extend(fwhm_by_mag.warnings)

    quality_cuts: tuple[QualityCutResult, ...]
    try:
        quality_cuts = apply_quality_cuts(point_like_prob, fwhm, ellipticity)
    except InsufficientDataError as exc:
        all_warnings.append(f"quality cut comparison skipped: {exc}")
        quality_cuts = ()

    measured_ra = np.array([m.centroid_ra for m in measurements])
    measured_dec = np.array([m.centroid_dec for m in measurements])
    matches = match_to_gaia(measured_ra, measured_dec, gaia_ra, gaia_dec, gaia_source_id)
    matched = [m for m in matches if m is not None]
    n_unmatched = len(matches) - len(matched)
    if n_unmatched:
        all_warnings.append(f"{n_unmatched} of {len(matches)} sources had no Gaia match within the match radius")

    gaia_rms = None
    if len(matched) >= 3:
        field_ra0, field_dec0 = float(np.mean(measured_ra)), float(np.mean(measured_dec))
        measured_xy = np.column_stack(
            sky_to_tangent_plane(np.array([m.measured_ra for m in matched]), np.array([m.measured_dec for m in matched]), field_ra0, field_dec0)
        )
        gaia_xy = np.column_stack(
            sky_to_tangent_plane(np.array([m.gaia_ra for m in matched]), np.array([m.gaia_dec for m in matched]), field_ra0, field_dec0)
        )
        alignment = fit_affine_alignment(measured_xy, gaia_xy)
        gaia_rms = alignment.rms_residual_arcsec
    else:
        all_warnings.append(
            f"only {len(matched)} Gaia matches; need >=3 to fit an affine alignment (see IMPLEMENTATION_PLAN.md)"
        )

    return PipelineResult(
        measurements=measurements,
        fwhm_by_magnitude=fwhm_by_mag,
        ellipticity_by_magnitude=ellip_by_mag,
        quality_cuts=quality_cuts,
        gaia_n_matched=len(matched),
        gaia_n_unmatched=n_unmatched,
        gaia_rms_residual_arcsec=gaia_rms,
        warnings=all_warnings,
    )
