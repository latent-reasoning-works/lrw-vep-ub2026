# Provenance — lrw-vep-ub2026

Figure → script → CSV mapping. Updated whenever a figure or its inputs change.

Format:

```markdown
## Figure N (§X.Y)

- Script: `analysis/NN_figures.py::figure_<name>()`
- Inputs: `results/<name>.csv`
- Producing script: `analysis/NN_<name>.py`
- Generated: YYYY-MM-DD against <tool> `<sha>`
```

## Resolution panels (slide: Part 2 "Resolution")

- Script: `analysis/01_resolution_panels.py` (3-panel: n=2, n=499, n=36,537 literature anchor)
- Inputs (n=2): `analysis/data/demo_pair_scores.json`
  (sha256 `3a7b8721…699b9b28a`) — pre-scored by
  `scripts/score_demo_pair.py` from the demo pair in
  `experiments/data/demo_pair.json` (sha256 `faf7ac58…a654b08cc`).
  Encoder: HF transformers ESM-1b via `vep_utils.ESM1bEncoder`,
  fp32 on MPS. Variant pair: BRCA1 L1854P (pathogenic, `clinvar_55631`,
  LLR +0.873) vs BRCA1 P1859R (benign, `clinvar_55634`, LLR +0.217).
  **Panel A is LLR-only as of 2026-05-11.** Delta L2 norm bars
  dropped — at n=2 the values (~0.03) sit near zero and dilute the
  LLR contrast. Both metrics still appear in panel B at scale.
  Underlying delta_norm/cosine values remain in `demo_pair_scores.json`
  for anyone who wants them.
- Inputs (n=499): `notebooks/data/s3_scores.npz`
  (sha256 `74225259…b09b865a1`, 499 rows: 250 P + 249 B across
  **437 unique genes**) — pre-scored by `scripts/cache_s3_scores.py`
  from `experiments/notebooks/data/validation_variants.csv`
  (500 rows source; one benign skipped at encode time). Same encoder
  as n=2. AUROCs computed via `sklearn.metrics.roc_auc_score`:
  delta_norm 0.6065, LLR 0.6381. **Cross-gene generalization,
  not BRCA1-specific** — see "Validation set composition" below.
- Inputs (n=36,537): no local data — literature anchor from
  Brandes et al., *Nat. Genet.* 2023, Fig 2B. Single bar at ESM-1b
  zero-shot AUROC 0.905 on ClinVar missense, plus one dashed
  reference line pulled forward from panel B at the measured LLR
  AUROC (0.64, red). Delta L2 norm reference line dropped to keep
  panel C aligned with panel A (also LLR-only); delta_norm is shown
  in panel B only. The floor->ceiling gap (LLR 0.64 -> Brandes
  0.905) is the panel's visual argument. Constant lives in
  `01_resolution_panels.py::BRANDES_2023_CLINVAR_AUROC`.
  **Revision history:**
  - 2026-05-11 (initial): cited AUROC 0.74 on a horizontal-line
    reference — wrong number, wrong figure type. Replaced.
  - 2026-05-11 (correction): rendered as ESM-1b-vs-EVE bar chart on
    ClinVar (0.905 vs 0.885) and HGMD/gnomAD (0.897 vs 0.882).
    Numbers correct but re-litigated a comparison already made on
    slide 3. Replaced.
  - 2026-05-11 (interim): EVE bars removed; panel collapses to one
    bar (ESM-1b ClinVar 0.905) plus two panel B reference lines
    (delta L2 norm + LLR).
  - 2026-05-11 (current): delta L2 norm reference line dropped to
    match panel A's LLR-only treatment. Panel C is now: one bar at
    0.905 + one LLR floor line at 0.64. Single metric across panels
    A and C; both metrics live in panel B where the at-scale
    comparison is the point.
- Outputs: `analysis/figures/resolution_panels.{pdf,png}`,
  `analysis/results/resolution_panels.csv`.
- Generated: 2026-05-11 against `manylatents-omics` `cceb1fa`.
  Regenerate post-2.11 with `manylatents.dogma.vep` to keep n=2 and
  n=499 parity-clean against Path B/C.

### Validation set composition (`notebooks/data/validation_variants.csv`)

This is the dataset behind panel B and the notebook's S3 scoring
loop. It is **not** BRCA1-specific. Recording the composition here
because the slide narration easily implies otherwise.

**Upstream source.** No script in this repo produces these files.
The CSV and the matching FASTA are pre-bundled workshop assets
(mtime 2026-05-06 17:07). The notebook fetches them at runtime from
`https://raw.githubusercontent.com/latent-reasoning-works/lrw-vep-ub2026/main/experiments/notebooks/data/`,
i.e. the same files served raw from this repo's GitHub mirror. The
upstream draw (ClinVar query → label-balanced sample) was done
before this repo's history began and is not reproducible from any
script here — the files are the source of truth.

**Files (sha256 / size / mtime):**
| file | sha256 (12 char) | size | mtime |
|---|---|---|---|
| `experiments/notebooks/data/validation_variants.csv` | `7c4a83683eb7` | 22,981 B | 2026-05-06 17:07 |
| `experiments/notebooks/data/validation_proteins.fasta` | `74b68cc26479` | 366,221 B | 2026-05-06 17:07 |

**Composition (n=500 in source, n=499 in scored set):**

| dimension | value |
|---|---|
| Total source rows | 500 |
| Label balance (source) | 250 pathogenic + 250 benign (deliberately stratified on label) |
| Label balance (scored) | 250 pathogenic + 249 benign (one benign dropped at encode time) |
| Unique genes (source) | **438** |
| Unique genes (scored) | **437** |
| Singletons in source | 392 of 438 (78%) |
| Singletons in scored | 391 of 437 (89%) |
| Genes with ≥10 variants | **0** |
| Top gene by count | COL1A1 (n=6, all pathogenic) |
| BRCA1 rows | **1** — `clinvar_845361`, H40L, Pathogenic/Likely_pathogenic |
| Position range | 0 – 1,566 |
| Variant-id ordering | unsorted; range `clinvar_15070` → `clinvar_4796951` — confirms this is a curated sample, not a top-N slice |

**Caveats for downstream framing:**
1. The 0.6065 / 0.6381 AUROCs are a 437-gene mixture, not BRCA1
   performance. Slide narration should say "ClinVar workshop set
   across 437 disease genes," not "BRCA1 validation."
2. Per-gene P/B balance is broken at the top — COL1A1 has 6 P / 0 B,
   LDLR 4 P / 0 B, etc. Label balance is global only. Any per-gene
   analysis from this set is meaningless for gene-specific claims.
3. Two different data layers easily conflate:
   - `experiments/data/clinvar/variants.tsv` — BRCA1-only; the demo
     pair and the audience-pick gene-bundle flow live here.
   - `experiments/notebooks/data/validation_variants.csv` — this
     438-gene workshop set; the notebook's S3 loop + `cache_s3_scores.py`
     consume it.
