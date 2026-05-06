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

### `expaper` (external CLI)

Scaffolding tool — already used to generate this layout. Relevant commands:
`expaper build`, `expaper link-overleaf <url>`, `expaper sync pull|push`,
`expaper tool add`.

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
- **Hugging Face Hub:** model weights for Evo2 and ESM3 download on first
  encode. Orthrus may require a separate path.
- **W&B** (optional): logger configured in `encode_*.yaml` configs as
  `logger: wandb`. Override to `logger: null` if not logging.
- **Anthropic API** (Claude Code): the agent's runtime — not a code dep, but a
  participant in the demo loop.

## 6. Deployment & Infrastructure

This is a research repo, not a service — "deployment" means *the demo path*.

- **Live demo (preferred):** Claude Code on the presenter's laptop, against a
  fresh clone. Heavy GPU steps run remotely via SSH if needed.
- **Attendee fallback (Colab):** `experiments/notebooks/01_workshop_followalong.ipynb`
  has an "Open in Colab" badge; runs end-to-end on a free T4 with the same
  six-task script the agent executes.
- **CI** (future): a `--smoke` flag on each numbered script (per
  `experiments/CLAUDE.md` contract); runs in <60s on CPU.

## 7. Security Considerations

- **Credentials:** none committed. `WANDB_API_KEY`, `HUGGING_FACE_HUB_TOKEN`
  read from env. `.env.example` lists names; `.env` is gitignored.
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
- **`expaper tool add` patch** for namespace packages — current `add_tool`
  script doesn't find configs/main.py when the tool's package dir name
  differs from the tool name (e.g. `manylatents-omics` ships under
  `manylatents/`). Worked around manually here.

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
