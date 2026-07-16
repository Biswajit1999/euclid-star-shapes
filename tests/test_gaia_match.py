from __future__ import annotations

import numpy as np
import pytest

from euclid_q1_vis_psf_astrometry_audit.exceptions import InsufficientDataError
from euclid_q1_vis_psf_astrometry_audit.gaia_match import (
    fit_affine_alignment,
    match_to_gaia,
    sky_to_tangent_plane,
)


def test_match_to_gaia_finds_close_matches():
    measured_ra = np.array([58.30, 58.31, 58.32])
    measured_dec = np.array([-51.25, -51.24, -51.23])
    gaia_ra = measured_ra + 0.05 / 3600
    gaia_dec = measured_dec.copy()
    gaia_id = np.array([1, 2, 3])

    matches = match_to_gaia(measured_ra, measured_dec, gaia_ra, gaia_dec, gaia_id, match_radius_arcsec=1.0)
    assert all(m is not None for m in matches)
    assert [m.gaia_source_id for m in matches] == [1, 2, 3]


def test_match_to_gaia_reports_unmatched_not_silently_dropped():
    measured_ra = np.array([58.30, 100.0])  # second point is far from any Gaia source
    measured_dec = np.array([-51.25, 0.0])
    gaia_ra = np.array([58.30 + 0.05 / 3600])
    gaia_dec = np.array([-51.25])
    gaia_id = np.array([1])

    matches = match_to_gaia(measured_ra, measured_dec, gaia_ra, gaia_dec, gaia_id, match_radius_arcsec=1.0)
    assert matches[0] is not None
    assert matches[1] is None


def test_match_to_gaia_rejects_empty_reference_catalog():
    with pytest.raises(InsufficientDataError):
        match_to_gaia(np.array([1.0]), np.array([1.0]), np.array([]), np.array([]), np.array([]))


def test_fit_affine_alignment_recovers_known_translation():
    rng = np.random.default_rng(7)
    n = 10
    ref_xy = rng.uniform(-5, 5, size=(n, 2))
    translation = np.array([0.2, -0.3])
    measured_xy = ref_xy - translation

    result = fit_affine_alignment(measured_xy, ref_xy)
    assert result.rms_residual_arcsec < 1e-8
    assert np.isclose(result.params[2], translation[0], atol=1e-8)
    assert np.isclose(result.params[5], translation[1], atol=1e-8)


def test_fit_affine_alignment_rejects_too_few_points():
    with pytest.raises(InsufficientDataError):
        fit_affine_alignment(np.array([[0.0, 0.0], [1.0, 1.0]]), np.array([[0.0, 0.0], [1.0, 1.0]]))


def test_fit_affine_alignment_rejects_mismatched_shapes():
    with pytest.raises(InsufficientDataError):
        fit_affine_alignment(np.zeros((3, 2)), np.zeros((4, 2)))


def test_sky_to_tangent_plane_zero_at_center():
    dx, dy = sky_to_tangent_plane(np.array([58.365]), np.array([-51.25]), 58.365, -51.25)
    assert np.allclose(dx, 0.0)
    assert np.allclose(dy, 0.0)
