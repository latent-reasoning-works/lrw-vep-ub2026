# workshop_set — ClinVar workshop validation set

**Generated:** 2026-05-12T05:30:14Z
**Script:** `experiments/scripts/build_validation_set.py --spec v2`
**Manifest:** `workshop_set_manifest.json` (canonical record;
read it for filter rules, seed, ClinVar sha, gene→UniProt map)

## What's in the set

`500` ClinVar missense variants across `400`
unique disease genes (`338` singletons). Label-balanced:
`250` pathogenic +
`250` benign, drawn by
stratified random sampling (seed `42`, no replacement,
no per-gene cap).

Every variant is canonical-isoform-validated against the UniProt
reviewed human entry for its gene: `WT[pos-1] == ref_aa` is required
to enter the universe.

Label binarization matches Brandes et al. 2023 (Nat. Genet.): canonical Pathogenic*/Benign* text classes are used directly; Conflicting* entries are binarized via ClinVar's `ClinSigSimple` field (1 if any submitter classified as pathogenic, 0 if all classified as benign). Uncertain*, drug-response, risk-factor, protective, association, and "other" entries are dropped.

## How to re-derive

```bash
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/scripts/build_validation_set.py --spec v2
```

Cold-cache runtime ~10 min (depends on ClinVar dump download +
UniProt REST throughput). Cached runs <1 min.

## What this set does NOT claim

- **Not gene-stratified.** Hot genes (BRCA1, TP53, BRCA2, etc.) are
  over-represented in proportion to their ClinVar density.
- **Not BRCA1-specific.** Panel A of `resolution_panels.pdf` uses a
  separate BRCA1 demo pair; this is a multi-gene workshop set.

Comparable in methodology to Brandes' AUROC reporting on ClinVar — same label-scope rule (`ClinSigSimple`-based binarization of conflicts), same canonical-isoform discipline. AUROC on this 500-variant slice should land in the same regime as Brandes' n=36,537 number, modulo small-sample variance.

## Deprecated predecessors

- `_archive/validation_variants_v0_2026-05-06.csv` — pre-bundled set
  with no producer script; isoform handling opaque.
- `_archive/validation_variants_v1_in_flight_2026-05-11.csv` —
  per-gene-capped variant; rolled back because the cap was
  unsanctioned and skewed the gene distribution.
- `_archive/workshop_set_v1_canonical-only_2026-05-11.tsv` — strict canonical-only
  binarization; replaced by v2 for Brandes comparability.
