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
- **wandb:** https://wandb.ai/cmvcordova/upper-bound-2026/runs/abcd1234
- **Notes:** First demo dry-run. ESM-1b weights cached on second run — first run took ~3 min for download. 18 pathogenic / 27 benign / 155 uncertain among the top 200 BRCA1 variants. Need to think about whether `pathogenicity=all` is the right default for the workshop demo.
```

## Entries

<!-- New entries below this line, most recent first. -->

