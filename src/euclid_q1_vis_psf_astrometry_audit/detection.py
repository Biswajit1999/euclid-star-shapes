"""Source detection and centroid refinement on VIS cutouts."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy.stats import sigma_clipped_stats
from astropy.wcs import WCS
from photutils.centroids import centroid_2dg
from photutils.detection import DAOStarFinder

from euclid_q1_vis_psf_astrometry_audit.exceptions import InsufficientDataError


@dataclass(frozen=True)
class RefinedCentroid:
    x: float
    y: float
    background_median: float
    background_std: float


def sky_to_pixel(wcs: WCS, ra: float, dec: float) -> tuple[float, float]:
    x, y = wcs.all_world2pix(ra, dec, 0)
    return float(x), float(y)


def refine_centroid(
    science: np.ndarray,
    x_guess: float,
    y_guess: float,
    box_size: int = 11,
) -> RefinedCentroid:
    """Refine a centroid guess (e.g. from a catalog RA/Dec projected through
    the cutout WCS) using a 2-D Gaussian centroid within a small box.

    Raises InsufficientDataError if the guess is too close to the cutout edge
    for a full box, or if the local region has no measurable signal above
    the background noise.
    """
    half = box_size // 2
    ny, nx = science.shape
    xi, yi = int(round(x_guess)), int(round(y_guess))
    x0, x1 = xi - half, xi + half + 1
    y0, y1 = yi - half, yi + half + 1
    if x0 < 0 or y0 < 0 or x1 > nx or y1 > ny:
        raise InsufficientDataError(
            f"centroid guess ({x_guess:.1f}, {y_guess:.1f}) is too close to the cutout edge "
            f"for a {box_size}x{box_size} centroiding box (cutout shape {science.shape})"
        )

    box = science[y0:y1, x0:x1]
    _, median, std = sigma_clipped_stats(science, sigma=3.0, maxiters=5)
    if std == 0 or box.max() < median + 3 * std:
        raise InsufficientDataError(
            f"no signal above 3-sigma background near ({x_guess:.1f}, {y_guess:.1f})"
        )

    cx, cy = centroid_2dg(box - median)
    if not (np.isfinite(cx) and np.isfinite(cy)):
        raise InsufficientDataError("2-D Gaussian centroid fit returned a non-finite result")

    return RefinedCentroid(x=x0 + cx, y=y0 + cy, background_median=float(median), background_std=float(std))


@dataclass(frozen=True)
class DetectedSource:
    x: float
    y: float
    flux: float


def detect_sources(science: np.ndarray, fwhm: float = 4.5, threshold_sigma: float = 8.0) -> list[DetectedSource]:
    """Detect point sources with DAOStarFinder; used for synthetic-validation tests."""
    _, median, std = sigma_clipped_stats(science, sigma=3.0, maxiters=5)
    if std == 0:
        raise InsufficientDataError("background standard deviation is zero; cannot run source detection")

    finder = DAOStarFinder(threshold=threshold_sigma * std, fwhm=fwhm)
    table = finder(science - median)
    if table is None or len(table) == 0:
        raise InsufficientDataError(f"no sources detected above {threshold_sigma}-sigma threshold")
    return [
        DetectedSource(x=float(row["xcentroid"]), y=float(row["ycentroid"]), flux=float(row["flux"]))
        for row in table
    ]
