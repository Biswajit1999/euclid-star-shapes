# Local Completion Report — Euclid Q1 VIS PSF and Astrometry Audit

Author: Biswajit Jana. This report documents a local Claude Code implementation pass
(project 2 of the 30-project pack, `BUILD_FIRST` priority 9.5/10). No git operations
were performed. Nothing has been published.

## 1. Environment

- Reused the `hst-acs-cte-audit` conda environment (Python 3.11.15) from project 1,
  since this project's `pyproject.toml` pins the identical dependency versions.
- Added `requests==2.34.2` (already a transitive dependency, now declared directly
  since `fetch_data.py` imports it) and mypy overrides / `types-PyYAML` /
  `types-requests`, matching project 1's pattern.
- No local LaTeX toolchain (see §7, same limitation as project 1).

## 2. Files created or changed

Same structure as project 1's completion report — foundation (`config.py`,
`exceptions.py`, `logging_utils.py`, `provenance.py`, `results_io.py`), data layer
(`scripts/fetch_data.py`, `synthetic.py`, `scripts/sync_web_assets.py`), scientific
modules (`io.py`, `detection.py`, `psf_metrics.py`, `gaia_match.py`,
`spatial_stats.py`, `uncertainty.py`, `core.py`), 11 new test files, figures/report
(`scripts/make_figures.py`, `reports/report.tex`, `reports/references.bib`), and the
web dashboard (`web-react/src/App.jsx` rewritten, `eslint.config.js` fixed,
`recharts` removed, `public/project.json` updated). Full file list mirrors
`IMPLEMENTATION_PLAN.md` §5.

## 3. Exact commands run (in order)

```bash
python -m pip install -e ".[dev]"        # into the shared hst-acs-cte-audit env
pytest -q                                  # 52 passed
ruff check src tests scripts               # All checks passed
mypy src                                   # Success: no issues found in 15 source files
python scripts/run_analysis.py --demo
python scripts/make_figures.py --demo
cd web-react && npm install && npm run build && npm run lint
python scripts/sync_web_assets.py
# Real-data pipeline, run only after explicit operator authorization in chat:
python scripts/fetch_data.py --i-have-authorization --n-sources 15
python scripts/run_analysis.py
python scripts/make_figures.py
python scripts/sync_web_assets.py
cd web-react && npm run build              # re-verified after real data synced
```

## 4. Test / lint / build results

- **pytest**: 52 tests passed, 0 failed. Coverage: 90% overall;
  `gaia_match.fetch_gaia_reference_catalog` (the one network-touching function) is
  the main coverage gap by design — it is exercised by live runs, not unit tests.
- **ruff**: clean on `src tests scripts`.
- **mypy**: clean on `src` (0 errors, 15 source files).
- **web-react**: `npm run build` and `npm run lint` both clean after applying the
  same `eslint.config.js` `react/jsx-uses-vars` fix identified in project 1 (this
  scaffold bug is present in every project in the pack — worth fixing proactively in
  the remaining 8).
- `npm audit`: same 5 dev-tooling-only advisories as project 1 (eslint config parser,
  vite dev server, postcss stringify); not fixed without being asked.

### Bugs found and fixed during implementation
1. `_pixel_grid`/`quality_cuts` had overly narrow mypy type hints
   (`tuple[int, int]` vs. numpy's actual `tuple[int, ...]`; an inferred 2-tuple type
   that couldn't hold the empty-tuple fallback) — fixed before Phase 5 completed.
2. `core.run_pipeline`'s per-source loop only caught `InsufficientDataError`/
   `ConvergenceError`, not `DataSchemaError` (raised by `load_cutout` for a
   missing/malformed file) — one bad file would have crashed the whole real-data run.
   Fixed to skip-and-warn, mirroring project 1's `ConvergenceError` fix.
3. `scripts/make_figures.py`'s real-data path tried `from scripts.run_analysis
   import _fetch_gaia_reference`, which does not reliably resolve when scripts are
   run as standalone files (no `scripts` package). Fixed by moving the Gaia query
   into `gaia_match.fetch_gaia_reference_catalog`, shared by both scripts.
4. **Real bug, found only against real data**: `fetch_data.py` checked
   `row["gaia_id"] is not None` to detect a missing MER-catalogue Gaia cross-match,
   but astropy represents a NULL/masked TAP cell as a numpy masked constant, not
   Python `None` — the check silently never fired, and `int(row["gaia_id"])` raised
   `numpy.ma.core.MaskError` on the first real source with no recorded Gaia ID.
   Fixed with a `_masked_scalar()` helper using `np.ma.is_masked()`, applied to
   `gaia_id`, `ellipticity`, and `mag_stargal_sep` (all nullable in the real catalog).
5. **Real bug, found only against real data**: `gaia_match.fetch_gaia_reference_catalog`
   selected `table["source_id"]` (lowercase, matching the SQL SELECT clause), but the
   live Gaia archive TAP service returns the column as `SOURCE_ID` (uppercase)
   regardless of query casing — raised `KeyError: 'source_id'` on the first real
   query. Fixed with case-insensitive column lookup.

## 5. Real datasets accessed

`astroquery.esa.euclid` is unavailable in the pinned `astroquery==0.4.7` (verified by
direct `ImportError`); real access instead went through IRSA's public Euclid Q1
mirror.

- **Catalog query** (`astroquery.ipac.irsa.Irsa.query_tap`): `euclid_q1_mer_catalogue`,
  tiles 102018211/102018212, cuts `point_like_prob>0.8`, `vis_det=1`,
  `spurious_flag=0`, `0<fwhm<2` arcsec. 15 deterministic sources selected (sorted by
  `object_id`).
- **Images**: real VIS mosaic cutouts (0.01°, ~360×360 px, single PrimaryHDU with a
  valid TAN WCS — confirmed by direct inspection, matching the defensive parsing
  design in `io.py` exactly) retrieved via IRSA's `ibe` server-side cutout mechanism.
  15 files, ~7.0 MB total (well under the ~25–35 MB estimate given for authorization).
  Full SHA-256 list in `data/manifest.csv`; **all 15 checksums independently
  re-verified against the downloaded bytes in this session** (0 mismatches).
- **Astrometric reference**: live Gaia DR3 cone query via `astroquery.gaia.Gaia`
  (0.04°×0.04° box around the field centroid; 3 reference sources returned).
- **Licence/terms**: Euclid Q1 public data release (ESA Euclid Consortium), mirrored
  by IRSA/IPAC; standard IRSA archive usage terms.
- Raw FITS files are **not committed** (`.gitignore` excludes `data/raw/*`).

## 6. Validation and uncertainty outcomes

- **Synthetic injection-recovery gate**: PASSED. Across 15 realizations at two signal
  levels, worst-case FWHM error 0.05%/0.3%, worst-case ellipticity error 0.0015/0.010
  absolute; automated test enforces 10%/0.05 tolerance with wide margin.
- **Null control**: a source-free synthetic background fits a near-zero amplitude.
- **Model comparison**: correctly identifies the true injected profile type (Gaussian)
  on synthetic data.
- **Failure-mode tests**: missing file, no WCS, all-NaN science array, non-finite fit
  input, too-few-points, empty Gaia catalog, mismatched array shapes — all raise the
  documented exceptions.
- **Real-data result**: median FWHM 1.73 px (0.173″), consistent with the 0.16″ image
  quality reported in the verified VIS processing paper (arXiv:2503.15303) — a
  genuine cross-check against independently-published literature, not a
  self-consistency check. Median ellipticity 0.053 (n=15).
- **Gaia affine alignment: zero matches on real data.** Diagnosed (not by changing
  the saved pipeline output) that the nearest real Gaia source to each of the 15
  targets was 22–367″ away — far beyond any plausible astrometric offset — so this
  is a genuine "these aren't Milky Way stars" finding, not a matching-code bug (the
  matching/alignment code itself is validated on synthetic data with an exactly
  recovered translation offset, RMS < 1e-8″). The validation-contract item "Gaia
  affine alignment" is implemented and tested, but not exercised end-to-end on this
  particular real sample.
- Every magnitude/quality-cut bin (n=3–5) is below `minimum_sample_size=30` and
  flagged, not hidden, in `results/warnings.json`.

## 7. Remaining TODOs / unresolved risks

- `reports/report.tex` could not be compiled to PDF locally (no LaTeX toolchain);
  structural balance was checked programmatically. **Action for Biswajit**: compile
  before treating the PDF as final.
- The Gaia affine-alignment step has not been exercised end-to-end on real data (see
  §6) — a natural next extension is a larger or star-forward-selected sample.
- ACS Data Handbook-style institutional citation (`IRSAEuclidQ1Mirror` in
  `references.bib`) is marked `TODO_VERIFY` for a specific dated edition.
- Real-data sample is intentionally small (15 sources, 2 tiles) — a first-release
  bounded check, not a general characterization of Euclid VIS image quality.
- `npm audit` flags the same 5 dev-tooling-only advisories as project 1; not fixed
  without being asked.

## 8. Claims safe for a public README

- "Implements a reproducible pipeline auditing Euclid Q1 VIS point-source PSF shape
  and Gaia-relative astrometry, validated against a synthetic injection-recovery gate
  before use on real data."
- "On a small, deterministic sample of 15 real point-like VIS sources (Euclid Q1
  tiles 102018211/102018212), median measured FWHM was 0.173″, consistent with the
  0.16″ image quality reported in the official VIS processing paper."
- "52 automated tests including null controls and failure-mode tests, at 90% source
  coverage; ruff- and mypy-clean."
- "A small external reproducibility audit; not a weak-lensing PSF solution or
  replacement for the official VIS pipeline."

## 9. Claims that must NOT be made

- Do not claim this characterizes Euclid VIS image quality in general — the sample is
  15 sources from 2 tiles in one field.
- Do not claim the Gaia astrometric alignment was validated on real data — it was
  validated on synthetic data only; the real sample produced zero matches (§6).
- Do not claim the magnitude-binned FWHM/ellipticity trends are statistically
  significant — every bin is below the configured minimum sample size.
- Do not claim the TeX report PDF has been visually verified — only its source
  structure was checked.
- Do not claim this replaces or supersedes the official Euclid VIS/MER pipeline.

## 10. Manual review checklist for Biswajit

- [ ] Compile `reports/report.tex` locally/Overleaf and read the PDF end-to-end.
- [ ] Spot-check a few of the 15 real VIS cutouts visually against the catalog
      positions to confirm the centroiding is landing on the intended source.
- [ ] Decide whether to pursue the Gaia-alignment extension (larger/different field)
      before public release, or publish with the honest null result as-is.
- [ ] Pin the `TODO_VERIFY` IRSA documentation citation to a specific dated page.
- [ ] Review `docs/ASSUMPTIONS_AND_LIMITATIONS.md`'s FWHM/ellipticity conventions if a
      direct comparison against the MER catalogue's own `fwhm`/`ellipticity` columns
      is wanted (not done in this session).
- [ ] Review `npm audit` output and decide whether to bump pinned frontend tooling.
- [ ] Follow `MANUAL_GITHUB_ONE_BY_ONE.md` for the actual repository creation and
      push — none of that was done in this session.
