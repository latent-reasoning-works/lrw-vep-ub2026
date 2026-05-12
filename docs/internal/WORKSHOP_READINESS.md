# Workshop Readiness — Audit Report
Generated: 2026-05-10 (revised same day with César's decisions; see *Decisions captured* below)
Talk date: 2026-05-23 (T-13 days)

> Audit of the harness against the slide claims listed in the brief. **No code
> changes made.** Status verdicts are based on file inspection, the recent
> EXPERIMENT_LOG entries (last validated run 2026-05-07, three days ago, on
> commit `9c4043a` against submodule pin `cceb1fa`), and the contents of the
> Colab notebook. Items marked ✅ are corroborated by a recent successful
> run; items marked 🟡/❌/❓ are explained inline.
>
> **2026-05-10 revision:** César's answers to the open questions are folded
> in throughout. Four cross-cutting requirements added: **2.0** (notebook
> clean-Colab smoke), **OB.1** (break-time install), **DR.1** (live-demo
> failure runbook), **SD.1** (slide 2.4 still title-only).

---

## Risk-ranked priority

Re-ranked 2026-05-10 around the Friday boss-demo deadline (T-5 days). Tier
mapping mirrors `WORKSHOP_BEATS.md`: 🔴 FRI = must work for code-along /
boss demo, 🟡 TALK = must work by 2026-05-23, 🟢 NICE = talk works
without it. Items inside a tier are ordered by what unblocks the most
downstream work.

| # | Tier | Item | Why |
|---|---|---|---|
| 1 | 🔴 FRI | **2.11** Variant-effect API collapse into `manylatents.dogma.vep` | Half-day of upstream work. Path A and Path B both depend on its exports; without it, `vep_utils.py` stays bespoke and the two paths can't merge. Gates B7, B9, B12. |
| 2 | 🔴 FRI | **REL.1** Cut releases of `manylatents` + `manylatents-omics`, pin in this repo | Boss demo wants `pip install manylatents-omics` to deliver the collapsed API. Blocks if 2.11 isn't tagged + published. |
| 3 | 🔴 FRI | **2.0** Notebook clean-Colab smoke + **2.7** s3 cache | Boss demo can't go live-fragile. Cache must exist; notebook must run end-to-end from a fresh kernel. |
| 4 | 🔴 FRI | **B8 / slide-2.6** Pick variant pair + bake IDs | 15-min task. Without this, slide says "BRCA1 [???]" — slide gap, not code gap, but Friday-blocking for B9. |
| 5 | 🔴 FRI | **2.5 + 2.10** Verify post-collapse: LLR formula on slide 2.5 still matches code, stack diagram (slide 2.10) layers all resolve to real artifacts and "shop" is dropped | Sanity check after 2.11 lands; trivial if collapse is clean. |
| 6 | 🔴 FRI | **3.5 / LD.4** Pre-bundle 5 genes (BRCA1, BRCA2, TP53, PTEN, MLH1) per Q6 | Promoted 2026-05-10 alongside B18. Parallel-path to 2.11/REL.1 (data work, not API). ~3–4 min after NCBI cache warms. Strongest rhetorical beat for the boss demo: "BRCA1 → TP53, same prompt." |
| 7 | 🟡 TALK | **P.1 + P.5** License and repo public flip | LICENSE missing; repo private. Gates Path A's Colab `wget`. Aim Friday if possible; can slip to following Monday if REL.1 is tighter. |
| 8 | 🟡 TALK | **OB.1** Break-time install across laptop OSes | 15-min install gate untested on Intel Mac / Linux / WSL. |
| 9 | 🟡 TALK | **2.6** Move encoder load from cell 8 → end of S1 | One-line edit; do post-Friday. |
| 10 | 🟡 TALK | **3.4** Overleaf live sync | ~2 h block; do post-Friday. Auth surprises common on first run. |
| 11 | 🟡 TALK | **3.3** `expstash` + `expaper` installability | Per Q3 prioritize `expaper`. |
| 12 | 🟡 TALK | **3.2 / LD.3** Parse-and-cite (JSON sidecar + CLAUDE.md paragraph) | Slide is "🟢 LIVE." |
| 13 | 🟡 TALK | **DR.1** Live-demo failure runbook | One-page contingency per LIVE slide. |
| 14 | 🟡 TALK | **2.8 / LD.2** Phase-2 cluster | Live Mila run or screencast. |
| 6.5 | ✅ DONE | **2.9** Resolution side-by-side panel (locked 2026-05-11) | All three panels traced and committed: n=2 BRCA1 (HF transformers MPS), n=499 ROC (AUROC 0.61/0.64 via sklearn on cached s3 scores), n=36,537 Brandes 2023 Fig 2B anchor (AUROC 0.74). Curve not fabricated for panel C — cite-only. Lineage in `PROVENANCE.md`. |
| 6.6 | 🔴 FRI | **NB.1** Notebook code-cell import swap (post-2.11) (added 2026-05-10) | Notebook S2/S3 still `from vep_utils import ...`. After 2.11 lands, swap to `from manylatents.dogma.vep import ...` so the slide claim "two paths merged" is honest. Code cells only — teaching cells stay untouched per the hard veto. |
| 6.7 | 🔴 FRI | **P.4-Friday** Wandb auth on the demo machine (escalated 2026-05-10) | Hardcoded entity `cesar-valdez-mcgill-university` plus a network that may block wandb. Need explicit `WANDB_MODE=offline` documented + a quick demo-machine auth check. |
| 16 | 🟡 TALK | **3.1** Schema docs for intermediate files | Foundation for 3.2; folds into LD.3 task. |
| 17 | 🟡 TALK | **2.3** ESM-1b on CUDA | Folds into 2.0 / LD.1 smoke. |
| 18 | 🟡 TALK | **P.4-public** Wandb portability — README callout | The post-Friday version: README quickstart explains override + offline mode for attendees. |
| 19 | 🟢 NICE | **P.2** Notebook personal scratch paths | Resolves automatically once Q3 install commands replace them. |
| 20 | 🟡 TALK | **SD.cluster** Slide content gaps (2.4 body, Part 2 closer, Part 3 opener, 2 new recap slides, "Agent enters" speaker notes, Part 1→2 transition, Acknowledgments) (expanded 2026-05-10) | Slide-side; user-owned. Tracked here only so it doesn't slip. |
| 21 | 🟡 TALK | **WS.1** Workshop landing page consistency (added 2026-05-10) | Upper Bound site's abstract vs. where the talk actually landed. Worth checking before press. |
| 22 | 🟡 TALK | **WS.2** Backup recording of Friday demo (added 2026-05-10) | Record a clean run once Friday demo works. Fallback for May 23 if live fails. |
| 23 | 🟡 TALK | **WS.3** Public-flip pre-flight (subsumes P.5) (added 2026-05-10) | Clean clone from a fresh GitHub account; Colab dry-run; time the install break. |
| 24 | 🟢 NICE | **3.8** pptx wiring — reframe as aspirational | Slide reword only. |
| 25 | 🟢 NICE | **POST.1** Blog post "Why ManyLatents?" — capture today (added 2026-05-10) | Window for writing well closes by June 1. Scaffolded at `docs/internal/BLOG_NOTES.md`. |
| 26 | 🟢 NICE | **POST.2** `paper/main.tex` status (added 2026-05-10) | Scaffolded but no content. Tied to this workshop or separate? Argument? |
| 27 | 🟢 NICE | **POST.3** Post-workshop follow-up plan (added 2026-05-10) | Email to attendees, repo announcement, blog timing rel. ICSB. |
| 28 | 🟢 NICE | **POST.4** ICSB version of the talk (added 2026-05-10) | What carries over, what changes, what timing. |
| 29 | 🟢 NICE | **QA.1** Q&A prep — "couldn't AlphaMissense just do this?" (added 2026-05-10) | Worst question + most common question + honest answers. |
| 30 | 🟢 NICE | **PB.1** Per-beat time budget for the 45-min Part 2 (added 2026-05-10) | Pacing reference, Friday + May 23. |
| 31 | 🟢 NICE | **HW.1** Backup hardware plan (added 2026-05-10) | If M5 Pro dies May 22: is fair-esm installable on a non-Mac laptop in <30 min? |

**Friday tier (rows 1–6.7) is three parallel work streams.** The 2.11 →
REL.1 → 2.7 cache → 2.0 smoke → B8 + 2.5/2.10 verify chain (rows 1–5) is
serial — each item gates the next. Row 6 (gene bundle) is independent.
Rows 6.5–6.7 (resolution plot, notebook import swap, wandb-auth) are
each their own short stream — the resolution plot uses already-shipped
artifacts (`s3_scores.npz` + `demo_pair.json`); the notebook import swap
waits on the 2.11 commit then takes ~2 min; the wandb-auth check is a
~10 min audit + README addendum. Recommend running all three Friday
streams in parallel.

**Top concern cluster (per the 2026-05-10 gap review)** — easy to forget
because nothing forces them:
1. **NB.1** notebook import swap. Without it, "two paths merged" is half
   true: slides describe `manylatents.dogma.vep`; attendees in the
   notebook see `vep_utils`.
2. **POST.1** blog post fodder. Friday's work is the post's spine.
   Capture while the rationale is fresh. Scaffolded at
   `docs/internal/BLOG_NOTES.md` (2026-05-10).
3. **SD.cluster → Acknowledgments**. Slip-prone in the room. Names
   captured in `docs/internal/ACKNOWLEDGMENTS_DRAFT.md`.

---

## Per-requirement status

### Part 2 — Variant effect prediction

#### 2.0 Notebook clean-Colab T4 smoke test (added 2026-05-10)
**Status:** ❓
**Evidence:** Per Q1, the workshop notebook (`01_workshop_followalong.ipynb`)
is **Path A** — the audience-facing live demo. No EXPERIMENT_LOG entry
covers a fresh-Colab-T4 run of the notebook from a public clone. The
notebook depends on `wget` from `raw.githubusercontent.com/.../main/...`
which 404s while the repo is private (P.5). Cell 17 falls back to live
scoring if `data/s3_scores.npz` is absent (which it is — see 2.7).
**Smallest fix path:** after P.1 + P.5 + 2.7 land, open the Colab badge
in a fresh kernel from a Google account with no GitHub auth. Run S1 → S2
→ S3 in order. Record (a) per-section wall time, (b) any cell needing a
manual fix, (c) whether the cache hit or live-scored. Repeat from a
second Google account to confirm no auth dependency. This is the audit's
single most important pre-talk smoke test.
**Smoke test:** click the Colab badge in `README.md` → Run all → confirm
last cell renders without error in <15 min.

#### 2.1 Canonical Phase-1 prompt → 2 commands
**Status:** ✅
**Evidence:** `CLAUDE.md` lines 50–70 document the exact two commands. `EXPERIMENT_LOG.md` entry dated 2026-05-07 (commit `940dc58` and again under `cceb1fa` sandboxed) shows both commands executing end-to-end and producing wandb runs (`0qpvx1s4`, `od5yp85x`) plus local PDF/CSV. The bundled `experiments/data/clinvar/` removes the NCBI prerequisite, so step 0 is `uv sync --extra workshop` only. **Per Q1 this is Path B** (slide-referenced, BYO-CLI attendees) — the audience-facing live demo is Path A (the notebook).
**Smoke test (from a clean clone, project root):**
```bash
git clone --recurse-submodules https://github.com/latent-reasoning-works/lrw-vep-ub2026
cd lrw-vep-ub2026
(cd experiments/tools/manylatents-omics && uv sync --extra workshop)
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
    --config-path=$(pwd)/experiments/configs/manylatents-omics \
    experiment=encode_esm1b_brca1 algorithms.latent.encoder_config.device=mps
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/analysis/00_demo_umap.py
```

#### 2.2 BRCA1 data bundled
**Status:** ✅
**Evidence:** `experiments/data/clinvar/` contains `variants.tsv` (196 KB), `protein.fasta` (1.8 MB), `dna.fasta` and `rna.fasta` stubs (17 KB each). `README.md` records the 2026-05-07 NCBI pull date, schema, and source UniProt accession (P38398). `encode_esm1b_brca1.yaml` pins `data_dir: ${hydra:runtime.cwd}/experiments/data`, so the encode finds the bundled files without any extra flag.
**Smoke test:**
```bash
ls -la experiments/data/clinvar/
head -2 experiments/data/clinvar/variants.tsv
```

#### 2.3 ESM-1b encoder works on CPU, MPS, CUDA
**Status:** 🟡
**Evidence:** `manylatents/dogma/encoders/esm.py` has `device: str = "cuda"` with `self._model.to(self.device)`, so any device string PyTorch accepts will work. CPU validated (default in `batch_encoder_esm1b.yaml`); MPS validated by all 2026-05-07 EXPERIMENT_LOG entries. **CUDA path is not validated** in this repo's logs.
**Smallest fix path:** the Colab T4 run for 2.0 / LD.1 also satisfies this. One task, three checks.
**Smoke test (on Colab T4 or any CUDA box):**
```bash
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
    --config-path=$(pwd)/experiments/configs/manylatents-omics \
    experiment=encode_esm1b_brca1 \
    algorithms.latent.encoder_config.device=cuda data.max_variants=50
```

#### 2.4 Phase-1 end-to-end smoke test
**Status:** ✅ on M-series Mac (≈70 s on MPS for 200 variants per 2026-05-07 entry); ❓ on Colab T4.
**Evidence:** Five EXPERIMENT_LOG entries on 2026-05-07 show end-to-end success on MPS in 60–75 s after warm-up. Per Q1 this is Path B; Path A's Colab T4 timing is what 2.0 chases.
**Smoke test:** see 2.1.

#### 2.5 LLR matches slide formula
**Status:** ✅
**Evidence:** `experiments/notebooks/vep_utils.py:235-276` implements `compute_llr` as `log P_wt(wt|wt_seq) - log P_mut(mut|mut_seq)` evaluated at `mutation.position` with the BOS-offset convention. `test_vep_utils.py:186-261` has two regression tests: `test_compute_llr_increases_with_unlikely_mutation` (sign convention) and `test_compute_llr_uses_correct_bos_offset` (index 1 not index 0).
**Smoke test:**
```bash
cd experiments/notebooks
python3 -m pytest test_vep_utils.py::test_compute_llr_increases_with_unlikely_mutation \
                  test_vep_utils.py::test_compute_llr_uses_correct_bos_offset -v
```

#### 2.6 S2 prototype runs <30 s
**Status:** 🟡 → resolves to ✅ after one-line move
**Evidence:** Notebook cells 8–12 load the model once, then encode two pairs. On T4 with the model already in memory, four encode calls of ≤1024-aa sequences take ~1 s each → ≤5 s for the math, plus plotting. **First-time model load is ~60 s**, currently in cell 8 (the first cell of S2).
**Per Q7 the slide claim is "<30 s after warm-up."**
**Smallest fix path:** move `encoder = ESM1bEncoder()` from cell 8 to the last cell of S1, so the load happens during the orientation portion when nobody is watching the clock. Timed S2 cells (9–12) then honestly run in <30 s. Also: log the cold-start S2 wall time on a fresh Colab T4 so you know the worst case if the warm-up is skipped.
**Smoke test:** open the notebook in Colab T4, run S1 to completion, then `%%time` cells 9–12.

#### 2.7 S3 validation produces real numbers
**Status:** ✅ (cache landed 2026-05-10)
**Evidence:** Cache built via `experiments/scripts/cache_s3_scores.py --device mps` on this M5 Pro: 499/500 variants scored in **3.8 min** at 2.19 var/s. Output `experiments/notebooks/data/s3_scores.npz` (64 KB, 6 arrays matching cell 17's schema). 249 benign / 250 pathogenic across 437 unique genes. AUROC delta_norm=0.6065, LLR=0.6381 — both above chance, LLR > delta_norm. One variant skipped (`clinvar_701307`: `*` stop codon in WT FASTA). Cache file at `experiments/notebooks/data/s3_scores.npz`. **Notebook S3 cell 17 now loads in <100 ms instead of running 10 min live; Friday B10 is no longer live-fragile.**
**Open follow-up (Q5 "ship both"):** cell 17 currently goes cache-first. Per Q5 the demo flow should start live and fall back to cache invisibly. Flipping the try-order is a one-line cell-17 edit; do post-Friday or at the same time as the 2.6 encoder-load move (P-tier item 9).
**Caveat (pre-collapse):** cache was built with HF transformers (`vep_utils.ESM1bEncoder`) since 2.11 hasn't merged on this clone yet. Numbers will shift slightly if regenerated from fair-esm post-2.11. Not a Friday blocker — Friday demo uses this cache; the post-2.11 regen lands with REL.1.
**Smoke test:**
```bash
test -f experiments/notebooks/data/s3_scores.npz && \
    /Users/cmvcordova/code/lrw/lrw-vep-ub2026/experiments/tools/manylatents-omics/.venv/bin/python -c "
import numpy as np
z = np.load('experiments/notebooks/data/s3_scores.npz', allow_pickle=True)
assert set(z.keys()) == {'variant_id','gene','label','delta_norm','llr','seq_len'}
assert len(z['variant_id']) >= 480
print(f'{len(z[\"variant_id\"])} variants, schema OK')
"
```

#### 2.8 Phase-2 cluster path validated
**Status:** ❌ (live), 🟡 (config exists)
**Evidence:** `encode_esm1b_brca1_mila.yaml` exists and inherits Phase-1 with `cluster: mila` + `launcher: mila_cluster`. Both configs ship with the manylatents venv. **CLAUDE.md line 117 and EXPERIMENT_LOG.md both explicitly flag this as "untested live as of 2026-05-07."** No EXPERIMENT_LOG entry exists for the `_mila` config.
**Smallest fix path:** between now and the talk, dispatch the config from a Mila login node and capture the wandb run URL + a screenshot of the squeue/sacct line; commit those as evidence and adjust the slide to "submitted live earlier today" or "submitted earlier this week, see [URL]." If a live run isn't possible, switch the slide to a recorded screencast with the same artifacts. Land the result in DR.1.
**Smoke test (on Mila login node):**
```bash
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
    --config-path=$(pwd)/experiments/configs/manylatents-omics \
    experiment=encode_esm1b_brca1_mila
```

#### 2.9 Resolution plots can be generated
**Status:** ❌
**Evidence:** No script under `experiments/analysis/` produces a side-by-side n=2 / n=500 / n=2,000 panel. The only script is `00_demo_umap.py`. No literature-anchor figure in `shared/figures/` either.
**Smallest fix path:** add `experiments/analysis/01_resolution_panels.py` that loads (a) `data/s3_scores.npz` for the n=500 panel, (b) two pre-cached encodings for the n=2 panel, and (c) either a multi-gene sweep CSV for n=2,000 or a hand-traced reference figure (Brandes 2023 Fig 2B). Same axes/colors across panels. Cite both in `PROVENANCE.md`.
**Smoke test:** none possible — implementation does not exist.

#### 2.10 Harness stack has real referents
**Status:** ✅ (after slide reword per Q2)
**Evidence:** Each layer maps to a real artifact:
- `CLAUDE.md` → `/Users/cmvcordova/code/lrw/lrw-vep-ub2026/CLAUDE.md` (12 552 bytes).
- Hydra experiment configs → `experiments/configs/manylatents-omics/experiment/` (10 YAMLs).
- `manylatents-omics` submodule → SHA-pinned at `cceb1fa` per `git submodule status`.
- submitit launcher → `manylatents/configs/launcher/mila_cluster.yaml` (in venv after `uv sync`).
- wandb env vars → `.env.example` lines 5–7.

**Per Q2: drop "shop" from the stack diagram. Replace with "submitit launcher."** Speaker notes acknowledge shop as future LRW work that wraps submitit. Do not implement `shop/` in this repo.

**Smoke test:**
```bash
ls CLAUDE.md ARCHITECTURE.md \
    experiments/configs/manylatents-omics/experiment/encode_esm1b_brca1.yaml \
    experiments/tools/manylatents-omics/manylatents \
    experiments/tools/manylatents-omics/.venv/lib/python3.12/site-packages/manylatents/configs/launcher/mila_cluster.yaml \
    .env.example
```

#### 2.11 Variant-effect API surface in `manylatents-omics` (added 2026-05-10)
**Status:** ❌ today; non-optional now per Friday boss-demo timing.
**Evidence:** Probed 2026-05-10 from the submodule's venv:
- `from manylatents.api import run` → OK (base library, generic geometry runner: `data + algorithm + metrics`).
- `from manylatents.dogma import encode_variant, compute_llr` → **`ImportError`**.
- `from manylatents.dogma.api import ...` → `ModuleNotFoundError`.
- `import manylatents_omics` → `ModuleNotFoundError` (the package name is namespace-extended `manylatents.dogma`, not `manylatents_omics`).
- `grep -rn "def compute_llr|def encode_variant|def apply_mutation"` against the whole submodule → **zero matches**.

The variant-effect helpers (`encode_variant`, `compute_llr`, `apply_mutation`, `parse_mutation`, `compute_delta_norm`, `compute_cosine_distance`, `compute_lid`, `truncate_around_mutation`, `validate_*`) live **only** in `experiments/notebooks/vep_utils.py`. The submodule exposes the building blocks (`manylatents.dogma.encoders.ESMEncoder` for fair-esm, `BatchEncoder`, `ClinVarDataModule`) but no top-level VEP API.

One subtlety: `ESMEncoder.encode()` returns the mean-pooled embedding only, even though fair-esm's underlying `_model(tokens, repr_layers=[...])` already produces logits. Computing LLR at the mutation position requires the logits — they're computed and discarded today.

**Smallest fix path (~half-day upstream):**
1. Extend `manylatents/dogma/encoders/esm.py::ESMEncoder` with `encode_with_logits(seq) → (embedding, logits)` (or a `return_logits` kwarg). The model already produces them — just wire them through. ~20 lines.
2. Add a tiny `ESMEncoder.tok_id(aa: str) -> int` helper that wraps `self._alphabet.get_idx(aa)`. B9's inline command uses it twice per variant (WT + MUT token ids for `compute_llr`); without it, B9 has to reach into `_alphabet` directly, which leaks the fair-esm internals into the demo script. ~3 lines.
3. Port the pure-Python helpers from `experiments/notebooks/vep_utils.py` into a new `manylatents/dogma/vep.py`: `parse_mutation`, `validate_sequence`, `validate_mutation`, `apply_mutation`, `truncate_around_mutation`, `encode_variant`, `compute_delta_norm`, `compute_cosine_distance`, `compute_llr`, `compute_lid`. Straight copy. Update `encode_variant` to call `encoder.encode_with_logits` (step 1) instead of the bespoke HF transformers loop in `vep_utils.py`.
4. Re-export from `manylatents/dogma/__init__.py`: add `"vep"` to `__all__` and the `__getattr__` lazy-import block.
5. **When work begins**, append a one-liner to `experiments/EXPERIMENT_LOG.md` marking the boundary — e.g. *"2026-05-XX — pre/post 2.11 collapse boundary. Entries above this line reference `vep_utils.py` (HF transformers); entries below reference `manylatents.dogma.vep` (fair-esm). Wall-time numbers may shift with the loader change."* Two-minute hygiene task that prevents future readers from misinterpreting 2026-05-07 entries as evidence of the post-collapse code path.

After this lands, the Colab notebook (Path A) becomes:
```python
!pip install manylatents-omics
from manylatents.dogma.encoders import ESMEncoder
from manylatents.dogma.vep import encode_variant, compute_llr
```
And `experiments/notebooks/vep_utils.py` collapses to a deprecation shim re-exporting from `manylatents.dogma.vep`. **Path A and Path B merge** — same encoder class, same LLR function, same BOS-offset convention by construction.

**Caveat — fair-esm vs HuggingFace transformers (decided per Q-followup: fair-esm).** The current `vep_utils.py` uses HF transformers; `manylatents.dogma.ESMEncoder` uses fair-esm. Both load the same weights but tokenize differently and have non-bit-identical embeddings. fair-esm is what the rest of `manylatents-omics` uses, so it's the natural canonical loader — but Colab attendees pay a ~30 s install hit (`pip install fair-esm`) that HF transformers (pre-installed on Colab) doesn't impose. Confirm this fits the demo's runtime budget when 2.0 is timed.

**Smoke test (post-collapse, from a clean clone):**
```bash
experiments/tools/manylatents-omics/.venv/bin/python -c "
from manylatents.dogma.encoders import ESMEncoder
from manylatents.dogma.vep import encode_variant, compute_llr, parse_mutation
print('API surface OK')
"
# And that the LLR regression test agrees:
cd experiments/notebooks
python3 -m pytest test_vep_utils.py::test_compute_llr_uses_correct_bos_offset -v
```

---

### Part 3 — Consolidation and integration

#### 3.1 Intermediate consolidation files
**Status:** 🟡
**Evidence:** Phase-1 produces `embeddings.pt` (torch dict) + `demo_umap_brca1.csv` + `.{pdf,png}`. Gaps: `embeddings.pt` is binary, not JSON/CSV; filenames don't carry a run identifier; no JSON sidecar with config hash + wandb run id.
**Smallest fix path:** add a thin post-step that writes `results/demo_umap_brca1__<run_id>.csv` (renamed) and `results/demo_umap_brca1__<run_id>.json` (sidecar: source `embeddings.pt` path, hydra config hash, wandb URL, P/B counts, generated-at timestamp). Update `experiments/CLAUDE.md` with a one-paragraph schema spec. **This is the foundation for 3.2 / LD.3** — do them as one task.
**Smoke test:** none until implemented.

#### 3.2 Parse-and-cite metadata
**Status:** ❌
**Evidence:** Grepping the repo for `parse_and_cite|parse-and-cite|stash_query|expstash|consolidat` returns only references in CHANGELOG/ARCHITECTURE strings. The CSV/PDF outputs from `00_demo_umap.py` carry no source-path or parse-method metadata.
**Smallest fix path:** the JSON sidecar from 3.1 is the foundation. Add a CLAUDE.md paragraph showing how the agent answers "where did this number come from?" — read the sidecar, cite source path + parse method. The slide stays "🟢 LIVE."
**Smoke test:** none until implemented.

#### 3.3 Stash-query mechanism (`expstash`) and `expaper` installability
**Status:** ❌ (today), → ✅ once Q3 lands
**Evidence:** `which expstash` → not found. `uv tool list` → `expaper`, `milatools`, `wandb`. The notebook references `expstash` at `/network/scratch/c/cesar.valdez/expstash` (line 689) — a personal checkout, not the public install.
**Per Q3 both ship public:** `github.com/cmvcordova/expstash` and `github.com/cmvcordova/expaper`.
**Smallest fix path:**
1. Verify `uv tool install git+https://github.com/cmvcordova/expstash` works from a clean machine — confirm the install command in the expstash README and update the notebook S4b prompt to match.
2. Verify `uv tool install git+https://github.com/cmvcordova/expaper` works (already tested locally; re-confirm in clean kernel).
3. Run each tool's core command end-to-end against this repo's outputs (expstash: a structured pull from the workshop wandb project; expaper: see 3.4).
4. **If only one can be hardened in time, prioritize expaper** — Overleaf is the more visible live demo per Q3.

**Smoke test:**
```bash
uv tool install git+https://github.com/cmvcordova/expstash
which expstash
uv tool install git+https://github.com/cmvcordova/expaper
expaper --version
```

#### 3.4 Overleaf sync via expaper
**Status:** ❌ (today), → ✅ once Q4 setup lands
**Evidence:** `expaper` CLI installed (`/Users/cmvcordova/.local/bin/expaper`, `expaper v0.1.0`). `git remote -v` → only `origin` — **no `overleaf/master` ref configured.** No `paper/main.pdf` (no `tectonic` either). No EXPERIMENT_LOG entry shows a successful `expaper sync push`.
**Per Q4 set up this week:** create Overleaf project (web UI) → copy git URL → `expaper link-overleaf <url>` → verify `expaper sync push`/`pull` round-trip.
**Live demo for slide 3.4:** the agent edits one paragraph in `paper/main.tex`, runs `expaper sync push`, audience sees the diff land in Overleaf within seconds.
**Fallback (record now, use if needed on the day):** screencast of the diff appearing in Overleaf. Land in DR.1.
**Smallest fix path:** block ~2 h this week. Auth issues with Overleaf's git bridge are common on first setup; do not discover them on talk day. Also confirm the Overleaf project's git URL is reachable from the venue network (some venues block Overleaf's git bridge).
**Smoke test:**
```bash
expaper sync push   # expect: succeeds, prints commit SHA
git log --oneline overleaf/master -3
```

#### 3.5 Tunable gene demo
**Status:** 🟡 (works locally), ❌ on Colab T4 in <15 min today, → ✅ once Q6 bundle lands
**Evidence:** CLAUDE.md lines 94–107 document the override and acknowledge that any non-BRCA1 gene requires regenerating data first via `download_clinvar.py --gene TP53`. That script downloads `variant_summary.txt.gz` (~440 MB).
**Per Q6 pre-bundle 5 genes:** BRCA1 (already), BRCA2, TP53, PTEN, MLH1 under `experiments/data/clinvar/<gene>/`. Document in `experiments/data/clinvar/README.md`. Add a "Run on your own gene" section to the README pointing to `--gene <NAME>` (built-in mappings) and `--uniprot <accession>` (arbitrary). The slide is about the tunable knob, not gene coverage.
**Open question for César:** agent-driven swap (audience names a gene → agent reads the prompt → harness runs it) vs presenter-driven swap (you type it). Agent-driven reinforces the harness thesis but is riskier; presenter-driven is faster and safer. Decide before talk day; the audit needs to know which to verify.
**Smoke test:** see 3.6 + 3.7 + LD.4.

#### 3.6 Built-in UniProt mappings
**Status:** ✅
**Evidence:** `experiments/data/clinvar/README.md` line 29 lists the six accessions; `download_clinvar.py:42-50` defines `DEFAULT_UNIPROT` matching.
**Smoke test:**
```bash
grep -A 8 'DEFAULT_UNIPROT = {' \
    experiments/tools/manylatents-omics/scripts/download_clinvar.py
```

#### 3.7 `--uniprot` flag
**Status:** 🟡 (implemented, untested in this audit)
**Evidence:** `download_clinvar.py` has the flag in its docstring (line 27) and argparse. Unchanged since 2026-05-06.
**Smallest fix path:** run `download_clinvar.py --gene EGFR --uniprot P00533 --max-variants 100` once and commit the result alongside the other genes; that simultaneously validates the flag and gives you a 7th demo gene. (Or skip and rely on `--gene` for the bundled five per Q6.)
**Smoke test:**
```bash
python3 experiments/tools/manylatents-omics/scripts/download_clinvar.py \
    --gene EGFR --uniprot P00533 --max-variants 50 \
    --data-dir /tmp/clinvar_test
test -s /tmp/clinvar_test/variants.tsv && echo OK
```

#### 3.8 pptx wiring
**Status:** ❌, → reframe-as-aspirational per Q3 not-in-scope
**Evidence:** No pptx code in repo. Per Q3 expaper + expstash are the in-scope tools; pptx is downstream.
**Smallest fix path:** reframe the slide ("the same parse-and-cite pattern would extend to slide decks via python-pptx — out of scope for this workshop").
**Smoke test:** none.

---

### Live-demo readiness (talk-day blockers)

#### LD.1 Phase-1 (Part 2 main demo) on Colab T4 from clean clone in <15 min
**Status:** ❓
**Evidence:** Per Q1, **the audience-facing live demo is Path A (the notebook)** — see 2.0. Path B (the two CLAUDE.md commands) is for BYO-CLI attendees on M-series Mac / Linux and has been validated locally at ~70 s. Two risks for either path: (1) repo private — Colab can't fetch (P.5). (2) `uv sync --extra workshop` on a fresh Colab kernel takes ~3 min (Path B only).
**Smallest fix path:** see 2.0. The same Colab T4 smoke also satisfies 2.3 (CUDA path) and 2.4 (Phase-1 timing on T4).
**Smoke test:** see 2.0.

#### LD.2 Phase-2 cluster — live or fallback
**Status:** ❌
**Evidence:** see 2.8.
**Smallest fix path:** see 2.8 + DR.1.

#### LD.3 Parse-and-cite live demo against Phase-1 outputs
**Status:** ❌
**Evidence:** see 3.2.
**Smallest fix path:** see 3.1 + 3.2 (JSON sidecar + agent paragraph).

#### LD.4 Tunable gene demo on Colab T4 in <15 min
**Status:** ❌, → ✅ once Q6 bundle lands
**Evidence:** see 3.5.
**Smallest fix path:** pre-bundle BRCA1, BRCA2, TP53, PTEN, MLH1 per Q6. After bundling, run an override path on Colab T4 (`data.genes=[TP53] data_dir=experiments/data/clinvar/tp53`) and time it. Should run in the same time budget as BRCA1.
**Smoke test:** after pre-bundling, run the override on Colab T4 and time it.

---

### Polish (must-do before flipping repo public)

#### P.1 License pinned to MIT
**Status:** ❌, → ✅ in two file changes per Q8
**Evidence:** No project-root `LICENSE`. **No project-root `pyproject.toml` exists** (only the submodule's). `ARCHITECTURE.md §10` line 234 still says "TBD."
**Per Q8:** required = `LICENSE` (MIT, full text) at repo root + `ARCHITECTURE.md §10` "TBD" → "MIT". Optional = `pyproject.toml` only if one already exists at root (it doesn't, so skip).
**Smoke test:** `test -f LICENSE && grep -q "MIT" LICENSE && echo OK`.

#### P.2 S4 personal scratch paths replaced
**Status:** ❌
**Evidence:** Notebook lines 635 (`/network/scratch/c/cesar.valdez/expaper`) and 689 (`/network/scratch/c/cesar.valdez/expstash`).
**Smallest fix path:** once Q3 lands install commands for both tools (public GitHub URLs), replace the path with the install command in each S4 prompt — or substitute `<YOUR_LOCAL_PATH>` with a one-line note, whichever the slide flow prefers. Either way, drop the personal paths.
**Smoke test:** `grep -c '/network/scratch/c/cesar.valdez' experiments/notebooks/01_workshop_followalong.ipynb` → should be 0.

#### P.3 Stale `**TOREMOVE` annotations stripped
**Status:** ✅
**Evidence:** Grep returns no matches in user-visible content. `paper/main.tex` has intentional `% TODO(agent)` scaffolding — leave it.
**Smoke test:**
```bash
grep -rn 'TOREMOVE' --include='*.md' --include='*.py' --include='*.ipynb' \
    --include='*.tex' --include='*.yaml' --include='*.yml' . 2>/dev/null \
    | grep -v '/.venv/\|/.git/'
```

#### P.4 Wandb entity portability
**Status:** ❌
**Evidence:** `encode_esm1b_brca1.yaml:65-66` defaults to `cesar-valdez-mcgill-university`. README quickstart has no override callout — only `.env.example` mentions it.
**Smallest fix path:** add a 4-line "Workshop attendees: set `WANDB_ENTITY` to your team or use offline mode (`WANDB_MODE=offline`)" callout in `README.md` between Quickstart and "Without Claude Code." Optionally create a public `lrw-workshop` wandb team. Touch on it again in OB.1 install instructions.
**Smoke test:** `grep -A 2 -i 'wandb' README.md | head -20`.

#### P.5 Repo public-flip pre-flight
**Status:** ❌ (untestable until flipped)
**Evidence:** Repo private. Notebook hard-codes `https://raw.githubusercontent.com/.../main/...` which 404s while private.
**Smallest fix path:** sequence the public flip *before* the talk: (1) close P.1, P.2, P.4 + 2.7 cache work first; (2) flip public; (3) test the Colab notebook from a clean Google account (this IS 2.0); (4) clean-clone smoke test of Phase-1 from a different machine (this IS OB.1 partial).
**Smoke test (post-flip):** see 2.0 and OB.1.

---

### Cross-cutting (added 2026-05-10 review)

#### OB.1 Break-time install across attendee laptops
**Status:** ❓
**Evidence:** README quickstart documents two install paths. Neither is verified within a 15-minute budget across Mac M-series, Intel Mac, Linux, Windows + WSL. The Hydra path requires `uv` + submodule init + `uv sync --extra workshop`. The Colab path requires only a working browser.
**Smallest fix path:** before the talk, dry-run the README quickstart on at least three OSes (M-series Mac is covered; add Intel Mac, Linux, WSL — borrow laptops if needed). For each: time the install, log failure modes, update README with OS-specific notes if any path needs them. If the Hydra path doesn't fit 15 min on Intel Mac / WSL, prefix the quickstart with "for the workshop, use the Colab path; the Hydra path is for after the talk."
**Smoke test:**
```bash
time (git clone --recurse-submodules <url> && \
      cd lrw-vep-ub2026/experiments/tools/manylatents-omics && \
      uv sync --extra workshop)   # expect under 6 min on a fresh checkout
```

#### DR.1 Live-demo failure runbook
**Status:** ❌
**Evidence:** Fallbacks are scattered — S3 cache (2.7), Phase-2 logs/screenshots (2.8 / LD.2), Overleaf pre-recorded screenshots (3.4) — but no single document collects the contingency plan per LIVE slide.
**Smallest fix path:** add `experiments/DEMO_RUNBOOK.md` with one row per LIVE slide: slide → expected behaviour → failure modes → fallback artifact (path or URL) → who triggers the fallback (you vs the agent). Keep it under one page. Tie each row to the audit's smoke tests so the runbook stays in sync.
**Smoke test:** none until written.

#### REL.1 Releases of `manylatents` and `manylatents-omics` before Friday (added 2026-05-10)
**Status:** ❌
**Evidence:** Both packages are at v0.1.x current; neither has the variant-effect API (gated by 2.11). The submodule pin in this repo (`cceb1fa`) is a workshop branch tag, not a published release. Boss demo wants `pip install manylatents-omics` to deliver the collapsed API directly to a Colab cell — the submodule path won't fly there.
**Priority:** rank 1–2 alongside 2.11. REL.1 cannot complete until 2.11 lands.
**Smallest fix path:**
1. Land 2.11 (variant-effect API in `manylatents.dogma.vep`, plus `encode_with_logits` on `ESMEncoder`).
2. In the `manylatents-omics` repo: bump version, regression-test against `vep_utils.py` outputs (LLR rankings agree, delta norms agree to within float tolerance), tag, push to PyPI.
3. If `manylatents` (base) needs companion changes for the API to load cleanly, cut a matching base release.
4. Pin both versions in this repo: update `experiments/tools/manylatents-omics/pyproject.toml` (or wherever the boss-demo install reads from) and bump the `.gitmodules` SHA to the release tag's commit.
5. Re-test the Phase-1 commands — they still resolve to two commands and produce a wandb run.
**Boss-demo dependency:** this is the gate that lets the Friday code-along say "pip install manylatents-omics" rather than "git clone --recurse-submodules and uv sync." The latter is fine for BYO-CLI attendees but not for a fresh Colab cell in front of the boss.
**Smoke test (post-release, from a clean clone):**
```bash
git clone https://github.com/latent-reasoning-works/lrw-vep-ub2026
cd lrw-vep-ub2026
uv venv && uv pip install manylatents-omics  # the published version, not the submodule
.venv/bin/python -c "from manylatents.dogma.vep import encode_variant, compute_llr; print('OK')"
# Then the canonical Phase-1 prompt resolves with the published package, not the submodule pin.
```

#### SD.1 Slide 2.4 "Where the agent enters" — title-only (slide gap, not repo gap)
**Status:** ❌
**Evidence:** Per César 2026-05-10, slide 2.4 is title-only in the deck.
**Smallest fix path:** out of scope for the repo audit. Flagged so it doesn't slip past you while you're working through the repo items.
**Smoke test:** none — slide deck is outside the repo.

---

## Decisions captured (2026-05-10)

César's answers to the open questions, locked in. Cite this section in any
follow-up.

1. **Phase-1 path (Q1):** Two paths, distinct roles.
   - **Path A (primary, on-stage):** Colab notebook S1–S3 with the
     self-contained `vep_utils.ESM1bEncoder` (HuggingFace transformers).
     No Hydra. **This is what runs live during the LIVE slides.**
   - **Path B (secondary, BYO-CLI):** the two-command Hydra invocation
     in CLAUDE.md, runnable on M-series Mac / Linux. **What the slides
     reference and the harness narrative depends on.**
   - Both must produce qualitatively agreeing outputs (LLR ranking,
     AUROC) — not bit-identical embeddings.
   - Each step writes an intermediate `.csv` / `.json` gate so the next
     step can resume on slip.
   - **Open follow-up:** the slides currently show Path B's verbose
     Hydra command but the live stage demo runs Path A. Decide whether
     the slides need a "what attendees see in Colab" sidebar.

2. **Harness stack (Q2):** Drop `shop` from the diagram. Replace with
   `submitit launcher`. Stack: **CLAUDE.md → Hydra experiment configs →
   manylatents-omics → submitit launcher → wandb.** Speaker notes
   acknowledge `shop` as future LRW work that wraps submitit. Do not
   implement `shop/` in this repo.

3. **expstash and expaper (Q3):** Both ship; both are public.
   - `expstash` — `github.com/cmvcordova/expstash`. Structured wandb
     pulls. Needed for slide 3.3 + parse-and-cite.
   - `expaper` — `github.com/cmvcordova/expaper`. Paper scaffolding +
     Overleaf sync. Needed for slide 3.4 + the full research cycle slide.
   - Audit must verify each installs cleanly via
     `uv tool install git+https://github.com/cmvcordova/<name>` and runs
     against this repo's outputs.
   - **If only one can be hardened in time, prioritize `expaper`** —
     Overleaf is the more visible live demo.

4. **Overleaf setup (Q4):** Set up this week (~2 h block).
   - Create Overleaf project (web UI) → copy git URL.
   - `expaper link-overleaf <url>` from repo root.
   - Verify `expaper sync push`/`pull` round-trip.
   - Live demo for slide 3.4: agent edits paragraph → `sync push` →
     audience sees diff in Overleaf within seconds.
   - Fallback: pre-recorded screenshots (capture this week, file under DR.1).
   - **Confirm the Overleaf git URL is reachable from the venue
     network** — some venues block Overleaf's git bridge.

5. **`s3_scores.npz` (Q5):** Ship both. Commit a reference cache from a
   clean run. Notebook S3 starts on the live path; on any slip — timing,
   model failure, network — falls back to the cache invisibly. Audience
   sees AUROC either way; only you know which path delivered it.

6. **Audience-picks-gene (Q6):** Pre-bundle BRCA1, BRCA2, TP53, PTEN,
   MLH1 under `experiments/data/clinvar/<gene>/`. Document in clinvar
   README. Add a "Run on your own gene" README section pointing to
   `--gene <NAME>` (built-in) and `--uniprot <accession>` (arbitrary).
   Slide is about the tunable knob, not gene coverage.
   **Open follow-up:** agent-driven swap vs presenter-driven swap. Decide
   before talk day; audit needs to know which to verify.

7. **2.6 timing (Q7):** Slide claim is **"<30 s after warm-up."** Move
   `encoder = ESM1bEncoder()` from cell 8 to the last cell of S1, so the
   model load happens during orientation. Log cold-start S2 wall time on
   a fresh Colab T4 so the worst case is known.

8. **License (Q8):** Required = `LICENSE` (MIT, full text) at repo root
   + `ARCHITECTURE.md §10` "TBD" → "MIT". Optional `pyproject.toml`
   skipped (none exists at root; the wrapper repo doesn't need one).

---

## Friday update (2026-05-10, post-decisions)

Boss demo on Friday (T-5 days) compresses the schedule. Two consequences:

- **2.11 (variant-effect API collapse) is now non-optional.** Confirmed
  ❌ today via direct probe: `from manylatents.dogma import encode_variant,
  compute_llr` raises `ImportError`, the whole submodule has zero matches
  for `def compute_llr|def encode_variant|def apply_mutation`, and
  `ESMEncoder.encode()` discards the logits fair-esm already produces.
  ~half-day of upstream work; details in the 2.11 entry.
- **REL.1 added** — both packages need versioned releases pinned in this
  repo before Friday so the boss demo can install `manylatents-omics`
  from PyPI rather than via submodule + `uv sync`. Sequenced after 2.11.

The **🔴 FRI tier** in the priority table (rows 1–5) is the connected
chunk that the boss demo lands on. Recommended order: 2.11 → REL.1 →
2.7 cache → 2.0 smoke → B8 variant-pair fill + 2.5/2.10 verify.

Companion doc: `docs/internal/WORKSHOP_BEATS.md` (added 2026-05-10) lists
the 21 structural beats the talk lands on, tier-tagged 🔴 FRI / 🟡 TALK /
🟢 NICE, each cross-referenced to its audit gate.

One sub-decision opened by 2.11 that affects everything downstream:
**fair-esm vs HuggingFace transformers as the canonical loader inside
`manylatents.dogma.encoders.ESMEncoder`.** Decided fair-esm (matches the
rest of `manylatents-omics`); Colab attendees pay a ~30 s install hit
that HF transformers wouldn't. Confirm this fits the demo runtime budget
when 2.0 is timed against a fresh Colab T4 kernel.
