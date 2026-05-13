# Architecture

> **Living template** — this document is the agent's first read on landing in
> this repository. Update it as the codebase evolves.
> Conventions follow [architecture.md](https://architecture.md/) (descriptive,
> agent-onboarding) layered with [expaper](https://github.com/cmvcordova/expaper)
> (operational scaffolding).

This repository is the demo harness for the **Upper Bound 2026** workshop:
*A well-plugged harness makes agents drive biological research tasks
automagically.* The repo IS the argument — a Claude Code agent runs the
end-to-end variant effect prediction (VEP) demo, edits this paper, and pushes
to Overleaf, all from a natural-language prompt. The Colab notebook in
`experiments/notebooks/` does the same six tasks manually for attendees
without Claude Code.

---

## 1. Project Structure

```
lrw-vep-ub2026/
├── ARCHITECTURE.md             # this file — agent orientation
├── CLAUDE.md                   # agent operation: how to drive the harness
├── README.md                   # human entry point + workshop quickstart
├── experiments/                # experimentStash (per expaper convention)
│   ├── CLAUDE.md               # tool API contract + numbered-script rules
│   ├── EXPERIMENT_LOG.md       # append-only run chronicle
│   ├── PROVENANCE.md           # figure → script → CSV mapping
│   ├── configs/
│   │   ├── meta.yaml           # tool registry for this project
│   │   └── manylatents-omics/
│   │       └── experiment/     # Hydra overrides — these ARE the prompts
│   │           ├── encode_evo2.yaml
│   │           ├── encode_esm3.yaml
│   │           ├── encode_orthrus.yaml
│   │           ├── alignment_matrix.yaml
│   │           ├── fusion_base.yaml
│   │           ├── fusion/      # autoencoder, concat, svd, ...
│   │           └── single_modality_baselines.yaml
│   ├── tools/
│   │   └── manylatents-omics/  # git submodule — pinned, has its own ARCHITECTURE.md
│   ├── scripts/                # add_tool, run_experiment, snapshot_experiment
│   ├── notebooks/
│   │   └── 01_workshop_followalong.ipynb   # Colab fallback, 1:1 with agent path
│   ├── analysis/               # numbered scripts (NN_*.py) — paper-cited code
│   └── outputs/                # raw runs (gitignored)
├── paper/
│   ├── main.tex                # NeurIPS-style preprint (arXiv-bound)
│   └── neurips_2024.sty        # official style file
├── shared/
│   ├── bib/references.bib
│   └── figures/                # figures shared between paper and analysis
└── .gitmodules
```

## 2. High-Level System Diagram

```
   user prompt ──┐                                paper/main.tex
                 ▼                                       ▲
            ┌─────────┐    Hydra configs (prompts)       │
            │  agent  │ ──── ▶  experiments/configs/  ──┐│
            └─────────┘             manylatents-omics/  ││
                 │                  experiment/*.yaml   ││
                 │                                       ││
                 ▼                                       ▼│
       ARCHITECTURE.md  ──orient─▶                manylatents
       CLAUDE.md        ──operate─▶                  .main
       experiments/                                     │
       CLAUDE.md                                        │
                                                        ▼
                                                  results/*.csv
                                                  figures/*.pdf
                                                        │
                                                        ▼
                                              expaper build (tectonic)
                                                or expaper sync push
                                                (→ Overleaf coauthors)
```

## 3. Core Components

### `experiments/tools/manylatents-omics/` (submodule)

Hydra plugin for `manylatents` that adds biological encoders (Evo2, Orthrus,
ESM3) and cross-modal alignment metrics. Has its own `ARCHITECTURE.md` and
`CLAUDE.md` — read them before invoking the tool. Entry point for all runs:

```bash
cd experiments/tools/manylatents-omics
.venv/bin/python -m manylatents.main +experiment=<name>
```

### Encoder protocol (the central abstraction)

VEP scoring is interface-agnostic over the encoder. The repo ships two
implementations of the same conceptual contract — a notebook prototype
and a library — that differ in method-name shape but produce compatible
outputs. Any new backend (hosted inference, batched, distilled,
cross-modal) must preserve one of these surfaces:

| Layer | Module | Tuple-returning method | Embedding-only method | Max-length attr | Backend |
|---|---|---|---|---|---|
| **Prototype** (live demo) | `experiments/notebooks/vep_utils.ESM1bEncoder` | `.encode(seq) -> (embedding, logits)` | — (the tuple form is the only encode method) | `.MAX_LEN` | HF `transformers` |
| **Library** (sweep + cluster) | `manylatents.dogma.encoders.ESMEncoder` | `.encode_with_logits(seq) -> (embedding, logits)` | `.encode(seq) -> embedding` | `.max_length` | `fair-esm` |

The two implementations differ deliberately: the prototype's
single-method API minimizes the live-demo cell count; the library's
two-method API supports the common case where callers (e.g.,
`BatchEncoder`) want embeddings only. `manylatents.dogma.vep.encode_variant`
duck-types against `encode_with_logits` and `max_length`; the notebook's
own `vep_utils.encode_variant` duck-types against `encode` and `MAX_LEN`.
Either backend → either scoring helper is the matrix the harness
supports.

**S1–S3 of the notebook use the prototype. S4 agent handoffs target the
library.** That's the workshop's narrative arc encoded in code. The
canonical scope for "score variants without a local GPU" is the
**notebook scope** — subclass `vep_utils.ESM1bEncoder` and live in
`experiments/notebooks/vep_utils.py`. The library scope (subclass
`FoundationEncoder`) is the cluster/sweep path.

**Contract.** A conforming encoder exposes:

| Member | Type | Invariants |
|---|---|---|
| `.encode_with_logits(seq: str) -> (np.ndarray, np.ndarray)` | method | Returns `(embedding, logits)`. `embedding` is mean-pooled across residue positions, shape `(D,)`, `D=1280` for ESM-1b/ESM-2-650M. `logits` is per-position over the model vocabulary, shape `(L+2, V)` — BOS at index 0, residues 1..L, EOS at L+1. The +2 framing is preserved across backends so downstream LLR / delta computations index the same way. |
| `.max_length` *(library)* or `.MAX_LEN` *(prototype)* | int | Max residue count the backend can process without truncation. For ESM-1b: **1022** (the 1024-slot position table minus BOS + EOS). Callers must `truncate_around_mutation` upstream when sequences exceed this. |
| `.encode(seq: str) -> np.ndarray` | method *(optional)* | Returns embedding only. Convenience for callers that don't need logits. Default impl: discard the second return of `encode_with_logits`. |

**Where to add a new backend.**

- *Library scope* (sweep-able, cluster-launchable, registry-discoverable):
  subclass `manylatents.algorithms.latent.foundation_encoder.FoundationEncoder`
  and register in `manylatents.dogma.encoders.__init__`. Existing
  examples: `ESMEncoder`, `Esm3Encoder`, `Evo2Encoder`,
  `OrthrusNativeEncoder`, `AlphaGenomeEncoder`.
- *Notebook scope* (live-demo backend swap, e.g., a hosted-inference
  encoder for no-GPU attendees): mirror the prototype contract by
  subclassing `vep_utils.ESM1bEncoder` and overriding `.encode`. Keep
  the file in `experiments/notebooks/vep_utils.py` alongside the
  baseline. See the parity protocol in
  [`experiments/notebooks/CLAUDE.md`](./experiments/notebooks/CLAUDE.md)
  for the validation pattern (10-variant subsample, 3-decimal agreement).

**Truncation responsibility.** Neither `vep_utils.encode_variant` nor
`manylatents.dogma.vep.encode_variant` truncates around the mutation
site. The caller does, via `truncate_around_mutation(seq, pos1, window=encoder.max_length)`.
If a caller forgets, both encoders raise a `ValueError` from
`apply_mutation` when the mutation position falls outside the
validate-and-chop window. The notebook's `s2-encode` and
`s3-score-loop` cells, and `experiments/scripts/cache_s3_scores.py`,
all follow this convention.

### `experiments/configs/manylatents-omics/experiment/` — *configs as prompts*

Each YAML file is a structured prompt. `encode_evo2.yaml` says "encode DNA via
Evo2 on the BRCA1 preset." `alignment_matrix.yaml` says "compute $k$-NN
Jaccard between DNA and protein embeddings." The agent translates a natural-
language ask into a config file, or selects an existing one and overrides via
Hydra CLI (`data.preset=clinvar`).

### `experiments/analysis/` — numbered scripts (when populated)

Per `experiments/CLAUDE.md`'s contract: each `NN_*.py` is a paper-anchored,
direct-API call into the tool. No wrappers, no re-implementations. Outputs
land in `analysis/results/` and `analysis/figures/`.

### `paper/`

NeurIPS-style preprint scaffold. Compiles locally via `tectonic`
(`expaper build`) or syncs to Overleaf via git subtree
(`expaper sync push/pull`). The `[preprint]` style option keeps author names
visible (arXiv-bound, not anonymous submission).

### External CLIs (`expaper`, `expstash`, `expanalysis`)

The harness depends on three external CLIs that live outside the repo. An
agent landing on any S4-style handoff task reaches for these rather than
hand-rolling equivalents. Each enforces conventions documented in §6.

| Tool | Path | Purpose | Primary commands |
|---|---|---|---|
| `expaper` | `/network/scratch/c/cesar.valdez/expaper` | Paper-project scaffolding + Overleaf sync. Already used to generate this repo's layout. | `expaper init <name>`, `expaper add-tool <path>`, `expaper link-overleaf <url>`, `expaper sync pull/push`, `expaper build --open` |
| `expstash` | `/network/scratch/c/cesar.valdez/expstash` | Experiment-registry + wandb-native sweep orchestration | `expstash add-experiment`, `expstash launch <experiment>`, `expstash fetch <sweep_id>` |
| `expanalysis` | `/network/scratch/c/cesar.valdez/expanalysis` | Cross-experiment figure aggregation + summary tables | `expanalysis aggregate`, `expanalysis figure <name>` |

The canonical sub-command form for `expaper` is `add-tool` (hyphenated,
single noun-verb pair). `<tool> --help` is the authoritative interface
for each. If a `which expaper` returns no result, the CLI hasn't been
installed on the current machine — fall back to running through the
scratch path directly.

## 4. Data Stores

- **In-repo:** Hydra configs (`experiments/configs/`), notebook source, paper
  source, `references.bib`, the `manylatents-omics` submodule pin.
- **Generated, gitignored:** `experiments/outputs/` (Hydra `outputs/` and
  `multirun/`), `analysis/embeddings/`, `analysis/data/`, tool venvs
  (`tools/*/.venv`).
- **Generated, committed:** `analysis/results/*.csv`, `analysis/figures/*.pdf`,
  `paper/main.pdf` (only when stable). The "what's committed" gate: anything
  the paper cites must be reproducible from a committed CSV.
- **External:** model weights for Evo2 / Orthrus / ESM3 are downloaded by the
  tool on first use (see `manylatents-omics/ARCHITECTURE.md` §3 for paths).

## 5. External Integrations

- **PyPI:** `manylatents`, `manylatents-omics` (used as the source of truth
  for the tool; the submodule pin tracks the same upstream).
- **GitHub:** submodule for `manylatents-omics`. Pinned by commit SHA in
  `.gitmodules` for reproducibility.
- **Overleaf** (optional): `paper/` is bidirectionally synced via git subtree.
  Linked post-init with `expaper link-overleaf <url>`.
- **Hugging Face Hub:** model weights for Evo2, ESM-1b/2, and ESM3 download on
  first encode. Orthrus may require a separate path.
- **W&B:** every `encode_*.yaml` sets `logger: wandb`. Defaults baked via
  `${oc.env:WANDB_PROJECT,upper-bound-2026}` and
  `${oc.env:WANDB_ENTITY,cesar-valdez-mcgill-university}` — set in `.env`
  to override per-checkout. Auth via `wandb login` (writes `~/.netrc`).
  Note: free wandb accounts disable personal entities; route to a team.
- **Anthropic API** (Claude Code): the agent's runtime — not a code dep, but a
  participant in the demo loop.

### Conventions for external systems

These are the schemas, parameters, and rules that downstream tooling
(`expstash fetch`, `expanalysis aggregate`, paper figure scripts)
assumes. A run that deviates won't be picked up by the aggregators.

**W&B logging schema.** Every encode/score run logs `auroc`, `ci_lo`,
`ci_hi`, `n_variants`, plus all config fields the run varies
(`layer`, `score`, `model`, `dataset`, …). The tags `[workshop, vep,
sweep]` are conventional for the workshop demos.

**Bootstrap.** AUROC confidence intervals: `n_resamples=10000`,
`seed=42`. Point estimate via `sklearn.metrics.roc_auc_score`;
resampling indices via `np.random.default_rng(42).integers(...)`. The
workshop set manifest and `experiments/PROVENANCE.md` record CIs
under this convention.

**Available score functions** (selectable-by-string in
`manylatents.dogma.vep.score_variant_report`): `delta_norm`,
`cosine_dist`, `llr`, `lid` (with configurable `k`). New scorers
extend the same module-level registry. Sign conventions (which
direction is "more disruptive"):

| Scorer | More disruptive when… | Computed from |
|---|---|---|
| `delta_norm` | **larger** | `‖mut_emb − wt_emb‖₂` over mean-pooled embeddings |
| `cosine_dist` | **larger** | `1 − cos(wt_emb, mut_emb)` |
| `llr` | **more negative** | `log p(mut | seq) − log p(wt | seq)` over masked-LM logits; negative ⇒ MUT less likely than WT ⇒ pathogenic-leaning |
| `lid` | varies with `k` | local intrinsic dim shift; interpret per-`k`, not signed |

At n=2 (the S2 demo pair) the verdict rule is: pathogenic should
have *larger* `delta_norm` AND *more negative* `llr` than benign. If
either inverts, S2 didn't separate them — flag rather than push past.

**Breakdown axes for analyses.** When an agent is asked to surface
"where the signal breaks", the harness-blessed axes are:
- **By gene** — per-gene AUROC requires at least 3 P and 3 B rows;
  below that, fall back to mean-rank or skip. PROVENANCE.md caveat #2
  flags hot label-skewed genes (FBN1 11P/0B, LDLR 6P/0B) as
  not-evaluable.
- **By length regime** — split at `MAX_LEN = 1022` aa (the Brandes /
  ESM-1b boundary). Workshop set: 264 short / 236 long.
- **By ClinVar label-source** — canonical (n=334) vs
  Conflicting-binarized (n=166). Workshop v2's distinguishing
  inclusion; PROVENANCE.md "Composition" table.
- **By substitution property** — BLOSUM62 bucket, charge change,
  or hydrophobicity flip from `aa_ref` / `aa_alt`. Agent's choice;
  disclose which property was used.

**Hosted-encoder backends.** Subclasses that wrap a remote inference
endpoint follow these invariants:
- **Env vars.** API keys go in `.env` (gitignored) under provider-
  matching names: `HF_API_KEY` for HuggingFace Inference,
  `VLLM_API_KEY` for self-hosted vLLM, `AWS_HEALTHOMICS_ROLE_ARN` for
  HealthOmics. `.env.example` lists the canonical names.
- **Retry policy.** Retry on 429 / 5xx with exponential backoff
  (3 attempts, base 2s). Raise on the 4th failure.
- **Vocab/alphabet invariant.** `logits` shape `(L+2, V)` must use
  the fair-esm ESM-1b alphabet ordering for index/residue alignment
  with `compute_llr`. A backend whose tokenizer reorders the alphabet
  must emit a permutation and apply it before return, or LLR silently
  corrupts.
- **Notebook-scope is canonical for the no-GPU path.** Subclass
  `vep_utils.ESM1bEncoder` and live in `experiments/notebooks/vep_utils.py`.
  Selected at runtime via `WORKSHOP_ENCODER_BACKEND={local,hosted}`
  read in the `s2-load-encoder` cell. The library scope (subclass
  `FoundationEncoder`) is the cluster/sweep path, not the live demo.
- **Parity-gating.** Gated by the protocol in
  `experiments/notebooks/CLAUDE.md` ("Backend parity protocol"):
  10-variant subsample of `workshop_set.tsv`, 3-decimal agreement on
  `delta_norm`/`llr`, embedding cosine ≥ 0.99. Add the test to
  `test_vep_utils.py`; log latency-per-call and per-1000-call cost to
  `EXPERIMENT_LOG.md` under a `Cost-per-1000-calls:` line.

**Figure output paths.** `experiments/analysis/figures/` for
in-experiment paper figures cited via `PROVENANCE.md` (the workshop
default). `shared/figures/` for cross-experiment artifacts consumed by
`expaper`-managed papers; used by sweep aggregation scripts that span
multiple experiments. Filenames default to the script's number prefix
(e.g., `01_resolution_panels.py` → `figures/resolution_panels.{pdf,png}`).

**`\includegraphics` path convention** (paper-side). `paper/main.tex`
lives at `paper/`; in-experiment figures live at
`experiments/analysis/figures/`. Use a relative path:
`\includegraphics{../experiments/analysis/figures/<name>.pdf}`. The
existing `demo_umap_brca1.pdf` and `resolution_panels.pdf` references
in `paper/main.tex` follow this pattern.

## 6. Deployment & Infrastructure

This is a research repo, not a service — "deployment" means *the demo path*.
The workshop ships two demo phases:

**Phase 1 — local agentic run (the canonical test):** the user prompts the
agent ("score top 200 ClinVar BRCA1 missense with ESM-1b, UMAP, log to
wandb"). The agent reads `CLAUDE.md`, runs:

```
cd experiments/tools/manylatents-omics
.venv/bin/python -m manylatents.main +experiment=encode_esm1b_brca1
cd ../..
.venv/bin/python experiments/analysis/00_demo_umap.py
```

Results land in W&B at `cesar-valdez-mcgill-university/upper-bound-2026`.

**Phase 2 — cluster sbatch handoff:** same prompt, but the agent dispatches
the encode step via `sbatch` to Mila / Tamia / DRAC (whichever cluster's
config the user picks at run time). Demonstrates the harness's portability.

- **Attendee fallback (Colab):** `experiments/notebooks/01_workshop_followalong.ipynb`
  has an "Open in Colab" badge; runs the same six tasks manually on a free
  T4. Available once the repo is flipped public.
- **CI** (future): a `--smoke` flag on each numbered script (per
  `experiments/CLAUDE.md` contract); runs in <60s on CPU. `00_demo_umap.py`
  already supports `--smoke`.

**Sweep launcher convention.** Hydra multiruns dispatch through one of:
- `hydra/launcher=submitit_slurm` for cluster work (mila, narval, tamia
  — each has a paired `cluster=<name>` config under
  `experiments/configs/manylatents-omics/cluster/`).
- `hydra/launcher=joblib` for local multiruns (laptop / workstation).

Set per-experiment in the Hydra config's `defaults` block; never
inline-override at the CLI. The `encode_esm1b_brca1_slurm_template.yaml`
experiment shows the cluster-handoff pattern; it does not ship a
default cluster — the caller supplies `cluster=<name> launcher=<name>_launcher`
either as Hydra-config `override` lines or at the CLI.

## 7. Security Considerations

- **Credentials:** none committed. `WANDB_API_KEY` lives in `~/.netrc` after
  `wandb login` (never in env or committed). `WANDB_ENTITY`,
  `WANDB_PROJECT`, and `HUGGING_FACE_HUB_TOKEN` read from env via `.env`.
  `.env.example` lists names; `.env` is gitignored.
- **Public exposure:** the repo is **private** during workshop preparation;
  intended to be flipped public the day of the talk. No PHI / PII used —
  ClinVar variants are public.
- **Submodule pinning:** SHA-pinned via `.gitmodules` so a future re-clone
  doesn't pull a moved/breaking upstream.
- **Overleaf:** treat `overleaf/master` as a live coauthor; never overwrite
  end-to-end (see `CLAUDE.md` *Writing directives → Overleaf sync*).

## 8. Development & Testing Environment

```bash
# Tool environment (where experiments run)
cd experiments/tools/manylatents-omics
uv sync                                              # creates .venv per tool
.venv/bin/python -m manylatents.main +experiment=encode_evo2 data.preset=gfp

# Paper build (no Overleaf needed)
expaper build --open                                 # tectonic → paper/main.pdf

# Adding a new experiment
# 1. Create experiments/configs/manylatents-omics/experiment/<name>.yaml
# 2. Run from tool: .venv/bin/python -m manylatents.main +experiment=<name>
# 3. Append to experiments/EXPERIMENT_LOG.md
```

Python pin: 3.12 (manylatents-omics requires `<3.13,>=3.11`). uv-managed.

## 9. Future Considerations / Roadmap

- **`expaper template create neurips2025`** — currently the template ships
  hand-installed; upstream once we're confident in the layout.
- **Numbered analysis scripts (`analysis/NN_*.py`)** — empty today; populated
  during the workshop demo as the agent produces results.
- **Public ICSB-bound or NeurIPS-bound version** — fork once the workshop
  ships, retitled as the formal paper.
- **`expaper add-tool` patch** for namespace packages — current
  `experiments/scripts/add_tool` doesn't find configs/main.py when the
  tool's package dir name differs from the tool name (e.g.
  `manylatents-omics` ships under `manylatents/`). Worked around
  manually here. Note: `add-tool` is the CLI subcommand form (canonical
  per §3); `add_tool` is the in-repo script file. Different things.

## 10. Project Identification

| Field | Value |
|---|---|
| Name | `lrw-vep-ub2026` |
| Owner | `latent-reasoning-works` |
| License | TBD (likely MIT, matching expaper / manylatents) |
| Maintainer | César M. Valdez Córdova |
| Workshop | Upper Bound 2026 |
| Companion paper | arXiv preprint (NeurIPS-style; venue TBD) |
| Companion talk | Upper Bound 2026 — *Agentic Research Engineering* |

## 11. Glossary

- **Harness** — the opinionated layer that lets an agent operate a research
  tool without rediscovering its API. Comprises CLAUDE.md, ARCHITECTURE.md,
  Hydra configs, and tool-specific contracts.
- **VEP** (Variant Effect Prediction) — predicting whether a DNA variant is
  benign or pathogenic.
- **manylatents** — base Python package for dimensionality reduction and
  cross-modal latent analysis.
- **manylatents-omics** — Hydra plugin that registers biological encoders
  (Evo2, ESM3, Orthrus) and dataset modules for `manylatents`.
- **Evo2 / ESM3 / Orthrus** — foundation models for DNA, protein, and RNA
  respectively. Used as feature extractors.
- **k-NN Jaccard alignment** — overlap of nearest-neighbor sets between two
  embeddings of the same samples; quantifies cross-modal geometric agreement.
- **Hydra plugin** — Python entry point that extends Hydra's config search
  path; lets `manylatents-omics` add configs without forking `manylatents`.
- **expaper** — research-project scaffolding CLI; this repo was generated by
  `expaper init` and follows its conventions.
- **experimentStash** — the layout under `experiments/` (configs, tools,
  scripts, analysis, outputs); a contract for reproducible experiment runs.
- **Configs as prompts** — the design stance that a YAML in
  `experiments/configs/<tool>/experiment/` is the durable, structured form of
  what a researcher would otherwise type as a prompt.
