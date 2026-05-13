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

Maintainer notes — uncommitted submodule changes from the same day, the
`manylatents.dogma.vep` collapse plan, and the Friday demo spec / runbook —
live in [`docs/internal/`](../docs/internal/) and are not part of the public
reproduction surface.

## 2026-05-07 — encode_esm1b_brca1 + 00_demo_umap.py  (workshop-pace: bundled data + max_variants=50)

- **Pin:** manylatents-omics `cceb1fa` (workshop/lrw-ub2026); manylatents v0.1.5; fair-esm 2.0.0
- **Cmd (encode):** `WANDB_INIT_TIMEOUT=180 WANDB_ENTITY=... experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main --config-path=$(pwd)/experiments/configs/manylatents-omics experiment=encode_esm1b_brca1 algorithms.latent.encoder_config.device=mps data.max_variants=50`
- **Cmd (umap):** `experiments/tools/manylatents-omics/.venv/bin/python experiments/analysis/00_demo_umap.py`
- **Output:** `experiments/outputs/2026-05-07/14-07-48/embeddings.pt` (50 × 1280); figures + CSV
- **wandb (encode):** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/62tyx05m
- **wandb (umap):** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/io084q8b
- **Data:** Bundled `experiments/data/clinvar/` (committed snapshot from 2026-05-07). `data.max_variants=50` cap → 35 pathogenic / 15 benign (P-heavy slice of the top of the TSV).
- **Notes:** Workshop-pace path. **Encode took 15 s on MPS** (3.25 it/s, 50 sequences). End-to-end ~25 s including UMAP. Validates the bundled data load (no NCBI download needed) and the `data.max_variants=50` workshop override. First-run wandb init timed out at the default 90 s — `WANDB_INIT_TIMEOUT=180` (now in `.env.example`) fixed it; relevant on conference Wi-Fi.

## 2026-05-07 — encode_esm1b_brca1 + 00_demo_umap.py  (sandboxed agent re-run, post-940dc58)

- **Pin:** manylatents-omics `cceb1fa` (workshop/lrw-ub2026); manylatents v0.1.5; fair-esm 2.0.0
- **Cmd (encode):** `WANDB_ENTITY=cesar-valdez-mcgill-university WANDB_PROJECT=upper-bound-2026 uv run --project experiments/tools/manylatents-omics --extra workshop python -m manylatents.main --config-path=$(pwd)/experiments/configs/manylatents-omics experiment=encode_esm1b_brca1 algorithms.latent.encoder_config.device=mps` (run from project root)
- **Cmd (umap):** `uv run --project experiments/tools/manylatents-omics --extra workshop python experiments/analysis/00_demo_umap.py`
- **Output:** `experiments/outputs/2026-05-07/12-12-25/embeddings.pt` (200 × 1280); `experiments/analysis/figures/demo_umap_brca1.{pdf,png}`; `experiments/analysis/results/demo_umap_brca1.csv`
- **wandb (encode):** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/0bafk3xk
- **wandb (umap):** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/4cfcb862
- **Data:** ClinVar BRCA1 ≥1-star missense (cached). Final split: 131 benign / 69 pathogenic — identical to prior runs at `seed=42`.
- **Notes:** Sandboxed agent run forced onto the `uv run --project ... --extra workshop` overlay (direct `.venv/bin/python` invocation blocked). Confirms the commit-`940dc58` fixes hold under sandbox: **no `data_dir=<abs>` override needed** and **no post-hoc `cp` of the hydra run dir** — `embeddings.pt` landed at `experiments/outputs/2026-05-07/12-12-25/` and `00_demo_umap.py` resolved it via `_config.latest_hydra_run` on the first try. MPS encode at 3.38 it/s, ~60 s for 200 sequences. UMAP step ~5 s. End-to-end Phase-1 wall clock ~70 s after warm-up. Difficulty 8.5/10 vs the prior 6/10 — both CWD-coupled landmines and the MPS device note are now folded into the canonical CLAUDE.md sequence.

## 2026-05-07 — encode_esm1b_brca1 + 00_demo_umap.py  (post-fix baseline, MPS, run-from-project-root)

- **Pin:** manylatents-omics `cceb1fa` (workshop/lrw-ub2026); manylatents v0.1.5; fair-esm 2.0.0
- **Cmd (encode):** `WANDB_ENTITY=... experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main --config-path=$(pwd)/experiments/configs/manylatents-omics experiment=encode_esm1b_brca1 algorithms.latent.encoder_config.device=mps` (run from project root)
- **Cmd (umap):** `experiments/tools/manylatents-omics/.venv/bin/python experiments/analysis/00_demo_umap.py`
- **Output:** `experiments/outputs/2026-05-07/12-06-36/embeddings.pt` — landed at the pinned location, no copy needed; `experiments/analysis/figures/demo_umap_brca1.{pdf,png}`; results CSV
- **wandb (encode):** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/0qpvx1s4
- **wandb (umap):** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/od5yp85x
- **Notes:** First run after pinning `data_dir` and `hydra.run.dir` against `${hydra:runtime.cwd}` in the experiment YAML. Confirms the two CWD-coupled landmines from the 11:56 agent run (data_dir relative-to-cwd, outputs landing at submodule instead of project) are gone — no manual `data_dir=<abs>` override or post-hoc directory copy. MPS device override gave **3.32 it/s** vs the cpu default's 0.74 it/s (~4.5× speedup). Total wall time 1:00 encode + ~5s UMAP = ~65s end-to-end after warm-up.

## 2026-05-07 — encode_esm1b_brca1 + 00_demo_umap.py  (Phase-1 local re-run, MPS)

- **Pin:** manylatents-omics `cceb1fa` (workshop/lrw-ub2026), v0.1.2; manylatents v0.1.5; fair-esm 2.0.0
- **Cmd (encode):** `uv run --project experiments/tools/manylatents-omics --extra workshop python -m manylatents.main --config-path=$(pwd)/experiments/configs/manylatents-omics experiment=encode_esm1b_brca1 algorithms.latent.encoder_config.device=mps data_dir=$(pwd)/experiments/tools/manylatents-omics/data`
- **Cmd (umap):** `uv run --project experiments/tools/manylatents-omics --extra workshop python experiments/analysis/00_demo_umap.py`
- **Output:** `outputs/2026-05-07/11-56-06/embeddings.pt` (200 × 1280, mirrored into `experiments/outputs/2026-05-07/11-56-06/` so `_config.latest_hydra_run` can find it); `experiments/analysis/results/demo_umap_brca1.csv`; `experiments/analysis/figures/demo_umap_brca1.{pdf,png}`
- **wandb (encode):** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/cei8iwqu
- **wandb (umap):** https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/714ptc17
- **Data:** Same ClinVar BRCA1 ≥1-star missense pull as 2026-05-06; 200 P/B kept after VUS drop. Final split: 131 benign / 69 pathogenic — identical to the first end-to-end run, as expected at `seed=42`.
- **Notes:** Sandboxed agent run; could not invoke `.venv/bin/python` directly or `uv sync`/`cp` cross-tree, so used `uv run --project ... --extra workshop` overlays for every step. Two non-default overrides forced by sandboxing:
  1. `data_dir=<absolute>` — Hydra's relative `./data` resolved against project root (the agent's CWD) instead of the manylatents-omics submodule, so the ClinVarDataModule couldn't find `variants.tsv`. Absolute override fixes it.
  2. Encode's hydra `outputs/` landed at project root instead of inside the submodule; copied the run dir to `experiments/outputs/...` (one of the candidate roots scanned by `_config.latest_hydra_run`) so `00_demo_umap.py` resolved it.

  ESM-1b encoded all 200 sequences in 0:60 on Mac arm64 MPS (3.4 it/s, weights warm-cached). UMAP step ran in ~5 s. Phase-1 runtime end-to-end: ~75 s after warm-up.

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

