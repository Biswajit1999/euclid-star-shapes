"""Gaia DR3 cross-match and affine astrometric alignment.

Positions are worked in a local tangent-plane pixel-like frame (arcsec offsets
from the field centre) rather than raw RA/Dec, so a single linear affine
transform is a reasonable local approximation over a single VIS cutout's
small field of view.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from euclid_q1_vis_psf_astrometry_audit.exceptions import ArchiveAccessError, InsufficientDataError

DEFAULT_MATCH_RADIUS_ARCSEC = 0.5
_MIN_POINTS_FOR_AFFINE = 3


def fetch_gaia_reference_catalog(
    field_ra: float, field_dec: float, radius_deg: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Live Gaia DR3 cone query (a rectangular RA/Dec box) around a field centre.

    This is the one function in this module that performs real network I/O
    (via astroquery.gaia); everything else here is pure and testable offline.
    Shared by scripts/run_analysis.py and scripts/make_figures.py so the
    query logic is not duplicated between them.
    """
    from astroquery.gaia import Gaia

    ra_lo, ra_hi = field_ra - radius_deg, field_ra + radius_deg
    dec_lo, dec_hi = field_dec - radius_deg, field_dec + radius_deg
    query = (
        f"SELECT source_id, ra, dec FROM gaiadr3.gaia_source "
        f"WHERE ra BETWEEN {ra_lo} AND {ra_hi} AND dec BETWEEN {dec_lo} AND {dec_hi}"
    )
    try:
        job = Gaia.launch_job(query)
        table = job.get_results()
    except Exception as exc:  # noqa: BLE001
        raise ArchiveAccessError(f"Gaia DR3 query failed: {exc}") from exc
    if len(table) == 0:
        raise ArchiveAccessError(f"Gaia DR3 query near ({field_ra}, {field_dec}) returned zero sources")

    # The Gaia archive TAP service returns column names in its own schema
    # casing (observed live: SOURCE_ID, uppercase) regardless of how the
    # SELECT clause was cased, so column access here is case-insensitive
    # rather than assuming the literal query casing round-trips.
    columns_lower = {name.lower(): name for name in table.colnames}
    try:
        ra_col, dec_col, id_col = columns_lower["ra"], columns_lower["dec"], columns_lower["source_id"]
    except KeyError as exc:
        raise ArchiveAccessError(
            f"Gaia DR3 result is missing an expected column (have: {table.colnames}): {exc}"
        ) from exc
    return np.array(table[ra_col]), np.array(table[dec_col]), np.array(table[id_col])


def sky_to_tangent_plane(ra: np.ndarray, dec: np.ndarray, ra0: float, dec0: float) -> tuple[np.ndarray, np.ndarray]:
    """Small-angle tangent-plane projection, in arcsec, centred on (ra0, dec0)."""
    ra, dec = np.asarray(ra, dtype=float), np.asarray(dec, dtype=float)
    dec0_rad = np.radians(dec0)
    dx = (ra - ra0) * np.cos(dec0_rad) * 3600.0
    dy = (dec - dec0) * 3600.0
    return dx, dy


@dataclass(frozen=True)
class GaiaMatch:
    measured_ra: float
    measured_dec: float
    gaia_ra: float
    gaia_dec: float
    gaia_source_id: int
    separation_arcsec: float


def match_to_gaia(
    measured_ra: np.ndarray,
    measured_dec: np.ndarray,
    gaia_ra: np.ndarray,
    gaia_dec: np.ndarray,
    gaia_source_id: np.ndarray,
    match_radius_arcsec: float = DEFAULT_MATCH_RADIUS_ARCSEC,
) -> list[GaiaMatch | None]:
    """Nearest-neighbour match each measured position to the closest Gaia source
    within `match_radius_arcsec`; unmatched sources are returned as None so the
    caller can count and report them rather than silently dropping them.
    """
    measured_ra = np.asarray(measured_ra, dtype=float)
    measured_dec = np.asarray(measured_dec, dtype=float)
    gaia_ra = np.asarray(gaia_ra, dtype=float)
    gaia_dec = np.asarray(gaia_dec, dtype=float)
    if gaia_ra.size == 0:
        raise InsufficientDataError("Gaia reference catalog is empty; cannot match")

    matches: list[GaiaMatch | None] = []
    for ra, dec in zip(measured_ra, measured_dec):
        dec_rad = np.radians(dec)
        dra = (gaia_ra - ra) * np.cos(dec_rad) * 3600.0
        ddec = (gaia_dec - dec) * 3600.0
        sep = np.hypot(dra, ddec)
        i_min = int(np.argmin(sep))
        if sep[i_min] <= match_radius_arcsec:
            matches.append(
                GaiaMatch(
                    measured_ra=float(ra), measured_dec=float(dec),
                    gaia_ra=float(gaia_ra[i_min]), gaia_dec=float(gaia_dec[i_min]),
                    gaia_source_id=int(gaia_source_id[i_min]), separation_arcsec=float(sep[i_min]),
                )
            )
        else:
            matches.append(None)
    return matches


@dataclass(frozen=True)
class AffineAlignment:
    params: np.ndarray  # [a, b, e, c, d, f] such that x' = a*x + b*y + e, y' = c*x + d*y + f
    residuals_x: np.ndarray
    residuals_y: np.ndarray
    residual_arcsec: np.ndarray
    rms_residual_arcsec: float


def fit_affine_alignment(measured_xy: np.ndarray, reference_xy: np.ndarray) -> AffineAlignment:
    """Fit a 2-D affine transform mapping measured (x, y) onto reference (x, y)
    (both in the same tangent-plane arcsec frame) via least squares.

    Requires at least 3 point pairs (6 free parameters, 2 equations per
    point); raises InsufficientDataError otherwise rather than returning an
    under-determined fit.
    """
    measured_xy = np.asarray(measured_xy, dtype=float)
    reference_xy = np.asarray(reference_xy, dtype=float)
    if measured_xy.shape != reference_xy.shape or measured_xy.ndim != 2 or measured_xy.shape[1] != 2:
        raise InsufficientDataError(
            f"measured_xy and reference_xy must both be (N, 2) arrays of the same shape, "
            f"got {measured_xy.shape} and {reference_xy.shape}"
        )
    n = measured_xy.shape[0]
    if n < _MIN_POINTS_FOR_AFFINE:
        raise InsufficientDataError(
            f"need at least {_MIN_POINTS_FOR_AFFINE} matched points to fit an affine transform, got {n}"
        )

    x, y = measured_xy[:, 0], measured_xy[:, 1]
    design = np.column_stack([x, y, np.ones_like(x)])
    params_x, *_ = np.linalg.lstsq(design, reference_xy[:, 0], rcond=None)
    params_y, *_ = np.linalg.lstsq(design, reference_xy[:, 1], rcond=None)

    predicted_x = design @ params_x
    predicted_y = design @ params_y
    residuals_x = reference_xy[:, 0] - predicted_x
    residuals_y = reference_xy[:, 1] - predicted_y
    residual_arcsec = np.hypot(residuals_x, residuals_y)

    return AffineAlignment(
        params=np.concatenate([params_x, params_y]),
        residuals_x=residuals_x,
        residuals_y=residuals_y,
        residual_arcsec=residual_arcsec,
        rms_residual_arcsec=float(np.sqrt(np.mean(residual_arcsec**2))),
    )
