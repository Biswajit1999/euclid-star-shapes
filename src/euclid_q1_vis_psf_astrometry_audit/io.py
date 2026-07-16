"""FITS ingestion for Euclid Q1 VIS mosaic cutouts.

Maps archive-specific FITS structure onto the logical fields documented in
data/INPUT_SCHEMA.md: product_id, science_array, uncertainty_array, dq_mask,
wcs_or_detector_geometry, exposure_metadata, calibration_reference_ids.

Parsing is deliberately defensive about extension layout: unlike ACS/WFC
FLT/FLC files (a fixed SCI/ERR/DQ triplet per chip), a real downloaded Euclid
MER VIS cutout's exact extension structure was not verified against a live
file before this was written (that download requires separate operator
authorization; see IMPLEMENTATION_PLAN.md §2/§7). `load_cutout` therefore
accepts either a bare PrimaryHDU-with-data layout or a named 'SCI' extension,
and reports which one it found in `exposure_metadata`, so a real file can be
sanity-checked against this assumption without a silent mismatch.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.wcs import WCS

from euclid_q1_vis_psf_astrometry_audit.exceptions import DataSchemaError


@dataclass(frozen=True)
class CutoutProduct:
    product_id: str
    science_array: np.ndarray
    uncertainty_array: np.ndarray
    dq_mask: np.ndarray | None
    wcs: WCS
    exposure_metadata: dict[str, Any]
    calibration_reference_ids: dict[str, str]


def load_cutout(path: str | Path) -> CutoutProduct:
    """Load a Euclid VIS cutout FITS file.

    Raises DataSchemaError for a missing file, missing science data, or a
    missing/unparseable WCS, per docs/ERROR_HANDLING.md.
    """
    fits_path = Path(path)
    if not fits_path.is_file():
        raise DataSchemaError(f"FITS product not found: {fits_path}")

    with fits.open(fits_path) as hdul:
        science_hdu = None
        layout = None
        if hdul[0].data is not None:
            science_hdu = hdul[0]
            layout = "primary"
        else:
            for name in ("SCI", "SCIENCE", "DATA"):
                if name in hdul and hdul[name].data is not None:
                    science_hdu = hdul[name]
                    layout = f"extension:{name}"
                    break
        if science_hdu is None:
            raise DataSchemaError(
                f"{fits_path.name}: no science data found in PrimaryHDU or a "
                "SCI/SCIENCE/DATA extension"
            )

        science = np.asarray(science_hdu.data, dtype=float)
        if not np.any(np.isfinite(science)):
            raise DataSchemaError(f"{fits_path.name}: science array is entirely non-finite")

        try:
            wcs = WCS(science_hdu.header)
        except Exception as exc:  # noqa: BLE001
            raise DataSchemaError(f"{fits_path.name}: could not parse WCS: {exc}") from exc
        if wcs.naxis < 2 or not wcs.has_celestial:
            raise DataSchemaError(f"{fits_path.name}: header has no usable celestial WCS")

        uncertainty = None
        for name in ("ERR", "RMS", "UNCERTAINTY"):
            if name in hdul and hdul[name].data is not None:
                uncertainty = np.asarray(hdul[name].data, dtype=float)
                break
        if uncertainty is None:
            # No formal error map shipped with this cutout: fall back to a
            # sigma-clipped estimate of the local background noise, which is
            # a defensible per-pixel uncertainty proxy for a background-
            # dominated cutout but not a substitute for a real error map.
            _, _, background_std = sigma_clipped_stats(science, sigma=3.0, maxiters=5)
            uncertainty = np.full_like(science, background_std)

        dq_mask = None
        for name in ("DQ", "FLAG", "MASK"):
            if name in hdul and hdul[name].data is not None:
                dq_mask = np.asarray(hdul[name].data, dtype=int)
                break

        primary_header = hdul[0].header
        exposure_metadata: dict[str, Any] = {
            "instrument": str(primary_header.get("INSTRUME", "")),
            "telescope": str(primary_header.get("TELESCOP", "")),
            "bunit": str(science_hdu.header.get("BUNIT", "")),
            "science_layout": layout,
            "uncertainty_source": "ERR/RMS/UNCERTAINTY extension" if any(
                name in hdul for name in ("ERR", "RMS", "UNCERTAINTY")
            ) else "sigma-clipped background estimate (no formal error map found)",
        }
        calibration_reference_ids = {
            key: str(primary_header[key]) for key in ("PIPELINE", "CALVERS", "PROCVERS") if key in primary_header
        }
        product_id = fits_path.stem

    return CutoutProduct(
        product_id=product_id,
        science_array=science,
        uncertainty_array=uncertainty,
        dq_mask=dq_mask,
        wcs=wcs,
        exposure_metadata=exposure_metadata,
        calibration_reference_ids=calibration_reference_ids,
    )
