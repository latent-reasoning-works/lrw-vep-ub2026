#!/usr/bin/env python
"""02_llr_distribution.py — headline ESM-1b LLR vs ClinVar label, n=500.

Paper anchor: §Results.
Inputs:  experiments/notebooks/data/s3_scores.npz (cached S3 score table)
         experiments/notebooks/data/workshop_set_manifest.json (anchor values)
Outputs: results/llr_distribution_500.csv, results/llr_distribution_500.json,
         figures/llr_distribution_500.{pdf,png}
Runtime: CPU, <30s
"""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import roc_auc_score

import _config as cfg

CACHE_PATH = cfg.EXPERIMENTS_DIR / "notebooks" / "data" / "s3_scores.npz"
MANIFEST_PATH = cfg.EXPERIMENTS_DIR / "notebooks" / "data" / "workshop_set_manifest.json"

PATHOGENIC_COLOR = "#c44e52"
BENIGN_COLOR = "#4a8fb8"


def bootstrap_auroc(y: np.ndarray, s: np.ndarray, n_boot: int = 10000, seed: int = 42):
    rng = np.random.default_rng(seed)
    aurocs = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        aurocs.append(roc_auc_score(y[idx], s[idx]))
    a = np.array(aurocs)
    return float(a.mean()), float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))


def main(smoke: bool = False) -> None:
    d = np.load(CACHE_PATH, allow_pickle=True)
    llr = d["llr"].astype(float)
    label = d["label"].astype(int)
    mask = ~np.isnan(llr)
    llr, label = llr[mask], label[mask]

    # Brandes convention: more negative LLR ⇒ more pathogenic. AUROC predictor
    # is -llr so pathogenic (label=1) ends up the positive class.
    score = -llr
    point_auroc = roc_auc_score(label, score)
    n_boot = 200 if smoke else 10000
    _, ci_lo, ci_hi = bootstrap_auroc(label, score, n_boot=n_boot)
    n_p = int((label == 1).sum())
    n_b = int((label == 0).sum())

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for lbl_val, color, lbl_name, n in [
        (0, BENIGN_COLOR, "Benign", n_b),
        (1, PATHOGENIC_COLOR, "Pathogenic", n_p),
    ]:
        sub = llr[label == lbl_val]
        sns.kdeplot(sub, ax=ax, color=color, fill=True, alpha=0.35, linewidth=1.8,
                    label=f"{lbl_name} (n={n}, median={np.median(sub):.2f})")
        ax.axvline(np.median(sub), color=color, linestyle="--", alpha=0.6, linewidth=1.0)

    ax.set_title(
        f"ESM-1b LLR separates ClinVar pathogenic from benign "
        f"(AUROC = {point_auroc:.3f}, 95% CI [{ci_lo:.3f}, {ci_hi:.3f}])"
    )
    ax.set_xlabel("LLR = log P(mut | WT) − log P(wt | WT)   (negative ⇒ pathogenic-leaning)")
    ax.set_ylabel("Density")
    ax.legend(loc="upper left", frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    fig_paths = cfg.save_figure("llr_distribution_500", fig)
    plt.close(fig)

    import pandas as pd
    out_df = pd.DataFrame({"variant_id": d["variant_id"][mask], "gene": d["gene"][mask],
                           "label": label, "llr": llr})
    csv_path = cfg.save_csv("llr_distribution_500", out_df)
    summary = {
        "scorer": "llr",
        "auroc": point_auroc,
        "ci95_lo": ci_lo,
        "ci95_hi": ci_hi,
        "n_variants": int(mask.sum()),
        "n_pathogenic": n_p,
        "n_benign": n_b,
        "n_bootstrap": n_boot,
        "bootstrap_seed": 42,
        "auroc_predictor": "-llr",
    }
    json_path = cfg.RESULTS_DIR / "llr_distribution_500.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"AUROC = {point_auroc:.4f}  CI95 = [{ci_lo:.4f}, {ci_hi:.4f}]  n = {mask.sum()}")
    print(f"Figure: {fig_paths}")
    print(f"CSV:    {csv_path}")
    print(f"JSON:   {json_path}")

    if MANIFEST_PATH.exists() and not smoke:
        m = json.loads(MANIFEST_PATH.read_text())["evaluation"]["metrics"]
        anchor = float(m["llr_auroc"])
        if abs(point_auroc - anchor) > 5e-4:
            raise SystemExit(
                f"AUROC drift: got {point_auroc:.6f}, manifest expects {anchor:.6f}"
            )
        print(f"Anchor check: matches manifest ({anchor:.6f}) within 5e-4.")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--smoke", action="store_true", help="200-resample bootstrap, no anchor assert")
    args = p.parse_args()
    main(smoke=args.smoke)
