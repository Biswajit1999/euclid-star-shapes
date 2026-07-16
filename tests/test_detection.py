from __future__ import annotations

import pytest

from euclid_q1_vis_psf_astrometry_audit.exceptions import InsufficientDataError
from euclid_q1_vis_psf_astrometry_audit.detection import detect_sources, refine_centroid, sky_to_pixel
from conftest import SyntheticPointSource, build_synthetic_vis_cutout


def test_sky_to_pixel_roundtrip():
    hdul = build_synthetic_vis_cutout(ra0=58.365, dec0=-51.25)
    from astropy.wcs import WCS

    wcs = WCS(hdul[0].header)
    x, y = sky_to_pixel(wcs, 58.365, -51.25)
    assert abs(x - 20) < 1.0
    assert abs(y - 20) < 1.0


def test_refine_centroid_recovers_known_source():
    source = SyntheticPointSource(x=20.3, y=19.7, amplitude=800.0, fwhm=4.5, ellipticity=0.1, position_angle=0.0)
    hdul = build_synthetic_vis_cutout(sources=(source,))
    centroid = refine_centroid(hdul[0].data, x_guess=20.0, y_guess=20.0)
    assert abs(centroid.x - source.x) < 0.5
    assert abs(centroid.y - source.y) < 0.5


def test_refine_centroid_rejects_guess_too_close_to_edge():
    hdul = build_synthetic_vis_cutout()
    with pytest.raises(InsufficientDataError):
        refine_centroid(hdul[0].data, x_guess=1.0, y_guess=1.0, box_size=11)


def test_refine_centroid_rejects_no_signal_region():
    hdul = build_synthetic_vis_cutout(sources=())
    with pytest.raises(InsufficientDataError):
        refine_centroid(hdul[0].data, x_guess=5.0, y_guess=35.0, box_size=7)


def test_detect_sources_finds_injected_source():
    source = SyntheticPointSource(x=20.0, y=20.0, amplitude=800.0, fwhm=4.5, ellipticity=0.1, position_angle=0.0)
    hdul = build_synthetic_vis_cutout(sources=(source,))
    detected = detect_sources(hdul[0].data)
    assert len(detected) >= 1
    closest = min(detected, key=lambda d: (d.x - source.x) ** 2 + (d.y - source.y) ** 2)
    assert abs(closest.x - source.x) < 1.5
    assert abs(closest.y - source.y) < 1.5


def test_detect_sources_rejects_zero_std_background():
    import numpy as np

    with pytest.raises(InsufficientDataError):
        detect_sources(np.zeros((30, 30)))
