#!/usr/bin/env python
"""00_demo_umap.py — UMAP of ESM-1b embeddings for BRCA1 ClinVar variants.

Paper anchor: §Results, Figure 1 (workshop demo).
Inputs:  outputs/<date>/<time>/embeddings/*.npy  (from encode_esm1b_brca1)
Outputs: results/demo_umap_brca1.csv (UMAP coords + label)
         figures/demo_umap_brca1.{pdf,png}
         wandb image artifact under run_type=plot
Runtime: ~30s CPU on 200 variants.

Demo command sequence (run from experiments/tools/manylatents-omics first):

    cd experiments/tools/manylatents-omics
    .venv/bin/python -m manylatents.main +experiment=encode_esm1b_brca1
    cd ../..
    .venv/bin/python experiments/analysis/00_demo_umap.py

Matches the workshop prompt:
  "Just score the top 200 clinvar missense variants, for BRCA1 or whatever,
   with esm-1b. plot a umap of the embeddings colored by pathogenic vs
   benign, ... log to wandb so I can see the thing already."
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from manylatents.algorithms.latent.umap import UMAPModule

import _config as cfg


PALETTE = {
    "pathogenic": "#D72638",
    "likely_pathogenic": "#F7A072",
    "benign": "#2A9D8F",
    "likely_benign": "#86CD82",
    "uncertain": "#888888",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--experiment", default="encode_esm1b_brca1",
                        help="Encoding experiment whose embeddings to load")
    parser.add_argument("--smoke", action="store_true",
                        help="CI mode: synthesize tiny embeddings, skip wandb")
    args = parser.parse_args()

    if args.smoke:
        rng = np.random.default_rng(0)
        emb = rng.standard_normal((40, 1280)).astype(np.float32)
        labels = np.array(["pathogenic"] * 20 + ["benign"] * 20)
        meta = pd.DataFrame({"clinical_significance": labels,
                             "variant_id": [f"v{i}" for i in range(40)]})
    else:
        emb, meta = cfg.load_encoded(args.experiment)
        if "clinical_significance" not in meta.columns:
            raise ValueError(
                f"metadata missing 'clinical_significance' column. Got: {list(meta.columns)}"
            )
        labels = meta["clinical_significance"].str.lower().str.replace(" ", "_").to_numpy()

    # UMAP via manylatents — direct API, no wrapper.
    reducer = UMAPModule(
        n_components=2, n_neighbors=15, min_dist=0.5, random_state=42,
    )
    coords = reducer.fit_transform(emb)

    out_df = pd.DataFrame({
        "umap_x": coords[:, 0], "umap_y": coords[:, 1],
        "label": labels,
        "variant_id": meta.get("variant_id", pd.Series(range(len(coords)))),
    })
    csv_path = cfg.save_csv("demo_umap_brca1", out_df)
    print(f"  saved coords → {csv_path}")

    fig, ax = plt.subplots(figsize=(6, 5))
    for label in sorted(set(labels)):
        mask = labels == label
        ax.scatter(coords[mask, 0], coords[mask, 1],
                   c=PALETTE.get(label, "#444444"), label=label,
                   s=22, alpha=0.85, edgecolor="white", linewidth=0.4)
    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    ax.set_title(f"BRCA1 ClinVar missense — ESM-1b (n={len(coords)})")
    ax.legend(loc="best", frameon=False, fontsize=9)
    fig_paths = cfg.save_figure("demo_umap_brca1", fig)
    print(f"  saved figure → {fig_paths[0]}")

    if args.smoke:
        print("[smoke] skipping wandb")
        return

    import wandb
    run = wandb.init(
        entity=cfg.WANDB_ENTITY,
        project=cfg.WANDB_PROJECT,
        name=f"{args.experiment}_umap",
        job_type="plot",
        tags=["workshop", "vep", "brca1", "esm1b", "umap"],
        reinit=True,
    )
    run.log({
        "umap_scatter": wandb.Image(str(fig_paths[1])),
        "n_variants": len(coords),
        "umap_table": wandb.Table(dataframe=out_df),
    })
    run.summary["pathogenic_count"] = int((out_df["label"].str.contains("pathogenic")).sum())
    run.summary["benign_count"] = int((out_df["label"].str.contains("benign")).sum())
    run.finish()
    print(f"  logged to wandb: {cfg.WANDB_ENTITY}/{cfg.WANDB_PROJECT}")


if __name__ == "__main__":
    main()
