# Experiment Log — lrw-vep-ub2026

Append-only chronicle of non-trivial runs. One entry per run that produced shipped data, including each successful workshop-demo run. **Add the wandb run URL** so a reader can click through.

## Format

```markdown
## YYYY-MM-DD — <experiment_or_script_name> <smoke|run>

- **Pin:** manylatents-omics commit `<sha>`, version `x.y.z`
- **Cmd:** `.venv/bin/python -m manylatents.main +experiment=<name>`
- **Output:** `outputs/<date>/<time>/embeddings/*.npy` + `results/<csv>` if applicable
- **wandb:** https://wandb.ai/<entity>/<project>/runs/<id>
- **Notes:** <what you actually learned — surprises, gotchas, what to fix next>
```

## Worked example (do not treat as a real entry)

```markdown
## 2026-05-06 — encode_esm1b_brca1 run

- **Pin:** manylatents-omics commit `abc1234`, v0.1.2; manylatents v0.1.5
- **Cmd:** `.venv/bin/python -m manylatents.main +experiment=encode_esm1b_brca1`
- **Output:** `outputs/2026-05-06/22-13-04/embeddings/encode_esm1b_brca1.npy` (200 × 1280)
- **wandb:** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/abcd1234
- **Notes:** First demo dry-run. ESM-1b weights cached on second run — first run took ~3 min for download. 18 pathogenic / 27 benign / 155 uncertain among the top 200 BRCA1 variants. Need to think about whether `pathogenicity=all` is the right default for the workshop demo.
```

## Entries

<!-- New entries below this line, most recent first. -->

## 2026-05-06 — encode_esm1b_brca1 + 00_demo_umap.py  (first end-to-end)

- **Pin:** manylatents-omics `cceb1fa` (workshop/lrw-ub2026), v0.1.2; manylatents v0.1.5 from PyPI; fair-esm 2.0.0
- **Cmd (encode):** `cd experiments/tools/manylatents-omics && .venv/bin/python -m manylatents.main --config-path=$(pwd)/../../configs/manylatents-omics experiment=encode_esm1b_brca1`
- **Cmd (umap):** `experiments/tools/manylatents-omics/.venv/bin/python experiments/analysis/00_demo_umap.py`
- **Output:** `experiments/tools/manylatents-omics/outputs/2026-05-06/21-40-24/embeddings.pt` (200 × 1280 ESM-1b embeddings + labels + variant_ids); `experiments/analysis/results/demo_umap_brca1.csv`; `experiments/analysis/figures/demo_umap_brca1.{pdf,png}`
- **wandb (encode):** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/bwi7x5i3
- **wandb (umap):** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/udjlt2ok
- **Data:** ClinVar `variant_summary.txt.gz` (NCBI), filtered to BRCA1 missense GRCh38 ≥1-star → 1000 variants; ClinVarDataModule then dropped VUS in `pathogenicity=all` mode → 200 P/B used by encoder. Final split: 131 benign / 69 pathogenic.
- **Notes:** First wired-up demo. Five harness gaps surfaced and fixed in one upstream commit + one local commit:
  1. `+experiment=...` (add) is wrong; must be `experiment=...` (override) — `experiment` is already in `/config`'s defaults.
  2. The experiment YAML can't include `/config` in its own defaults — that creates an infinite recursion when loaded via `experiment=...`. Drop the entry; the parent already loads it.
  3. `paths.output_dir` isn't available without `/config`; use `${hydra:runtime.output_dir}` instead.
  4. `BatchEncoder` needs `_recursive_: false` on its instantiate, otherwise Hydra eagerly constructs the inner `ESMEncoder` and BatchEncoder fails when it tries to instantiate again.
  5. wandb personal entities are disabled on free accounts; route to a team (`cesar-valdez-mcgill-university`).

  ESM-1b encoded all 200 sequences in 4:32 on Mac arm64 MPS (1.36 s/seq). First-time wall clock including weights download was ~7 min. Cached, the demo will be ~5 min end-to-end. UMAP step adds ~5 s.

