from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from euclid_q1_vis_psf_astrometry_audit.exceptions import DataSchemaError
from euclid_q1_vis_psf_astrometry_audit.io import load_cutout
from conftest import SyntheticPointSource, build_synthetic_vis_cutout


def test_load_cutout_reads_synthetic_fixture(tmp_path):
    source = SyntheticPointSource(x=20.0, y=20.0, amplitude=500.0, fwhm=4.5, ellipticity=0.1, position_angle=0.0)
    hdul = build_synthetic_vis_cutout(sources=(source,))
    path = tmp_path / "synthetic.fits"
    hdul.writeto(path)

    product = load_cutout(path)

    assert product.science_array.shape == (41, 41)
    assert product.exposure_metadata["science_layout"] == "primary"
    assert product.exposure_metadata["uncertainty_source"].startswith("sigma-clipped")
    assert product.wcs.has_celestial


def test_load_cutout_missing_file_raises():
    with pytest.raises(DataSchemaError):
        load_cutout("does_not_exist.fits")


def test_load_cutout_no_science_data_raises(tmp_path):
    hdul = fits.HDUList([fits.PrimaryHDU()])
    path = tmp_path / "empty.fits"
    hdul.writeto(path)
    with pytest.raises(DataSchemaError):
        load_cutout(path)


def test_load_cutout_no_wcs_raises(tmp_path):
    hdul = fits.HDUList([fits.PrimaryHDU(data=np.ones((10, 10)))])
    path = tmp_path / "no_wcs.fits"
    hdul.writeto(path)
    with pytest.raises(DataSchemaError):
        load_cutout(path)


def test_load_cutout_all_nan_science_raises(tmp_path):
    from astropy.wcs import WCS

    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [5, 5]
    wcs.wcs.crval = [58.0, -51.0]
    wcs.wcs.cdelt = [-1 / 3600, 1 / 3600]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    header = wcs.to_header()
    data = np.full((10, 10), np.nan)
    hdul = fits.HDUList([fits.PrimaryHDU(data=data, header=header)])
    path = tmp_path / "all_nan.fits"
    hdul.writeto(path)
    with pytest.raises(DataSchemaError):
        load_cutout(path)


def test_load_cutout_uses_err_extension_when_present(tmp_path):
    from astropy.wcs import WCS

    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [5, 5]
    wcs.wcs.crval = [58.0, -51.0]
    wcs.wcs.cdelt = [-1 / 3600, 1 / 3600]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    header = wcs.to_header()
    science = np.ones((10, 10)) * 5.0
    err = np.ones((10, 10)) * 0.5
    hdul = fits.HDUList([fits.PrimaryHDU(data=science, header=header), fits.ImageHDU(data=err, name="ERR")])
    path = tmp_path / "with_err.fits"
    hdul.writeto(path)

    product = load_cutout(path)
    assert product.exposure_metadata["uncertainty_source"] == "ERR/RMS/UNCERTAINTY extension"
    assert np.allclose(product.uncertainty_array, 0.5)
