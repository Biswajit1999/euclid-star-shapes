"""Spatial and magnitude binning of per-source PSF/astrometric metrics.

Bins below `minimum_sample_size` are reported with `underpopulated=True` and
a message rather than being silently dropped, per docs/ERROR_HANDLING.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from euclid_q1_vis_psf_astrometry_audit.exceptions import InsufficientDataError


@dataclass(frozen=True)
class ScalarBin:
    bin_low: float
    bin_high: float
    mean: float
    std: float
    n_members: int
    underpopulated: bool


@dataclass(frozen=True)
class ScalarBinningResult:
    bins: list[ScalarBin]
    warnings: list[str] = field(default_factory=list)


def bin_scalar_statistic(
    keys: np.ndarray,
    values: np.ndarray,
    edges: np.ndarray,
    minimum_sample_size: int,
) -> ScalarBinningResult:
    """Bin scalar `values` (e.g. per-source FWHM) by scalar `keys` (e.g.
    distance from tile centre, or VIS magnitude), reporting mean/std per bin.
    """
    keys = np.asarray(keys, dtype=float)
    values = np.asarray(values, dtype=float)
    if keys.shape != values.shape:
        raise InsufficientDataError(f"keys shape {keys.shape} does not match values shape {values.shape}")
    edges = np.asarray(edges, dtype=float)
    if edges.ndim != 1 or edges.size < 2:
        raise InsufficientDataError("edges must be a 1-D array with at least 2 values")

    bin_indices = np.digitize(keys, edges) - 1
    bins: list[ScalarBin] = []
    warnings: list[str] = []

    for i in range(edges.size - 1):
        low, high = float(edges[i]), float(edges[i + 1])
        members = values[bin_indices == i]
        n_members = int(members.size)
        underpopulated = n_members < minimum_sample_size

        if underpopulated:
            warnings.append(
                f"bin [{low:.3g}, {high:.3g}) has {n_members} members, "
                f"below minimum_sample_size={minimum_sample_size}"
            )

        mean = float(np.mean(members)) if n_members >= 1 else float("nan")
        std = float(np.std(members, ddof=1)) if n_members >= 2 else float("nan")
        bins.append(
            ScalarBin(bin_low=low, bin_high=high, mean=mean, std=std, n_members=n_members, underpopulated=underpopulated)
        )

    return ScalarBinningResult(bins=bins, warnings=warnings)


@dataclass(frozen=True)
class QualityCutResult:
    cut_name: str
    threshold_description: str
    n_sources: int
    fwhm_median: float
    ellipticity_median: float


def apply_quality_cuts(
    point_like_prob: np.ndarray,
    fwhm: np.ndarray,
    ellipticity: np.ndarray,
    strict_threshold: float = 0.95,
    permissive_threshold: float = 0.8,
) -> tuple[QualityCutResult, QualityCutResult]:
    """Report FWHM/ellipticity medians under strict vs. permissive point-source
    quality cuts, so cut-sensitivity is visible rather than hidden behind a
    single arbitrary threshold (the "strict/permissive cuts" validation-contract item).
    """
    point_like_prob = np.asarray(point_like_prob, dtype=float)
    fwhm = np.asarray(fwhm, dtype=float)
    ellipticity = np.asarray(ellipticity, dtype=float)

    results = []
    for name, threshold in (("strict", strict_threshold), ("permissive", permissive_threshold)):
        mask = point_like_prob >= threshold
        n = int(np.sum(mask))
        if n == 0:
            raise InsufficientDataError(f"{name} cut (point_like_prob >= {threshold}) leaves zero sources")
        results.append(
            QualityCutResult(
                cut_name=name,
                threshold_description=f"point_like_prob >= {threshold}",
                n_sources=n,
                fwhm_median=float(np.median(fwhm[mask])),
                ellipticity_median=float(np.median(ellipticity[mask])),
            )
        )
    return tuple(results)  # type: ignore[return-value]
