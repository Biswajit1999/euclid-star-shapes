"""Shared synthetic-data fixtures for tests.

The synthetic-data model lives in
`euclid_q1_vis_psf_astrometry_audit.synthetic` (shared with
`scripts/make_figures.py --demo`); this module only adds the pytest fixture
layer on top.
"""
from __future__ import annotations

import pytest

from euclid_q1_vis_psf_astrometry_audit.synthetic import (
    SyntheticPointSource,
    build_synthetic_vis_cutout,
    fwhm_ellipticity_to_sigmas,
)

__all__ = [
    "SyntheticPointSource",
    "build_synthetic_vis_cutout",
    "fwhm_ellipticity_to_sigmas",
    "synthetic_cutout_with_known_source",
]


@pytest.fixture
def synthetic_cutout_with_known_source(tmp_path):
    """A (path, truth) pair: a synthetic VIS cutout with one known point source."""
    truth_source = SyntheticPointSource(x=20.0, y=20.0, amplitude=800.0, fwhm=4.5, ellipticity=0.15, position_angle=0.3)
    hdul = build_synthetic_vis_cutout(sources=(truth_source,))
    path = tmp_path / "synthetic_vis_cutout.fits"
    hdul.writeto(path)
    return path, truth_source
