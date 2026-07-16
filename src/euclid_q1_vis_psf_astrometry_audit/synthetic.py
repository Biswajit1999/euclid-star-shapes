"""Synthetic Euclid-VIS-like cutout generation, clearly labelled and never real data.

Shared by the test suite (injection-recovery validation) and
`scripts/make_figures.py --demo` / `scripts/run_analysis.py --demo`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

PIXEL_SCALE_DEG = 0.1 / 3600.0  # Euclid VIS pixel scale ~0.1 arcsec/pixel (verified: arXiv:2503.15303)


@dataclass(frozen=True)
class SyntheticPointSource:
    x: float
    y: float
    amplitude: float
    fwhm: float  # pixels
    ellipticity: float = 0.0
    position_angle: float = 0.0  # radians


def _gaussian_2d(yy, xx, x0, y0, amplitude, sigma_x, sigma_y, theta):
    ct, st = np.cos(theta), np.sin(theta)
    xr = ct * (xx - x0) + st * (yy - y0)
    yr = -st * (xx - x0) + ct * (yy - y0)
    return amplitude * np.exp(-0.5 * ((xr / sigma_x) ** 2 + (yr / sigma_y) ** 2))


def fwhm_ellipticity_to_sigmas(fwhm: float, ellipticity: float) -> tuple[float, float]:
    """Convert a mean FWHM + ellipticity (1 - b/a) into (sigma_x, sigma_y)."""
    sigma_mean = fwhm / 2.3548200450309493
    axis_ratio = max(1.0 - ellipticity, 0.05)
    sigma_major = sigma_mean / np.sqrt(axis_ratio)
    sigma_minor = sigma_major * axis_ratio
    return sigma_major, sigma_minor


def build_synthetic_vis_cutout(
    *,
    seed: int = 20260713,
    size: int = 41,
    ra0: float = 58.365,
    dec0: float = -51.250,
    background: float = 5.0,
    read_noise: float = 1.0,
    sources: tuple[SyntheticPointSource, ...] = (
        SyntheticPointSource(x=20.0, y=20.0, amplitude=500.0, fwhm=4.5, ellipticity=0.1, position_angle=0.4),
    ),
) -> fits.HDUList:
    """Build a small, labelled-synthetic Euclid-VIS-like cutout with a real WCS.

    Single science extension, matching the expected structure of a real Euclid
    MER VIS mosaic cutout (a drizzled, calibrated single-band image), as
    documented in the verified VIS processing paper (arXiv:2503.15303).
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size]
    science = rng.normal(loc=background, scale=read_noise, size=(size, size)).astype(np.float32)

    for src in sources:
        sigma_x, sigma_y = fwhm_ellipticity_to_sigmas(src.fwhm, src.ellipticity)
        science += _gaussian_2d(yy, xx, src.x, src.y, src.amplitude, sigma_x, sigma_y, src.position_angle)

    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [size / 2, size / 2]
    wcs.wcs.crval = [ra0, dec0]
    wcs.wcs.cdelt = [-PIXEL_SCALE_DEG, PIXEL_SCALE_DEG]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]

    header = wcs.to_header()
    header["INSTRUME"] = "VIS"
    header["TELESCOP"] = "EUCLID"
    header["BUNIT"] = "ELECTRONS/S"

    return fits.HDUList([fits.PrimaryHDU(data=science, header=header)])
