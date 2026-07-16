# Research Blueprint

## Technical title

Euclid Q1 VIS PSF and Astrometry Audit

## Category

Space-imaging instrumentation / data science

## Bounded scientific question

Do local point-source FWHM, ellipticity and Gaia-relative astrometric residuals vary across selected public Euclid Q1 VIS products?

## Gap statement

A small external reproducibility audit; not a weak-lensing PSF solution or replacement for the official VIS pipeline.

## First-release scope

The first release must be completable as a focused 4–6 hour implementation pass after data access is working. It must deliver one reproducible analysis pipeline, one deterministic example/smoke dataset, tests, 4–6 figures, a concise TeX report and a deployable research webpage.

## Validation and uncertainty

- synthetic star injection
- Gaussian/Moffat comparison
- bootstrap tile statistics
- Gaia affine alignment
- strict/permissive cuts

## Required figures

1. VIS cutouts
2. FWHM/ellipticity distributions
3. spatial maps
4. Gaia residuals
5. magnitude/colour trends
6. injection recovery

## Reusable scientific modules

- `io.py`
- `detection.py`
- `psf_metrics.py`
- `gaia_match.py`
- `spatial_stats.py`
- `uncertainty.py`
- `provenance.py`

## Explicit exclusions

- No novelty claim beyond the bounded dataset/question/method combination.
- No causal claim from descriptive catalogue correlations.
- No hidden manual data editing.
- No unsupported precision beyond the input uncertainties.
- No production-pipeline replacement claim.
