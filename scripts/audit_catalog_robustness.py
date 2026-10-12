"""Generate real-catalogue uncertainty and sensitivity products."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import scienceplots  # noqa: F401

from euclid_q1_vis_psf_astrometry_audit.catalog_robustness import (
    bootstrap_median,
    jackknife_influence,
    magnitude_trend,
    selection_sensitivity,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    data = pd.read_csv(ROOT / "data/source_catalog.csv")
    fwhm = bootstrap_median(data.fwhm_catalog)
    ellipticity = bootstrap_median(data.ellipticity_catalog)
    trends = {
        "fwhm": magnitude_trend(data, "fwhm_catalog"),
        "ellipticity": magnitude_trend(data, "ellipticity_catalog"),
    }
    sensitivity = selection_sensitivity(data)
    influence = jackknife_influence(data.fwhm_catalog)
    influence["object_id"] = data.object_id
    out = ROOT / "results/catalog-robustness"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps(
            {
                "data_kind": "real Euclid Q1 catalogue measurements",
                "fwhm_bootstrap": fwhm,
                "ellipticity_bootstrap": ellipticity,
                "magnitude_trends": trends,
                "limitations": (
                    "Only 15 deterministically selected objects in two adjacent tiles are "
                    "available. Bootstrap draws quantify resampling variability of this sample, "
                    "not survey-scale uncertainty. Catalogue shapes are official measurements, "
                    "not the repository's image-domain remeasurements or a weak-lensing PSF model."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    sensitivity.to_csv(out / "selection_sensitivity.csv", index=False)
    influence.to_csv(out / "fwhm_jackknife.csv", index=False)

    with plt.style.context(["science", "no-latex", "bright"]):
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), constrained_layout=True)
        axes[0].scatter(
            data.mag_stargal_sep, data.fwhm_catalog, s=48, c=data.point_like_prob, cmap="viridis"
        )
        axes[0].set(
            xlabel="Catalogue magnitude",
            ylabel="Catalogue FWHM [px]",
            title="(a) Magnitude response",
        )
        axes[0].invert_xaxis()
        axes[1].stem(influence.row_index, influence.influence, basefmt=" ")
        axes[1].axhline(0, color="0.4", lw=1)
        axes[1].set(
            xlabel="Deleted catalogue row",
            ylabel="Median FWHM change [px]",
            title="(b) Jackknife influence",
        )
        axes[2].plot(
            sensitivity.point_like_probability_min,
            sensitivity.median_fwhm_catalog_px,
            "o-",
            label="FWHM [px]",
        )
        twin = axes[2].twinx()
        twin.plot(
            sensitivity.point_like_probability_min,
            sensitivity.median_ellipticity_catalog,
            "s--",
            color="#e66101",
            label="Ellipticity",
        )
        axes[2].set(
            xlabel="Minimum point-like probability",
            ylabel="Median FWHM [px]",
            title="(c) Selection sensitivity",
        )
        twin.set_ylabel("Median ellipticity")
        axes[2].legend(frameon=False, loc="upper left")
        twin.legend(frameon=False, loc="lower right")
        fig.suptitle("Euclid Q1 catalogue shape robustness (15 real objects)")
        fig.savefig(out / "catalog_robustness.png", dpi=240)
        fig.savefig(out / "catalog_robustness.pdf")
        plt.close(fig)


if __name__ == "__main__":
    main()
