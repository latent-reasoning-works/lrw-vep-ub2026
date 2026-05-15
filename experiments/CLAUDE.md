# Experiments

This folder produces every CSV, JSON, and figure cited in the paper or the
slide deck. **Public-facing reproduction surface** — assume a reviewer
lands here cold and runs scripts in numeric order.

## How analysis scripts work (cache-first regenerators)

Every `analysis/NN_*.py` is a *paper-figure regenerator*: it reads a
committed artifact (a `.npz`, `.json`, or Hydra-output `.pt`) and produces
a figure + a results table. Encoding runs upstream — in the notebook
(`s2-encode`, `s3-score-loop`), in `experiments/scripts/cache_s3_scores.py`,
in `experiments/scripts/score_demo_pair.py`, or via a Hydra config
(`experiment=encode_esm1b_brca1`). Analysis scripts **do not call the
encoder**; that's the upstream caller's job. This makes them fast (~5–30 s
on CPU), deterministic (no float drift across machines), and CI-runnable
against committed inputs.

When a numbered script is the producer of an artifact the paper anchors
on (`02_llr_distribution.py` → AUROC headline; `01_resolution_panels.py`
→ slide-anchor figure), it asserts its computed numbers against
`experiments/notebooks/data/workshop_set_manifest.json` within a documented
tolerance. The assertion is the script's own integrity check, not a unit
test.

If you need a primitive that doesn't exist (e.g. a new scorer, a different
truncation strategy), **add it upstream first** — in
`experiments/notebooks/vep_utils.py` (notebook scope) or
`manylatents.dogma.vep` (library scope, in the submodule) — then call it
from your numbered script. Re-implementing scoring rules inside an
analysis script silently forks the methodology.

## Layout

```
experiments/
  CLAUDE.md                  # this file
  EXPERIMENT_LOG.md          # chronicle: what was run when, against which pin
  PROVENANCE.md              # figure → script → input mapping
  configs/<tool>/            # Hydra overrides for sweep launches
  tools/<tool>/              # git submodules
  scripts/                   # producers (cache_s3_scores, score_demo_pair,
                             # pick_demo_pair, build_validation_set,
                             # snapshot_experiment, add_tool, run_experiment)
                             # + `_archive/` for retired one-shots
  notebooks/                 # workshop notebook scope (vep_utils, data, validators)
  analysis/                  # numbered scripts — the reviewer's reading order
    _config.py               # shared paths + I/O helpers
    00_demo_umap.py          # Phase-1 agentic-demo UMAP (reads Hydra .pt)
    01_resolution_panels.py  # 3-panel resolution ladder (reads .json + .npz)
    02_llr_distribution.py   # headline LLR KDE (reads .npz; asserts anchor)
    results/                 # CSVs/JSONs land here
    figures/                 # PDF + PNG land here
    embeddings/              # cached run() outputs
    data/                    # cached intermediate artifacts
    _archive/                # exploratory scripts not on the figure-repro path
  outputs/                   # raw Hydra outputs (gitignored)
```

## Numbered-script contract

Every `analysis/NN_*.py` follows this template:

```python
#!/usr/bin/env python
"""NN_<name>.py — <one-line paper claim this script supports>.

Paper anchor: §<Section> (<arc name>).
Inputs:  <input artifact path(s)>
Outputs: figures/<name>.{pdf,png}, results/<name>.csv [, results/<name>.json]
Runtime: CPU, ~<seconds>
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import _config as cfg

CACHE_PATH = cfg.EXPERIMENTS_DIR / "notebooks" / "data" / "<artifact>.npz"


def main(smoke: bool = False) -> None:
    # 1. Load cached artifact (no encoder calls).
    d = np.load(CACHE_PATH, allow_pickle=True)

    # 2. Compute paper claim (AUROC, summary stat, panel layout, …).
    ...

    # 3. Save figure + results via cfg helpers.
    cfg.save_figure("<name>", fig)
    cfg.save_csv("<name>", df)

    # 4. (Headline scripts only) anchor-assert against the manifest.
    if not smoke:
        anchor = json.loads(MANIFEST_PATH.read_text())["..."]
        if abs(computed - anchor) > TOL:
            raise SystemExit(f"drift: got {computed}, expects {anchor}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--smoke", action="store_true",
                   help="fast variant (smaller bootstrap / skip anchor)")
    args = p.parse_args()
    main(smoke=args.smoke)
```

### Forbidden

- Calling the encoder inline. Encoding happens upstream (scripts/ or
  notebook S2/S3 cells); analysis scripts read the cache.
- Re-implementing scoring rules. Use `vep_utils.compute_*` (notebook
  scope) or `manylatents.dogma.vep.compute_*` (library scope). If
  you need a new scorer, add it to one of those modules first.
- Path constants inline — use `cfg.*`.
- Cross-script imports. Communicate through files in `results/`.

### Required

- Module docstring naming paper anchor + inputs + outputs + runtime.
- Only project-local import is `import _config as cfg`.
- Output filenames match the script's number prefix (e.g.
  `02_llr_distribution.py` → `02_llr_distribution.{pdf,png,csv,json}`
  *or* the conventional unnumbered stem like `llr_distribution_500`
  when the artifact is referenced elsewhere by name).
- A `--smoke` flag for a fast variant — typically a smaller bootstrap
  count + skip the anchor assertion. Runs in <30 s on CPU.
- If the script regenerates a number the paper or manifest cites,
  add an anchor-assertion against the manifest in non-smoke mode.
  Document the tolerance.

## `_config.py`

Single source of truth for paths and I/O helpers. Never duplicate
across scripts. Current surface:

```python
EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT    = EXPERIMENTS_DIR.parent
ANALYSIS_DIR    = EXPERIMENTS_DIR / "analysis"
RESULTS_DIR     = ANALYSIS_DIR / "results"
FIGURES_DIR     = ANALYSIS_DIR / "figures"
EMBEDDINGS_DIR  = ANALYSIS_DIR / "embeddings"

def latest_hydra_run(experiment_name: str) -> Path: ...
def load_encoded(experiment_name: str) -> (np.ndarray, pd.DataFrame): ...
def save_csv(name: str, df: pd.DataFrame) -> Path: ...
def save_figure(name: str, fig, formats=("pdf", "png")) -> list[Path]: ...
```

When a constant or helper shows up in two scripts, that's the signal it
belongs in `_config.py`.

## Running scripts

Two venvs cover everything; pick by what the script imports:

```bash
# Default — uses notebook-scope deps (HF transformers, no fair-esm).
# Covers 01_resolution_panels.py, 02_llr_distribution.py, and anything
# else that only reads caches.
experiments/notebooks/.venv/bin/python experiments/analysis/02_<name>.py
experiments/notebooks/.venv/bin/python experiments/analysis/02_<name>.py --smoke

# Submodule venv — when the script needs library-scope encoders
# (fair-esm via `manylatents.dogma.encoders.ESMEncoder`) or the full
# Hydra entrypoint. 00_demo_umap.py + Hydra encode launches go here.
experiments/tools/manylatents-omics/.venv/bin/python experiments/analysis/00_demo_umap.py
```

Hydra sweeps (different surface — these launch the tool's CLI, not
numbered scripts):

```bash
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
    --config-path=$(pwd)/experiments/configs/manylatents-omics \
    experiment=<name> [cluster=<profile> launcher=<profile>_launcher]
```

Long jobs go through a SLURM submitter (via the `submitit_slurm`
launcher or the dispatcher skill — see root `CLAUDE.md` §workshop-demo
Phase 2), never raw `sbatch --wrap`.

## EXPERIMENT_LOG.md

Append-only chronicle. One entry per non-trivial run:

```markdown
## YYYY-MM-DD — <script-or-experiment> <smoke|run>

- **Pin:** manylatents-omics `<sha>` (branch `<branch>`); manylatents
  `x.y.z`; relevant other libs.
- **Cmd:** `experiments/notebooks/.venv/bin/python ../../analysis/NN_<name>.py`
- **Output:** `figures/<name>.{pdf,png}`, `results/<name>.csv` (N rows)
- **Numbers:** AUROC, CI, anchor match
- **Notes:** what you actually learned. Don't auto-generate.
```

## PROVENANCE.md

Figure → script → input mapping. Updated whenever a figure or its
inputs change:

```markdown
## <Figure name> (slide / §section)

- Script: `analysis/NN_<name>.py`
- Inputs: `notebooks/data/<artifact>.npz` (sha256 `…`)
- Outputs: `analysis/figures/<name>.{pdf,png}`, `analysis/results/<name>.csv`
- Generated: YYYY-MM-DD against manylatents-omics `<sha>`
```

## Pre-PR checklist for numbered scripts

- [ ] Module docstring names paper anchor + inputs + outputs + runtime.
- [ ] Only project-local import is `import _config as cfg`.
- [ ] No encoder calls in the script (encoding lives upstream).
- [ ] `--smoke` flag exists and runs in <30 s on CPU.
- [ ] Outputs land in `cfg.RESULTS_DIR` / `cfg.FIGURES_DIR` via
      `cfg.save_csv` / `cfg.save_figure`.
- [ ] If the script regenerates a paper-cited number, an anchor
      assertion against the manifest runs in non-smoke mode.
- [ ] `EXPERIMENT_LOG.md` entry added for any shipped data.
- [ ] `PROVENANCE.md` updated if a figure changed.
