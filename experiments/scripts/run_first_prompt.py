#!/usr/bin/env python3
"""run_first_prompt.py — slide-fallback for the workshop's first agent prompt.

The opening slide prompt is, verbatim:

    "Just score the top 200 clinvar missense variants, for BRCA1 or
     whatever, with esm-1b. plot a umap of the embeddings colored by
     pathogenic vs benign, and log to wandb so I CAN SEE THE THING
     ALREADY!!!"

This script is the canned version of what the agent would do — a single
self-contained Python file the speaker can run if the live agent demo
of slide 1 blows up. No Hydra, no submodule venv: just the workshop
notebook env (`uv sync` in `experiments/notebooks/` first).

What it does:
  1. Load the top 200 BRCA1 P/B missense from `experiments/data/clinvar/variants.tsv`
  2. Reconstruct WT once from a pathogenic variant's MUT FASTA entry
  3. For each variant: truncate WT around the position, apply the mutation,
     encode the MUT sequence via `vep_utils.ESM1bEncoder`
  4. UMAP the 200 × 1280 embedding matrix
  5. Scatter plot colored by pathogenic / benign
  6. Save to `experiments/analysis/figures/first_prompt_brca1.{pdf,png}`
     (NB: deliberately *not* `demo_umap_brca1.*` — that file is Phase-1's
     canonical Hydra-encoded output; this fallback is its sibling.)
  7. Optionally log to wandb. Set `WANDB_MODE=offline` if you don't have
     credentials; the script auto-falls back to offline on auth failure.

Wall clock: ~3-5 min on MPS, ~15-20 min on CPU.

Usage:
    cd experiments/notebooks && uv sync           # one-time
    cd ../..
    experiments/notebooks/.venv/bin/python experiments/scripts/run_first_prompt.py
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
NB_DIR = REPO_ROOT / "experiments" / "notebooks"
sys.path.insert(0, str(NB_DIR))

from vep_utils import (  # noqa: E402
    ESM1bEncoder,
    apply_mutation,
    parse_mutation,
    truncate_around_mutation,
)

CLINVAR_DIR = REPO_ROOT / "experiments" / "data" / "clinvar"
FIG_DIR = REPO_ROOT / "experiments" / "analysis" / "figures"
RESULT_DIR = REPO_ROOT / "experiments" / "analysis" / "results"
FIG_STEM = "first_prompt_brca1"


def _auto_device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_fasta(path: Path) -> dict[str, str]:
    seqs: dict[str, str] = {}
    cur_id, cur_seq = None, []
    for line in path.read_text().splitlines():
        if line.startswith(">"):
            if cur_id is not None:
                seqs[cur_id] = "".join(cur_seq)
            cur_id = line[1:].strip()
            cur_seq = []
        else:
            cur_seq.append(line.strip())
    if cur_id is not None:
        seqs[cur_id] = "".join(cur_seq)
    return seqs


def _reconstruct_wt(mut: str, position: int, wt_aa: str, mut_aa: str) -> str | None:
    p0 = position - 1
    if p0 < 0 or p0 >= len(mut) or mut[p0] != mut_aa:
        return None
    return mut[:p0] + wt_aa + mut[p0 + 1:]


def _init_wandb() -> object | None:
    """Init wandb if possible; return the run, or None if disabled."""
    try:
        import wandb
    except ImportError:
        return None
    mode = os.environ.get("WANDB_MODE", "online")
    try:
        run = wandb.init(
            project=os.environ.get("WANDB_PROJECT", "upper-bound-2026"),
            entity=os.environ.get("WANDB_ENTITY"),
            name="first-prompt-fallback",
            tags=["workshop", "vep", "brca1", "esm1b", "fallback"],
            job_type="encode+umap",
            mode=mode,
        )
        return run
    except Exception as e:
        print(f"  WARN  wandb init failed ({e}); continuing without it")
        return None


def main(gene: str = "BRCA1", n: int = 200, device: str | None = None) -> int:
    device = device or _auto_device()
    # BRCA1 lives at the clinvar/ root (the bundled default); other genes
    # live in clinvar/<gene>/ subdirs.
    gene_dir = CLINVAR_DIR if gene.upper() == "BRCA1" else CLINVAR_DIR / gene.lower()
    print(f"run_first_prompt.py — gene={gene}, n={n}, device={device}")
    print(f"data: {gene_dir}")
    print()

    tsv = gene_dir / "variants.tsv"
    fasta = gene_dir / "protein.fasta"
    if not (tsv.exists() and fasta.exists()):
        print(f"FAIL  missing data: {tsv}, {fasta}")
        return 1

    df = pd.read_csv(tsv, sep="\t")
    df = df[df["label"].isin([0, 1])].head(n).reset_index(drop=True)
    print(f"  loaded {len(df)} P/B variants ({(df.label==1).sum()} P / {(df.label==0).sum()} B)")

    seqs = _load_fasta(fasta)
    wt_seq = None
    for _, row in df[df.label == 1].iterrows():
        key = f"clinvar_{row['variation_id']}"
        mut = seqs.get(key)
        if mut is None:
            continue
        wt_seq = _reconstruct_wt(mut, int(row["position"]), row["wt_aa"], row["alt_aa"])
        if wt_seq is not None:
            break
    if wt_seq is None:
        print("FAIL  couldn't reconstruct WT (no pathogenic row had a matching FASTA entry)")
        return 1
    print(f"  reconstructed WT ({len(wt_seq)} aa)")

    run = _init_wandb()
    if run is not None:
        run.config.update({"gene": gene, "n_variants": len(df), "device": device})

    encoder = ESM1bEncoder(device=device)
    print(f"  encoder loaded. encoding {len(df)} variants...")

    embeddings: list[np.ndarray] = []
    labels: list[int] = []
    variant_ids: list[str] = []
    t0 = time.time()
    for i, (_, row) in enumerate(df.iterrows(), 1):
        hgvs = f"{row['wt_aa']}{int(row['position'])}{row['alt_aa']}"
        try:
            mutation = parse_mutation(hgvs)
            wt_t, new_pos = truncate_around_mutation(
                wt_seq, mutation.position, window=encoder.MAX_LEN
            )
            mut_t = apply_mutation(
                wt_t,
                parse_mutation(f"{mutation.wt_aa}{new_pos}{mutation.mut_aa}"),
            )
            emb, _ = encoder.encode(mut_t)
            embeddings.append(emb)
            labels.append(int(row["label"]))
            variant_ids.append(f"clinvar_{row['variation_id']}")
        except Exception as e:
            print(f"  WARN  skipped clinvar_{row['variation_id']} {hgvs}: {type(e).__name__}: {e}")
        if i % 25 == 0 or i == len(df):
            print(f"    [{i}/{len(df)}] {(time.time()-t0):.1f}s elapsed")
    print(f"  encoded {len(embeddings)} variants in {time.time()-t0:.1f}s")
    if len(embeddings) < 10:
        print("FAIL  too few embeddings to UMAP")
        return 1

    X = np.stack(embeddings)
    y = np.array(labels)

    print(f"  fitting UMAP on {X.shape[0]} × {X.shape[1]}...")
    try:
        from umap import UMAP
    except ImportError:
        print("FAIL  umap-learn not installed (add to workshop env)")
        return 1
    reducer = UMAP(n_neighbors=15, min_dist=0.1, random_state=42, metric="cosine")
    Z = reducer.fit_transform(X)

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.5, 6))
    for lbl_val, color, name in [(0, "#4a8fb8", "Benign"), (1, "#c44e52", "Pathogenic")]:
        m = y == lbl_val
        ax.scatter(Z[m, 0], Z[m, 1], s=24, alpha=0.7, c=color, edgecolor="white",
                   linewidth=0.6, label=f"{name} (n={int(m.sum())})")
    ax.set_title(
        f"ESM-1b UMAP — {gene} ClinVar missense (n={len(y)}) — slide-1 fallback"
    )
    ax.set_xlabel("UMAP-1"); ax.set_ylabel("UMAP-2"); ax.legend()
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    fig.tight_layout()
    pdf_path = FIG_DIR / f"{FIG_STEM}.pdf"
    png_path = FIG_DIR / f"{FIG_STEM}.png"
    fig.savefig(pdf_path)
    fig.savefig(png_path, dpi=200)
    plt.close(fig)

    out_df = pd.DataFrame({
        "variant_id": variant_ids, "label": y, "umap_1": Z[:, 0], "umap_2": Z[:, 1],
    })
    csv_path = RESULT_DIR / f"{FIG_STEM}.csv"
    out_df.to_csv(csv_path, index=False)

    print()
    print(f"  figure:  {pdf_path}")
    print(f"  figure:  {png_path}")
    print(f"  coords:  {csv_path}")

    if run is not None:
        try:
            import wandb
            run.log({"umap": wandb.Image(str(png_path)),
                     "n_variants": len(y),
                     "n_pathogenic": int((y == 1).sum()),
                     "n_benign": int((y == 0).sum())})
            run.finish()
            print(f"  wandb:   {run.url}")
        except Exception as e:
            print(f"  WARN  wandb log failed: {e}")

    print()
    print(f"PASS  slide-1 fallback regenerated")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--gene", default="BRCA1",
                   help="gene name (must have a clinvar/<gene>/ dir, default BRCA1)")
    p.add_argument("--n", type=int, default=200, help="max variants (default 200)")
    p.add_argument("--device", choices=["mps", "cuda", "cpu"], default=None,
                   help="encoder device (default: auto)")
    args = p.parse_args()
    sys.exit(main(gene=args.gene, n=args.n, device=args.device))
