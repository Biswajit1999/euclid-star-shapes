"""Elliptical Gaussian and Moffat PSF model fitting and comparison.

FWHM convention: geometric mean of the major/minor-axis FWHMs
(`2.3548 * sqrt(sigma_major * sigma_minor)` for Gaussian, the equivalent
Moffat-alpha form for Moffat), matching common SExtractor-style scalar-FWHM
reporting. Ellipticity convention: `1 - minor/major`, consistent with
`synthetic.py`'s injection convention so injection-recovery tests are
self-consistent.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import curve_fit

from euclid_q1_vis_psf_astrometry_audit.exceptions import ConvergenceError, InsufficientDataError
from euclid_q1_vis_psf_astrometry_audit.uncertainty import FitConvergence, check_fit_convergence

GAUSSIAN_FWHM_FACTOR = 2.3548200450309493  # 2*sqrt(2*ln2)
_MIN_BOX_PIXELS = 20


def elliptical_gaussian_2d(coords, amplitude, x0, y0, sigma_x, sigma_y, theta, offset):
    x, y = coords
    ct, st = np.cos(theta), np.sin(theta)
    xr = ct * (x - x0) + st * (y - y0)
    yr = -st * (x - x0) + ct * (y - y0)
    return offset + amplitude * np.exp(-0.5 * ((xr / sigma_x) ** 2 + (yr / sigma_y) ** 2))


def elliptical_moffat_2d(coords, amplitude, x0, y0, alpha_x, alpha_y, beta, theta, offset):
    x, y = coords
    ct, st = np.cos(theta), np.sin(theta)
    xr = ct * (x - x0) + st * (y - y0)
    yr = -st * (x - x0) + ct * (y - y0)
    return offset + amplitude * (1.0 + (xr / alpha_x) ** 2 + (yr / alpha_y) ** 2) ** (-beta)


def _pixel_grid(shape: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
    ny, nx = shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    return xx.ravel().astype(float), yy.ravel().astype(float)


@dataclass(frozen=True)
class PSFFitResult:
    model: str
    amplitude: float
    x0: float
    y0: float
    fwhm: float
    ellipticity: float
    position_angle: float
    offset: float
    convergence: FitConvergence
    extra: dict = field(default_factory=dict)


def fit_gaussian(box: np.ndarray) -> PSFFitResult:
    """Fit an elliptical 2-D Gaussian to a small PSF cutout box."""
    if box.size < _MIN_BOX_PIXELS:
        raise InsufficientDataError(f"box too small to fit a 2-D Gaussian ({box.shape})")
    if not np.all(np.isfinite(box)):
        raise ConvergenceError("PSF fitting box contains non-finite values; refusing to fit")
    ny, nx = box.shape
    xx, yy = _pixel_grid(box.shape)
    z = box.ravel().astype(float)

    amplitude_guess = float(z.max() - np.median(z))
    p0 = [max(amplitude_guess, 1.0), nx / 2, ny / 2, 2.0, 2.0, 0.0, float(np.median(z))]
    bounds = (
        [0.0, 0.0, 0.0, 0.3, 0.3, -np.pi, -np.inf],
        [np.inf, nx, ny, nx, ny, np.pi, np.inf],
    )
    try:
        popt, pcov = curve_fit(elliptical_gaussian_2d, (xx, yy), z, p0=p0, bounds=bounds, maxfev=10000)
    except RuntimeError as exc:
        raise ConvergenceError(f"Gaussian PSF fit failed to converge: {exc}") from exc

    residuals = z - elliptical_gaussian_2d((xx, yy), *popt)
    dof = z.size - len(popt)
    convergence = check_fit_convergence(pcov, residuals=residuals, dof=dof, max_condition_number=1e14)

    amplitude, x0, y0, sigma_x, sigma_y, theta, offset = popt
    sigma_major, sigma_minor = max(sigma_x, sigma_y), min(sigma_x, sigma_y)
    fwhm = GAUSSIAN_FWHM_FACTOR * np.sqrt(sigma_major * sigma_minor)
    ellipticity = 1 - sigma_minor / sigma_major

    return PSFFitResult(
        model="gaussian", amplitude=float(amplitude), x0=float(x0), y0=float(y0),
        fwhm=float(fwhm), ellipticity=float(ellipticity), position_angle=float(theta),
        offset=float(offset), convergence=convergence,
    )


def fit_moffat(box: np.ndarray) -> PSFFitResult:
    """Fit an elliptical 2-D Moffat profile to a small PSF cutout box."""
    if box.size < _MIN_BOX_PIXELS:
        raise InsufficientDataError(f"box too small to fit a 2-D Moffat ({box.shape})")
    if not np.all(np.isfinite(box)):
        raise ConvergenceError("PSF fitting box contains non-finite values; refusing to fit")
    ny, nx = box.shape
    xx, yy = _pixel_grid(box.shape)
    z = box.ravel().astype(float)

    amplitude_guess = float(z.max() - np.median(z))
    p0 = [max(amplitude_guess, 1.0), nx / 2, ny / 2, 2.0, 2.0, 3.0, 0.0, float(np.median(z))]
    bounds = (
        [0.0, 0.0, 0.0, 0.2, 0.2, 1.1, -np.pi, -np.inf],
        [np.inf, nx, ny, nx, ny, 20.0, np.pi, np.inf],
    )
    try:
        popt, pcov = curve_fit(elliptical_moffat_2d, (xx, yy), z, p0=p0, bounds=bounds, maxfev=10000)
    except RuntimeError as exc:
        raise ConvergenceError(f"Moffat PSF fit failed to converge: {exc}") from exc

    residuals = z - elliptical_moffat_2d((xx, yy), *popt)
    dof = z.size - len(popt)
    convergence = check_fit_convergence(pcov, residuals=residuals, dof=dof, max_condition_number=1e14)

    amplitude, x0, y0, alpha_x, alpha_y, beta, theta, offset = popt
    alpha_major, alpha_minor = max(alpha_x, alpha_y), min(alpha_x, alpha_y)
    fwhm_factor = 2.0 * np.sqrt(2.0 ** (1.0 / beta) - 1.0)
    fwhm = fwhm_factor * np.sqrt(alpha_major * alpha_minor)
    ellipticity = 1 - alpha_minor / alpha_major

    return PSFFitResult(
        model="moffat", amplitude=float(amplitude), x0=float(x0), y0=float(y0),
        fwhm=float(fwhm), ellipticity=float(ellipticity), position_angle=float(theta),
        offset=float(offset), convergence=convergence, extra={"beta": float(beta)},
    )


@dataclass(frozen=True)
class ModelComparison:
    gaussian: PSFFitResult
    moffat: PSFFitResult
    better_model: str


def compare_gaussian_moffat(box: np.ndarray) -> ModelComparison:
    """Fit both models and report which has the lower reduced chi-square."""
    gaussian = fit_gaussian(box)
    moffat = fit_moffat(box)
    g_chi2 = gaussian.convergence.reduced_chi_square
    m_chi2 = moffat.convergence.reduced_chi_square
    better = "gaussian" if (g_chi2 is not None and m_chi2 is not None and g_chi2 <= m_chi2) else "moffat"
    return ModelComparison(gaussian=gaussian, moffat=moffat, better_model=better)
