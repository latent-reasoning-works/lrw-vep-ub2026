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
  (sha256 `d11cc7f2fc0c…`, 500 rows: 250 P + 250 B across
  **400 unique genes**) — pre-scored by `scripts/cache_s3_scores.py`
  from `experiments/notebooks/data/workshop_set.tsv` (sha256
  `355822298e09…`) + matching FASTA. Same encoder as n=2.
  AUROCs via `sklearn.metrics.roc_auc_score`:
  delta_norm **0.6718** (CI95 [0.623, 0.719]),
  LLR **0.929** (CI95 [0.906, 0.950]).
  **Brandes 2023's 0.905 sits 0.001 below our CI95 lower bound**
  (0.906) — well within Brandes' own standard-error band for
  n=36,537. See "Validation set lineage" below for the v0 → v2
  history and "Long-sequence handling" below for the methodology
  comparison.
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

### Validation set lineage (four revisions → `workshop_set`)

The current panel B dataset is **`workshop_set`** — produced by
`experiments/scripts/build_validation_set.py --spec v2` (the v2 spec
is recorded in the manifest's `spec` field for audit; the filename
is intentionally unversioned because there is one canonical workshop
set, with a documented history). Full lineage in
`docs/internal/WORKSHOP_SET_LINEAGE.md`. Summary:

| revision | label scope | isoform | producer | LLR AUROC | status |
|---|---|---|---|---|---|
| v0 (2026-05-06, pre-bundled) | canonical-only | unverified | none in repo | 0.638 | **deprecated** — `_archive/validation_variants_v0_2026-05-06.{csv,fasta}` |
| v1 in-flight (per-gene cap) | canonical-only | UniProt-validated | `build_validation_set.py` | 0.925 | **deprecated** — unsanctioned per-gene cap, see `_archive/*_v1_in_flight_*` |
| v1 canonical-only (no cap) | canonical-only | UniProt-validated | `--spec v1` | 0.944 | **deprecated** — replaced for Brandes comparability; see `_archive/workshop_set_v1_canonical-only_*` |
| **`workshop_set` (current canonical, v2 spec)** | **Brandes-match (canonical + Conflicting via ClinSigSimple)** | **UniProt-validated** | **`--spec v2`** | **0.929** | **shipped** — 2026-05-12 (post MAX_LEN=1022 fix) |

**Files (sha256, current canonical):**

| file | sha256 (12 char) |
|---|---|
| `experiments/notebooks/data/workshop_set.tsv` | `355822298e09` |
| `experiments/notebooks/data/workshop_set_proteins.fasta` | `115a822a90a3` |
| `experiments/notebooks/data/workshop_set_manifest.json` | (includes bootstrap CI95 and Brandes anchor) |
| `experiments/notebooks/data/s3_scores.npz` | `d11cc7f2fc0c` |

**ClinVar source:** `experiments/cache/variant_summary.txt.gz` (gitignored,
sha256 `61e2b1fd3123…`). Recorded in the manifest.

**Composition:**

| dimension | value |
|---|---|
| Total rows | 500 (exactly 250 P + 250 B) |
| Unique genes | 400 |
| Singletons | 338 (84%) |
| Conflicting-binarized entries | 166 (33%) — the v2-spec inclusion |
| Canonical-text entries | 334 (Pathogenic/LP/B/LB etc.) |
| BRCA1 rows | 5 (re-appears via Conflicting-binarized) |
| BRCA2 rows | 7 |
| Top gene by count | FBN1 (n=11) |

**Bootstrap CI95 (10,000 resamples, seed 42):**
- delta L2 norm AUROC: 0.6718  [0.623, 0.719]
- LLR AUROC: **0.929  [0.906, 0.950]**
- Brandes 2023 (n=36,537) LLR AUROC: 0.9050 — sits 0.001 below
  our CI95 lower bound (0.906); within Brandes' own SE band for
  n=36,537.

**Caveats for downstream framing:**
1. AUROCs are a 400-gene mixture. Slide narration: "ClinVar workshop
   set across 400 disease genes," not "BRCA1 validation." (BRCA1 is
   present with 5 rows but is not over-represented.)
2. Per-gene P/B balance is not enforced. Hot genes (FBN1 11P/0B,
   LDLR 6P/0B, etc.) have label-skewed distributions. Label balance
   is global only.
3. Two distinct data layers in the repo:
   - `experiments/data/clinvar/variants.tsv` — BRCA1-only; the demo
     pair and audience-pick gene-bundle flow live here.
   - `experiments/notebooks/data/workshop_set.tsv` — the multi-gene
     validation set; the notebook's S3 loop + `cache_s3_scores.py`
     consume it.

### Long-sequence handling (Brandes methodology comparison)

The workshop set includes **236 of 500 variants on proteins >1022 aa**
(the ESM-1b context window, accounting for BOS/EOS — see
`vep_utils.ESM1bEncoder.MAX_LEN`). These are scored via Brandes'
"option 4" strategy: a variant-centered single window at
`window=MAX_LEN=1022`, implemented in `vep_utils.truncate_around_mutation`
and invoked uniformly by `cache_s3_scores.py` and the notebook's
S2-encode + S3-score-loop cells.

Brandes et al.'s own ablation (Extended Data Fig. 6a) shows that at
window size 1,022 — the maximum supported by ESM-1b — no aggregation
method outperformed their preferred sliding-window weighted average,
and the variant-centered single window is within noise of it. Their
headline AUROC of 0.905 (n=36,537) was computed on proteins ≤1022 aa
**only** (Extended Data Fig. 5 caption), explicitly avoiding the
sliding window. Our workshop set therefore covers a *broader* length
distribution than Brandes' benchmark — including the long-protein
slice they excluded — and scores it with the Brandes-validated
single-window method at the same window size.

**Source:** Brandes et al., *Nat. Genet.* 2023, Methods §
"Handling long sequences" and Extended Data Figs. 5 and 6a.
