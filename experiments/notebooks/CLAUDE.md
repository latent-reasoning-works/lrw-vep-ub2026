# Workshop notebook surface

> The live-demo notebook (`01_workshop_followalong.ipynb`) + its primitives
> (`vep_utils.py`) + its data (`data/`). An agent landing here should be
> able to: audit the dataset, score variants, swap encoder backends,
> regenerate the score cache — without being told which file to open.

**Read first:** root [`CLAUDE.md`](../../CLAUDE.md) for the workshop demo
wiring, then [`../CLAUDE.md`](../CLAUDE.md) for the analysis-script API
contract. This file is the notebook-specific orientation.

## Where things live

| If you need… | Look at |
|---|---|
| The variant dataset for scoring | `data/workshop_set.tsv` (TSV; columns: `variant_id`, `gene`, `protein_pos`, `aa_ref`, `aa_alt`, `clinical_significance`, `label`, `uniprot_id`, `isoform_validated`) |
| The matching WT protein sequences | `data/workshop_set_proteins.fasta` (one record per `variant_id`) |
| The dataset's schema, conventions, build provenance | `data/workshop_set_manifest.json` (includes ClinVar source, label scope, AUROCs, bootstrap CI95, literature anchor) |
| The S2 demo pair (canonical pathogenic + benign for the live demo) | `data/demo_pair.tsv` (2 rows; current pick: BRCA1 L1854P + P1859R) |
| Encoder primitive (current: ESM-1b via HF transformers) | `vep_utils.ESM1bEncoder` |
| Variant-scoring primitives | `vep_utils.{encode_variant, truncate_around_mutation, validate_sequence, validate_mutation, parse_mutation, apply_mutation}` |
| FASTA loader | `vep_utils.load_fasta` |
| Cached S3 scores (for the figure's fast path) | `data/s3_scores.npz` (`variant_id`, `gene`, `label`, `delta_norm`, `llr`, `seq_len`) |
| Script that regenerates `s3_scores.npz` | `../scripts/cache_s3_scores.py` |
| Tests for the primitives | `test_vep_utils.py` |
| Expected AUROCs + Brandes 2023 anchor + lineage | `../PROVENANCE.md` |
| What's been run (chronicle) | `../EXPERIMENT_LOG.md` |
| Archived predecessors of the dataset (historical) | `data/_archive/` |

## Conventions

- **Position indexing.** `protein_pos` in TSV is **0-indexed**. HGVS strings (`L1854P`) are **1-indexed**. Convert at the boundary: `pos1 = int(row['protein_pos']) + 1`.

- **Sequence-length limit.** ESM-1b's effective max is **`MAX_LEN = 1022`** residues (the position-embedding table has 1024 slots; the tokenizer adds BOS + EOS, taking 2). For any variant in a protein longer than `MAX_LEN`, truncate around the mutation:
  ```python
  seq_t, pos_t = truncate_around_mutation(seq, pos1, window=encoder.MAX_LEN)
  ```
  This implements Brandes 2023's "option 4" strategy (variant-centered single window). Brandes' Extended Data Fig. 6a shows it's within noise of their sliding-window weighted-average method at `w=1022`.

- **Encoder interface.** Encoders implement `.encode(seq) -> (embedding, logits)` with `.MAX_LEN`. New backends (hosted inference, batched, distilled) **subclass this interface** and live in `vep_utils.py` alongside `ESM1bEncoder`. The S3 scoring loop is interface-agnostic.

- **Don't bypass `vep_utils`.** If you reach for `transformers` / `fair-esm` / a model SDK directly in notebook code, add the missing primitive to `vep_utils` first. The notebook should import only from `vep_utils` and the standard scientific stack (numpy, pandas, sklearn, matplotlib, seaborn).

- **Cache mtime is the freshness signal.** If `s3_scores.npz` is older than `vep_utils.py`, the cache is stale. Regenerate via `../scripts/cache_s3_scores.py --device {mps,cuda,cpu}`.

- **Notebook cell tags.** Cells are tagged (`s1-download`, `s1-load`, `s2-pick-pair`, `s2-encode`, `s3-score-loop`, `s3-roc`, …). When patching, find by tag id, not by index. **Markdown cells are the workshop's teaching voice — do not modify them without explicit user instruction.** Code cells are fair game when the task requires it.

## When to escalate

- **The dataset doesn't fit your need.** Don't silently re-spec the validation set inside an unrelated task. Surface as an explicit decision with trade-off framing. The build history is in `../../docs/internal/WORKSHOP_SET_LINEAGE.md`; the current spec is `--spec v2` in `../scripts/build_validation_set.py`.

- **A workshop attendee wants a different gene** (TP53, BRCA2, PTEN, MLH1). The data-regeneration block in the root [`CLAUDE.md`](../../CLAUDE.md) handles this. Pre-bundled gene pulls live in `../data/clinvar/<gene>/`.

- **The encoder interface needs to change.** That's a `vep_utils.py` change with a corresponding test in `test_vep_utils.py`. Don't paper over a shape mismatch in one call site.

- **You need GPU but the local machine is CPU-only.** The hosted-encoder path (S4 in the notebook) is the answer — subclass `ESM1bEncoder` with a remote-inference backend.

## What this directory is NOT

- Not the place for new analysis. Numbered scripts that produce paper figures go in `../analysis/` and follow `../CLAUDE.md`'s contract.
- Not the place for raw experiment outputs. Those live in `../outputs/` (gitignored) or as Hydra run directories.
- Not the place for tool internals. The encoder model code lives upstream in `transformers`; we wrap it in `vep_utils.ESM1bEncoder`.
