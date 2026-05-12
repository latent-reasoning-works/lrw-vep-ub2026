# Friday Code-Along — Engineering Spec

> Target: 12-minute boss demo on César's M5 Pro local, fair-esm-on-MPS.
> This document is what the parallel agent builds toward. **Commands +
> expected outputs only.** Speaker beats live in `FRIDAY_RUNBOOK.md`.
>
> Beat IDs reference `WORKSHOP_BEATS.md`. Audit gates reference
> `WORKSHOP_READINESS.md`.

## Pre-demo checklist (one-shot, must pass before demo starts)

Run these in order from a clean morning kernel. Each must pass before
the demo begins. **If any check fails, fix or activate the per-beat
fallback before going live.**

```bash
# 0. Variant pair pick — run once; spec self-fills the B8 / B9 placeholders.
#    Idempotent: re-running with --write-spec is safe; second run is a no-op
#    if the placeholders are already filled.
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/scripts/pick_demo_pair.py \
    --write-spec docs/internal/FRIDAY_CODEALONG.md
# Expected stdout (BRCA1-only, from experiments/data/clinvar/variants.tsv):
#   Pathogenic: clinvar_55631      BRCA1    L1854P   (clinical_significance=Likely pathogenic)
#   Benign:     clinvar_55634      BRCA1    P1859R   (clinical_significance=Benign)
#   WT sequence reconstructed: 1863 aa (BRCA1 canonical UniProt P38398)
# Side effects:
#   - Replaces the four B8/B9 placeholder tokens (and the two gene tokens
#     used by FRIDAY_RUNBOOK.md) in the file passed to --write-spec.
#   - Writes experiments/data/demo_pair.json: pathogenic + benign records,
#     the canonical WT BRCA1 sequence (reconstructed by reverse-applying
#     the pathogenic mutation to its mutant FASTA entry), and a 12-char
#     SHA256 prefix of variants.tsv for parse-and-cite.
#
# Picker logic (BRCA1-only, no length filter — manylatents.dogma.vep
# truncate_around_mutation handles BRCA1's 1863 aa at encode time):
#   pick(gene='BRCA1', label=1)   # first pathogenic, stable on TSV row order
#   pick(gene='BRCA1', label=0)   # first benign
#
# Agent contract: deterministic against experiments/data/clinvar/variants.tsv
# at the current SHA. If that TSV ever changes, re-run; the spec self-updates.
# Why this data source (not the notebook's workshop_set.tsv): the
# bundled clinvar is what the canonical Phase-1 prompt operates on, and is
# the only data source with both BRCA1 pathogenic and BRCA1 benign present.

# 1. Repo state
git -C /Users/cmvcordova/code/lrw/lrw-vep-ub2026 status        # clean tree, on main
git -C /Users/cmvcordova/code/lrw/lrw-vep-ub2026 submodule status  # cceb1fa or release tag
# Expected: clean tree, submodule pin matches the REL.1 release tag

# 2. Required artifacts present
test -f experiments/data/clinvar/variants.tsv                        # BRCA1
test -f experiments/data/clinvar/tp53/variants.tsv                   # B18 prereq
test -f experiments/data/clinvar/brca2/variants.tsv                  # B18 prereq
test -f experiments/data/clinvar/pten/variants.tsv                   # B18 prereq
test -f experiments/data/clinvar/mlh1/variants.tsv                   # B18 prereq
test -f experiments/notebooks/data/s3_scores.npz                     # B10 cache fallback
echo all-present

# 3. Python API surface (post-2.11 collapse)
experiments/tools/manylatents-omics/.venv/bin/python -c "
from manylatents.dogma.encoders import ESMEncoder
from manylatents.dogma.vep import encode_variant, compute_llr, parse_mutation
print('API surface OK')
"
# Expected stdout: API surface OK

# 4. Encoder warm-up — model weights cached, MPS reachable
experiments/tools/manylatents-omics/.venv/bin/python -c "
from manylatents.dogma.encoders import ESMEncoder
e = ESMEncoder(model_name='esm1b_t33_650M_UR50S', device='mps')
e._load_model()
print('warm OK')
"
# Expected stdout: warm OK (~60 s first time, ~5 s once cached)

# 5. Wandb auth (Friday-critical for B18)
#    The demo's Hydra path logs to wandb. Two safe configurations; pick one:
#
#    a) Authenticated — verify api_key is set + reachable:
#       wandb status | grep -i 'api_key'
#       # Expected: api_key value present (not null). If null, run: wandb login
#
#    b) Offline (safe default if venue network blocks wandb):
#       export WANDB_MODE=offline
#       # Confirm: WANDB_MODE=offline echo "logs to ./wandb/offline-run-*"
#
#    **As of 2026-05-10 on this machine, api_key is null.** Either run
#    `wandb login` before Friday or commit to offline mode in the runbook.
```

If checks 1–5 all pass, demo is green. If any fail, see the per-beat
fallbacks below.

---

## Beat sequence (target 12 min)

Time budget per beat is the *upper* bound — finishing a beat under
budget buys recovery time for later beats. Total stated time: 11 min;
1 min reserved for transitions and unexpected delay.

### B6 — Where the agent enters (~30 s, slide 2.4)
**Live action:** none. Speaker beat over slide.
**On-screen reference (have ready in another window):** open
`CLAUDE.md` lines 26–70 in VS Code. The two canonical commands are the
visual.
**Expected output:** none — slide-only beat.
**Fallback:** SD.1 means slide 2.4 may still be title-only on Friday;
in that case land the beat as voiceover and gesture to the open
`CLAUDE.md`.

### B7 — ESM-1b LLR mechanic (~30 s, slide 2.5)
**Live action:** none. Slide-only beat.
**Pre-demo verification (already in checklist if collapse landed):**
```bash
cd experiments/notebooks
python3 -m pytest test_vep_utils.py::test_compute_llr_uses_correct_bos_offset \
                  test_vep_utils.py::test_compute_llr_increases_with_unlikely_mutation -v
```
Expected: 2 passed. This proves the formula on the slide matches the
code that ships in `manylatents.dogma.vep`.
**Fallback:** if the regression tests aren't passing on Friday morning,
**do not run B9** — the rest of the chain is unsound. Activate B9's
fallback (pre-cached LLR output text) and skip the live encode.

### B8 — Variant pair chosen (~30 s, slide 2.6)
**Live action:** none. Slide displays the locked pair.
**Locked variant pair (auto-filled by pre-demo step 0):**
- Pathogenic: `clinvar_55631` — BRCA1 `L1854P`, ClinVar significance: Likely pathogenic
- Benign:    `clinvar_55634` — BRCA1 `P1859R`, ClinVar significance: Benign

Both rows live in `experiments/data/clinvar/variants.tsv` — the same
data the canonical Phase-1 prompt operates on. BRCA1 is 1863 aa, so
the picker imposes no length filter; `truncate_around_mutation`
centers a 1024-aa window at encode time (B9). Pair regenerates from
current data — if the TSV ever changes, re-run step 0 and the spec
self-updates.
**Pre-demo verification:**
```bash
awk -F'\t' 'NR==1 || $1==55631 || $1==55634' experiments/data/clinvar/variants.tsv
# Expected: header + 2 rows, one labeled 1 (pathogenic), one labeled 0 (benign)
python3 -m json.tool experiments/data/demo_pair.json | head -20
# Expected: pathogenic + benign blocks + the variants.tsv SHA at pick time
```
**Fallback:** if step 0 hasn't run by Friday morning, run it then; it's
deterministic and idempotent. If the picker script itself is broken,
read `variants.tsv` directly — first BRCA1 row with `label=1` plus
first BRCA1 row with `label=0` is the same logic, by hand.

### B9 — LIVE: prototype scores one pair, returns a number (~3 min, slide 2.7) ★
**Live command (Path C, post-2.11 collapse).** Reads the variant pair
and the canonical WT BRCA1 sequence from `experiments/data/demo_pair.json`
(produced by pre-demo step 0). BRCA1 is 1863 aa — exceeds ESM-1b's 1024
window — so `truncate_around_mutation` centers a 1024-aa window on each
mutation site. The HGVS reflects the truncated position.

```bash
experiments/tools/manylatents-omics/.venv/bin/python -c "
import json
from manylatents.dogma.encoders import ESMEncoder
from manylatents.dogma.vep import (
    encode_variant, compute_llr, parse_mutation, truncate_around_mutation,
)

pair = json.loads(open('experiments/data/demo_pair.json').read())
wt_seq = pair['wt_sequence']
encoder = ESMEncoder(model_name='esm1b_t33_650M_UR50S', device='mps')

for tag in ['pathogenic', 'benign']:
    v = pair[tag]
    seq, pos = truncate_around_mutation(wt_seq, v['position'], window=1024)
    hgvs = f\"{v['wt_aa']}{pos}{v['alt_aa']}\"
    r = encode_variant(encoder, seq, hgvs)
    delta = float(((r['mut_embedding'] - r['wt_embedding'])**2).sum()**0.5)
    llr = compute_llr(
        r['wt_logits'], r['mut_logits'], parse_mutation(hgvs),
        wt_token_id=encoder.tok_id(v['wt_aa']),
        mut_token_id=encoder.tok_id(v['alt_aa']),
    )
    print(f\"{tag.capitalize():12s} {v['gene']} {v['hgvs']:8s}  \"
          f\"delta={delta:6.3f}  LLR={llr:+6.3f}\")
"
```

**Expected output (numbers land once the actual encode runs; pre-record
during the Friday morning dry-run):**
```
Pathogenic   BRCA1 L1854P  delta=<X.XXX>  LLR=<+X.XXX>
Benign       BRCA1 P1859R  delta=<X.XXX>  LLR=<+X.XXX>
```
The pathogenic LLR should be larger than the benign LLR (sign:
`log P_wt(wt) − log P_mut(mut)`; bigger = bigger confidence drop at the
mutation site).

**Wall time on M5 Pro MPS:** ~10 s after warm-up (4 forward passes ×
~2 s each).

**Required post-2.11 API surface** (flag for the agent doing the
collapse — listed here, also tracked in WORKSHOP_READINESS.md §2.11):
- `manylatents.dogma.vep.encode_variant(encoder, seq, hgvs_str)` →
  `{wt_embedding, mut_embedding, wt_logits, mut_logits, ...}`
- `manylatents.dogma.vep.compute_llr(wt_logits, mut_logits, mutation, wt_token_id, mut_token_id)`
- `manylatents.dogma.vep.parse_mutation`, `truncate_around_mutation`
- `ESMEncoder.tok_id(aa: str) -> int` — looks up the fair-esm vocab
  index for a single AA letter. Today the code calls
  `encoder._alphabet.get_idx(aa)` directly; expose as `tok_id` so B9's
  command stays one line per token. ~3 lines on the encoder.

**Fallback (cell errors / OOM / network glitch):** display the pre-baked
output text directly — same numbers, presented as "here's what the
prototype produced earlier today." Have the text ready in a TextEdit
window before the demo starts.

### B10 — Validation visible (n=500 AUROC + CIs) (~2 min, slide 2.8)
**Live action:** open `experiments/notebooks/01_workshop_followalong.ipynb`
in Jupyter Lab. Run cell 17 (which detects the cache and loads it
instantly), then cells 18, 20 — bootstrap AUROC table + ROC curves.

**Expected output (cell 18):**
```
                 score    AUROC  CI95_lo  CI95_hi    n
0      Delta L2 norm    0.<XXX>   0.<XX>   0.<XX>  500
1                LLR    0.<XXX>   0.<XX>   0.<XX>  500
```
**Expected plot (cell 20):** ROC curves for both scorers, AUROCs in the
legend, dashed chance line.

**Fallback (cache missing / cell error):** open the pre-rendered ROC PNG
from `experiments/analysis/figures/` and read the AUROC numbers off it.
The cache *should* be present per checklist step 2; if it isn't,
something else is broken.

### B12 — The harness integrates (~1 min, slide 2.10)
**Live action:** none. Slide displays the stack diagram. Speaker beat.

**Pre-demo verification (already in checklist if you trust it; otherwise
re-run):**
```bash
ls -la \
  CLAUDE.md \
  experiments/configs/manylatents-omics/experiment/encode_esm1b_brca1.yaml \
  experiments/tools/manylatents-omics/manylatents/dogma/vep.py \
  experiments/tools/manylatents-omics/.venv/lib/python3.12/site-packages/manylatents/configs/launcher/mila_cluster.yaml \
  .env.example
```
Expected: 5 files, all non-empty. Each maps to one box in the stack
diagram.

**Fallback:** if `manylatents/dogma/vep.py` is missing (2.11 not landed),
the diagram's "manylatents-omics" box has no referent. Reword the
slide line to "manylatents-omics (in progress; ships next week)" and
keep moving.

### B18 — LIVE: tunable gene demo (~3 min, "Same harness, any gene" slide) ★
**Live command (TP53 — audience pick if you want to invite participation):**
```bash
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
    --config-path=$(pwd)/experiments/configs/manylatents-omics \
    experiment=encode_esm1b_brca1 \
    data.genes=[TP53] \
    data.data_dir=$(pwd)/experiments/data/clinvar/tp53 \
    name=encode_esm1b_tp53 \
    algorithms.latent.encoder_config.device=mps \
    data.max_variants=50
```
**Note:** the override is `data.data_dir=...`, not `data_dir=...`. The
clinvar data config does `data.data_dir: ${data_dir}/clinvar`, so the
top-level `data_dir` gets `/clinvar` appended — the per-gene bundle
lives at `experiments/data/clinvar/<gene>/`, not
`experiments/data/clinvar/<gene>/clinvar/`. Override the leaf directly.

**Audience-pick gene-to-path map (all five pre-bundled
2026-05-10):**

| Gene  | `data.data_dir` override                                    | P / B / VUS  |
|-------|-------------------------------------------------------------|--------------|
| BRCA1 | `$(pwd)/experiments/data/clinvar`               (default)   | 264 / 52 / 684 |
| TP53  | `$(pwd)/experiments/data/clinvar/tp53`                      | 206 / 82 / 712 |
| BRCA2 | `$(pwd)/experiments/data/clinvar/brca2`                     | 54 / 172 / 774 |
| PTEN  | `$(pwd)/experiments/data/clinvar/pten`                      | 234 / 6 / 760  |
| MLH1  | `$(pwd)/experiments/data/clinvar/mlh1`                      | 135 / 32 / 833 |

PTEN's benign set is thin (n=6) — if the audience picks PTEN and the
encode finishes too fast for the UMAP to be visually compelling,
redirect to BRCA2 or MLH1 for a richer P-vs-B contrast.
**Expected output (final lines):**
```
[INFO] BatchEncoder ... Saved embeddings to .../embeddings.pt
[INFO] wandb run: https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026/runs/<id>
```
**Wall time on M5 Pro MPS:** ~15–20 s for `max_variants=50` on TP53
(~393 aa median sequence — TP53 is shorter than BRCA1; faster than the
Phase-1 baseline).

**Then chain UMAP for the visual:**
```bash
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/analysis/00_demo_umap.py --experiment encode_esm1b_tp53
```
**Expected output:**
```
  saved coords → experiments/analysis/results/demo_umap_brca1.csv
  saved figure → experiments/analysis/figures/demo_umap_brca1.pdf
  logged to wandb: cesar-valdez-mcgill-university/upper-bound-2026
```
(The post-step keeps the BRCA1 filename — that's a known minor; doesn't
break the demo.)

**Fallback (audience picks gene that's not pre-bundled):** redirect to a
bundled gene with a one-liner: "We pre-bundled BRCA1, BRCA2, TP53, PTEN,
MLH1 to avoid hitting NCBI live — pick one of those." If the encode
itself fails on a bundled gene, swap to the BRCA1 baseline run from B9
and frame it as "same prompt, same shape — gene swap is the data layer."

### B13 — LIVE: cluster invocation (~1 min, optional, slide 2.11)
**Friday-only if Phase-2 has been validated this week.** If not, skip
this beat in the boss demo; covered by 🟡 TALK timeline for the workshop.

**Live command (on Mila login session, only if validated):**
```bash
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
    --config-path=$(pwd)/experiments/configs/manylatents-omics \
    experiment=encode_esm1b_brca1_mila
```
**Expected output:**
```
[INFO] submitit_slurm launching job <jobid> on partition long
[INFO] log dir: logs/encode_esm1b_brca1_mila/runs/<date>/<time>/
```
**Wall time:** dispatch is instantaneous; the job itself runs
asynchronously.

**Fallback (B13 not Friday-ready):** show a screenshot of a previous
successful Mila dispatch + the corresponding wandb run URL. Frame as
"this same prompt has dispatched to Mila; here's last week's run."

---

## Buffer + close (~1 min)

Total of beat budgets: B6 (0.5) + B7 (0.5) + B8 (0.5) + B9 (3) + B10 (2)
+ B12 (1) + B18 (3) + B13 (1, optional) = **11 min**, plus ~1 min
buffer. If B13 is skipped, you have ~2 min buffer; spend it on B18
(longer pause for "same harness, different gene" to land) or close
early.

## Post-demo cleanup (after the boss leaves)

```bash
# Wipe demo wandb runs out of the project if you want to keep the
# project log clean — optional.
# wandb runs ls --entity cesar-valdez-mcgill-university \
#               --project upper-bound-2026 \
#               --filter '{"display_name": {"$regex": "encode_esm1b_tp53"}}'
```

---

## Summary table for the parallel agent

The agent's job before Friday is to make the following six tests pass.
Each maps to a beat above:

| Test | Beat | Audit gate(s) |
|---|---|---|
| `python3 experiments/scripts/pick_demo_pair.py --write-spec ...` runs idempotently and writes `experiments/data/demo_pair.json` (subsumes the B8 placeholder fill) | pre-demo #0 | slide-2.6 placeholder fill |
| `from manylatents.dogma.vep import encode_variant, compute_llr` succeeds | pre-demo #3 | 2.11 + REL.1 |
| `pytest test_vep_utils.py::test_compute_llr_*` passes | B7 | 2.5 |
| B9 inline `python -c "..."` produces non-NaN delta + LLR for both variants | B9 | 2.0 (Path C variant), 2.4 |
| `experiments/notebooks/data/s3_scores.npz` exists, cell 17 loads it | B10 | 2.7 |
| `data/clinvar/{tp53,brca2,pten,mlh1}/variants.tsv` all exist | B18 | 3.5 / LD.4 |

Optional (Friday-stretch):
| Test | Beat | Audit gate |
|---|---|---|
| `experiment=encode_esm1b_brca1_mila` dispatches successfully on Mila | B13 | 2.8 / LD.2 |

When all six required tests pass, Friday is green.
