# Dataset Plan

## Mode

**real public Euclid Q1 VIS products**

## Official sources and literature seeds

- Euclid Q1 overview, arXiv:2503.15302
- Euclid Q1 VIS processing, arXiv:2503.15303
- Euclid Q1 MER processing, arXiv:2503.15305
- Euclid mission overview, arXiv:2405.13491
- Euclid mission design, arXiv:1610.05508

## Acquisition rules

- Prefer official mission/archive endpoints and author-maintained catalogue deposits.
- Record product identifier, query, retrieval UTC, source URL, file size, checksum and licence/terms.
- Do not commit large raw FITS, HDF5 or catalogue files.
- Store a deterministic manifest under `data/manifest.csv`.
- Store only a tiny, clearly labelled synthetic/example dataset in `data/example/`.
- Never replace inaccessible real data with fabricated values while presenting them as observations.

## Required manifest columns

`product_id, source, source_url, retrieved_utc, sha256, file_size_bytes, selection_reason, licence_or_terms`

## FAIR contract

Every derived product must point to the raw product ID, software commit, configuration hash and transformation script.
