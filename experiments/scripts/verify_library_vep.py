#!/usr/bin/env python3
"""verify_library_vep.py — exercise manylatents.dogma.vep end-to-end.

The notebook validators (validate.py, validate_notebook.py, validate_paper.py)
exercise the *notebook-scope* encoder (`vep_utils.ESM1bEncoder`, HF transformers).
The *library-scope* path — `manylatents.dogma.encoders.ESMEncoder` (fair-esm)
plus `manylatents.dogma.vep` (the just-upstreamed module from SHA bump
2026-05-14 e97d469) — had no test caller until this script.

Run from the manylatents-omics venv (it ships fair-esm; the notebook venv
does not):

    cd experiments/tools/manylatents-omics
    .venv/bin/python ../../scripts/verify_library_vep.py

What it checks:
  1. The library imports cleanly (no circular, no missing dep).
  2. `ESMEncoder.encode_with_logits` returns (embedding, logits) with the
     expected shapes.
  3. `compute_llr` on the demo pair produces sign-correct LLRs
     (pathogenic more negative than benign).
  4. LLR values agree with the notebook-scope cache to a tolerance
     (fair-esm vs HF transformers — same checkpoint, different libraries,
     near-identical numerics).

Exits 0 on PASS, non-zero on FAIL.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PAIR_SCORES = REPO_ROOT / "experiments" / "analysis" / "data" / "demo_pair_scores.json"

# Tolerance between fair-esm (library) and HF transformers (notebook) LLR.
# Empirically the two libraries agree to ~1e-3 on identical inputs;
# generous floor here so single-precision drift doesn't flap the check.
LLR_TOL = 0.05


def _section(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


def main() -> int:
    _section("Stage 1: library imports")
    t0 = time.time()
    try:
        from manylatents.dogma import vep
        from manylatents.dogma.encoders import ESMEncoder
    except Exception as e:
        print(f"  FAIL  import: {type(e).__name__}: {e}")
        print("  Are you running from the manylatents-omics venv?")
        return 1
    print(f"  PASS  manylatents.dogma.vep + ESMEncoder ({time.time()-t0:.1f}s)")

    _section("Stage 2: encoder + encode_with_logits surface")
    t0 = time.time()
    # Default device is "cuda" — pick whatever this machine has.
    import torch
    if torch.cuda.is_available():
        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    print(f"  device: {device}")
    enc = ESMEncoder(model_name="esm1b_t33_650M_UR50S", device=device)
    test_seq = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
    try:
        emb, logits = enc.encode_with_logits(test_seq)
    except AttributeError:
        print("  FAIL  ESMEncoder.encode_with_logits missing — submodule pin out of date?")
        return 1
    except Exception as e:
        print(f"  FAIL  encode_with_logits: {type(e).__name__}: {e}")
        return 1
    if emb.shape != (1280,):
        print(f"  FAIL  embedding shape {emb.shape}, expected (1280,)")
        return 1
    if logits.shape[0] != len(test_seq) + 2:
        print(f"  FAIL  logits len {logits.shape[0]}, expected {len(test_seq)+2}")
        return 1
    print(f"  PASS  encode_with_logits returns embedding {emb.shape}, logits {logits.shape} ({time.time()-t0:.1f}s)")

    _section("Stage 3: demo pair LLR (cross-library agreement)")
    if not DEMO_PAIR_SCORES.exists():
        print(f"  FAIL  canonical cache missing: {DEMO_PAIR_SCORES}")
        return 1
    canonical = json.loads(DEMO_PAIR_SCORES.read_text())

    # Reconstruct WT BRCA1 by reverse-applying the pathogenic L1854P swap.
    # The bundled FASTA in clinvar/ has MUT sequences; this is how
    # pick_demo_pair.py builds the WT.
    from manylatents.dogma.vep import (
        encode_variant, parse_mutation, truncate_around_mutation,
        compute_llr, compute_delta_norm,
    )

    demo_pair_json = REPO_ROOT / "experiments" / "data" / "demo_pair.json"
    if not demo_pair_json.exists():
        print(f"  FAIL  demo pair source missing: {demo_pair_json}")
        return 1
    demo = json.loads(demo_pair_json.read_text())
    wt_full = demo["wt_sequence"]
    pathogenic_hgvs = f"{demo['pathogenic']['wt_aa']}{demo['pathogenic']['position']}{demo['pathogenic']['alt_aa']}"
    benign_hgvs = f"{demo['benign']['wt_aa']}{demo['benign']['position']}{demo['benign']['alt_aa']}"

    print(f"  WT sequence length: {len(wt_full)} aa (truncate to {enc.max_length} aa around each mutation)")

    results = {}
    for label, hgvs in [("pathogenic", pathogenic_hgvs), ("benign", benign_hgvs)]:
        t0 = time.time()
        mutation = parse_mutation(hgvs)
        wt_t, new_pos = truncate_around_mutation(wt_full, mutation.position, window=enc.max_length)
        # encode_variant re-parses; pass the position-corrected HGVS string.
        corrected_hgvs = f"{mutation.wt_aa}{new_pos}{mutation.mut_aa}"
        result = encode_variant(enc, wt_t, corrected_hgvs)
        wt_tok = enc.tok_id(mutation.wt_aa)
        mut_tok = enc.tok_id(mutation.mut_aa)
        llr = compute_llr(result["wt_logits"], result["mutation"], wt_tok, mut_tok)
        dn = compute_delta_norm(result["wt_embedding"], result["mut_embedding"])
        results[label] = {"hgvs": hgvs, "llr": llr, "delta_norm": dn}
        print(f"  {label} {hgvs}: LLR={llr:+.4f}  delta_norm={dn:.4f}  ({time.time()-t0:.1f}s)")

    print()
    print("  Sign convention check:")
    if results["pathogenic"]["llr"] < results["benign"]["llr"]:
        print(f"    PASS  pathogenic LLR ({results['pathogenic']['llr']:+.4f}) more negative than benign ({results['benign']['llr']:+.4f})")
    else:
        print(f"    FAIL  pathogenic LLR ({results['pathogenic']['llr']:+.4f}) NOT more negative than benign ({results['benign']['llr']:+.4f})")
        return 1

    print()
    print(f"  Cross-library agreement (fair-esm library vs HF-transformers notebook, tolerance {LLR_TOL}):")
    fails = 0
    for label in ("pathogenic", "benign"):
        expected = canonical[label]["llr"]
        got = results[label]["llr"]
        diff = abs(got - expected)
        status = "PASS" if diff <= LLR_TOL else "FAIL"
        if status == "FAIL":
            fails += 1
        print(f"    {status}  {label}: library {got:+.4f}, notebook {expected:+.4f}, |diff|={diff:.4f}")

    _section("Summary")
    if fails:
        print(f"  FAIL  {fails} cross-library disagreement(s) above tolerance {LLR_TOL}")
        return 1
    print("  PASS  library-scope manylatents.dogma.vep reproduces the demo pair within tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
