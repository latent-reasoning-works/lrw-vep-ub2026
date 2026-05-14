#!/usr/bin/env python3
"""validate_genes.py — smoke-test the audience-pick gene paths.

The bundled `experiments/data/clinvar/<gene>/` dirs (TP53, BRCA2, PTEN,
MLH1) exist so the speaker can swap gene under audience pressure:

    "do TP53 instead"

This validator confirms that the encode → LLR → sign-convention chain
actually works on those genes — not just on BRCA1. For each gene:

  1. load variants.tsv + protein.fasta from the bundled snapshot
  2. pick N pathogenic + N benign rows (label == 1 / 0)
  3. reconstruct WT by reverse-applying any one variant's mutation
  4. for each variant: truncate WT around the position, encode via
     `vep_utils.encode_variant`, compute LLR via `compute_llr`
  5. assert: pathogenic mean LLR < benign mean LLR (sign convention)

Exits 0 only if every gene passes. ~30 s on MPS, ~3 min on CPU.

Run from the workshop venv (uv sync'd or pip-installed):
    cd experiments/notebooks
    uv run python validate_genes.py [--n 5] [--device mps|cuda|cpu]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from vep_utils import (
    ESM1bEncoder,
    compute_llr,
    encode_variant,
    parse_mutation,
    truncate_around_mutation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CLINVAR_DIR = REPO_ROOT / "experiments" / "data" / "clinvar"
GENES = ["tp53", "brca2", "pten", "mlh1"]


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


def _reconstruct_wt(mut_seq: str, position: int, wt_aa: str, mut_aa: str) -> str | None:
    """Reverse-apply a mutation: replace mut_aa at 1-indexed position with wt_aa.

    Returns None if the position is out of range or the residue doesn't match.
    """
    p0 = position - 1
    if p0 < 0 or p0 >= len(mut_seq):
        return None
    if mut_seq[p0] != mut_aa:
        return None
    return mut_seq[:p0] + wt_aa + mut_seq[p0 + 1:]


def _score_gene(
    gene: str, encoder: ESM1bEncoder, n_per_class: int
) -> tuple[bool, str]:
    gene_dir = CLINVAR_DIR / gene
    tsv = gene_dir / "variants.tsv"
    fasta = gene_dir / "protein.fasta"
    if not (tsv.exists() and fasta.exists()):
        return False, f"missing data: {tsv}, {fasta}"

    df = pd.read_csv(tsv, sep="\t")
    df = df[df["label"].isin([0, 1])].reset_index(drop=True)
    seqs = _load_fasta(fasta)

    path_rows = df[df["label"] == 1].head(n_per_class)
    benign_rows = df[df["label"] == 0].head(n_per_class)
    if len(path_rows) < 1 or len(benign_rows) < 1:
        return False, (
            f"insufficient rows: {len(path_rows)} P / {len(benign_rows)} B "
            f"(want {n_per_class} of each)"
        )

    # Reconstruct WT from the first pathogenic row whose FASTA entry matches.
    wt_seq = None
    for _, row in path_rows.iterrows():
        key = f"clinvar_{row['variation_id']}"
        mut = seqs.get(key)
        if mut is None:
            continue
        wt_seq = _reconstruct_wt(mut, int(row["position"]), row["wt_aa"], row["alt_aa"])
        if wt_seq is not None:
            break
    if wt_seq is None:
        return False, "couldn't reconstruct WT (no path row had a matching FASTA entry)"

    llrs: dict[int, list[float]] = {0: [], 1: []}
    skipped: list[str] = []
    for _, row in pd.concat([path_rows, benign_rows]).iterrows():
        hgvs = f"{row['wt_aa']}{int(row['position'])}{row['alt_aa']}"
        try:
            mutation = parse_mutation(hgvs)
            # Truncate WT around the mutation (Brandes "option 4") so positions
            # beyond 1022 still resolve. Long proteins like BRCA2 (3418 aa)
            # have ~70 % of variants at positions >1022.
            wt_t, new_pos = truncate_around_mutation(
                wt_seq, mutation.position, window=encoder.MAX_LEN
            )
            corrected_hgvs = f"{mutation.wt_aa}{new_pos}{mutation.mut_aa}"
            result = encode_variant(encoder, wt_t, corrected_hgvs)
            wt_tok = encoder.tok_id(mutation.wt_aa) if hasattr(encoder, "tok_id") else _tok_id(encoder, mutation.wt_aa)
            mut_tok = encoder.tok_id(mutation.mut_aa) if hasattr(encoder, "tok_id") else _tok_id(encoder, mutation.mut_aa)
            llr = compute_llr(result["wt_logits"], result["mutation"], wt_tok, mut_tok)
            llrs[int(row["label"])].append(llr)
        except Exception as e:
            skipped.append(f"clinvar_{row['variation_id']} {hgvs}: {type(e).__name__}: {e}")

    if not llrs[1] or not llrs[0]:
        return False, f"all scoring failed; skipped: {skipped[:3]}"

    path_mean = float(np.mean(llrs[1]))
    benign_mean = float(np.mean(llrs[0]))
    n_path, n_ben = len(llrs[1]), len(llrs[0])
    msg = (
        f"path mean LLR {path_mean:+.4f} (n={n_path}), "
        f"benign mean LLR {benign_mean:+.4f} (n={n_ben}), "
        f"gap {benign_mean - path_mean:+.4f}"
    )
    if skipped:
        msg += f" — skipped {len(skipped)}"
    if path_mean < benign_mean:
        return True, msg
    return False, f"separation inverted: {msg}"


def _tok_id(encoder, aa: str) -> int:
    """Fallback for encoder backends that don't expose a `.tok_id` method."""
    try:
        return encoder.tokenizer.convert_tokens_to_ids(aa)
    except AttributeError:
        raise AttributeError(
            "encoder needs either a `.tok_id(aa)` method or a HF-style tokenizer"
        )


def main(n_per_class: int = 5, device: str | None = None) -> int:
    device = device or _auto_device()
    print(f"validate_genes.py — device={device}, n_per_class={n_per_class}")
    print(f"data: {CLINVAR_DIR}")
    print()

    t_total = time.time()
    encoder = ESM1bEncoder(device=device)

    fails: list[str] = []
    for gene in GENES:
        t0 = time.time()
        try:
            ok, msg = _score_gene(gene, encoder, n_per_class)
        except Exception as e:
            ok, msg = False, f"{type(e).__name__}: {e}"
        elapsed = time.time() - t0
        tag = "PASS" if ok else "FAIL"
        print(f"  [{tag}] {gene.upper()}: {msg} ({elapsed:.1f}s)")
        if not ok:
            fails.append(gene)

    print()
    total = time.time() - t_total
    if fails:
        print(f"FAIL  {len(fails)}/{len(GENES)} genes failed ({total:.1f}s total): {fails}")
        return 1
    print(f"PASS  {len(GENES)}/{len(GENES)} audience-pick genes separate cleanly ({total:.1f}s)")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--n", type=int, default=5,
                   help="variants per class per gene (default 5)")
    p.add_argument("--device", choices=["mps", "cuda", "cpu"], default=None,
                   help="encoder device (default: auto-detect)")
    args = p.parse_args()
    sys.exit(main(n_per_class=args.n, device=args.device))
