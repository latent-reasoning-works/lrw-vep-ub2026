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
| Encoder primitive (notebook scope, HF transformers ESM-1b) | `vep_utils.ESM1bEncoder` — the live-demo prototype. Library equivalent + protocol contract: `ARCHITECTURE.md` §3. |
| Variant-scoring primitives (notebook scope) | `vep_utils.{encode_variant, truncate_around_mutation, validate_sequence, validate_mutation, parse_mutation, apply_mutation, load_fasta}`. Library equivalents + the full scorer list: `ARCHITECTURE.md` §3 + §5. |
| FASTA loader | `vep_utils.load_fasta` |
| Cached S3 scores (for the figure's fast path) | `data/s3_scores.npz` (`variant_id`, `gene`, `label`, `delta_norm`, `llr`, `seq_len`) |
| Script that regenerates `s3_scores.npz` | `../scripts/cache_s3_scores.py` (notebook-scoped; lives alongside the infra scripts in `../scripts/` but is **not** a numbered analysis script) |
| Tests for the primitives | `test_vep_utils.py` |
| Expected AUROCs + Brandes 2023 anchor + lineage | `../PROVENANCE.md` — **canonical**. (The manifest's AUROC field is a build-time snapshot; PROVENANCE is what's updated when the cache regenerates.) |
| What's been run (chronicle) | `../EXPERIMENT_LOG.md` |
| Archived predecessors of the dataset (historical) | `data/_archive/` |
| Pinned env for local + Colab attendees | `pyproject.toml` + `uv.lock` (uv-native: `uv sync`); `requirements-workshop.txt` (pip path; same floors). The notebook's `s1-install` cell mirrors the same pins inline so Colab works without an external fetch. |
| Reproducibility validator | `validate.py` — runs the s1+s2 (quick) or s1+s2+s3 (full) cell logic and asserts the computed values match `data/workshop_set_manifest.json` to documented tolerances. The workshop's "did my setup work" check. |
| Agent-driven paper-prep smoke test | `validate_paper.py` — `--prepare` cleans `_paper_validation_tmp/` and emits a self-contained prompt; running the script after a subagent has produced the paper validates the TeX structure, DOI citation, figure include, headline AUROC, and the PDF page count. Ships its own LaTeX renderer: tectonic from PATH, then `~/.cache/lrw-vep-ub2026/tectonic/`, then `--fetch-tectonic` to auto-download. `--real-paper` builds `paper/main.tex` (structural compile only — TODO placeholders are expected). |
| Literal-notebook smoke test | `validate_notebook.py` — executes every code cell in `01_workshop_followalong.ipynb` via nbconvert's `ExecutePreprocessor` and reports per-cell PASS/FAIL. Catches a different class of bugs from `validate.py`: a typo in `s3-distributions`, a stale import in `s2-visualize`, a `plt.show()` glitch under the non-interactive backend. Numbers come from `validate.py`; this is the "cells don't explode" check. ~20 s when the s3 cache short-circuit fires; ~4 min cold. |
| Audience-pick gene smoke | `validate_genes.py` — for each bundled gene (TP53/BRCA2/PTEN/MLH1) loads the clinvar/<gene>/ snapshot, picks N P / N B, encodes via `vep_utils.ESM1bEncoder` (with `truncate_around_mutation` for long proteins like BRCA2 at 3418 aa), and asserts pathogenic mean LLR < benign mean LLR. Workshop-day insurance for "do TP53 instead". ~18 s on MPS. |

## Running the notebook locally

For attendees not on Colab:

```bash
cd experiments/notebooks
# uv (recommended — uses pyproject.toml + uv.lock for bit-identical pins):
uv sync                                    # creates .venv/, installs locked deps
uv run python validate.py --quick          # ~10s: confirms install reproduces demo-pair LLRs
uv run jupyter notebook 01_workshop_followalong.ipynb

# pip (works against the same floors via requirements-workshop.txt):
pip install -r requirements-workshop.txt
python validate.py --quick
jupyter notebook 01_workshop_followalong.ipynb
```

The notebook's `s1-install` cell is a no-op when these are already installed — pip detects "Requirement already satisfied" and skips.

On Colab: just run cells top-to-bottom; `s1-install` brings the env up.

If something breaks on the env, the pins live in three places (in priority order: `pyproject.toml`/`uv.lock` for the uv path, `requirements-workshop.txt` for the pip path, the inline `s1-install` cell for Colab). When bumping a floor, update all three to keep them in sync.

## Validating reproducibility

`validate.py` is the workshop's "did my setup work" check. It runs the same logic as the notebook cells and asserts the computed values match `data/workshop_set_manifest.json` within documented tolerances. Two modes:

```bash
cd experiments/notebooks
python validate.py --quick   # ~10s: schema + demo pair + 5-variant sample
python validate.py --full    # ~4 min: regenerates 500-variant cache, asserts AUROC + CI95
```

Quick mode runs:
- Stage 1: schema (500 rows, 250P/250B, 400 genes, required columns)
- Stage 2: demo pair encoding (pathogenic L1854P + benign P1859R LLRs match the cached `analysis/data/demo_pair_scores.json` within ±0.05; sign convention check)
- Stage 3a: 5-variant sample (all LLRs negative; pathogenic mean < benign mean)

Full mode adds:
- Stage 3b: regenerates the full 500-variant cache from scratch, computes AUROCs + bootstrap CI95, asserts they match the manifest's `llr_auroc` (±5e-4), `delta_norm_auroc` (±5e-4), and both CI95 bounds (±1e-3).

When the validator fails, the per-check FAIL lines name the diverging value and the tolerance. Common causes are listed in the failure footer (wrong `transformers` version, stale cache, cross-device numerical drift).

**Use this when:** verifying your local install before the workshop; debugging a divergent number on someone else's machine; confirming a fix didn't break the headline numbers.

`validate_notebook.py` is the third validator — it executes every code cell in `01_workshop_followalong.ipynb` via `nbconvert.ExecutePreprocessor` and reports per-cell PASS/FAIL. Catches cell-level bugs (typo, broken import, plot backend glitch) that `validate.py` doesn't see because `validate.py` calls the primitives directly, not the cells.

```bash
cd experiments/notebooks
uv run python validate_notebook.py     # ~20 s when the s3 cache short-circuit fires
```

15 code cells span S1 → S3 (S4 is markdown-only handoff prompts; no execution). The script exits non-zero on any cell error and prints the failing cell's id, first line, and traceback ename/evalue.

More targeted checks:

```bash
# Audience-pick gene smoke (TP53 / BRCA2 / PTEN / MLH1, ~18 s on MPS):
cd experiments/notebooks && uv run python validate_genes.py

# Library-scope path (fair-esm + manylatents.dogma.vep, run from the submodule venv):
experiments/tools/manylatents-omics/.venv/bin/python experiments/scripts/verify_library_vep.py

# Real paper compile (paper/main.tex with its TODO placeholders — structural only):
cd experiments/notebooks && uv run python validate_paper.py --real-paper

# Slide-1 fallback (regenerate the first-prompt UMAP figure, ~3-5 min on MPS):
experiments/notebooks/.venv/bin/python experiments/scripts/run_first_prompt.py
```

`verify_library_vep.py` exercises the just-upstreamed library scope (notebook validators only cover notebook-scope `vep_utils.ESM1bEncoder`). It encodes the demo pair via `ESMEncoder.encode_with_logits` + `manylatents.dogma.vep.compute_llr` and asserts cross-library agreement with the notebook cache (LLR_TOL 0.05; in practice diff is 0 on identical hardware). `validate_paper.py --real-paper` builds `paper/main.tex` and asserts structural compile only — TODO sections are expected.

`validate_paper.py` is the matching check for the other half of the workshop story: prompt → biological result is covered by `validate.py`; prompt → paper edit is covered here. Two-phase:

```bash
cd experiments/notebooks
python validate_paper.py --prepare    # wipe + recreate _paper_validation_tmp/, emit PROMPT.md
# now, from your Claude Code session, spawn a subagent with PROMPT.md
python validate_paper.py              # validate what the agent produced
```

Per-stage checks: required files present (main.tex + references.bib), TeX structure (NeurIPS preprint style, required sections, `\cite` + `\bibliography`), Brandes DOI present in the bib, cite-keys resolve, headline AUROC mentioned, and a 2-page PDF build. The workdir is gitignored, so re-running `--prepare` is a clean slate.

The validator ships its own LaTeX renderer to keep the smoke test self-contained — if `tectonic` isn't on PATH it looks at `~/.cache/lrw-vep-ub2026/tectonic/`, and `--fetch-tectonic` will pull the binary from the official tectonic GitHub releases on first use (~50 MB, cached forever). Page count is parsed directly from the PDF's compressed object streams, so no `pdfinfo` / `mdls` / poppler dep.

**Use this when:** verifying the agent-driven paper-prep pipeline works end-to-end; debugging a stuck or hallucinating subagent (compare its output to the prompt spec); demonstrating "prompt → paper" to a workshop attendee.

## Conventions

- **Position indexing.** `protein_pos` in TSV is **0-indexed**. HGVS strings (`L1854P`) are **1-indexed**. Convert at the boundary: `pos1 = int(row['protein_pos']) + 1`.

- **Sequence-length limit.** ESM-1b's effective max is **`MAX_LEN = 1022`** residues (the position-embedding table has 1024 slots; the tokenizer adds BOS + EOS, taking 2). For any variant in a protein longer than `MAX_LEN`, truncate around the mutation:
  ```python
  seq_t, pos_t = truncate_around_mutation(seq, pos1, window=encoder.MAX_LEN)
  ```
  This implements Brandes 2023's "option 4" strategy (variant-centered single window). Brandes' Extended Data Fig. 6a shows it's within noise of their sliding-window weighted-average method at `w=1022`.

- **Encoder interface (notebook scope).** The prototype's API is `.encode(seq) -> (embedding, logits)` with `.MAX_LEN` (HF-transformers convention; deliberately single-method). The library uses a different shape — see `ARCHITECTURE.md` §3 for the two-API table. New **notebook-scope** backends (hosted inference, batched, distilled) subclass `ESM1bEncoder` and live in `vep_utils.py`. Library-scope subclasses (`FoundationEncoder`) live upstream. For "no local GPU" prompts, the notebook scope is canonical.

- **Backend parity protocol.** When adding a new encoder backend, parity-test it against `ESM1bEncoder` on a 10-variant subsample of `data/workshop_set.tsv` before declaring it usable. Expected agreement: `delta_norm` and `llr` within 3 decimals (i.e. abs diff ≤ 5e-4); embedding cosine similarity ≥ 0.99. Add the parity test to `test_vep_utils.py` and log latency-per-call + cost-per-call (if hosted) in `../EXPERIMENT_LOG.md`.

- **Don't bypass `vep_utils`.** If you reach for `transformers` / `fair-esm` / a model SDK directly in notebook code, add the missing primitive to `vep_utils` first. The notebook should import only from `vep_utils` and the standard scientific stack (numpy, pandas, sklearn, matplotlib, seaborn).

- **Cache mtime is the freshness signal — for cell-driven runs.** If `s3_scores.npz` is older than `vep_utils.py`, the cache is stale. The s3-score-loop cell short-circuits to a cache read when fresh, so the live demo's figure-pass is fast. Regenerate via `../scripts/cache_s3_scores.py --device {mps,cuda,cpu}`.
- **Agent-driven runs of the S3 prompt should regenerate, not shortcut.** The s3-agent-prompt asks the agent to *run* S2's pattern across 500 variants — actually run it. The cache is described as *output* (`Write the result to data/s3_scores.npz`), never as input. An agent that reads the cache to satisfy the s3 prompt has misread the contract; the audience needs to see the encoder churn, not a `np.load` in 30ms.

- **Notebook cell tags.** Cells are tagged with a stage prefix (`s1-*`, `s2-*`, `s3-*`, `s4-*`). When patching, find by tag id, not by index. **Markdown cells are the workshop's teaching voice — do not modify them without explicit user instruction.** Code cells are fair game when the task requires it. Stage purposes:

  | Stage | Purpose | Key code cells |
  |---|---|---|
  | S1 | Bootstrap: install deps, fetch assets, load `df` + `wt_seqs`, EDA | `s1-install`, `s1-download`, `s1-load`, `s1-eda` |
  | S2 | Prototype end-to-end on the canonical demo pair (BRCA1 L1854P + P1859R) | `s2-load-encoder`, `s2-pick-pair`, `s2-encode`, `s2-visualize`, `s2-interactive` |
  | S3 | Scale to 500 variants; ROC + diagnostic figures | Compute: `s3-score-loop` (cache + table), `s3-auroc` (CIs). **Four figure-producing cells**: `s3-distributions`, `s3-roc`, `s3-per-gene`, `s3-seqlen`. When extracted to numbered analysis scripts, filenames default to `s3_<panel>.{pdf,png}` in `../analysis/figures/`. |
  | S4 | Handoff prompts — agent-driven follow-ups (writing, sweeping, serving); not executed in the notebook | `s4-paper-prompt`, `s4-sweep-prompt`, `s4-hosted-prompt` (all markdown) |

  Agent-prompt markdown cells follow the pattern `s{N}-agent-prompt` (one each for S1, S2, S3) plus the three `s4-*-prompt` variants. These are the surfaces the workshop demos as drivable by an agent.

## When to escalate

- **The dataset doesn't fit your need.** Don't silently re-spec the validation set inside an unrelated task. Surface as an explicit decision with trade-off framing. The four-revision build history + catch ledger lives in `../PROVENANCE.md` → "Validation set lineage"; the current spec is `--spec v2` in `../scripts/build_validation_set.py`.

- **A workshop attendee wants a different gene** (TP53, BRCA2, PTEN, MLH1). The data-regeneration block in the root [`CLAUDE.md`](../../CLAUDE.md) handles this for the **demo encode path** (Phase 1: BRCA1 → TP53 swap for the Encode+UMAP demo). Pre-bundled gene pulls live in `../data/clinvar/<gene>/`. The notebook's **S3 validation set is separate** — `data/workshop_set.tsv` has a fixed multi-gene composition (400 unique disease genes; see `data/workshop_set_manifest.json`). Rescoping S3 is a different operation; if asked, escalate per the validation-set-decision rule rather than silently swapping.

- **The encoder interface needs to change.** That's a `vep_utils.py` change with a corresponding test in `test_vep_utils.py`. Don't paper over a shape mismatch in one call site.

- **You need GPU but the local machine is CPU-only.** The hosted-encoder path (S4 in the notebook) is the answer — subclass `ESM1bEncoder` with a remote-inference backend.

## What this directory is NOT

- Not the place for new analysis. Numbered scripts that produce paper figures go in `../analysis/` and follow `../CLAUDE.md`'s contract.
- Not the place for raw experiment outputs. Those live in `../outputs/` (gitignored) or as Hydra run directories.
- Not the place for tool internals. The encoder model code lives upstream in `transformers`; we wrap it in `vep_utils.ESM1bEncoder`.
