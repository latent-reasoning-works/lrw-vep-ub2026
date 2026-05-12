#!/usr/bin/env python3
"""verify_llr_independent.py — Cross-check v1 LLR values via fair-esm.

The v1 cache (`experiments/notebooks/data/s3_scores.npz`) was produced
by `cache_s3_scores.py` which uses HuggingFace `transformers` via
`vep_utils.ESM1bEncoder`. This script independently recomputes LLRs
for a sample of v1 variants using **fair-esm** — Meta's official ESM
library — with a different tokenizer, different model loader, different
forward implementation. Shares only the mathematical LLR formula
(log P_wt(wt|wt_ctx) - log P_mut(mut|mut_ctx)), not any code path.

If fair-esm LLRs match the cached HF LLRs (≤ ~1e-3 absolute diff after
floating-point + framework numerical noise), the pipeline is correct
and the v1 0.92 AUROC is real (filter-conditional, but not a bug).

Sample of 10 variants picked deterministically (seed 0).

Usage:
    experiments/tools/manylatents-omics/.venv/bin/python \\
        experiments/scripts/verify_llr_independent.py
"""

from __future__ import annotations

import csv
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "experiments" / "notebooks" / "data"
TSV_PATH = DATA_DIR / "workshop_set.tsv"
FASTA_PATH = DATA_DIR / "workshop_set_proteins.fasta"
CACHE_PATH = DATA_DIR / "s3_scores.npz"

N_SAMPLE = 10
SEED = 0
DEVICE = "mps"
FULL_OUTPUT = REPO_ROOT / "experiments" / "analysis" / "data" / "verify_llr_full.npz"


def load_fasta(path: Path) -> dict[str, str]:
    seqs: dict[str, str] = {}
    cur, chunks = None, []
    with path.open() as fh:
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


def truncate_around(seq: str, pos1: int, window: int = 1024) -> tuple[str, int]:
    """Mirror vep_utils.truncate_around_mutation for ESM-1b's 1022 cap.

    Independent re-derivation; the math is the same but the code is not
    shared with cache_s3_scores.py.
    """
    if len(seq) <= window:
        return seq, pos1
    half = window // 2
    start = max(0, pos1 - 1 - half)
    end = start + window
    if end > len(seq):
        end = len(seq)
        start = end - window
    return seq[start:end], pos1 - start


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true",
                    help="Score all 500 v1 variants and dump to verify_llr_full.npz "
                         "for AUROC comparison.")
    args = ap.parse_args()

    import torch
    import esm  # fair-esm

    cache = np.load(CACHE_PATH, allow_pickle=True)
    n = len(cache["variant_id"])
    if args.full:
        indices = list(range(n))
    else:
        rng = random.Random(SEED)
        indices = sorted(rng.sample(range(n), N_SAMPLE))

    tsv_rows: list[dict] = []
    with TSV_PATH.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            tsv_rows.append(r)
    rows_by_id = {r["variant_id"]: r for r in tsv_rows}

    fastas = load_fasta(FASTA_PATH)
    print(f"[INFO] loaded {len(tsv_rows)} rows from {TSV_PATH.name}")
    print(f"[INFO] loaded {len(fastas)} sequences from {FASTA_PATH.name}")

    # Load fair-esm — different code path than HF transformers
    print(f"[INFO] loading fair-esm esm1b_t33_650M_UR50S on {DEVICE}...", flush=True)
    t0 = time.time()
    model, alphabet = esm.pretrained.esm1b_t33_650M_UR50S()
    model = model.eval().to(DEVICE)
    batch_converter = alphabet.get_batch_converter()
    print(f"[INFO] fair-esm loaded in {time.time() - t0:.1f}s", flush=True)

    if not args.full:
        print(
            f"\n{'variant_id':<18} {'gene':<10} {'hgvs':<12} "
            f"{'cached_llr':>11} {'fair_esm_llr':>13} {'abs_diff':>10} {'status':>8}"
        )
        print("-" * 90)

    n_match = 0
    n_mismatch = 0
    max_diff = 0.0
    fair_llrs_full: list[float] = []
    cached_llrs_full: list[float] = []
    labels_full: list[int] = []
    t_start = time.time()
    for k, i in enumerate(indices):
        vid = str(cache["variant_id"][i])
        cached_llr = float(cache["llr"][i])
        cached_label = int(cache["label"][i])
        cached_gene = str(cache["gene"][i])

        row = rows_by_id[vid]
        pos0 = int(row["protein_pos"])  # 0-indexed in CSV
        pos1 = pos0 + 1                  # 1-indexed for ESM-1b
        wt_aa = row["aa_ref"]
        mut_aa = row["aa_alt"]

        full_seq = fastas[vid]
        wt_seq, pos_t = truncate_around(full_seq, pos1, window=1022)
        mut_seq = wt_seq[: pos_t - 1] + mut_aa + wt_seq[pos_t:]

        # Sanity: WT seq has the right ref AA at the (truncated) position
        if wt_seq[pos_t - 1] != wt_aa:
            print(f"  [WARN] {vid} ref_aa mismatch at truncated pos: "
                  f"wt_seq[{pos_t-1}]={wt_seq[pos_t-1]!r} vs csv={wt_aa!r}",
                  flush=True)

        # Tokenize via fair-esm's BatchConverter (independent path from HF)
        data = [(f"{vid}_wt", wt_seq), (f"{vid}_mut", mut_seq)]
        _labels, _strs, toks = batch_converter(data)
        toks = toks.to(DEVICE)
        with torch.inference_mode():
            out = model(toks, repr_layers=[], return_contacts=False)
        logits = out["logits"].cpu().float().numpy()  # [2, L+2, 33]

        wt_logits = logits[0]   # (L+2, 33)
        mut_logits = logits[1]
        wt_tid = alphabet.get_idx(wt_aa)
        mut_tid = alphabet.get_idx(mut_aa)

        # LLR = log_softmax(wt_logits[pos_t])[wt_tid] - log_softmax(mut_logits[pos_t])[mut_tid]
        # BOS at index 0, so 1-indexed sequence pos -> token index pos directly.
        def log_softmax(x: np.ndarray) -> np.ndarray:
            xm = np.max(x)
            s = x - xm
            return s - np.log(np.sum(np.exp(s)))

        wt_lp = log_softmax(wt_logits[pos_t])
        mut_lp = log_softmax(mut_logits[pos_t])
        fair_llr = float(wt_lp[wt_tid] - mut_lp[mut_tid])

        diff = abs(fair_llr - cached_llr)
        max_diff = max(max_diff, diff)
        status = "ok" if diff < 0.01 else "MISMATCH"
        if diff < 0.01:
            n_match += 1
        else:
            n_mismatch += 1

        fair_llrs_full.append(fair_llr)
        cached_llrs_full.append(cached_llr)
        labels_full.append(cached_label)

        if not args.full:
            hgvs = f"{wt_aa}{pos1}{mut_aa}"
            print(
                f"{vid:<18} {cached_gene:<10} {hgvs:<12} "
                f"{cached_llr:>+11.4f} {fair_llr:>+13.4f} {diff:>10.6f} {status:>8}",
                flush=True,
            )
        elif (k + 1) % 50 == 0:
            elapsed = time.time() - t_start
            rate = (k + 1) / elapsed
            eta = (len(indices) - k - 1) / rate if rate > 0 else 0
            print(
                f"  [{k + 1:4d}/{len(indices)}] match={n_match} miss={n_mismatch} "
                f"max_diff={max_diff:.4f} rate={rate:.2f}/s ETA={eta/60:.1f}m",
                flush=True,
            )

    if args.full:
        from sklearn.metrics import roc_auc_score
        y = np.array(labels_full)
        f = np.array(fair_llrs_full)
        c = np.array(cached_llrs_full)
        rho = float(np.corrcoef(f, c)[0, 1])
        spearman = float(
            np.corrcoef(np.argsort(np.argsort(f)), np.argsort(np.argsort(c)))[0, 1]
        )
        auroc_fair = float(roc_auc_score(y, f))
        auroc_cache = float(roc_auc_score(y, c))
        print()
        print(f"[SUMMARY full n={len(indices)}]")
        print(f"  Pearson r (cache vs fair-esm LLR):  {rho:.6f}")
        print(f"  Spearman ρ (rank correlation):      {spearman:.6f}")
        print(f"  Max abs_diff: {max_diff:.6f}")
        print(f"  Mean abs_diff: {np.mean(np.abs(f - c)):.6f}")
        print(f"  AUROC from cache LLR:  {auroc_cache:.6f}")
        print(f"  AUROC from fair-esm LLR: {auroc_fair:.6f}")
        print(f"  AUROC delta: {abs(auroc_fair - auroc_cache):.6f}")
        FULL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        np.savez(FULL_OUTPUT, variant_id=np.array([str(cache["variant_id"][i]) for i in indices]),
                 label=y, fair_llr=f, cached_llr=c)
        print(f"  saved -> {FULL_OUTPUT.relative_to(REPO_ROOT)}")
        return 0
    else:
        print("-" * 90)
        print(f"\n[SUMMARY] {n_match}/{N_SAMPLE} match (abs_diff < 1e-2), "
              f"{n_mismatch} mismatch. Max abs_diff: {max_diff:.6f}")
        if n_mismatch == 0:
            print("[OK] Pipeline verified: cache LLRs match independent fair-esm path.")
            return 0
        else:
            print("[ERR] Cache LLRs disagree with independent verifier — investigate.")
            return 1


if __name__ == "__main__":
    sys.exit(main())
