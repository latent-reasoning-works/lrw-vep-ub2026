#!/usr/bin/env python3
"""score_demo_pair.py — Score the demo BRCA1 P/B pair through `vep_utils`.

Encodes the pair stored in `experiments/data/demo_pair.json` with the
notebook's HF-transformers ESM1bEncoder (same code path as the S3 cache,
so the n=2 and n=500 numbers in the resolution plot come from the same
encoder). Writes `experiments/analysis/data/demo_pair_scores.json` with
delta_norm, cosine_dist, LLR per variant.

Runtime: ~25 s on Apple Silicon MPS with weights already cached.

Pre/post-2.11: this script imports `vep_utils` directly. Post-2.11 +
NB.1 (notebook import swap), the canonical equivalent is
`manylatents.dogma.vep.encode_variant` + `manylatents.dogma.encoders.ESMEncoder.encode_with_logits`.
The numbers will shift slightly with the loader change; regenerate this
file when NB.1 lands.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_DIR = REPO_ROOT / "experiments" / "notebooks"
DEMO_PAIR_JSON = REPO_ROOT / "experiments" / "data" / "demo_pair.json"
OUTPUT_JSON = (
    REPO_ROOT / "experiments" / "analysis" / "data" / "demo_pair_scores.json"
)

sys.path.insert(0, str(NOTEBOOK_DIR))


def main() -> int:
    if not DEMO_PAIR_JSON.exists():
        print(f"[ERR] {DEMO_PAIR_JSON} missing — run pick_demo_pair.py first")
        return 1

    pair = json.loads(DEMO_PAIR_JSON.read_text())
    wt_seq = pair["wt_sequence"]

    from vep_utils import (  # type: ignore  # noqa: E402
        ESM1bEncoder,
        encode_variant,
        compute_delta_norm,
        compute_cosine_distance,
        compute_llr,
        parse_mutation,
        truncate_around_mutation,
    )

    print("[INFO] loading ESM-1b on mps...")
    t0 = time.time()
    encoder = ESM1bEncoder(device="mps")
    print(f"[INFO] encoder warm in {time.time() - t0:.1f}s")

    wt_token_ids = {
        aa: encoder.tokenizer.convert_tokens_to_ids(aa)
        for aa in "ACDEFGHIKLMNPQRSTVWY"
    }

    results = {}
    for tag in ["pathogenic", "benign"]:
        v = pair[tag]
        seq, pos = truncate_around_mutation(wt_seq, v["position"], window=encoder.MAX_LEN)
        hgvs = f"{v['wt_aa']}{pos}{v['alt_aa']}"
        r = encode_variant(encoder, seq, hgvs)
        delta_norm = compute_delta_norm(r["wt_embedding"], r["mut_embedding"])
        cosine_dist = compute_cosine_distance(r["wt_embedding"], r["mut_embedding"])
        llr = compute_llr(
            r["wt_logits"], r["mut_logits"], parse_mutation(hgvs),
            wt_token_ids[v["wt_aa"]], wt_token_ids[v["alt_aa"]],
        )
        results[tag] = {
            "variant_id": v["variant_id"],
            "gene": v["gene"],
            "hgvs": v["hgvs"],
            "delta_norm": delta_norm,
            "cosine_dist": cosine_dist,
            "llr": llr,
        }
        print(
            f"  {tag.capitalize():12s} {v['gene']} {v['hgvs']:8s}  "
            f"delta={delta_norm:6.3f}  cos={cosine_dist:6.4f}  LLR={llr:+6.3f}"
        )

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps({
        "encoder": "vep_utils.ESM1bEncoder (HF transformers, fp32 on mps)",
        "source_pair": str(DEMO_PAIR_JSON.relative_to(REPO_ROOT)),
        "pathogenic": results["pathogenic"],
        "benign": results["benign"],
    }, indent=2) + "\n")
    print(f"[OK] wrote {OUTPUT_JSON.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
