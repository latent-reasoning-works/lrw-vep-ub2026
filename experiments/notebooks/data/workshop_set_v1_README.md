# workshop_set_v1 — ClinVar workshop validation set

**Generated:** 2026-05-12T05:06:03Z
**Script:** `experiments/scripts/build_validation_set.py`
**Manifest:** `workshop_set_v1_manifest.json` (canonical record;
read it for filter rules, seed, ClinVar sha, gene→UniProt map)

## What's in the set

`500` ClinVar missense variants across `439`
unique disease genes (`393` singletons). Label-balanced:
`250` pathogenic +
`250` benign, drawn by
stratified random sampling (seed `42`, no replacement,
no per-gene cap).

Every variant is canonical-isoform-validated against the UniProt
reviewed human entry for its gene: `WT[pos-1] == ref_aa` is required
to enter the universe. Clinical significance is restricted to the
high-confidence set {Pathogenic, Likely_pathogenic, P/LP, Benign,
Likely_benign, B/LB} — "Uncertain", "Conflicting", and lower-grade
labels are excluded.

## How to re-derive

```bash
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/scripts/build_validation_set.py
```

Cold-cache runtime ~15–90 min (depends on ClinVar dump download +
UniProt REST throughput). Cached runs <1 min.

## What this set does NOT claim

- **Not gene-stratified.** Hot genes (BRCA1, TP53, BRCA2, etc.) are
  over-represented relative to a per-gene-flat draw, in proportion
  to their ClinVar density.
- **Not BRCA1-specific.** Panel A of `resolution_panels.pdf` uses a
  separate BRCA1 demo pair; this is a multi-gene workshop set.
- **Not unfiltered ClinVar.** Brandes et al. 2023 (Fig 2B, n=36,537)
  report on unfiltered ClinVar. Our set drops "Uncertain"/"Conflicting"
  + requires canonical isoform — easier subset; AUROCs are not
  directly comparable.

## Deprecated predecessors

- `_archive/validation_variants_v0_2026-05-06.csv` — pre-bundled set
  with no producer script; isoform handling opaque.
- `_archive/validation_variants_v1_in_flight_2026-05-11.csv` —
  per-gene-capped variant of this script; rolled back because the
  cap was unsanctioned and skewed the gene distribution.
