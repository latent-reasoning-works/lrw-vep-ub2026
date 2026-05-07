"""Shared paths and I/O helpers for analysis/ scripts.

Per experiments/CLAUDE.md, every numbered NN_*.py imports this and nothing
else from the project. Constants and helpers that show up in two scripts
belong here.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = EXPERIMENTS_DIR.parent
ANALYSIS_DIR = EXPERIMENTS_DIR / "analysis"
RESULTS_DIR = ANALYSIS_DIR / "results"
FIGURES_DIR = ANALYSIS_DIR / "figures"
EMBEDDINGS_DIR = ANALYSIS_DIR / "embeddings"

# Hydra writes to <cwd>/outputs/<date>/<time>/. The encode runs from inside
# the manylatents-omics submodule, so check both candidate roots.
OUTPUT_ROOTS = [
    EXPERIMENTS_DIR / "outputs",
    EXPERIMENTS_DIR / "tools" / "manylatents-omics" / "outputs",
]

WANDB_ENTITY = os.environ.get("WANDB_ENTITY", "cesar-valdez-mcgill-university")
WANDB_PROJECT = os.environ.get("WANDB_PROJECT", "upper-bound-2026")


def latest_hydra_run(experiment_name: str) -> Path:
    """Return the path to the most recent Hydra output dir for an experiment.

    Hydra writes runs to <cwd>/outputs/YYYY-MM-DD/HH-MM-SS/. We scan every
    candidate root (project + tool-relative) and pick the most-recent run
    whose config.yaml records the matching experiment name.
    """
    candidates = []
    for root in OUTPUT_ROOTS:
        if not root.exists():
            continue
        for date_dir in root.glob("*"):
            if not date_dir.is_dir():
                continue
            for run_dir in date_dir.glob("*"):
                cfg = run_dir / ".hydra" / "config.yaml"
                if not cfg.exists():
                    continue
                text = cfg.read_text()
                if f"name: {experiment_name}" in text:
                    candidates.append(run_dir)
    if not candidates:
        roots = ", ".join(str(r) for r in OUTPUT_ROOTS)
        raise FileNotFoundError(
            f"No Hydra outputs/<date>/<time>/ found for experiment '{experiment_name}' "
            f"under any of: {roots}. Run the encode first: "
            f"cd experiments/tools/manylatents-omics && "
            f".venv/bin/python -m manylatents.main "
            f"--config-path=$(pwd)/../../configs/manylatents-omics "
            f"experiment={experiment_name}"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_encoded(experiment_name: str) -> tuple[np.ndarray, pd.DataFrame]:
    """Load (embeddings, metadata) from the BatchEncoder save_path .pt file.

    BatchEncoder._save_embeddings writes torch.save(dict, path) where the
    dict is {embeddings: Tensor, labels: ndarray, variant_ids: list[str]}.
    Returns embeddings as numpy + a DataFrame with label/variant_id columns.
    """
    import torch
    run = latest_hydra_run(experiment_name)
    pt_path = run / "embeddings.pt"
    if not pt_path.exists():
        # Fall back to any .pt under the run dir
        pts = sorted(run.rglob("*.pt"))
        if not pts:
            raise FileNotFoundError(f"No .pt embeddings under {run}")
        pt_path = pts[0]
    state = torch.load(pt_path, map_location="cpu", weights_only=False)
    emb = state["embeddings"]
    if hasattr(emb, "numpy"):
        emb = emb.numpy()
    meta = pd.DataFrame({
        "variant_id": state.get("variant_ids", list(range(len(emb)))),
        "label": state.get("labels", np.full(len(emb), -1)),
    })
    return emb, meta


def save_csv(name: str, df: pd.DataFrame) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{name}.csv"
    df.to_csv(out, index=False)
    return out


def save_figure(name: str, fig, formats: tuple[str, ...] = ("pdf", "png")) -> list[Path]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for fmt in formats:
        out = FIGURES_DIR / f"{name}.{fmt}"
        fig.savefig(out, bbox_inches="tight", dpi=200)
        paths.append(out)
    return paths
