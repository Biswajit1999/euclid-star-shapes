from __future__ import annotations

import json

import pytest

from euclid_q1_vis_psf_astrometry_audit.exceptions import DataSchemaError
from euclid_q1_vis_psf_astrometry_audit.results_io import Metric, validate_summary, write_summary


def test_write_summary_roundtrip(tmp_path):
    metrics = [Metric(name="median_fwhm", estimate=4.5, units="arcsec", sample_size=10, uncertainty_low=4.2, uncertainty_high=4.8)]
    path = tmp_path / "summary.json"
    payload = write_summary(path, "test-project", "synthetic_demo", metrics, {"git_commit": "abc"}, [])

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == payload
    assert loaded["metrics"][0]["name"] == "median_fwhm"


def test_validate_summary_rejects_missing_top_key():
    with pytest.raises(DataSchemaError):
        validate_summary({"project": "x", "data_kind": "y", "metrics": [], "warnings": []})


def test_validate_summary_rejects_metric_missing_required_field():
    payload = {
        "project": "x",
        "data_kind": "y",
        "metrics": [{"name": "m", "estimate": 1.0}],
        "provenance": {},
        "warnings": [],
    }
    with pytest.raises(DataSchemaError):
        validate_summary(payload)
