"""Small-sample robustness checks for the committed real Euclid source catalogue."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def bootstrap_median(values, *, draws: int = 20000, seed: int = 20261012) -> dict:
    """Return a deterministic percentile interval for a sample median."""
    values = np.asarray(values, dtype=float)
    if values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError("at least two finite values are required")
    rng = np.random.default_rng(seed)
    medians = np.median(rng.choice(values, size=(draws, len(values)), replace=True), axis=1)
    return {
        "n": len(values),
        "median": float(np.median(values)),
        "ci95_low": float(np.quantile(medians, 0.025)),
        "ci95_high": float(np.quantile(medians, 0.975)),
        "draws": draws,
        "seed": seed,
    }


def jackknife_influence(values) -> pd.DataFrame:
    """Quantify each row's influence on the median by leave-one-out deletion."""
    values = np.asarray(values, dtype=float)
    full = np.median(values)
    return pd.DataFrame(
        {
            "row_index": np.arange(len(values)),
            "value": values,
            "leave_one_out_median": [np.median(np.delete(values, i)) for i in range(len(values))],
        }
    ).assign(influence=lambda frame: frame.leave_one_out_median - full)


def magnitude_trend(df: pd.DataFrame, column: str) -> dict:
    """Robust Theil--Sen shape trend against catalogue magnitude."""
    # scipy.theilslopes sorts array-like inputs in place in some versions;
    # copies prevent accidental row-wise corruption of the source DataFrame.
    x = df["mag_stargal_sep"].to_numpy(dtype=float, copy=True)
    y = df[column].to_numpy(dtype=float, copy=True)
    result = stats.theilslopes(y.copy(), x.copy(), alpha=0.95)
    rho, pvalue = stats.spearmanr(x, y)
    return {
        "column": column,
        "slope_per_magnitude": float(result.slope),
        "slope_ci95_low": float(result.low_slope),
        "slope_ci95_high": float(result.high_slope),
        "spearman_r": float(rho),
        "spearman_p": float(pvalue),
    }


def selection_sensitivity(df: pd.DataFrame, thresholds=(0.8, 0.9, 0.95, 0.99)) -> pd.DataFrame:
    """Recompute medians while tightening the point-source probability gate."""
    rows = []
    for threshold in thresholds:
        selected = df[df.point_like_prob >= threshold]
        rows.append(
            {
                "point_like_probability_min": threshold,
                "n": len(selected),
                "median_fwhm_catalog_px": selected.fwhm_catalog.median(),
                "median_ellipticity_catalog": selected.ellipticity_catalog.median(),
            }
        )
    return pd.DataFrame(rows)
