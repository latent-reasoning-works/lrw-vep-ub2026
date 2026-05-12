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
- Inputs (n=500): `notebooks/data/s3_scores.npz`
  (sha256 `87aa972a1e45…`, 500 rows: 250 P + 250 B across
  **400 unique genes**) — pre-scored by `scripts/cache_s3_scores.py`
  from `experiments/notebooks/data/workshop_set_v2.tsv` (sha256
  `85aa5903d3d4…`) + matching FASTA. Same encoder as n=2.
  AUROCs via `sklearn.metrics.roc_auc_score`:
  delta_norm **0.6703** (CI95 [0.622, 0.717]),
  LLR **0.9250** (CI95 [0.900, 0.947]).
  **Brandes 2023's 0.905 is inside our CI95** — statistically
  indistinguishable. See "Validation set lineage" below for the
  v0 → v2 history.
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

### Validation set lineage (v0 → workshop_set_v2)

The current panel B dataset is **`workshop_set_v2`** — produced by
`experiments/scripts/build_validation_set.py --spec v2`. Full lineage
is documented in `docs/internal/WORKSHOP_SET_LINEAGE.md` (the
four-revision history with rationale at each step). Summary here:

| version | label scope | isoform | producer | LLR AUROC | status |
|---|---|---|---|---|---|
| v0 (2026-05-06, pre-bundled) | canonical-only | unverified | none in repo | 0.638 | **deprecated** — `_archive/validation_variants_v0_2026-05-06.{csv,fasta}` |
| v1 in-flight (per-gene cap) | canonical-only | UniProt-validated | `build_validation_set.py` | 0.925 | **deprecated** — unsanctioned per-gene cap, see `_archive/*_v1_in_flight_*` |
| workshop_set_v1 (no cap) | canonical-only | UniProt-validated | `--spec v1` | 0.944 | **deprecated** — replaced by v2 for Brandes comparability; files still on disk |
| **workshop_set_v2 (current canonical)** | **Brandes-match (canonical + Conflicting via ClinSigSimple)** | **UniProt-validated** | **`--spec v2`** | **0.925** | **shipped** — 2026-05-11 |

**workshop_set_v2 files (sha256, all current canonical):**

| file | sha256 (12 char) |
|---|---|
| `experiments/notebooks/data/workshop_set_v2.tsv` | `85aa5903d3d4` |
| `experiments/notebooks/data/workshop_set_v2_proteins.fasta` | `5df061810f48` |
| `experiments/notebooks/data/workshop_set_v2_manifest.json` | (includes bootstrap CI95 and Brandes anchor) |
| `experiments/notebooks/data/s3_scores.npz` | `87aa972a1e45` |

**ClinVar source:** `experiments/cache/variant_summary.txt.gz` (gitignored,
sha256 `61e2b1fd3123…`). Recorded in the manifest.

**Composition (workshop_set_v2):**

| dimension | value |
|---|---|
| Total rows | 500 (exactly 250 P + 250 B) |
| Unique genes | 400 |
| Singletons | 338 (84%) |
| Conflicting-binarized entries | 166 (33%) — the v2 addition |
| Canonical-text entries | 334 (Pathogenic/LP/B/LB etc.) |
| BRCA1 rows | 5 (re-appears in v2 via Conflicting-binarized) |
| BRCA2 rows | 7 |
| Top gene by count | FBN1 (n=11) |

**Bootstrap CI95 (10,000 resamples, seed 42):**
- delta L2 norm AUROC: 0.6703  [0.622, 0.717]
- LLR AUROC: **0.9250  [0.900, 0.947]**
- Brandes 2023 (n=36,537) LLR AUROC: 0.9050 — **inside v2's CI95**

**Caveats for downstream framing:**
1. AUROCs are a 400-gene mixture. Slide narration: "ClinVar workshop
   set across 400 disease genes," not "BRCA1 validation." (BRCA1 is
   present in v2 with 5 rows but is not over-represented.)
2. Per-gene P/B balance is not enforced. Hot genes (FBN1 11P/0B,
   LDLR 6P/0B, etc.) have label-skewed distributions. Label balance
   is global only.
3. Two distinct data layers in the repo:
   - `experiments/data/clinvar/variants.tsv` — BRCA1-only; the demo
     pair and audience-pick gene-bundle flow live here.
   - `experiments/notebooks/data/workshop_set_v2.tsv` — the multi-gene
     validation set; the notebook's S3 loop + `cache_s3_scores.py`
     consume it.
