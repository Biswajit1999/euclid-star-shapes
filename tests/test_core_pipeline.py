from __future__ import annotations

import csv

import numpy as np
import pytest

from euclid_q1_vis_psf_astrometry_audit.config import load_config
from euclid_q1_vis_psf_astrometry_audit.core import SourceCatalogEntry, read_source_catalog, run_pipeline
from euclid_q1_vis_psf_astrometry_audit.exceptions import InsufficientDataError
from conftest import SyntheticPointSource, build_synthetic_vis_cutout


def test_read_source_catalog_roundtrip(tmp_path):
    path = tmp_path / "source_catalog.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["object_id", "product_id", "ra", "dec", "fwhm_catalog", "ellipticity_catalog",
                        "mag_stargal_sep", "point_like_prob", "gaia_id", "tileid"],
        )
        writer.writeheader()
        writer.writerow({"object_id": 1, "product_id": "p1", "ra": 58.3, "dec": -51.2, "fwhm_catalog": 0.45,
                          "ellipticity_catalog": 0.1, "mag_stargal_sep": 20.0, "point_like_prob": 0.9,
                          "gaia_id": 100, "tileid": 102018211})

    entries = read_source_catalog(path)
    assert len(entries) == 1
    assert entries[0].object_id == 1
    assert entries[0].ra == pytest.approx(58.3)


def test_read_source_catalog_missing_file_raises():
    with pytest.raises(InsufficientDataError):
        read_source_catalog("does_not_exist.csv")


def _make_entry(i: int, raw_dir, ra0, dec0, fwhm, ellip, point_like_prob, mag) -> SourceCatalogEntry:
    source = SyntheticPointSource(x=20.0, y=20.0, amplitude=600.0, fwhm=fwhm, ellipticity=ellip, position_angle=0.2)
    hdul = build_synthetic_vis_cutout(seed=200 + i, ra0=ra0, dec0=dec0, sources=(source,))
    product_id = f"euclid_q1_vis_test_{i}"
    hdul.writeto(raw_dir / f"{product_id}.fits")
    return SourceCatalogEntry(
        object_id=i, product_id=product_id, ra=ra0, dec=dec0, fwhm_catalog=fwhm * 0.1,
        ellipticity_catalog=ellip, mag_stargal_sep=mag, point_like_prob=point_like_prob,
        gaia_id=1000 + i, tileid=102018211,
    )


def test_run_pipeline_end_to_end_on_synthetic_cutouts(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    config = load_config("config/analysis.yml")

    entries = []
    gaia_ra, gaia_dec, gaia_id = [], [], []
    for i in range(6):
        ra0 = 58.30 + i * 0.002
        dec0 = -51.25 + i * 0.001
        entry = _make_entry(i, raw_dir, ra0, dec0, fwhm=4.0 + 0.1 * i, ellip=0.1, point_like_prob=0.9, mag=19.0 + i)
        entries.append(entry)
        gaia_ra.append(ra0 + 0.05 / 3600 / np.cos(np.radians(dec0)))
        gaia_dec.append(dec0)
        gaia_id.append(1000 + i)

    result = run_pipeline(entries, raw_dir, config, np.array(gaia_ra), np.array(gaia_dec), np.array(gaia_id))

    assert len(result.measurements) == 6
    assert result.gaia_n_matched == 6
    assert result.gaia_rms_residual_arcsec is not None
    assert result.gaia_rms_residual_arcsec < 0.01
    assert any("minimum_sample_size" in w for w in result.warnings)


def test_run_pipeline_raises_when_no_entries(tmp_path):
    config = load_config("config/analysis.yml")
    with pytest.raises(InsufficientDataError):
        run_pipeline([], tmp_path, config, np.array([1.0]), np.array([1.0]), np.array([1]))


def test_run_pipeline_warns_not_crashes_on_missing_cutout_file(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    config = load_config("config/analysis.yml")
    entries = [
        SourceCatalogEntry(object_id=1, product_id="missing_product", ra=58.3, dec=-51.25, fwhm_catalog=0.4,
                            ellipticity_catalog=0.1, mag_stargal_sep=20.0, point_like_prob=0.9, gaia_id=1, tileid=102018211)
    ]
    with pytest.raises(InsufficientDataError):
        # all sources fail (missing file) -> no usable measurements -> raises
        run_pipeline(entries, raw_dir, config, np.array([58.3]), np.array([-51.25]), np.array([1]))
