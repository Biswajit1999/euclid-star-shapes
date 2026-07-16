from __future__ import annotations

import numpy as np
from astropy.io import fits

from euclid_q1_vis_psf_astrometry_audit.config import load_config
from euclid_q1_vis_psf_astrometry_audit.provenance import (
    ManifestRow,
    append_manifest_row,
    get_git_commit,
    read_manifest,
    sha256_file,
)


def test_load_config_reads_real_project_config():
    cfg = load_config("config/analysis.yml")
    assert cfg.project.repository == "euclid-q1-vis-psf-astrometry-audit"
    assert cfg.execution.seed == 20260713
    assert cfg.validation.bootstrap_resamples == 1000


def test_manifest_roundtrip(tmp_path):
    manifest_path = tmp_path / "manifest.csv"
    row = ManifestRow(
        product_id="euclid_q1_vis_12345",
        source="IRSA/Euclid-Q1",
        source_url="https://irsa.ipac.caltech.edu",
        retrieved_utc="2026-07-13T00:00:00+00:00",
        sha256="0" * 64,
        file_size_bytes=1800000,
        selection_reason="unit test",
        licence_or_terms="Euclid Q1 public data release",
    )
    append_manifest_row(manifest_path, row)
    rows = read_manifest(manifest_path)
    assert len(rows) == 1
    assert rows[0]["product_id"] == "euclid_q1_vis_12345"


def test_sha256_file_matches_known_content(tmp_path):
    path = tmp_path / "sample.bin"
    path.write_bytes(b"euclid-q1-vis-psf-astrometry-audit")
    digest = sha256_file(path)
    assert len(digest) == 64
    assert digest == sha256_file(path)


def test_get_git_commit_never_raises(tmp_path):
    result = get_git_commit(tmp_path)
    assert isinstance(result, str)
    assert result != ""


def test_synthetic_fixture_has_injected_source(synthetic_cutout_with_known_source):
    path, truth = synthetic_cutout_with_known_source
    with fits.open(path) as hdul:
        data = hdul[0].data
    peak_region = data[15:26, 15:26]
    background_region = data[:5, :5]
    assert peak_region.max() > np.median(background_region) + 5 * np.std(background_region)
