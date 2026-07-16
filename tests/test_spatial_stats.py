from __future__ import annotations

import numpy as np
import pytest

from euclid_q1_vis_psf_astrometry_audit.exceptions import InsufficientDataError
from euclid_q1_vis_psf_astrometry_audit.spatial_stats import apply_quality_cuts, bin_scalar_statistic


def test_bin_scalar_statistic_computes_mean_per_bin():
    keys = np.array([1.0, 1.5, 5.0, 5.5])
    values = np.array([10.0, 12.0, 100.0, 104.0])
    result = bin_scalar_statistic(keys, values, edges=np.array([0.0, 3.0, 6.0]), minimum_sample_size=1)
    assert len(result.bins) == 2
    assert result.bins[0].mean == pytest.approx(11.0)
    assert result.bins[1].mean == pytest.approx(102.0)
    assert not result.bins[0].underpopulated


def test_bin_scalar_statistic_flags_underpopulated_bins():
    keys = np.array([1.0, 2.0, 3.0])
    values = np.array([1.0, 2.0, 3.0])
    result = bin_scalar_statistic(keys, values, edges=np.array([0.0, 5.0]), minimum_sample_size=10)
    assert result.bins[0].underpopulated
    assert len(result.warnings) == 1


def test_bin_scalar_statistic_rejects_mismatched_shapes():
    with pytest.raises(InsufficientDataError):
        bin_scalar_statistic(np.array([1.0, 2.0]), np.array([1.0]), edges=np.array([0.0, 3.0]), minimum_sample_size=1)


def test_apply_quality_cuts_strict_and_permissive():
    point_like_prob = np.array([0.99, 0.98, 0.85, 0.82, 0.5])
    fwhm = np.array([4.0, 4.2, 5.0, 5.2, 8.0])
    ellipticity = np.array([0.1, 0.12, 0.2, 0.22, 0.5])

    strict, permissive = apply_quality_cuts(point_like_prob, fwhm, ellipticity, strict_threshold=0.95, permissive_threshold=0.8)

    assert strict.n_sources == 2
    assert permissive.n_sources == 4
    assert strict.fwhm_median == pytest.approx(4.1)


def test_apply_quality_cuts_raises_when_strict_cut_empty():
    point_like_prob = np.array([0.5, 0.6])
    fwhm = np.array([4.0, 4.2])
    ellipticity = np.array([0.1, 0.1])
    with pytest.raises(InsufficientDataError):
        apply_quality_cuts(point_like_prob, fwhm, ellipticity, strict_threshold=0.95, permissive_threshold=0.8)
