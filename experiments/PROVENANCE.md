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
  fp32 on MPS. Variant pair: BRCA1 L1854P (pathogenic, `clinvar_55631`)
  vs BRCA1 P1859R (benign, `clinvar_55634`).
- Inputs (n=499): `notebooks/data/s3_scores.npz`
  (sha256 `74225259…b09b865a1`, 499 rows: 250 P + 249 B across
  ~280 genes) — pre-scored by `scripts/cache_s3_scores.py` from
  `experiments/notebooks/data/validation_variants.csv` (500 rows
  source; one variant skipped at encode time). Same encoder as n=2.
  AUROCs computed via `sklearn.metrics.roc_auc_score`: delta_norm
  0.6065, LLR 0.6381.
- Inputs (n=36,537): no local data — literature anchor from
  Brandes et al., *Nat. Genet.* 2023, Fig 2B (ESM-1b zero-shot,
  ClinVar missense). AUROC 0.74 plotted as a horizontal reference on
  the same FPR/TPR axes as panel B. Curve not reproduced; citation
  is the data. Constants live in
  `01_resolution_panels.py::BRANDES_2023_CLINVAR_{AUROC,N}` —
  verify against the source paper before the May 23 deck.
- Outputs: `analysis/figures/resolution_panels.{pdf,png}`,
  `analysis/results/resolution_panels.csv`.
- Generated: 2026-05-11 against `manylatents-omics` `cceb1fa`.
  Regenerate post-2.11 with `manylatents.dogma.vep` to keep n=2 and
  n=499 parity-clean against Path B/C.
