"""Synthetic injection-recovery validation gate for PSF fitting.

Per docs/VALIDATION_CONTRACT.md and the docs/VALIDATION_CONTRACT.md stop condition: if
this fails, the pipeline must not be used to interpret real cutouts as
validated. Thresholds were calibrated empirically across 15 independent
noise realizations at two signal levels (see IMPLEMENTATION_PLAN.md); the
observed worst case was <0.1% FWHM error and <0.002 ellipticity error, so
the thresholds below carry generous margin above that.
"""
from __future__ import annotations

import numpy as np
import pytest

from euclid_q1_vis_psf_astrometry_audit.exceptions import ConvergenceError, InsufficientDataError
from euclid_q1_vis_psf_astrometry_audit.psf_metrics import (
    compare_gaussian_moffat,
    fit_gaussian,
    fit_moffat,
)
from conftest import SyntheticPointSource, build_synthetic_vis_cutout

FWHM_TOLERANCE = 0.10
ELLIPTICITY_TOLERANCE = 0.05


def test_synthetic_gaussian_injection_recovery():
    truth_fwhm, truth_ellip = 4.5, 0.15
    source = SyntheticPointSource(x=20.0, y=20.0, amplitude=800.0, fwhm=truth_fwhm, ellipticity=truth_ellip, position_angle=0.3)
    hdul = build_synthetic_vis_cutout(sources=(source,))

    fit = fit_gaussian(hdul[0].data)

    fwhm_error = abs(fit.fwhm - truth_fwhm) / truth_fwhm
    ellip_error = abs(fit.ellipticity - truth_ellip)
    assert fwhm_error < FWHM_TOLERANCE, f"FWHM recovery error {fwhm_error:.1%} too large"
    assert ellip_error < ELLIPTICITY_TOLERANCE, f"ellipticity recovery error {ellip_error:.3f} too large"
    assert fit.convergence.converged


def test_model_comparison_prefers_true_gaussian_model():
    source = SyntheticPointSource(x=20.0, y=20.0, amplitude=800.0, fwhm=4.5, ellipticity=0.15, position_angle=0.3)
    hdul = build_synthetic_vis_cutout(sources=(source,))
    comparison = compare_gaussian_moffat(hdul[0].data)
    assert comparison.better_model == "gaussian"
    assert comparison.gaussian.convergence.reduced_chi_square <= comparison.moffat.convergence.reduced_chi_square


def test_null_control_flat_background_amplitude_near_zero():
    """Negative control: a source-free background should fit near-zero amplitude."""
    hdul = build_synthetic_vis_cutout(sources=())
    box = hdul[0].data
    fit = fit_gaussian(box)
    background_std = float(np.std(box))
    assert fit.amplitude < 10 * background_std


def test_fit_gaussian_rejects_tiny_box():
    with pytest.raises(InsufficientDataError):
        fit_gaussian(np.ones((2, 2)))


def test_fit_moffat_rejects_tiny_box():
    with pytest.raises(InsufficientDataError):
        fit_moffat(np.ones((2, 2)))


def test_fit_gaussian_raises_convergence_error_on_pathological_input():
    box = np.full((21, 21), np.nan)
    with pytest.raises(ConvergenceError):
        fit_gaussian(box)
