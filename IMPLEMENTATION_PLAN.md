# Implementation Plan — Euclid Q1 VIS PSF and Astrometry Audit

Status: Phase 1 (audit) complete.

## 1. Environment audit

- Same pinned dependency stack as `hst-acs-two-axis-cte-audit` (numpy 1.26.4, scipy
  1.13.1, pandas 2.2.2, matplotlib 3.9.0, astropy 6.1.0, photutils 1.13.0,
  astroquery 0.4.7, Python 3.11–3.12). Installed into the existing
  `hst-acs-cte-audit` conda env (Python 3.11.15) rather than creating a new one —
  confirmed `pip install -e ".[dev]"` succeeds with all deps already satisfied.
- Node/npm and LaTeX-toolchain constraints are identical to project 1 (no local
  `pdflatex`; Node 20.14.0 at `D:\Softwares\nodejs` works for `web-react`).

## 2. Dataset decision (real data, verified live)

`astroquery.esa.euclid` is **not available** in the pinned astroquery 0.4.7 (that
module was added after this version; verified by direct `ImportError`). Real access
instead goes through **IRSA's public Euclid Q1 mirror** (`astroquery.ipac.irsa.Irsa`,
part of core astroquery, no extra dependency):

- **Catalog**: `euclid_q1_mer_catalogue` (TAP table) has per-source `ra`, `dec`,
  `fwhm` (arcsec), `ellipticity`, `ellipticity_err`, `point_like_flag`,
  `point_like_prob`, `mag_stargal_sep`, `mu_max`, `spurious_flag`,
  `det_quality_flag`, `gaia_id`, `gaia_match_quality`, `tileid`. Verified live: tile
  `102018211` has 465 catalogued sources; a query for
  `point_like_prob>0.8 AND vis_det=1 AND spurious_flag=0 AND 0<fwhm<2` returns 12
  clean point-source candidates with real RA/Dec/FWHM/ellipticity/magnitude values.
  (First broad, unrestricted-by-tile query against this table hung for 5+ minutes
  and was abandoned — the table is evidently not efficiently scanned without a
  `tileid` restriction; all subsequent queries restrict by `tileid`.)
- **Images**: `Irsa.query_sia(pos=(ra, dec, radius), collection='euclid_DpdMerBksMosaic')`
  returns real Euclid VIS mosaic products (`EUC_MER_BGSUB-MOSAIC-VIS_...fits`,
  calib_level 3, science). Each **full tile mosaic is ~1.4 GB** — far too large to
  download whole. **Verified live** that IRSA's `ibe` file server honours
  server-side cutout parameters (`?center=RA,DEC&size=DEG` appended to the FITS
  URL): a 0.02° (~72″) cutout around a real source returned `Content-Length` ≈
  1.79 MB (gzip), vs. 1.4 GB for the full mosaic. All image access will use this
  cutout mechanism, never the full mosaic.
- **Astrometric reference**: Gaia DR3 via `astroquery.gaia.Gaia` (core, always
  available) — verified live with a real cone query near the same sky region
  (3 real Gaia sources returned with source_id/ra/dec/G mag).
- **Sample budget**: ~12–20 point-source cutouts (~1.8 MB each ≈ 25–35 MB total)
  from 1–2 real tiles (102018211, 102018212 both have VIS mosaics available) —
  much smaller than project 1's ~1 GB, reflecting the cutout-based access pattern.
  Real download requires explicit operator authorization in chat before
  `scripts/fetch_data.py` is run for real (same pattern as project 1), even though
  the total size is small.
- Licence/terms: Euclid Q1 data are public (ESA Euclid Consortium data release);
  IRSA serves it under NASA/IPAC's standard archive terms. Recorded verbatim per
  manifest row.

## 3. Literature verification (done in Phase 1)

All 5 seeds in `docs/LITERATURE_SEEDS.md` verified against arXiv abstract pages:

- Euclid Q1 overview, arXiv:2503.15302 — Euclid Collaboration, 2025 — verified.
- Euclid Q1 VIS processing, arXiv:2503.15303 — Euclid Collaboration (McCracken+),
  2025 — verified.
- Euclid Q1 MER processing, arXiv:2503.15305 — Euclid Collaboration (Romelli+),
  2025 — verified.
- Euclid mission overview, arXiv:2405.13491 — Euclid Collaboration (Mellier+), 2024
  — verified.
- Euclid mission design, arXiv:1610.05508 — Racca et al., 2016, SPIE, DOI
  10.1117/12.2230762 — verified.

## 4. Scientific method (bounded to the stated question)

**Question**: Do local point-source FWHM, ellipticity and Gaia-relative astrometric
residuals vary across selected public Euclid Q1 VIS products?

1. **Source selection**: query `euclid_q1_mer_catalogue` for clean point-like
   sources (documented cuts below) in 1–2 real tiles.
2. **Cutout retrieval**: fetch a small real VIS mosaic cutout (IRSA `ibe` server-side
   cutout) centered on each source.
3. **PSF metrics** (independent of the MER catalog's own `fwhm`/`ellipticity`
   values — this audit re-measures them from pixels, only using the catalog
   values as a cross-check): fit both a 2-D Gaussian and a 2-D Moffat profile to
   each cutout (`astropy.modeling` + `scipy.optimize`), report FWHM and ellipticity
   from each, and compare which model fits better (reduced χ²) — this is the
   "Gaussian/Moffat comparison" validation-contract item.
4. **Astrometric residuals**: cross-match each source's re-measured centroid
   against Gaia DR3 (`astroquery.gaia`), fit an affine (or similarity) transform
   between the local pixel/WCS frame and Gaia, and report per-source residuals —
   the "Gaia affine alignment" validation-contract item.
5. **Spatial and magnitude trends**: bin FWHM/ellipticity/residuals spatially
   across the tile and by VIS magnitude, matching required figures 3 and 5.
6. **Strict/permissive cuts**: report all four metrics (FWHM, ellipticity, both
   residual components) under two documented source-quality cut levels (e.g.
   `point_like_prob>0.95` strict vs. `>0.8` permissive) to show cut-sensitivity —
   the "strict/permissive cuts" validation-contract item.
7. **Synthetic star injection gate**: before touching real cutouts, inject a
   synthetic Gaussian/Moffat point source of known FWHM/ellipticity into a
   labelled-synthetic background and confirm the fitting pipeline recovers it
   within a documented tolerance (mirrors project 1's exponential-trail gate).

## 5. File-level task list

### Phase 2 — Foundation
Port the same `config.py`, `exceptions.py` (+ `ArchiveAccessError`,
`ConvergenceError`, `InsufficientDataError`), `logging_utils.py`, `provenance.py`
pattern from `hst-acs-two-axis-cte-audit`, adapted to this project's
`config/analysis.yml` (same schema, different title/repository) and package name
`euclid_q1_vis_psf_astrometry_audit`.

### Phase 3 — Data layer
- `scripts/fetch_data.py`: real IRSA TAP query (tile-restricted, per §2) + SIA
  lookup + `ibe` server-side cutout download + SHA-256 + manifest write. Gated
  behind `--i-have-authorization` like project 1.
- `src/euclid_q1_vis_psf_astrometry_audit/synthetic.py`: synthetic 2-D
  Gaussian/Moffat point-source cutout generator (shared by tests and `--demo`).

### Phase 4 — Scientific modules (`src/euclid_q1_vis_psf_astrometry_audit/`)
- `io.py`: load a VIS cutout FITS file, validate against `INPUT_SCHEMA.md`
  (science array + WCS; Euclid cutouts are single-extension unlike ACS's
  SCI/ERR/DQ triplet — document this real structural difference).
- `detection.py`: locate the source centroid within the cutout (photutils
  centroiding around the known catalog RA/Dec projected through the cutout WCS).
- `psf_metrics.py`: Gaussian and Moffat 2-D profile fits, FWHM/ellipticity
  extraction, reduced-χ² model comparison.
- `gaia_match.py`: Gaia DR3 cone search, nearest-neighbour match, affine transform
  fit, residual computation.
- `spatial_stats.py`: spatial and magnitude binning of the above metrics, reusing
  the `bin_scalar_statistic`-style pattern from project 1 (flag underpopulated
  bins, never silently drop).
- `uncertainty.py`, `provenance.py`: same bootstrap / fit-convergence separation
  and manifest utilities as project 1.
- `core.py`: `run_pipeline()` orchestrator; keep starter `demo_series`/
  `robust_summary` for the smoke path.

### Phase 5 — Validation and QA
- Synthetic star injection-recovery test (the required pass/fail gate).
- Gaussian-vs-Moffat comparison test on a known synthetic profile.
- Null control: pure-noise cutout (no injected source) ⇒ fit amplitude consistent
  with zero / detection correctly rejected.
- Failure tests: missing WCS, malformed cutout, empty Gaia cross-match region.
- Strict vs. permissive cut sensitivity test.
- Benchmarks per `docs/BENCHMARK_PLAN.md` (same tracemalloc + perf_counter pattern).

### Phase 6 — Figures and report
Six figures per `docs/FIGURE_AND_UI_SPEC.md`: VIS cutouts, FWHM/ellipticity
distributions, spatial maps, Gaia residuals, magnitude/colour trends, injection
recovery. Complete `reports/report.tex`/`references.bib` from real
`results/summary.json` once available; demo path first.

### Phase 7 — React dashboard
Same pattern as project 1: fetch `results/summary.json` + `project.json`, figure
gallery, provenance/downloads, methodology/validation/limitations, no fake
live-data language. Reuse the `eslint.config.js` `react/jsx-uses-vars` fix
proactively (known scaffold bug from project 1) rather than rediscovering it.

### Phase 8 — Verification
Same command sequence as project 1; write `LOCAL_COMPLETION_REPORT.md`.

## 6. Validation thresholds (from `docs/VALIDATION_CONTRACT.md`, made concrete)

| Check | Threshold |
|---|---|
| Synthetic FWHM recovery | within 15% of injected value |
| Synthetic ellipticity recovery | within 0.05 (absolute) of injected value |
| Minimum sample size per bin | ≥30 (config), underpopulated bins flagged not dropped |
| Bootstrap resamples | 1000, seed 20260713 |
| Gaia match radius | documented fixed radius (e.g. 0.5″), sources with no match excluded and counted |
| Finite-value check | 100% of reported metric arrays finite after documented masking |

## 7. Unresolved risks / stop-condition watchlist

- **Only 465 catalogued sources in the first tile queried** — if strict cuts leave
  too few sources for `minimum_sample_size=30` per spatial/magnitude bin (likely,
  given only 12 passed permissive cuts in one tile), bins will be flagged
  underpopulated rather than silently dropped or padded; a second tile
  (102018212 or 102018666, both confirmed to have VIS mosaics) may be added to the
  sample if needed.
- **Euclid cutout FITS structure differs from ACS's SCI/ERR/DQ triplet** — must be
  verified against a real downloaded cutout's actual extension layout before
  writing `io.py`'s parser, not assumed from the HST pattern.
- `astroquery.esa.euclid` unavailability means the fetch script depends on IRSA's
  mirror rather than the official ESA archive directly; if IRSA's Euclid mirror
  access changes, this is a real external dependency risk to note in limitations.
- Per `docs/VALIDATION_CONTRACT.md` stop conditions: if synthetic injection-recovery fails, stop
  and document rather than proceeding to real cutouts.

## 8. Non-negotiables carried forward

No `git commit`/`push`/remote creation.
Biswajit Jana remains sole author in `CITATION.cff`. No fabricated data,
benchmarks, or citation metadata. Real-data download requires explicit operator
authorization in chat before execution, regardless of the (small, ~30MB) size.
