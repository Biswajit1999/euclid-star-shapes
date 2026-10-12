import pandas as pd
import pytest

from euclid_q1_vis_psf_astrometry_audit.catalog_robustness import (
    bootstrap_median,
    jackknife_influence,
    magnitude_trend,
    selection_sensitivity,
)


def test_bootstrap_reproducibility_and_interval():
    first = bootstrap_median([1, 2, 3, 4], draws=200, seed=2)
    assert first == bootstrap_median([1, 2, 3, 4], draws=200, seed=2)
    assert first["ci95_low"] <= first["median"] <= first["ci95_high"]


def test_jackknife_and_selection_conserve_definitions():
    assert len(jackknife_influence([1, 2, 3])) == 3
    data = pd.DataFrame(
        {
            "point_like_prob": [0.85, 0.95, 0.995],
            "fwhm_catalog": [1.0, 2.0, 3.0],
            "ellipticity_catalog": [0.1, 0.2, 0.3],
        }
    )
    result = selection_sensitivity(data, thresholds=(0.8, 0.99))
    assert result.n.tolist() == [3, 1]
    assert result.median_fwhm_catalog_px.iloc[-1] == pytest.approx(3)


def test_magnitude_trend_does_not_reorder_source_frame():
    data = pd.DataFrame({"mag_stargal_sep": [3.0, 1.0, 2.0], "fwhm_catalog": [1.0, 3.0, 2.0]})
    before = data.copy()
    result = magnitude_trend(data, "fwhm_catalog")
    pd.testing.assert_frame_equal(data, before)
    assert result["spearman_r"] == pytest.approx(-1)
