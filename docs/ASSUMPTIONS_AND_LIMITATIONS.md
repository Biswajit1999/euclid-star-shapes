# Assumptions and Limitations

## Assumptions

- Archive metadata and calibration versions are recorded and interpreted correctly.
- Selection rules are deterministic and version controlled.
- Uncertainty treatment matches the measurement or numerical process.
- Synthetic examples are used only for validation and smoke testing.
- **Real archive access route** (`scripts/fetch_data.py`): `astroquery.esa.euclid` is
  not available in the pinned `astroquery==0.4.7`, so real access goes through IRSA's
  public Euclid Q1 mirror instead of the official ESA archive directly. This is an
  external dependency on IRSA's mirror staying in sync with the ESA release, not the
  primary archive.
- **Euclid cutout FITS structure** (`io.py`): parsed defensively (PrimaryHDU-with-data
  or a named SCI/SCIENCE/DATA extension; ERR/RMS/UNCERTAINTY extension if present,
  else a sigma-clipped background-noise proxy) because the exact real structure was
  not verified against a live downloaded file before this was written (that download
  needs separate operator authorization). `exposure_metadata` records which layout
  was actually found in each real file so this can be sanity-checked post hoc.
- **PSF metric conventions** (`psf_metrics.py`): FWHM is the geometric mean of
  major/minor-axis FWHMs; ellipticity is `1 - minor/major`. Consistent with the
  synthetic injection convention so injection-recovery tests are self-consistent, but
  not independently verified against the MER catalogue's own `fwhm`/`ellipticity`
  columns in this session (a real-data comparison against those catalogue values,
  which the `euclid_q1_mer_catalogue` table also ships, is a natural extension).
- **Gaia affine alignment** (`gaia_match.py`) requires >= 3 matched points; the
  bounded real-data sample (target ~15 sources) may only marginally satisfy this
  after quality cuts and match-radius rejection.

## Limitations

- Do local point-source FWHM, ellipticity and Gaia-relative astrometric residuals vary across selected public Euclid Q1 VIS products?
- The first release is intentionally bounded and does not replace mature mission or community pipelines.
- Results may apply only to the selected products, dates, detector regions, source classes or parameter range.
- Correlated errors, censoring, calibration systematics and selection effects must be discussed where relevant.
- Only 465 sources were found in the first real tile queried (102018211); a
  deterministic sample of ~15 point sources across two tiles is small by design for a
  first release, and per-bin sample sizes will likely fall below
  `config/analysis.yml`'s `minimum_sample_size=30` — flagged, not hidden, in
  `results/warnings.json`.
- "Magnitude/colour trends" is implemented as FWHM/ellipticity vs. VIS magnitude
  only; multi-band colour trends are out of scope for this bounded first release.
- `reports/report.tex` could not be compiled to PDF locally (no LaTeX toolchain);
  only structural completeness was verified.
