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

  Panel A — n=2: LLR bars for the BRCA1 demo pair (benign vs
    pathogenic). LLR-only at n=2; delta_norm dropped here because at
    this scale it sits near zero and dilutes the visual. The
    "prototype" beat.
  Panel B — n=500: ROC curves for delta-norm and LLR over the workshop
    validation set, AUROC in the legend, dashed chance line. The
    "validate" beat.
  Panel C — n=36,537: Brandes et al. 2023 (Nature Genetics) anchor,
    ESM-1b zero-shot on ClinVar missense (AUROC 0.905). Single bar
    showing the ceiling, with two dashed reference lines pulled
    forward from panel B (delta L2 norm 0.61 in blue, LLR 0.64 in
    red) so the gap from "where we are" to "where Brandes is" is
    legible at a glance. The ladder is the slide's argument; this
    panel is its top rung.

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
    """n=2 — LLR bars for the BRCA1 demo pair (benign vs pathogenic).

    Delta L2 norm is dropped from this panel: at n=2 the two values
    (~0.03) are visually indistinguishable from zero and dilute the
    LLR signal the prototype is meant to demonstrate. Both metrics
    still appear in panel B at scale, where the AUROC comparison
    makes them mutually informative.
    """
    p, b = scores["pathogenic"], scores["benign"]
    labels = [f"Benign\n{b['hgvs']}", f"Pathogenic\n{p['hgvs']}"]
    values = [b["llr"], p["llr"]]
    colors = [PALETTE["Benign"], PALETTE["Pathogenic"]]
    x = np.arange(len(labels))
    ax.bar(x, values, width=0.55, color=colors, edgecolor="white", linewidth=0.8)
    for xi, v in zip(x, values):
        ax.text(xi, v + 0.02, f"{v:+.2f}", ha="center", va="bottom",
                fontsize=10, weight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title(f"n = 2 — BRCA1 prototype, LLR")
    ax.set_ylabel("LLR")
    ax.axhline(0, color="black", linewidth=0.4)
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


BRANDES_2023_CLINVAR_N = 36_537
BRANDES_2023_CLINVAR_AUROC = 0.905
DELTA_NORM_COLOR = "#3a7ca5"
LLR_COLOR = PALETTE["Pathogenic"]


def panel_c_brandes_anchor(ax: plt.Axes, auroc_dn: float, auroc_llr: float) -> None:
    """n=36,537 — Brandes et al. 2023 ceiling, with panel B floor pulled forward.

    Single bar at AUROC 0.905 (ESM-1b zero-shot, ClinVar missense)
    from Brandes Fig 2B, plus two dashed reference lines at panel B's
    measured AUROCs (delta L2 norm in blue, LLR in red) so the
    floor->ceiling gap is the visual argument. Caption frames the
    ceiling as "the climb the harness enables."
    """
    bar_x = 0.0
    bar_w = 0.55
    ax.bar(
        bar_x, BRANDES_2023_CLINVAR_AUROC, width=bar_w,
        color=LLR_COLOR, edgecolor="white", linewidth=0.8,
    )
    ax.text(
        bar_x, BRANDES_2023_CLINVAR_AUROC + 0.012,
        f"ESM-1b\n{BRANDES_2023_CLINVAR_AUROC:.3f}",
        ha="center", va="bottom", fontsize=9, weight="bold", color=LLR_COLOR,
    )
    for label, value, color in [
        ("delta L2 norm", auroc_dn, DELTA_NORM_COLOR),
        ("LLR", auroc_llr, LLR_COLOR),
    ]:
        ax.axhline(value, color=color, linestyle="--", linewidth=1.4, alpha=0.85)
        ax.text(
            bar_w / 2 + 0.05, value, f"{label} — {value:.2f}",
            ha="left", va="center", fontsize=8, color=color,
            bbox=dict(facecolor="white", edgecolor="none", pad=1.2),
        )
    ax.set_xlim(-bar_w, bar_w + 0.7)
    ax.set_ylim(0.5, 1.0)
    ax.set_xticks([])
    ax.set_ylabel("AUROC")
    ax.set_title(f"n = {BRANDES_2023_CLINVAR_N:,} — Brandes et al. 2023")
    ax.text(
        0.5, -0.10,
        "ESM-1b zero-shot, ClinVar missense (all genes).\n"
        "The ceiling this harness climbs toward.",
        ha="center", va="top", fontsize=8, color="#444444",
        transform=ax.transAxes,
    )
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

    from sklearn.metrics import roc_auc_score
    m_dn = ~np.isnan(dn)
    m_llr = ~np.isnan(llr)
    auroc_dn = float(roc_auc_score(y[m_dn], dn[m_dn]))
    auroc_llr = float(roc_auc_score(y[m_llr], llr[m_llr]))

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), gridspec_kw={"wspace": 0.32})
    panel_a(axes[0], scores)
    panel_b(axes[1], y, dn, llr)
    panel_c_brandes_anchor(axes[2], auroc_dn=auroc_dn, auroc_llr=auroc_llr)
    fig.suptitle(
        "Resolution: same harness, three scales",
        fontsize=12, y=1.02, weight="bold",
    )

    fig_paths = cfg.save_figure(OUT_NAME, fig)
    for fp in fig_paths:
        print(f"  saved figure → {fp.relative_to(cfg.EXPERIMENTS_DIR.parent)}")

    rows = [
        {"panel": "A", "n": 1, "label": "benign", "gene": scores["benign"]["gene"],
         "id": scores["benign"].get("variant_id", scores["benign"]["hgvs"]),
         "metric": "llr", "value": scores["benign"]["llr"]},
        {"panel": "A", "n": 1, "label": "pathogenic", "gene": scores["pathogenic"]["gene"],
         "id": scores["pathogenic"].get("variant_id", scores["pathogenic"]["hgvs"]),
         "metric": "llr", "value": scores["pathogenic"]["llr"]},
    ]
    if not args.smoke:
        rows += [
            {"panel": "B", "n": int(m_dn.sum()), "label": "auroc", "gene": "all",
             "id": "validation_set", "metric": "delta_norm", "value": auroc_dn},
            {"panel": "B", "n": int(m_llr.sum()), "label": "auroc", "gene": "all",
             "id": "validation_set", "metric": "llr", "value": auroc_llr},
        ]
    rows.append({
        "panel": "C", "n": BRANDES_2023_CLINVAR_N, "label": "auroc",
        "gene": "ClinVar", "id": "brandes_2023_fig2b",
        "metric": "esm1b_zero_shot", "value": BRANDES_2023_CLINVAR_AUROC,
    })
    csv_path = cfg.save_csv(OUT_NAME, pd.DataFrame(rows))
    print(f"  saved csv → {csv_path.relative_to(cfg.EXPERIMENTS_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
