# Experiments

This folder produces every CSV, JSON, and figure cited in the paper. **Public-facing reproduction surface** — assume a reviewer lands here cold and runs scripts in numeric order.

## CRITICAL: Use the tool's API first

Every numbered script in `analysis/` calls the upstream tool's Python API directly. **No wrappers, no local re-implementations, no helper functions.**

```python
# CORRECT — direct functional call into the tool
from <module>.api import run

result = run(data=..., algorithms=..., metrics=...)
```

```python
# WRONG — wrapping the API hides the surface the paper depends on
def run_my_thing(...):
    ...
```

```python
# WRONG — re-implementing what the tool already provides
from sklearn.neighbors import NearestNeighbors  # tool already has this, with caching
```

If the tool lacks a primitive you need, **add it upstream first** (with tests), then call it from here.

## Layout

```
experiments/
  CLAUDE.md                  # this file
  EXPERIMENT_LOG.md          # chronicle: what was run when, against which tool pin
  PROVENANCE.md              # figure → script → CSV mapping
  configs/<tool>/            # Hydra overrides for sweep launches
  tools/<tool>/              # git submodules
  scripts/                   # infrastructure (add_tool, run_experiment, snapshot_experiment)
  analysis/                  # numbered scripts — the reviewer's reading order
    _config.py               # shared paths, dataset registry, I/O helpers
    00_smoke.py              # health check: API + cfg work end-to-end
    01_*.py                  # data prep
    02_*.py                  # ...
    NN_figures.py            # all body figures
    results/                 # CSVs/JSONs land here
    figures/                 # PDF + PNG land here
    embeddings/              # cached run() outputs
    data/                    # caches
    _archive/                # exploratory scripts not on the figure-reproduction path
  outputs/                   # raw experiment outputs (gitignored)
```

## Numbered-script contract

Every `analysis/NN_*.py` follows this template:

```python
#!/usr/bin/env python
"""NN_<name>.py — <one-line paper claim this script supports>.

Paper anchor: §X.Y (<arc name>).
Inputs:  <prior numbered outputs + cfg.load_*>
Outputs: results/<name>.csv, results/<name>.json
Runtime: <CPU/GPU>, ~<minutes>
"""

import numpy as np
import pandas as pd

from <module>.api import run

import _config as cfg


def main():
    # 1. Load via cfg
    # 2. Call run() per (dataset, algorithm, ...) — no wrappers
    # 3. Aggregate → DataFrame
    # 4. cfg.save_csv / cfg.save_result
    ...


if __name__ == "__main__":
    main()
```

### Forbidden

- Wrapping `run()` in a helper function.
- Re-implementing primitives the tool already provides.
- `argparse` for anything except `--smoke` (CI flag).
- Path constants inline — use `cfg.*`.
- Cross-script imports. Communicate through files in `results/`.

### Required

- Module docstring naming paper anchor + inputs/outputs/runtime.
- Only project-local import is `import _config as cfg`.
- Output filenames match the script's number prefix.
- A `--smoke` flag that runs in <60s on CPU. CI runs this.

## `_config.py`

Single source of truth for paths, datasets, and I/O. Never duplicate across scripts.

```python
EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
ANALYSIS_DIR    = EXPERIMENTS_DIR / "analysis"
RESULTS_DIR     = ANALYSIS_DIR / "results"
FIGURES_DIR     = ANALYSIS_DIR / "figures"

DATASETS   = { ... }   # name → {pca: ..., label_key: ...}
ALGORITHMS = [...]
K_SWEEP    = [...]

def load_pca(dataset: str): ...
def load_labels(dataset: str): ...
def save_csv(name: str, df): ...
def save_result(name: str, data): ...
def load_result(name: str): ...
```

When a constant or helper shows up in two scripts, that's the signal it belongs in `_config.py`.

## Running scripts

```bash
# From the tool's venv (so the tool is importable)
cd experiments/tools/<tool>
.venv/bin/python3 ../../analysis/03_<name>.py
.venv/bin/python3 ../../analysis/03_<name>.py --smoke
```

Long jobs go through your cluster submitter, never raw `sbatch --wrap`.

Hydra sweeps (different surface — these launch the tool's CLI, not numbered scripts):

```bash
.venv/bin/python3 -m <module>.main --config-path=../../configs/<tool> \
  -m experiment=<name> cluster=<profile>
```

## EXPERIMENT_LOG.md

Append-only chronicle. One entry per non-trivial run:

```markdown
## YYYY-MM-DD — NN_<name> <smoke|run>

- **Pin:** <tool> commit `<sha>`, version `x.y.z`
- **Cmd:** `.venv/bin/python3 ../../analysis/NN_<name>.py [...]`
- **Output:** `results/<name>.csv` (N rows)
- **Notes:** <what you actually learned>
```

The point of the log is the human-readable note. Don't auto-generate.

## PROVENANCE.md

Figure → script → CSV mapping. Updated whenever a figure or its inputs change:

```markdown
## Figure N (§X.Y)

- Script: `analysis/NN_figures.py::figure_<name>()`
- Inputs: `results/<name>.csv`
- Producing script: `analysis/NN_<name>.py`
- Generated: YYYY-MM-DD against <tool> `<sha>`
```

## Pre-PR checklist for numbered scripts

- [ ] Module docstring names paper anchor + inputs/outputs/runtime.
- [ ] Only project-local import is `import _config as cfg`.
- [ ] All `run()` calls are direct.
- [ ] `--smoke` flag runs in <60s on CPU.
- [ ] Outputs land in `cfg.RESULTS_DIR` / `cfg.FIGURES_DIR`.
- [ ] `EXPERIMENT_LOG.md` entry added for any shipped data.
- [ ] `PROVENANCE.md` updated if a figure changed.
