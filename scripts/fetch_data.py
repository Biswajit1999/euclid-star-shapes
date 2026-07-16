"""Deterministic, provenance-recording fetch of real public Euclid Q1 VIS data.

Queries IRSA's public Euclid Q1 mirror directly (no fabricated metadata) —
astroquery.esa.euclid is not available in the pinned astroquery==0.4.7, so this
goes through astroquery.ipac.irsa.Irsa's TAP (catalog) and SIA (image) services,
verified live during Phase 1 (see IMPLEMENTATION_PLAN.md §2). Real VIS mosaic
tiles are ~1.4 GB each; this script never downloads a full tile, only small
server-side cutouts (IRSA's `ibe` file server honours `?center=RA,DEC&size=DEG`
query parameters appended to the FITS URL).

This script performs real network requests and must only be invoked with
explicit user authorization for the session, per docs/DATASET_PLAN.md.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

from euclid_q1_vis_psf_astrometry_audit.exceptions import ArchiveAccessError
from euclid_q1_vis_psf_astrometry_audit.logging_utils import get_logger
from euclid_q1_vis_psf_astrometry_audit.provenance import ManifestRow, append_manifest_row, sha256_file

LOGGER = get_logger(__name__)

TILE_IDS = (102018211, 102018212)
CUTOUT_SIZE_DEG = 0.01  # ~36 arcsec on a side
LICENCE_TERMS = (
    "Euclid Q1 public data release (ESA Euclid Consortium), mirrored by IRSA/IPAC; "
    "standard IRSA archive usage terms apply, https://irsa.ipac.caltech.edu/holdings/copyright.html"
)
SOURCE_URL = "https://irsa.ipac.caltech.edu"
SOURCE_CATALOG_COLUMNS = (
    "object_id", "product_id", "ra", "dec", "fwhm_catalog", "ellipticity_catalog",
    "mag_stargal_sep", "point_like_prob", "gaia_id", "tileid",
)


def _masked_scalar(value):
    """Return None for a masked/NULL TAP result cell, else the raw value.

    Real Euclid MER catalogue rows can have NULL gaia_id/ellipticity/
    mag_stargal_sep (e.g. a point-like source with no recorded Gaia
    cross-match) — astropy represents this as a numpy masked constant, not
    Python None, so `value is not None` silently fails to catch it.
    """
    return None if np.ma.is_masked(value) else value


def _select_point_sources(n_sources: int):
    """Query IRSA TAP for a deterministic sample of clean point-like sources.

    Raises ArchiveAccessError if the query fails or returns too few rows.
    Restricted to specific tileids: an earlier unrestricted query against
    euclid_q1_mer_catalogue hung for 5+ minutes and was abandoned (see
    IMPLEMENTATION_PLAN.md) — this table is not efficiently scanned without a
    tileid filter.
    """
    try:
        from astroquery.ipac.irsa import Irsa
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ArchiveAccessError("astroquery is not installed in this environment") from exc

    tile_list = ",".join(str(t) for t in TILE_IDS)
    query = f"""
        SELECT TOP {n_sources} object_id, ra, dec, fwhm, ellipticity, mag_stargal_sep,
               point_like_prob, gaia_id, tileid, spurious_flag, det_quality_flag
        FROM euclid_q1_mer_catalogue
        WHERE tileid IN ({tile_list}) AND point_like_prob > 0.8 AND vis_det = 1
              AND spurious_flag = 0 AND fwhm > 0 AND fwhm < 2
        ORDER BY object_id
    """
    try:
        result = Irsa.query_tap(query)
        table = result.to_table()
    except Exception as exc:  # noqa: BLE001 - any archive/network failure is fatal here
        raise ArchiveAccessError(f"IRSA TAP query failed: {exc}") from exc

    if len(table) == 0:
        raise ArchiveAccessError(
            f"IRSA TAP query for tiles {TILE_IDS} returned zero point-like sources"
        )
    return table


def _find_vis_science_url(ra: float, dec: float) -> str:
    from astroquery.ipac.irsa import Irsa

    try:
        sia_result = Irsa.query_sia(pos=(ra, dec, 0.001), collection="euclid_DpdMerBksMosaic")
        table = sia_result.to_table()
    except Exception as exc:  # noqa: BLE001
        raise ArchiveAccessError(f"IRSA SIA query failed for ({ra}, {dec}): {exc}") from exc

    vis_science = table[
        [str(inst) == "VIS" and str(subtype) == "science" for inst, subtype in zip(table["instrument_name"], table["dataproduct_subtype"])]
    ]
    if len(vis_science) == 0:
        raise ArchiveAccessError(f"no VIS science mosaic found near ({ra}, {dec})")
    return str(vis_science[0]["access_url"])


def _download_cutout(mosaic_url: str, ra: float, dec: float, out_path: Path) -> None:
    params = {"center": f"{ra},{dec}", "size": str(CUTOUT_SIZE_DEG)}
    try:
        response = requests.get(mosaic_url, params=params, stream=True, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ArchiveAccessError(f"cutout download failed for {mosaic_url}: {exc}") from exc

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            handle.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--n-sources",
        type=int,
        default=15,
        help="Number of point-source cutouts to fetch deterministically.",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    parser.add_argument(
        "--source-catalog",
        type=Path,
        default=Path("data/source_catalog.csv"),
        help=(
            "Companion CSV (not the provenance manifest) carrying per-source "
            "RA/Dec/photometry/point_like_prob needed to run the pipeline."
        ),
    )
    parser.add_argument(
        "--i-have-authorization",
        action="store_true",
        help=(
            "Required flag confirming the operator has explicitly authorized this "
            "real network download in the current session."
        ),
    )
    args = parser.parse_args()

    if not args.i_have_authorization:
        raise SystemExit(
            "Refusing to download real archive data without --i-have-authorization. "
            "This flag exists so the download only runs after the operator has "
            "explicitly confirmed it in the current session (see docs/DATASET_PLAN.md)."
        )

    sources = _select_point_sources(args.n_sources)
    LOGGER.info("Selected %d point-like sources across tiles %s", len(sources), TILE_IDS)

    retrieved_utc = datetime.now(timezone.utc).isoformat()
    n_downloaded = 0
    catalog_rows = []
    for row in sources:
        object_id = int(row["object_id"])
        ra, dec = float(row["ra"]), float(row["dec"])
        product_id = f"euclid_q1_vis_{object_id}"
        out_path = args.out_dir / f"{product_id}.fits"

        try:
            mosaic_url = _find_vis_science_url(ra, dec)
            _download_cutout(mosaic_url, ra, dec, out_path)
        except ArchiveAccessError as exc:
            LOGGER.warning("Skipping object_id=%d: %s", object_id, exc)
            continue

        digest = sha256_file(out_path)
        size = out_path.stat().st_size
        manifest_row = ManifestRow(
            product_id=product_id,
            source="IRSA/Euclid-Q1",
            source_url=SOURCE_URL,
            retrieved_utc=retrieved_utc,
            sha256=digest,
            file_size_bytes=size,
            selection_reason=(
                f"deterministic point-like source sample (point_like_prob>0.8, vis_det=1, "
                f"spurious_flag=0, 0<fwhm<2 arcsec) from tiles {TILE_IDS}, object_id={object_id}, "
                f"cutout size {CUTOUT_SIZE_DEG} deg centered on catalog RA/Dec"
            ),
            licence_or_terms=LICENCE_TERMS,
        )
        append_manifest_row(args.manifest, manifest_row)
        LOGGER.info("Recorded manifest row for %s (%d bytes)", product_id, size)
        n_downloaded += 1

        catalog_rows.append(
            {
                "object_id": object_id,
                "product_id": product_id,
                "ra": ra,
                "dec": dec,
                "fwhm_catalog": float(row["fwhm"]),
                "ellipticity_catalog": float(v) if (v := _masked_scalar(row["ellipticity"])) is not None else "",
                "mag_stargal_sep": float(v) if (v := _masked_scalar(row["mag_stargal_sep"])) is not None else "",
                "point_like_prob": float(row["point_like_prob"]),
                "gaia_id": int(v) if (v := _masked_scalar(row["gaia_id"])) is not None else "",
                "tileid": int(row["tileid"]),
            }
        )

    if n_downloaded == 0:
        raise ArchiveAccessError("no cutouts were successfully downloaded")

    args.source_catalog.parent.mkdir(parents=True, exist_ok=True)
    with args.source_catalog.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SOURCE_CATALOG_COLUMNS))
        writer.writeheader()
        writer.writerows(catalog_rows)

    print(f"Downloaded and recorded {n_downloaded} cutouts under {args.out_dir}")
    print(f"Wrote source catalog with {len(catalog_rows)} rows to {args.source_catalog}")


if __name__ == "__main__":
    main()
