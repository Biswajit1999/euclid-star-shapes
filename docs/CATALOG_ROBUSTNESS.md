# Catalogue-shape robustness audit

This follow-up quantifies how much the committed 15-object real Euclid Q1 catalogue sample can support. It adds deterministic 20,000-draw percentile bootstrap intervals for median FWHM and ellipticity, leave-one-object-out influence on median FWHM, Theil--Sen and Spearman magnitude trends, and sensitivity to increasingly strict point-source probability cuts.

The input columns are official Euclid catalogue measurements with archive provenance in `data/manifest.csv`. They are not the repository's image-domain remeasurements and are not a weak-lensing PSF calibration. Bootstrap intervals represent resampling variability conditional on these 15 deterministically selected objects; they do not include field selection, calibration systematics, or survey-scale spatial variation.

Run `python scripts/audit_catalog_robustness.py` after installing the package.
