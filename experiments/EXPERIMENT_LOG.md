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

## 2026-05-14 — Repo lean pass (log + provenance trim, archive)

- Collapsed the 2026-05-07 cluster (four `encode_esm1b_brca1 + 00_demo_umap.py` re-runs) into one consolidated entry; load-bearing findings (`data_dir` pinning, `WANDB_INIT_TIMEOUT`, MPS 4.5× speedup, `uv run` sandbox overlay) preserved.
- Collapsed PROVENANCE.md's "Resolution panels" 2026-05-11 panel-C revision history (initial → correction → interim → current) to the current-state description. The earlier iterations were useful while in flight; once the figure settled they were stale.
- Archived `experiments/scripts/verify_llr_independent.py` → `experiments/scripts/_archive/`. Its job was to cross-check the pre-Brandes LLR via fair-esm; that bug is fixed and upstreamed (submodule bump 2026-05-14), so the script has no live caller. Kept in `_archive/` rather than deleted for the "here's how we caught it" story.

## 2026-05-14 — Tolerance test: S2 + S3 agent prompts vs cell-path manifest

Spawned two parallel subagents with the verbatim S1+S2 and S3 agent-prompt markdown cells from `01_workshop_followalong.ipynb` to confirm the prompts replicate the cell-path run-through. Each subagent landed cold (no shared context with this session), read the project root + notebook CLAUDE.md, picked its own approach.

**S1+S2 subagent (data sanity + demo pair).** Used `vep_utils.ESM1bEncoder(device="mps")` directly; fresh encode on the demo pair (no cache). LLRs:
- Pathogenic `clinvar_55631 BRCA1 L1854P`: **-6.5283** (manifest demo_pair_scores.json: -6.528341)
- Benign `clinvar_55634 BRCA1 P1859R`: **-3.7580** (manifest: -3.757988)
- Both match to 4 decimal places; sign convention (path more negative) holds.

S1 surprises were genuine (long-protein truncation hit class-skewed, 166/500 conflicting-binarized labels, top genes single-label only, 5 start-codon pathogenics, 338/400 singleton genes). Not generic — actually surfaced from the data.

**S3 subagent (500-variant scoring).** Honored the "not a cache read" instruction: fresh encode of all 500 variants on MPS, 270 s wall-clock, wrote `notebooks/data/s3_scores__validation_rerun.npz` as a sibling to the canonical cache (no overwrite). Numbers:
- AUROC LLR: **0.9300** (manifest 0.930032; matches within 5e-4)
- CI95: **[0.9062, 0.9512]** (manifest [0.9062, 0.9512]; matches to 4 dp)
- AUROC delta_norm: **0.6718** (manifest 0.671808; matches)
- Diff vs canonical cache: max abs = 0.0 on both `llr` and `delta_norm` (deterministic forward pass on identical MPS hardware).

Breakdown findings (agent's own):
- **Gene axis:** zero genes meet the ≥3P+≥3B threshold per ARCHITECTURE.md §5; relaxed ≥2/≥2 leaves only DNAH11 (AUROC 0.75) and BRCA2 (AUROC 1.00). Per-gene AUROC is structurally not a useful axis on this set.
- **Length regime:** short (≤1022) AUROC 0.9435 vs long (>1022) AUROC 0.9197; 0.024 absolute gap, CI95 of the difference crosses zero (suggestive, not significant at n=500).
- **BLOSUM62:** monotonic — disruptive (≤-3) 0.9454 → moderate 0.9286 → conservative (≥+1) **0.9053**. Charge-changing 0.9492 vs charge-neutral 0.9172. Signal weakens where biochemical disruption is smallest, never inverts.

**Verdict:** prompts replicate the cell path. Both subagents reached manifest-pinned numbers via independent code without being told what number to expect.

Sibling validation rerun cache (`notebooks/data/s3_scores__validation_rerun.npz`, 70.6 KB) left in place pending cleanup decision; can `git rm` once we're done diffing.

## 2026-05-14 — manylatents-omics submodule SHA bump (cceb1fa → e97d469)

- **Pin:** manylatents-omics commit `e97d469` (branch `workshop/lrw-ub2026`).
- **Why:** the Brandes-correct LLR + `manylatents.dogma.vep` API lived only in this repo's working-tree copy of the submodule. A fresh `git clone --recurse-submodules` would have pulled the old `cceb1fa` and missed the fix entirely. Upstreamed `__init__.py`, `encoders/esm.py` (added `encode_with_logits`, `tok_id`), and the new `dogma/vep.py` (380 lines: parsing, truncation, scorers, sign-conventions), then bumped the parent pin.
- **Effect:** library scope (Path B/C: cluster + sweep) now hits the same LLR formula as the notebook prototype (Path A). Workshop attendees who clone fresh get the fix. Re-running `experiments/analysis/02_llr_distribution.py` against the cache still reproduces AUROC = 0.9300 (anchor-asserted within 5e-4).
- **Tests:** the cache (`notebooks/data/s3_scores.npz`) is unchanged — produced by the previous run that already used Brandes-correct LLR via notebook scope. Library scope had no in-tree caller exercising it before this commit; first end-to-end test of upstream `dogma.vep` will land with the S4 sweep work.

## 2026-05-14 — 02_llr_distribution.py (new headline figure)

- **Pin:** manylatents-omics submodule (unchanged from 2026-05-13 cache rebuild); analysis script lives in this repo, no submodule bump.
- **Cmd:** `experiments/tools/manylatents-omics/.venv/bin/python experiments/analysis/02_llr_distribution.py`
- **Output:**
  - `analysis/figures/llr_distribution_500.{pdf,png}` (KDE: pathogenic vs benign LLR over the full n=500 workshop set)
  - `analysis/results/llr_distribution_500.csv` (500 rows: variant_id, gene, label, llr)
  - `analysis/results/llr_distribution_500.json` (AUROC + CI + bootstrap config)
- **Numbers:** AUROC = 0.9300 (95 % CI [0.9062, 0.9512], 10k bootstrap, seed 42). Bit-identical to `data/workshop_set_manifest.json::evaluation.metrics.llr_auroc` within 5e-4; the script asserts this anchor at the bottom of `main()`.
- **Notes:** Replaces `00_demo_umap.py` (BRCA1 UMAP) as the headline visual for `validate_paper.py` and the slide deck. The figure literally is the AUROC — readers see pathogenic and benign densities separating along the LLR axis, with medians (-12 vs -5) and the AUROC + CI in the title. Same cache (`notebooks/data/s3_scores.npz`) `01_resolution_panels.py` already uses for its panel B, so no encoder calls — runs in ≲ 30 s on CPU. Dispatcher not involved: the workload is one process reading a cached npz; sub-second per metric. PROVENANCE.md updated.

## 2026-05-13 — Tolerance test (two subagents on s3) + dispatcher e2e verification

After the Brandes LLR fix landed, ran two verifications:

### Test A — Two fresh subagents on the s3 consequential prompt

Goal: do two independent agents reading the same prompt converge on the
same answer? If yes, the prompt + harness are unambiguous; if not, one
of them has a gap.

Both agents got the same instructions: read the CLAUDE.md hierarchy +
PROVENANCE.md, then answer the s3 prompt (scale to 500 variants;
report AUROC + CI95 + per-axis breakdowns). They ran independently in
parallel with no shared context.

Results:

| Metric | Agent A | Agent B | Verdict |
|---|---|---|---|
| LLR AUROC | 0.9300 | 0.9300 | ✓ bit-identical |
| CI95 | [0.9062, 0.9512] | [0.9062, 0.9512] | ✓ bit-identical |
| Length ≤1022 AUROC | 0.9435 | 0.9435 | ✓ |
| Length >1022 AUROC | 0.9197 | 0.9197 | ✓ |
| Per-gene evaluability | not-evaluable (≥3/≥3 rule) | not-evaluable | ✓ same verdict |
| Mutation-class axis | charge-change | BLOSUM62 substitution score | ✗ divergent (expected) |
| Sign-convention reasoning | -llr predictor; cache stores Brandes-sign | -llr predictor; same | ✓ |

The mutation-class axis divergence is **within the harness contract**:
ARCHITECTURE.md §5 lists three blessed axes (BLOSUM, charge, hydro
flip) and explicitly says "agent's choice; disclose which." Both agents
picked from the blessed list, both disclosed. Different axis ≠ different
answer — just a different *lens* on the same data.

The bit-identical match on AUROC + CI + length breakdowns reproduces
PROVENANCE.md exactly to 4 decimals, confirming the bootstrap seed,
the sign-flip-at-callsite convention, and the cache freshness rule all
wire together correctly when read cold from the harness.

### Test B — End-to-end dispatcher (VEP via dispatcher skill)

A separate subagent was given a two-repo task: use the dispatcher at
`/tmp/shop-skill/.claude/skills/dispatcher` to plan a 5-variant VEP
scoring task, then run the plan against `vep_utils.encode_variant`.
Tests that the dispatcher's substrate decision + device_override
contract actually delivers an end-to-end run with no layer crossing.

Result: **DISPATCH_E2E_PASS**

- Substrate decision: `mps` (correct for Apple Silicon, no nvidia-smi,
  no SLURM backends configured).
- `device_override` flows cleanly: `ESM1bEncoder(device=plan["device_override"])`
  produces `encoder.device == "mps"`.
- All 5 LLRs negative (Brandes sign). Pathogenic mean −11.18; benign
  mean −4.79. Sign-convention sanity check passes.
- Fail-fast on missing `gpu_memory_gb`: structured JSON error, exit 1.
- No layer crossing: vep_utils and dispatcher code unchanged; agent
  didn't write substrate-detection logic of its own; only invoked
  `route.py` and passed the resulting `device_override` to the encoder.
- Wall time: 1.29 s for 5 variants post-model-load on MPS.

Both tests confirm the harness carries the weight it claims: agents
landing cold can drive both the prompt-shaped tasks (s3 narrative
analysis) and the skill-shaped tasks (dispatcher routing) without
grepping past the harness docs.

### Note on the manylatents.dogma.vep upstream "bug"

The 2026-05-13 LLR commit (`565958a`) flagged that the submodule's
`manylatents.dogma.vep.compute_llr` had the same two-pass / inverted-sign
errors. On follow-up: the submodule's `manylatents/dogma/vep.py` is
**untracked locally** — not yet in the submodule's git history. The
file is in-progress collapse work that hasn't shipped. The Brandes fix
has been applied to the local untracked copy, so the user's eventual
`vep.py` commit will carry the corrected formula. No public artifact
ever shipped with the buggy upstream `compute_llr`; the only shipped
copy was `experiments/notebooks/vep_utils.py`, which is now fixed.

## 2026-05-13 — Brandes-correct LLR + S3 cache regeneration

The LLR computed by `vep_utils.compute_llr` did not match Brandes 2023's
Methods. Two errors, both documented in the docstring at the time:

1. **Two-pass formula** instead of one. The function was computing
   `log P_wt(wt_aa | wt_seq) − log P_mut(mut_aa | mut_seq)` — i.e., two
   ESM-1b forward passes per variant, each reading one amino-acid
   probability from a different softmax. Brandes 2023 uses **one
   forward pass** on the WT sequence and reads **both** `wt_aa` and
   `mut_aa` probabilities from the **same** softmax.
2. **Inverted sign.** The old docstring said "LLR > 0 → pathogenic."
   Brandes: `LLR = log P(mut|WT_seq) − log P(wt|WT_seq)`, **negative =
   deleterious** (MUT is less likely than WT under WT-context).

Both errors are subtle enough that the AUROC barely moved — the two
quantities are highly correlated for SNP scoring, because the
MUT-context model in the old formula is just the WT-context model with
one residue swapped, so the softmax at the variant position doesn't
change radically. We landed at **0.929** with the wrong methodology and
**0.930** with Brandes' methodology. *Right number was almost
guaranteed; right method was not.*

- **Fix:** `vep_utils.compute_llr` now takes `(wt_logits, mutation,
  wt_token_id, mut_token_id)` and returns
  `log P(mut|WT_seq) − log P(wt|WT_seq)`. The `mut_logits` argument
  was removed. `encode_variant` still does two forward passes for
  `delta_norm`/`cosine_dist`; a single-pass optimization is a
  follow-up.
- **Sign-flip lives at the AUROC call site**, not in the cache.
  `s3_scores.npz` stores Brandes-sign LLR (negative = deleterious);
  callers pass `-llr` to `roc_auc_score` so pathogenic = positive
  class. Documented in PROVENANCE.md and the manifest's
  `evaluation.metrics.llr_method` field.
- **Tests rewritten:** `test_compute_llr_brandes_unlikely_mutation_is_negative`
  (deleterious case → large-negative LLR) and
  `test_compute_llr_uses_correct_bos_offset` (single-arg signature,
  controlled-zero logits). 35/35 pass.
- **Pin:** main HEAD after this commit. The submodule
  `manylatents.dogma.vep.compute_llr` carries the **same** bug; not
  fixed in this commit. The workshop live demo uses `vep_utils.py`
  (notebook scope) which is now correct. The upstream library fix is a
  follow-up — it affects the S4 sweep handoff path, which is still
  PARTIAL on Phase-2 wiring anyway.
- **Cmd (regen):** `experiments/tools/manylatents-omics/.venv/bin/python experiments/scripts/cache_s3_scores.py --device mps --force`
- **Cmd (figure regen):** `experiments/tools/manylatents-omics/.venv/bin/python experiments/analysis/01_resolution_panels.py`
- **Cmd (demo-pair regen):** `experiments/tools/manylatents-omics/.venv/bin/python experiments/scripts/score_demo_pair.py`
- **Output:** `experiments/notebooks/data/s3_scores.npz` (sha256
  `c00eeae60744…`); `experiments/analysis/data/demo_pair_scores.json`
  (sha256 `acc170ccd948…`); `experiments/analysis/figures/resolution_panels.{pdf,png}`
  (caption + smoke-mode LLRs updated to Brandes sign).
- **AUROCs (workshop set, n=500, balanced 250 P / 250 B; predictor = -llr):**
  - LLR: **0.930032** (was 0.92904)
  - delta L2 norm: 0.671808 (unchanged — different metric)
  - Bootstrap CI95 (n_resamples=10000, seed=42): LLR
    [0.9062, 0.9512], delta_norm [0.6235, 0.7187] (unchanged).
- **Sign sanity (demo pair):**
  - Pathogenic L1854P: LLR = −6.5283 (more negative)
  - Benign P1859R:     LLR = −3.7580
  - Both negative, pathogenic more negative. ✓
- **Long-protein spot check (ASPM, 3477 aa):** LLR = −8.20 (finite,
  consistent with center-windowed scoring at MAX_LEN=1022). All 236
  long-protein variants finite; no `|LLR| > 50` outliers. AUROC by
  length regime: short (n=264) 0.944, long (n=236) 0.920.
- **Notes:** The methodology change is invisible in headline numbers
  (0.929 → 0.930, CI95 essentially unchanged) but corrects what we
  *did* relative to what we *say we did*. The slide narration
  "AUROC 0.93 within noise of Brandes 0.905" doesn't change. The
  "we use Brandes' option-4 single-window strategy" framing in
  PROVENANCE.md is now defensible — we also use Brandes' LLR.

## 2026-05-12 — MAX_LEN off-by-2 fix + S3 cache regeneration

Pre-talk regression test on the notebook caught a latent bug in
`vep_utils.ESM1bEncoder.MAX_LEN = 1024`: the HF tokenizer adds BOS +
EOS, so a length-1024 input becomes a 1026-token sequence that
overflows ESM-1b's 1024-slot position-embedding table with
`IndexError`. S2-encode crashed on the new canonical demo pair
(BRCA1 L1854P / P1859R, both >1022 aa into a 1863-aa protein). S3
appeared healthy only because it was reading a stale on-disk cache
produced under different library/version conditions.

- **Fix:** `MAX_LEN = 1024 → 1022` in `vep_utils.py`; new regression
  test `test_encoder_max_len_respects_bos_eos` locks it in.
  `notebook/01_workshop_followalong.ipynb` S2-encode cell now mirrors
  S3's `truncate_around_mutation(seq, pos1, window=encoder.MAX_LEN)`
  pattern. Cache regenerated via
  `experiments/scripts/cache_s3_scores.py --device mps --force`
  in 4.2 min on Apple Silicon MPS (500 variants, 0 skipped).
- **Pin:** main branch HEAD `71381f7` for the code fix; this entry
  captures the downstream artifact updates.
- **Cmd (regen):** `experiments/tools/manylatents-omics/.venv/bin/python experiments/scripts/cache_s3_scores.py --device mps --force`
- **Cmd (figure regen):** `experiments/tools/manylatents-omics/.venv/bin/python experiments/analysis/01_resolution_panels.py`
- **Output:** `experiments/notebooks/data/s3_scores.npz` (sha256
  `d11cc7f2fc0c…`), `experiments/notebooks/data/workshop_set_manifest.json`
  (metrics + literature-anchor block updated), `experiments/analysis/figures/resolution_panels.{pdf,png}`
  (caption + comment updated to new numbers), `experiments/PROVENANCE.md`
  (CI95 + sha refresh + new "Long-sequence handling" section), and
  `experiments/analysis/results/resolution_panels.csv`.
- **wandb:** n/a (cache regen, not a tracked training run).
- **AUROCs (workshop set, n=500, balanced 250 P / 250 B):**
  - LLR: **0.929** (was 0.9250)
  - delta L2 norm: **0.6718** (was 0.6703)
  - Bootstrap CI95 (10,000 resamples, seed=42): LLR
    [0.9057, 0.9503], delta_norm [0.6235, 0.7187].
- **Brandes anchor:** Brandes' 0.905 (n=36,537) sits 0.001 below
  our CI95 lower bound (0.906) — i.e. our point estimate is higher
  on a *broader* length distribution. Their headline benchmark
  excluded proteins >1022 aa (Extended Data Fig. 5 caption);
  ours includes 236 of 500 such variants, scored with Brandes'
  "option 4" (variant-centered single window at w=1022), which
  Brandes' own ablation (Extended Data Fig. 6a) shows is within
  noise of their sliding-window weighted-average method at the
  same window size.
- **Notes:** Five-prompt notebook lockdown sequence (rename → S1 swap →
  S2 demo pair → final sweep → regression) caught the bug in the
  regression step before slides were locked. The 0.004 shift in LLR
  AUROC is small but the underlying fix is load-bearing: any fresh
  clone re-running the cache would have crashed before; now it
  reproduces cleanly. Updated artifacts kept apples-to-apples
  (manifest + figure + provenance all reflect the post-fix cache).

## 2026-05-10 — workshop prep (no wandb runs)

Three artifacts shipped; no model training. Pre-flight for the workshop demos.

- **Pre-bundled ClinVar data for five genes** at `experiments/data/clinvar/` —
  BRCA1 at the root, plus `tp53/`, `brca2/`, `pten/`, `mlh1/` subdirectories.
  See [the clinvar README](./data/clinvar/README.md) for per-gene P/B/VUS
  counts. Built against a warm NCBI cache; no live download required for
  any of the five.
- **Variant-pair picker** [`scripts/pick_demo_pair.py`](./scripts/pick_demo_pair.py)
  reproducibly selects one pathogenic + one benign BRCA1 ClinVar variant
  and writes [`experiments/data/demo_pair.json`](./data/demo_pair.json)
  (parse-and-cite metadata + the canonical WT BRCA1 sequence, reconstructed
  from the bundled mutant FASTA). Current pick: BRCA1 L1854P (pathogenic,
  `clinvar_55631`) vs BRCA1 P1859R (benign, `clinvar_55634`).
- **S3 scoring cache** [`scripts/cache_s3_scores.py`](./scripts/cache_s3_scores.py)
  scored 499/500 validation variants on Apple Silicon MPS in 3.8 min.
  Output: [`notebooks/data/s3_scores.npz`](./notebooks/data/s3_scores.npz) (64 KB).
  Notebook S3 cell 17 now loads this in <100 ms instead of running ~10 min of
  live scoring. AUROC: `delta_norm` 0.61, `llr` 0.64 (both above chance,
  LLR > delta_norm). One variant skipped (`clinvar_701307` has a `*` stop
  codon in its WT FASTA).

## 2026-05-07 — encode_esm1b_brca1 + 00_demo_umap.py (post-fix baseline + workshop-pace + sandbox findings)

Consolidates four runs across 2026-05-07 (workshop-pace, sandboxed agent re-run, post-fix baseline, Phase-1 local re-run). The numbers are consistent across runs; what each one *added* is captured below.

- **Pin:** manylatents-omics `cceb1fa` (workshop/lrw-ub2026), v0.1.2; manylatents v0.1.5; fair-esm 2.0.0.
- **Canonical command** (post-fix baseline, MPS, project-root):
  ```
  experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
      --config-path=$(pwd)/experiments/configs/manylatents-omics \
      experiment=encode_esm1b_brca1 algorithms.latent.encoder_config.device=mps
  experiments/tools/manylatents-omics/.venv/bin/python experiments/analysis/00_demo_umap.py
  ```
- **Outputs:** `experiments/outputs/2026-05-07/<HH-MM-SS>/embeddings.pt` (200×1280); `experiments/analysis/figures/demo_umap_brca1.{pdf,png}`; results CSV.
- **Numbers:** MPS encode at 3.32–3.4 it/s (~60 s for 200 sequences) vs CPU default's 0.74 it/s — **~4.5× speedup** from the `device=mps` override. End-to-end Phase-1 wall clock ~65–75 s after warm-up. Workshop-pace `data.max_variants=50` cap runs in ~15 s end-to-end. ClinVar BRCA1 ≥1-star missense filter leaves 200 P/B after VUS drop; final split 131 benign / 69 pathogenic at `seed=42` (reproducible).
- **Load-bearing findings folded into the harness afterwards:**
  - **`data_dir` + `hydra.run.dir` pinned against `${hydra:runtime.cwd}`** in the experiment YAML. Removes the two CWD-coupled landmines from earlier sandbox runs (Hydra resolving `./data` against the wrong root; outputs landing at submodule root instead of project root). Eliminates the need for `data_dir=<abs>` override and post-hoc `cp` of the hydra run dir.
  - **`WANDB_INIT_TIMEOUT=180`** in `.env.example`. Default 90 s timed out on first init under conference-Wi-Fi conditions.
  - **`uv run --project … --extra workshop`** overlay confirmed as the sandbox-mode fallback (when sandboxed Claude Code can't call `.venv/bin/python` directly). All harness logic works under that overlay with no further overrides.
- **wandb (representative run, post-fix MPS baseline):**
  - encode: https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/0qpvx1s4
  - umap:   https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/od5yp85x

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

