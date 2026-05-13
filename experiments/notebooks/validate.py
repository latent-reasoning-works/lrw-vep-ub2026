#!/usr/bin/env python3
"""validate.py — reproduces the workshop notebook's headline numbers.

Run this after `pip install -r requirements-workshop.txt` (or
`uv pip install -r requirements-workshop.txt`) to confirm your
installation reproduces what the notebook claims.

Usage:
    python validate.py --quick    # demo pair + sample scoring, ~10s
    python validate.py --full     # full 500-variant regen + AUROC, ~4min

The validator mirrors the logic in cells s1-load, s2-pick-pair,
s2-encode, s3-score-loop, and s3-auroc. Expected values come from
`data/workshop_set_manifest.json` (single source of truth).

If a check fails, you'll get a tolerance report telling you which
value diverged and by how much. Common causes:
  - Wrong transformers version (see requirements-workshop.txt)
  - CPU vs GPU/MPS numerical drift (LLR tolerance is generous; AUROC
    should match to 4 decimals on any device)
  - Stale cache (delete data/s3_scores.npz and rerun --full)

This script is the workshop's "did my setup work" check.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))
from vep_utils import (  # noqa: E402
    ESM1bEncoder, encode_variant, parse_mutation, validate_mutation,
    truncate_around_mutation, compute_delta_norm, compute_llr,
    load_fasta,
)

# --- Tolerances --------------------------------------------------------------
# LLR is fp32 forward-pass output; same-device run-to-run drift is tiny but
# cross-device (CPU vs MPS vs CUDA) can drift by ~1e-3 in the last decimals.
# AUROC is rank-based so robust to small score changes; tight tolerance.
LLR_TOL = 0.05         # generous; expected for cross-device parity
AUROC_TOL = 5e-4       # roc_auc_score is rank-based; same-device should be exact
CI95_TOL = 1e-3        # bootstrap with fixed seed is deterministic

# --- Expected values (from manifest; mirror at validation time) --------------
MANIFEST_PATH = THIS_DIR / "data" / "workshop_set_manifest.json"

# --- Helpers -----------------------------------------------------------------

def _green(s: str) -> str:  return f"\033[32m{s}\033[0m"
def _red(s: str) -> str:    return f"\033[31m{s}\033[0m"
def _yellow(s: str) -> str: return f"\033[33m{s}\033[0m"

def _check(label: str, got, want, tol, fail_fast: bool = False) -> bool:
    """Print PASS/FAIL with a tolerance band; return True on pass."""
    delta = abs(got - want)
    ok = delta <= tol
    marker = _green("PASS") if ok else _red("FAIL")
    print(f"  [{marker}] {label}: got={got!r}, want={want!r}, delta={delta:.6f} (tol={tol})")
    if not ok and fail_fast:
        sys.exit(1)
    return ok


def _detect_device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        sys.exit(_red(f"FATAL: {MANIFEST_PATH} not found. Are you in experiments/notebooks/?"))
    return json.loads(MANIFEST_PATH.read_text())


# --- Stage 1 — environment + schema -----------------------------------------

def stage_env_and_schema(manifest: dict) -> dict:
    print(_yellow("\n== Stage 1: env + schema =="))
    import torch, transformers
    print(f"  torch={torch.__version__}, transformers={transformers.__version__}")
    print(f"  detected device: {_detect_device()}")

    df = pd.read_csv(THIS_DIR / "data" / "workshop_set.tsv", sep="\t")
    expected_cols = {"variant_id", "gene", "protein_pos", "aa_ref", "aa_alt",
                     "clinical_significance", "label"}
    missing = expected_cols - set(df.columns)
    _check("required schema columns", len(missing), 0, 0, fail_fast=True)

    n_path = int((df["label"] == 1).sum())
    n_benign = int((df["label"] == 0).sum())
    _check("variant count", len(df), 500, 0, fail_fast=True)
    _check("pathogenic count", n_path, 250, 0)
    _check("benign count", n_benign, 250, 0)
    _check("unique gene count", df["gene"].nunique(), 400, 0)

    return {"df": df}


# --- Stage 2 — demo pair encoding -------------------------------------------

def stage_demo_pair(state: dict, manifest: dict) -> dict:
    print(_yellow("\n== Stage 2: demo pair (BRCA1 L1854P + P1859R) =="))

    demo = pd.read_csv(THIS_DIR / "data" / "demo_pair.tsv", sep="\t")
    _check("demo pair has 2 rows", len(demo), 2, 0, fail_fast=True)

    wt_seqs = load_fasta(str(THIS_DIR / "data" / "workshop_set_proteins.fasta"))
    device = _detect_device()
    print(f"  loading ESM-1b on {device}... (first load ~1 min, cached after)")
    t0 = time.time()
    encoder = ESM1bEncoder(device=device)
    print(f"  loaded in {time.time() - t0:.1f}s")
    wt_tok = {aa: encoder.tokenizer.convert_tokens_to_ids(aa) for aa in "ACDEFGHIKLMNPQRSTVWY"}

    # Score both variants
    llrs = {}
    for _, row in demo.iterrows():
        kind = "pathogenic" if row.label == 1 else "benign"
        seq = wt_seqs[row.variant_id]
        pos1 = int(row.protein_pos) + 1
        seq_t, pos_t = truncate_around_mutation(seq, pos1, window=encoder.MAX_LEN)
        mut_str = f"{row.aa_ref}{pos_t}{row.aa_alt}"
        validate_mutation(seq_t, parse_mutation(mut_str))
        r = encode_variant(encoder, seq_t, mut_str)
        llrs[kind] = compute_llr(r["wt_logits"], r["mutation"],
                                 wt_tok[row.aa_ref], wt_tok[row.aa_alt])

    # Compare against the canonical demo-pair scores file
    expected_path = THIS_DIR.parent / "analysis" / "data" / "demo_pair_scores.json"
    expected = json.loads(expected_path.read_text()) if expected_path.exists() else {
        "pathogenic": {"llr": -6.53}, "benign": {"llr": -3.76},
    }
    p_want = expected["pathogenic"]["llr"]
    b_want = expected["benign"]["llr"]

    p_ok = _check(f"pathogenic LLR (Brandes sign)", llrs["pathogenic"], p_want, LLR_TOL)
    b_ok = _check(f"benign LLR (Brandes sign)",     llrs["benign"],     b_want, LLR_TOL)

    # Sign sanity (the assertion the workshop demo rests on)
    if llrs["pathogenic"] >= 0 or llrs["benign"] >= 0:
        print(_red("  [FAIL] sign convention: at least one LLR is non-negative; "
                  "Brandes convention is negative=deleterious"))
        return {"encoder": encoder, "wt_seqs": wt_seqs, "wt_tok": wt_tok, "ok": False}
    if llrs["pathogenic"] >= llrs["benign"]:
        print(_red(f"  [FAIL] pathogenic LLR ({llrs['pathogenic']:.3f}) is not more "
                   f"negative than benign LLR ({llrs['benign']:.3f}) — separation lost"))
        return {"encoder": encoder, "wt_seqs": wt_seqs, "wt_tok": wt_tok, "ok": False}
    print(_green(f"  [PASS] sign convention: pathogenic ({llrs['pathogenic']:.3f}) "
                 f"more negative than benign ({llrs['benign']:.3f})"))

    state.update({"encoder": encoder, "wt_seqs": wt_seqs, "wt_tok": wt_tok})
    return state


# --- Stage 3 — sample scoring (quick) or full regen (--full) ----------------

def stage_sample_scoring(state: dict, manifest: dict, n_sample: int = 5) -> bool:
    """Quick mode: score a random sample, check sign sanity. Not AUROC."""
    print(_yellow(f"\n== Stage 3a: sample scoring (n={n_sample}, quick mode) =="))
    df, encoder, wt_seqs, wt_tok = state["df"], state["encoder"], state["wt_seqs"], state["wt_tok"]
    rng = np.random.default_rng(42)
    # 3 pathogenic + 2 benign
    p_idx = rng.choice(np.where(df["label"] == 1)[0], 3, replace=False)
    b_idx = rng.choice(np.where(df["label"] == 0)[0], 2, replace=False)
    sub = df.iloc[list(p_idx) + list(b_idx)].reset_index(drop=True)

    llrs = []
    t0 = time.time()
    for _, row in sub.iterrows():
        seq = wt_seqs[row.variant_id]
        pos1 = int(row.protein_pos) + 1
        seq_t, pos_t = truncate_around_mutation(seq, pos1, window=encoder.MAX_LEN)
        mut_str = f"{row.aa_ref}{pos_t}{row.aa_alt}"
        validate_mutation(seq_t, parse_mutation(mut_str))
        r = encode_variant(encoder, seq_t, mut_str)
        llr = compute_llr(r["wt_logits"], r["mutation"],
                          wt_tok[row.aa_ref], wt_tok[row.aa_alt])
        llrs.append((row.variant_id, row.gene, int(row.label), llr, len(seq)))
    elapsed = time.time() - t0
    print(f"  scored {len(llrs)} variants in {elapsed:.1f}s")

    all_neg = all(x[3] < 0 for x in llrs)
    p_mean = np.mean([x[3] for x in llrs if x[2] == 1])
    b_mean = np.mean([x[3] for x in llrs if x[2] == 0])
    print(f"  pathogenic mean LLR: {p_mean:+.3f}; benign mean LLR: {b_mean:+.3f}")
    _check("all sample LLRs negative (Brandes)", int(all_neg), 1, 0)
    _check("pathogenic_mean < benign_mean (separation)",
           int(p_mean < b_mean), 1, 0)
    return all_neg and p_mean < b_mean


def stage_full_regen_and_auroc(state: dict, manifest: dict) -> bool:
    """Full mode: regenerate s3_scores.npz from scratch, then compute AUROCs."""
    print(_yellow("\n== Stage 3b: full regen + AUROC (slow, ~4 min on MPS) =="))
    from sklearn.metrics import roc_auc_score
    df, encoder, wt_seqs, wt_tok = state["df"], state["encoder"], state["wt_seqs"], state["wt_tok"]

    rows, dn_vals, llr_vals, slen = [], [], [], []
    t0 = time.time()
    for i, r in enumerate(df.itertuples(index=False)):
        seq = wt_seqs[r.variant_id]
        pos1 = int(r.protein_pos) + 1
        seq_t, pos_t = truncate_around_mutation(seq, pos1, window=encoder.MAX_LEN)
        mut_str = f"{r.aa_ref}{pos_t}{r.aa_alt}"
        try:
            validate_mutation(seq_t, parse_mutation(mut_str))
            result = encode_variant(encoder, seq_t, mut_str)
        except Exception as e:
            print(_yellow(f"  skip {r.variant_id}: {e}"))
            continue
        rows.append((r.variant_id, r.gene, int(r.label)))
        dn_vals.append(compute_delta_norm(result["wt_embedding"], result["mut_embedding"]))
        llr_vals.append(compute_llr(result["wt_logits"], result["mutation"],
                                    wt_tok[r.aa_ref], wt_tok[r.aa_alt]))
        slen.append(len(seq))
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(df)} ({(i + 1) / (time.time() - t0):.1f} var/s)")
    print(f"  regen complete in {(time.time() - t0) / 60:.1f} min")

    y = np.array([r[2] for r in rows])
    dn = np.array(dn_vals)
    llr = np.array(llr_vals)
    auroc_llr = float(roc_auc_score(y, -llr))     # Brandes sign-flip
    auroc_dn = float(roc_auc_score(y, dn))

    # Bootstrap CI95
    def bootstrap_ci(y, s, n_boot=10000, seed=42):
        rng = np.random.default_rng(seed)
        n = len(y)
        aucs = np.empty(n_boot)
        for i in range(n_boot):
            idx = rng.integers(0, n, n)
            if len(np.unique(y[idx])) < 2:
                aucs[i] = np.nan
            else:
                aucs[i] = roc_auc_score(y[idx], s[idx])
        aucs = aucs[~np.isnan(aucs)]
        return float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))

    llr_lo, llr_hi = bootstrap_ci(y, -llr)
    dn_lo, dn_hi = bootstrap_ci(y, dn)

    m = manifest["evaluation"]["metrics"]
    ok = True
    ok &= _check("LLR AUROC", auroc_llr, m["llr_auroc"], AUROC_TOL)
    ok &= _check("LLR CI95 lower", llr_lo, m["llr_auroc_ci95_bootstrap"][0], CI95_TOL)
    ok &= _check("LLR CI95 upper", llr_hi, m["llr_auroc_ci95_bootstrap"][1], CI95_TOL)
    ok &= _check("delta_norm AUROC", auroc_dn, m["delta_norm_auroc"], AUROC_TOL)
    ok &= _check("delta_norm CI95 lower", dn_lo, m["delta_norm_auroc_ci95_bootstrap"][0], CI95_TOL)
    ok &= _check("delta_norm CI95 upper", dn_hi, m["delta_norm_auroc_ci95_bootstrap"][1], CI95_TOL)
    return ok


# --- Main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--quick", action="store_true",
                   help="Demo pair + 5-variant sample (~10s). Default.")
    g.add_argument("--full", action="store_true",
                   help="Regenerate full 500-variant cache + AUROC (~4 min).")
    args = ap.parse_args()

    if not args.full:
        args.quick = True  # default

    manifest = _load_manifest()
    state = stage_env_and_schema(manifest)
    state = stage_demo_pair(state, manifest)
    if args.full:
        ok = stage_full_regen_and_auroc(state, manifest)
    else:
        ok = stage_sample_scoring(state, manifest)

    print()
    if ok and state.get("ok") is not False:
        print(_green("== VALIDATION PASSED =="))
        print("Your installation reproduces the workshop's headline numbers.")
        sys.exit(0)
    else:
        print(_red("== VALIDATION FAILED =="))
        print("See per-check FAIL lines above. Common causes:")
        print("  - Wrong transformers version (pip install -r requirements-workshop.txt)")
        print("  - Stale cache (delete data/s3_scores.npz, rerun --full)")
        print("  - Cross-device numerical drift (LLR_TOL=0.05 is generous, but huge")
        print("    differences mean the encoder weights or tokenizer changed)")
        sys.exit(1)


if __name__ == "__main__":
    main()
