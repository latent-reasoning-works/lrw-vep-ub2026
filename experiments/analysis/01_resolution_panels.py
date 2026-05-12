#!/usr/bin/env python
"""01_resolution_panels.py — Three-panel resolution figure for the Part 2 slide.

Paper anchor: §Results, "Resolution" slide.
Inputs:
  - experiments/analysis/data/demo_pair_scores.json  (n=2; pre-scored by
    experiments/scripts/score_demo_pair.py)
  - experiments/notebooks/data/s3_scores.npz         (n=500; cached by
    experiments/scripts/cache_s3_scores.py)
Outputs:
  - experiments/analysis/figures/resolution_panels.{pdf,png}
  - experiments/analysis/results/resolution_panels.csv  (long-form numbers
    for parse-and-cite)
Runtime: ~5 s on CPU (no encoder calls; reads pre-computed artifacts).

The figure has three panels arranged left-to-right, shared color palette
(pathogenic = #D72638, benign = #2A9D8F):

  Panel A — n=2: bar chart of pathogenic vs benign for delta-norm and
    LLR on the BRCA1 demo pair. The "prototype" beat.
  Panel B — n=500: ROC curves for delta-norm and LLR over the workshop
    validation set, AUROC in the legend, dashed chance line. The
    "validate" beat.
  Panel C — n=36,537: Brandes et al. 2023 (Nature Genetics) literature
    anchor, ESM-1b zero-shot on ClinVar missense. Plotted on the same
    FPR/TPR axes as panel B for visual continuity, with the AUROC scalar
    rendered as a horizontal reference and the citation in-figure. We
    cite the literature value rather than fabricate a curve we do not
    own. Verify the AUROC against the source before the May 23 deck.

The n=2 and n=500 panels share an encoder code path (HF transformers via
vep_utils.ESM1bEncoder). Post-2.11 + NB.1, regenerate both via
manylatents.dogma.vep so the numbers stay consistent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import _config as cfg  # type: ignore


PALETTE = {"Pathogenic": "#D72638", "Benign": "#2A9D8F"}

DEMO_PAIR_SCORES = (
    cfg.ANALYSIS_DIR / "data" / "demo_pair_scores.json"
)
S3_CACHE = cfg.EXPERIMENTS_DIR / "notebooks" / "data" / "s3_scores.npz"
OUT_NAME = "resolution_panels"


def _load_n2() -> dict:
    if not DEMO_PAIR_SCORES.exists():
        raise FileNotFoundError(
            f"{DEMO_PAIR_SCORES.relative_to(cfg.EXPERIMENTS_DIR.parent)} not found. "
            "Run experiments/scripts/score_demo_pair.py first."
        )
    return json.loads(DEMO_PAIR_SCORES.read_text())


def _load_n500() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not S3_CACHE.exists():
        raise FileNotFoundError(
            f"{S3_CACHE.relative_to(cfg.EXPERIMENTS_DIR.parent)} not found. "
            "Run experiments/scripts/cache_s3_scores.py first."
        )
    z = np.load(S3_CACHE, allow_pickle=True)
    return z["label"].astype(int), z["delta_norm"].astype(float), z["llr"].astype(float)


def panel_a(ax: plt.Axes, scores: dict) -> None:
    """n=2 — bar chart of pathogenic vs benign on the BRCA1 demo pair."""
    p, b = scores["pathogenic"], scores["benign"]
    metrics = ["delta_norm", "llr"]
    p_vals = [p["delta_norm"], p["llr"]]
    b_vals = [b["delta_norm"], b["llr"]]
    x = np.arange(len(metrics))
    w = 0.35
    ax.bar(x - w / 2, b_vals, width=w, color=PALETTE["Benign"], label=f"Benign ({b['hgvs']})")
    ax.bar(x + w / 2, p_vals, width=w, color=PALETTE["Pathogenic"], label=f"Pathogenic ({p['hgvs']})")
    for i, (bv, pv) in enumerate(zip(b_vals, p_vals)):
        ax.text(i - w / 2, bv, f"{bv:.2f}", ha="center", va="bottom", fontsize=8)
        ax.text(i + w / 2, pv, f"{pv:.2f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(["delta L2 norm", "LLR"])
    ax.set_title(f"n = 2 — BRCA1 prototype\n{p['gene']} {p['hgvs']} vs {b['gene']} {b['hgvs']}")
    ax.set_ylabel("score")
    ax.axhline(0, color="black", linewidth=0.4)
    ax.legend(loc="best", fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)


def panel_b(ax: plt.Axes, y: np.ndarray, dn: np.ndarray, llr: np.ndarray) -> None:
    """n=500 — ROC curves for delta_norm and llr over the validation set."""
    from sklearn.metrics import roc_auc_score, roc_curve

    for name, s, color, linestyle in [
        ("delta L2 norm", dn, "#3a7ca5", "-"),
        ("LLR", llr, PALETTE["Pathogenic"], "-"),
    ]:
        m = ~np.isnan(s)
        fpr, tpr, _ = roc_curve(y[m], s[m])
        auc = roc_auc_score(y[m], s[m])
        ax.plot(fpr, tpr, lw=2, color=color, linestyle=linestyle,
                label=f"{name} — AUROC {auc:.2f}")
    ax.plot([0, 1], [0, 1], "k--", alpha=0.3, linewidth=0.8, label="chance")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(f"n = {int((~np.isnan(dn)).sum())} — workshop validation set")
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    ax.set_aspect("equal")
    ax.spines[["top", "right"]].set_visible(False)


BRANDES_2023_CLINVAR_AUROC = 0.74
BRANDES_2023_CLINVAR_N = 36_537


def panel_c_brandes_anchor(ax: plt.Axes) -> None:
    """n=36,537 — Brandes et al. 2023 ClinVar zero-shot anchor.

    We do not own Brandes' per-variant scores, so we render the cited
    summary as a horizontal reference at TPR = AUROC on the same axes as
    panel B. The chance diagonal and palette match panel B for visual
    continuity. AUROC value sourced from Brandes 2023 Fig 2B / Table 1
    (ESM-1b zero-shot on ClinVar, n=36,537 missense). Verify against the
    paper before the May 23 deck.
    """
    auroc = BRANDES_2023_CLINVAR_AUROC
    ax.plot([0, 1], [0, 1], "k--", alpha=0.3, linewidth=0.8, label="chance")
    ax.axhline(
        auroc, color=PALETTE["Pathogenic"], linewidth=2,
        label=f"ESM-1b zero-shot — AUROC {auroc:.2f}",
    )
    ax.text(
        0.5, 0.05,
        "Brandes et al., Nat. Genet. 2023, Fig 2B\nClinVar missense (all genes)",
        ha="center", va="bottom", fontsize=8, color="#444444",
        transform=ax.transAxes,
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(f"n = {BRANDES_2023_CLINVAR_N:,} — Brandes et al. 2023")
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    ax.set_aspect("equal")
    ax.spines[["top", "right"]].set_visible(False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--smoke", action="store_true",
                        help="CI mode: synthesize a tiny dataset, skip cache reads")
    args = parser.parse_args()

    if args.smoke:
        rng = np.random.default_rng(0)
        n = 60
        y = np.concatenate([np.zeros(n // 2), np.ones(n // 2)]).astype(int)
        dn = rng.normal(loc=y * 0.2, scale=0.5)
        llr = rng.normal(loc=y * 0.4, scale=0.5)
        scores = {
            "pathogenic": {"gene": "BRCA1", "hgvs": "L1854P", "delta_norm": 0.030, "llr": 0.87},
            "benign":     {"gene": "BRCA1", "hgvs": "P1859R", "delta_norm": 0.027, "llr": 0.22},
        }
    else:
        scores = _load_n2()
        y, dn, llr = _load_n500()

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), gridspec_kw={"wspace": 0.32})
    panel_a(axes[0], scores)
    panel_b(axes[1], y, dn, llr)
    panel_c_brandes_anchor(axes[2])
    fig.suptitle(
        "Resolution: same harness, three scales",
        fontsize=12, y=1.02, weight="bold",
    )

    fig_paths = cfg.save_figure(OUT_NAME, fig)
    for fp in fig_paths:
        print(f"  saved figure → {fp.relative_to(cfg.EXPERIMENTS_DIR.parent)}")

    rows = [
        {"panel": "A", "n": 1, "label": "pathogenic", "gene": scores["pathogenic"]["gene"],
         "id": scores["pathogenic"].get("variant_id", scores["pathogenic"]["hgvs"]),
         "metric": "delta_norm", "value": scores["pathogenic"]["delta_norm"]},
        {"panel": "A", "n": 1, "label": "pathogenic", "gene": scores["pathogenic"]["gene"],
         "id": scores["pathogenic"].get("variant_id", scores["pathogenic"]["hgvs"]),
         "metric": "llr", "value": scores["pathogenic"]["llr"]},
        {"panel": "A", "n": 1, "label": "benign", "gene": scores["benign"]["gene"],
         "id": scores["benign"].get("variant_id", scores["benign"]["hgvs"]),
         "metric": "delta_norm", "value": scores["benign"]["delta_norm"]},
        {"panel": "A", "n": 1, "label": "benign", "gene": scores["benign"]["gene"],
         "id": scores["benign"].get("variant_id", scores["benign"]["hgvs"]),
         "metric": "llr", "value": scores["benign"]["llr"]},
    ]
    if not args.smoke:
        from sklearn.metrics import roc_auc_score
        m_dn = ~np.isnan(dn)
        m_llr = ~np.isnan(llr)
        rows += [
            {"panel": "B", "n": int(m_dn.sum()), "label": "auroc", "gene": "all",
             "id": "validation_set", "metric": "delta_norm",
             "value": float(roc_auc_score(y[m_dn], dn[m_dn]))},
            {"panel": "B", "n": int(m_llr.sum()), "label": "auroc", "gene": "all",
             "id": "validation_set", "metric": "llr",
             "value": float(roc_auc_score(y[m_llr], llr[m_llr]))},
        ]
    rows += [
        {"panel": "C", "n": BRANDES_2023_CLINVAR_N, "label": "auroc", "gene": "all",
         "id": "brandes_2023_fig2b", "metric": "esm1b_zero_shot",
         "value": BRANDES_2023_CLINVAR_AUROC},
    ]
    csv_path = cfg.save_csv(OUT_NAME, pd.DataFrame(rows))
    print(f"  saved csv → {csv_path.relative_to(cfg.EXPERIMENTS_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
