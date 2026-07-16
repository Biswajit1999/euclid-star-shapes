"""Generate the 6 required figures (docs/FIGURE_AND_UI_SPEC.md) as SVG + 300 dpi PNG,
each with a sidecar JSON recording git commit, config hash, sample size and units.

--demo builds figures from the synthetic, clearly-labelled data model in
`euclid_q1_vis_psf_astrometry_audit.synthetic`. The real-data path reads
data/source_catalog.csv + data/raw/ + a live Gaia DR3 cross-match and must
only be run after scripts/run_analysis.py (real mode) has produced validated
results.

Scope note: "magnitude/colour trends" (figure 5 in docs/FIGURE_AND_UI_SPEC.md)
is implemented here as FWHM/ellipticity vs. VIS magnitude only — multi-band
colour trends are out of scope for this bounded first release (see
docs/ASSUMPTIONS_AND_LIMITATIONS.md).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from euclid_q1_vis_psf_astrometry_audit import __version__
from euclid_q1_vis_psf_astrometry_audit.config import load_config
from euclid_q1_vis_psf_astrometry_audit.core import read_source_catalog, run_pipeline
from euclid_q1_vis_psf_astrometry_audit.gaia_match import (
    fetch_gaia_reference_catalog,
    fit_affine_alignment,
    match_to_gaia,
    sky_to_tangent_plane,
)
from euclid_q1_vis_psf_astrometry_audit.io import load_cutout
from euclid_q1_vis_psf_astrometry_audit.plotting import plot_demo
from euclid_q1_vis_psf_astrometry_audit.provenance import get_git_commit, sha256_config
from euclid_q1_vis_psf_astrometry_audit.psf_metrics import compare_gaussian_moffat
from euclid_q1_vis_psf_astrometry_audit.synthetic import SyntheticPointSource, build_synthetic_vis_cutout


def _sidecar(path: Path, *, data_kind: str, sample_size: int, units: str, config_path: Path, extra: dict | None = None) -> None:
    payload = {
        "figure": path.stem,
        "data_kind": data_kind,
        "sample_size": sample_size,
        "units": units,
        "git_commit": get_git_commit(Path(__file__).resolve().parents[1]),
        "config_sha256": sha256_config(config_path) if config_path.is_file() else None,
        "package_version": __version__,
    }
    if extra:
        payload.update(extra)
    path.with_suffix(".json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _save(fig, out_dir: Path, name: str) -> Path:
    svg_path = out_dir / f"{name}.svg"
    png_path = out_dir / f"{name}.png"
    fig.savefig(svg_path)
    fig.savefig(png_path, dpi=300)
    plt.close(fig)
    return png_path


def make_demo_figures(out_dir: Path, config_path: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    data_kind = "synthetic_demo"

    rng = np.random.default_rng(20260713)
    sources, fwhm_truth, ellip_truth, mag = [], [], [], []
    for i in range(30):
        fwhm = 4.0 + rng.normal(0, 0.4)
        ellip = 0.12 + rng.uniform(0, 0.15)
        amp = rng.uniform(150, 900)
        sources.append(SyntheticPointSource(x=20.0, y=20.0, amplitude=amp, fwhm=fwhm, ellipticity=ellip, position_angle=rng.uniform(0, np.pi)))
        fwhm_truth.append(fwhm)
        ellip_truth.append(ellip)
        mag.append(24.0 - 2.5 * np.log10(amp))

    fitted_fwhm, fitted_ellip = [], []
    example_hdul = None
    for i, src in enumerate(sources):
        hdul = build_synthetic_vis_cutout(seed=300 + i, sources=(src,))
        comparison = compare_gaussian_moffat(hdul[0].data)
        best = comparison.gaussian if comparison.better_model == "gaussian" else comparison.moffat
        fitted_fwhm.append(best.fwhm)
        fitted_ellip.append(best.ellipticity)
        if i == 0:
            example_hdul = hdul
    fitted_fwhm, fitted_ellip, mag = np.array(fitted_fwhm), np.array(fitted_ellip), np.array(mag)

    # 1. VIS cutouts
    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(example_hdul[0].data, origin="lower", cmap="viridis")
    ax.set_title("Example VIS cutout — SYNTHETIC DEMO")
    ax.set_xlabel("x (pixels)")
    ax.set_ylabel("y (pixels)")
    fig.colorbar(im, ax=ax, shrink=0.8, label="Counts")
    path = _save(fig, out_dir, "fig01_vis_cutouts")
    _sidecar(path, data_kind=data_kind, sample_size=1, units="pixels", config_path=config_path)

    # 2. FWHM/ellipticity distributions
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    axes[0].hist(fitted_fwhm, bins=10, color="tab:blue", edgecolor="white")
    axes[0].set_xlabel("Measured FWHM (pixels)")
    axes[0].set_ylabel("N sources")
    axes[1].hist(fitted_ellip, bins=10, color="tab:orange", edgecolor="white")
    axes[1].set_xlabel("Measured ellipticity")
    fig.suptitle(f"FWHM / ellipticity distributions — SYNTHETIC DEMO (n={len(fitted_fwhm)})")
    path = _save(fig, out_dir, "fig02_fwhm_ellipticity_distributions")
    _sidecar(path, data_kind=data_kind, sample_size=len(fitted_fwhm), units="pixels / dimensionless", config_path=config_path)

    # 3. spatial maps (synthetic (x,y) tile positions since demo cutouts share one field)
    xs = rng.uniform(0, 100, size=len(fitted_fwhm))
    ys = rng.uniform(0, 100, size=len(fitted_fwhm))
    fig, ax = plt.subplots(figsize=(6, 5))
    sc = ax.scatter(xs, ys, c=fitted_fwhm, cmap="viridis", s=60, edgecolor="black")
    ax.set_xlabel("Tile x (arbitrary units)")
    ax.set_ylabel("Tile y (arbitrary units)")
    ax.set_title(f"Spatial FWHM map — SYNTHETIC DEMO (n={len(fitted_fwhm)})")
    fig.colorbar(sc, ax=ax, label="FWHM (pixels)")
    path = _save(fig, out_dir, "fig03_spatial_maps")
    _sidecar(path, data_kind=data_kind, sample_size=len(fitted_fwhm), units="pixels", config_path=config_path)

    # 4. Gaia residuals
    ref_xy = rng.uniform(-10, 10, size=(len(fitted_fwhm), 2))
    measured_xy = ref_xy + rng.normal(0, 0.02, size=ref_xy.shape)
    alignment = fit_affine_alignment(measured_xy, ref_xy)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(alignment.residuals_x, alignment.residuals_y, color="tab:red")
    ax.axhline(0, color="black", lw=0.5)
    ax.axvline(0, color="black", lw=0.5)
    ax.set_xlabel("RA residual (arcsec)")
    ax.set_ylabel("Dec residual (arcsec)")
    ax.set_title(f"Gaia astrometric residuals — SYNTHETIC DEMO (RMS={alignment.rms_residual_arcsec:.4f}\", n={len(fitted_fwhm)})")
    path = _save(fig, out_dir, "fig04_gaia_residuals")
    _sidecar(path, data_kind=data_kind, sample_size=len(fitted_fwhm), units="arcsec", config_path=config_path)

    # 5. magnitude trends (FWHM/ellipticity vs VIS magnitude; colour trends out of scope, see docstring)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    axes[0].scatter(mag, fitted_fwhm, color="tab:blue")
    axes[0].set_xlabel("VIS magnitude (synthetic)")
    axes[0].set_ylabel("FWHM (pixels)")
    axes[1].scatter(mag, fitted_ellip, color="tab:orange")
    axes[1].set_xlabel("VIS magnitude (synthetic)")
    axes[1].set_ylabel("Ellipticity")
    fig.suptitle(f"FWHM / ellipticity vs magnitude — SYNTHETIC DEMO (n={len(fitted_fwhm)})")
    path = _save(fig, out_dir, "fig05_magnitude_trends")
    _sidecar(path, data_kind=data_kind, sample_size=len(fitted_fwhm), units="mag vs pixels/dimensionless", config_path=config_path)

    # 6. injection recovery
    truth_fwhms = np.array([3.0, 3.75, 4.5, 5.25, 6.0])
    recovered = []
    for i, f in enumerate(truth_fwhms):
        src = SyntheticPointSource(x=20.0, y=20.0, amplitude=800.0, fwhm=float(f), ellipticity=0.15, position_angle=0.3)
        hdul_i = build_synthetic_vis_cutout(seed=500 + i, sources=(src,))
        comparison = compare_gaussian_moffat(hdul_i[0].data)
        best = comparison.gaussian if comparison.better_model == "gaussian" else comparison.moffat
        recovered.append(best.fwhm)
    fig, ax = plt.subplots(figsize=(6, 6))
    lims = [0, float(truth_fwhms.max()) * 1.1]
    ax.plot(lims, lims, "k--", label="1:1")
    ax.plot(truth_fwhms, recovered, "o", color="tab:red", label="recovered vs injected")
    ax.set_xlabel("Injected FWHM (pixels)")
    ax.set_ylabel("Recovered FWHM (pixels)")
    ax.set_title(f"Injection-recovery validation — SYNTHETIC DEMO (n={len(truth_fwhms)})")
    ax.legend()
    path = _save(fig, out_dir, "fig06_injection_recovery")
    _sidecar(path, data_kind=data_kind, sample_size=len(truth_fwhms), units="pixels", config_path=config_path)

    print(f"Wrote 6 demo figures (SVG+PNG+JSON) to {out_dir}")


def make_real_figures(out_dir: Path, config_path: Path, source_catalog_path: Path, raw_dir: Path) -> None:
    config = load_config(config_path)
    catalog_entries = read_source_catalog(source_catalog_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_kind = config.input.data_mode

    field_ra = float(np.mean([e.ra for e in catalog_entries]))
    field_dec = float(np.mean([e.dec for e in catalog_entries]))
    gaia_ra, gaia_dec, gaia_source_id = fetch_gaia_reference_catalog(field_ra, field_dec, 0.02)
    result = run_pipeline(catalog_entries, raw_dir, config, gaia_ra, gaia_dec, gaia_source_id)

    first_entry = catalog_entries[0]
    cutout = load_cutout(raw_dir / f"{first_entry.product_id}.fits")

    # 1. VIS cutouts
    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(cutout.science_array, origin="lower", cmap="viridis")
    ax.set_title(f"VIS cutout: {first_entry.product_id}")
    ax.set_xlabel("x (pixels)")
    ax.set_ylabel("y (pixels)")
    fig.colorbar(im, ax=ax, shrink=0.8, label=cutout.exposure_metadata.get("bunit", "Counts"))
    path = _save(fig, out_dir, "fig01_vis_cutouts")
    _sidecar(path, data_kind=data_kind, sample_size=1, units="pixels", config_path=config_path)

    fwhm = np.array([m.fwhm_measured for m in result.measurements])
    ellip = np.array([m.ellipticity_measured for m in result.measurements])
    ra = np.array([m.ra for m in result.measurements])
    dec = np.array([m.dec for m in result.measurements])
    mag = np.array([m.mag_stargal_sep if m.mag_stargal_sep is not None else np.nan for m in result.measurements])

    # 2. FWHM/ellipticity distributions
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    axes[0].hist(fwhm, bins=min(10, len(fwhm)), color="tab:blue", edgecolor="white")
    axes[0].set_xlabel("Measured FWHM (pixels)")
    axes[0].set_ylabel("N sources")
    axes[1].hist(ellip, bins=min(10, len(ellip)), color="tab:orange", edgecolor="white")
    axes[1].set_xlabel("Measured ellipticity")
    fig.suptitle(f"FWHM / ellipticity distributions (n={len(fwhm)})")
    path = _save(fig, out_dir, "fig02_fwhm_ellipticity_distributions")
    _sidecar(path, data_kind=data_kind, sample_size=len(fwhm), units="pixels / dimensionless", config_path=config_path)

    # 3. spatial maps
    fig, ax = plt.subplots(figsize=(6, 5))
    sc = ax.scatter(ra, dec, c=fwhm, cmap="viridis", s=60, edgecolor="black")
    ax.set_xlabel("RA (deg)")
    ax.set_ylabel("Dec (deg)")
    ax.set_title(f"Spatial FWHM map (n={len(fwhm)})")
    fig.colorbar(sc, ax=ax, label="FWHM (pixels)")
    path = _save(fig, out_dir, "fig03_spatial_maps")
    _sidecar(path, data_kind=data_kind, sample_size=len(fwhm), units="pixels", config_path=config_path)

    # 4. Gaia residuals
    measured_ra = np.array([m.centroid_ra for m in result.measurements])
    measured_dec = np.array([m.centroid_dec for m in result.measurements])
    matches = match_to_gaia(measured_ra, measured_dec, gaia_ra, gaia_dec, gaia_source_id)
    matched = [m for m in matches if m is not None]
    fig, ax = plt.subplots(figsize=(7, 6))
    if len(matched) >= 3:
        m_xy = np.column_stack(sky_to_tangent_plane(np.array([m.measured_ra for m in matched]), np.array([m.measured_dec for m in matched]), field_ra, field_dec))
        g_xy = np.column_stack(sky_to_tangent_plane(np.array([m.gaia_ra for m in matched]), np.array([m.gaia_dec for m in matched]), field_ra, field_dec))
        alignment = fit_affine_alignment(m_xy, g_xy)
        ax.scatter(alignment.residuals_x, alignment.residuals_y, color="tab:red")
        title_extra = f"RMS={alignment.rms_residual_arcsec:.4f}\""
    else:
        title_extra = f"insufficient matches (n={len(matched)})"
        ax.text(
            0.5, 0.5,
            f"{len(matched)} of {len(result.measurements)} sources matched Gaia DR3\nwithin 0.5\"\n"
            f"({len(gaia_ra)} Gaia sources found in the search field)\nSee report Section 6 for interpretation.",
            transform=ax.transAxes, ha="center", va="center", fontsize=10, color="dimgray",
        )
    ax.axhline(0, color="black", lw=0.5)
    ax.axvline(0, color="black", lw=0.5)
    ax.set_xlabel("RA residual (arcsec)")
    ax.set_ylabel("Dec residual (arcsec)")
    ax.set_title(f"Gaia astrometric residuals\n({title_extra}, n_sources={len(result.measurements)})", fontsize=12)
    fig.tight_layout()
    path = _save(fig, out_dir, "fig04_gaia_residuals")
    _sidecar(path, data_kind=data_kind, sample_size=len(matched), units="arcsec", config_path=config_path)

    # 5. magnitude trends
    valid = np.isfinite(mag)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    axes[0].scatter(mag[valid], fwhm[valid], color="tab:blue")
    axes[0].set_xlabel("VIS magnitude (mag_stargal_sep)")
    axes[0].set_ylabel("FWHM (pixels)")
    axes[1].scatter(mag[valid], ellip[valid], color="tab:orange")
    axes[1].set_xlabel("VIS magnitude (mag_stargal_sep)")
    axes[1].set_ylabel("Ellipticity")
    fig.suptitle(f"FWHM / ellipticity vs magnitude (n={int(valid.sum())})")
    path = _save(fig, out_dir, "fig05_magnitude_trends")
    _sidecar(path, data_kind=data_kind, sample_size=int(valid.sum()), units="mag vs pixels/dimensionless", config_path=config_path)

    # 6. injection recovery (synthetic gate, run alongside real results)
    truth_fwhms = np.array([3.0, 3.75, 4.5, 5.25, 6.0])
    recovered = []
    for i, f in enumerate(truth_fwhms):
        src = SyntheticPointSource(x=20.0, y=20.0, amplitude=800.0, fwhm=float(f), ellipticity=0.15, position_angle=0.3)
        hdul_i = build_synthetic_vis_cutout(seed=500 + i, sources=(src,))
        comparison = compare_gaussian_moffat(hdul_i[0].data)
        best = comparison.gaussian if comparison.better_model == "gaussian" else comparison.moffat
        recovered.append(best.fwhm)
    fig, ax = plt.subplots(figsize=(6, 6))
    lims = [0, float(truth_fwhms.max()) * 1.1]
    ax.plot(lims, lims, "k--", label="1:1")
    ax.plot(truth_fwhms, recovered, "o", color="tab:red", label="recovered vs injected")
    ax.set_xlabel("Injected FWHM (pixels)")
    ax.set_ylabel("Recovered FWHM (pixels)")
    ax.set_title(f"Injection-recovery validation gate (n={len(truth_fwhms)}, run alongside real data)")
    ax.legend()
    path = _save(fig, out_dir, "fig06_injection_recovery")
    _sidecar(path, data_kind="synthetic_validation_gate", sample_size=len(truth_fwhms), units="pixels", config_path=config_path)

    print(f"Wrote 6 real-data figures (SVG+PNG+JSON) to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=Path("figures"))
    parser.add_argument("--config", type=Path, default=Path("config/analysis.yml"))
    parser.add_argument("--source-catalog", type=Path, default=Path("data/source_catalog.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()

    if args.demo:
        from euclid_q1_vis_psf_astrometry_audit.core import demo_series

        plot_demo(demo_series(), args.out_dir / "fig00_smoke_test.png")
        make_demo_figures(args.out_dir, args.config)
        return

    make_real_figures(args.out_dir, args.config, args.source_catalog, args.raw_dir)


if __name__ == "__main__":
    main()
