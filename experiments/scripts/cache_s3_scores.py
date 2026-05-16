#!/usr/bin/env python3
"""cache_s3_scores.py — Build experiments/notebooks/data/s3_scores.npz.

Standalone CLI mirror of notebook cell 17 (S3 scoring loop). Scores every
variant in workshop_set.tsv with the notebook's HF-transformers
ESM1bEncoder + LLR + delta-norm, writes a .npz the notebook then loads
instantly. **B10's invisible fallback for the Friday boss demo.**

Schema (matches what cell 17 expects):
    variant_id, gene, label, delta_norm, llr, seq_len  — all np.ndarray

Runtime: ~10–12 min on Apple Silicon MPS (500 variants × 2 forward passes
× ~0.5 s each). First-run model load adds ~60 s.

Pre/post-2.11 note: this script uses `vep_utils.py` directly (HF
transformers). Post-2.11, regenerate from `manylatents.dogma.vep` for
parity with Path B / B9; until then the cache is honestly the
pre-collapse encoder's output.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_DIR = REPO_ROOT / "experiments" / "notebooks"
TSV_PATH = NOTEBOOK_DIR / "data" / "workshop_set.tsv"
FASTA_PATH = NOTEBOOK_DIR / "data" / "workshop_set_proteins.fasta"
CACHE_PATH = NOTEBOOK_DIR / "data" / "s3_scores.npz"

# vep_utils.py lives next to the notebook; add the dir to the import path.
sys.path.insert(0, str(NOTEBOOK_DIR))


def load_fasta(path: Path) -> dict[str, str]:
    seqs: dict[str, str] = {}
    cur, chunks = None, []
    with open(path) as fh:
        for line in fh:
            line = line.rstrip()
            if line.startswith(">"):
                if cur is not None:
                    seqs[cur] = "".join(chunks)
                cur, chunks = line[1:].split()[0], []
            else:
                chunks.append(line)
        if cur is not None:
            seqs[cur] = "".join(chunks)
    return seqs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--device", default="mps", choices=["mps", "cpu", "cuda"])
    ap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing cache (default: refuse if present).",
    )
    ap.add_argument(
        "--max-variants",
        type=int,
        default=None,
        help="Cap variant count (debug only — production cache should score all).",
    )
    args = ap.parse_args()

    if CACHE_PATH.exists() and not args.force:
        print(f"[OK] cache already present: {CACHE_PATH} (pass --force to overwrite)")
        return 0

    from vep_utils import (  # type: ignore  # noqa: E402
        ESM1bEncoder,
        encode_variant,
        parse_mutation,
        validate_mutation,
        truncate_around_mutation,
        compute_delta_norm,
        compute_llr,
    )

    df = pd.read_csv(TSV_PATH, sep="\t")
    if args.max_variants is not None:
        df = df.head(args.max_variants)
    wt_seqs = load_fasta(FASTA_PATH)

    n = len(df)
    print(f"[INFO] scoring {n} variants on {args.device}")
    t0 = time.time()
    encoder = ESM1bEncoder(device=args.device)
    print(f"[INFO] encoder loaded in {time.time() - t0:.1f}s")

    wt_token_ids = {aa: encoder.tok_id(aa) for aa in "ACDEFGHIKLMNPQRSTVWY"}

    rows: list[tuple[str, str, int]] = []
    dn: list[float] = []
    llr_vals: list[float] = []
    slen: list[int] = []

    t_start = time.time()
    skipped = 0
    for i, r in enumerate(df.itertuples(index=False)):
        seq = wt_seqs[r.variant_id]
        pos1 = int(r.protein_pos) + 1  # TSV is 0-indexed; HGVS is 1-indexed
        seq_t, pos_t = truncate_around_mutation(seq, pos1, window=encoder.MAX_LEN)
        mut_str = f"{r.aa_ref}{pos_t}{r.aa_alt}"
        try:
            validate_mutation(seq_t, parse_mutation(mut_str))
            result = encode_variant(encoder, seq_t, mut_str)
        except Exception as e:
            print(f"  skip {r.variant_id}: {e}")
            skipped += 1
            continue
        rows.append((r.variant_id, r.gene, int(r.label)))
        dn.append(compute_delta_norm(result["wt_embedding"], result["mut_embedding"]))
        # Brandes 2023 LLR: single WT pass; both wt_aa and mut_aa probabilities
        # read from the same softmax. Sign: negative = deleterious.
        # (`result["mut_logits"]` is unused by compute_llr now — kept in the
        # encode_variant return for delta_norm/cosine_dist callers.)
        llr_vals.append(
            compute_llr(
                result["wt_logits"],
                result["mutation"],
                wt_token_ids[r.aa_ref],
                wt_token_ids[r.aa_alt],
            )
        )
        slen.append(len(seq))

        # Cheap progress every 25 variants — ETA in seconds based on running rate.
        if (i + 1) % 25 == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (n - i - 1) / rate
            print(
                f"  [{i + 1:4d}/{n}]  rate={rate:.2f} var/s  "
                f"elapsed={elapsed/60:.1f}m  ETA={eta/60:.1f}m"
            )

    elapsed = time.time() - t_start
    print(
        f"[INFO] scored {len(rows)} / {n} variants in {elapsed/60:.1f}m "
        f"({skipped} skipped)"
    )

    if not rows:
        print("[ERR] no variants scored; refusing to write empty cache")
        return 1

    vid, gene, lbl = zip(*rows)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        CACHE_PATH,
        variant_id=np.array(vid),
        gene=np.array(gene),
        label=np.array(lbl),
        delta_norm=np.array(dn),
        llr=np.array(llr_vals),
        seq_len=np.array(slen),
    )
    size_kb = CACHE_PATH.stat().st_size / 1024
    print(f"[OK] wrote {CACHE_PATH} ({size_kb:.1f} KB, {len(rows)} variants)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
