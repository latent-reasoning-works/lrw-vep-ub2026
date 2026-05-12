#!/usr/bin/env python3
"""pick_demo_pair.py — Pick the variant pair for the Friday boss demo.

Reads the same data the canonical Phase-1 prompt operates on:
`experiments/data/clinvar/variants.tsv` + `experiments/data/clinvar/protein.fasta`.
The bundled clinvar is the harness's actual input; the workshop notebook's
validation CSV is an S3 artifact, not the demo data source.

Picks one pathogenic + one benign BRCA1 variant. **No ≤1024 aa filter**:
BRCA1 is 1863 aa, exceeding ESM-1b's context. `truncate_around_mutation`
(in vep_utils.py today, manylatents.dogma.vep post-2.11) handles the
windowing at encode time. The picker only chooses; it does not truncate.

The bundled FASTA contains *mutant* sequences (one per variant). The WT
BRCA1 sequence is reconstructed by reverse-applying any chosen variant's
mutation (replace the alt_aa at `position` with the wt_aa). This is
exact: all entries derive from UniProt P38398.

Outputs:
  - stdout: 2 summary lines.
  - experiments/data/demo_pair.json: pathogenic + benign records, source
    metadata (TSV SHA), and the WT sequence (so B9 reads from one file).
  - (with --write-spec FILE) replaces tokens `<pathogenic_id>`,
    `<P_HGVS>`, `<benign_id>`, `<B_HGVS>`, `<pathogenic_gene>`,
    `<benign_gene>` in FILE. Idempotent.

Picker logic (rhetorically consistent with notebook cell 9, but on
BRCA1-only data and without the length filter):
  - pick(label=1, gene='BRCA1')   pathogenic
  - pick(label=0, gene='BRCA1')   benign
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
TSV_PATH = REPO_ROOT / "experiments" / "data" / "clinvar" / "variants.tsv"
FASTA_PATH = REPO_ROOT / "experiments" / "data" / "clinvar" / "protein.fasta"
OUTPUT_JSON = REPO_ROOT / "experiments" / "data" / "demo_pair.json"

DEFAULT_GENE = "BRCA1"


def load_fasta(path: Path) -> dict[str, str]:
    """Parse a FASTA into {id: sequence}. IDs are the first whitespace token."""
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


def hgvs(row: pd.Series) -> str:
    """HGVS short form: `<wt_aa><position><alt_aa>` (positions are 1-indexed in the TSV)."""
    return f"{row['wt_aa']}{int(row['position'])}{row['alt_aa']}"


def pick(df: pd.DataFrame, gene: str, label: int) -> pd.Series:
    """Pick the first entry matching (gene_symbol, label). Stable on the TSV's row order."""
    pool = df[(df["gene_symbol"] == gene) & (df["label"] == label)]
    if pool.empty:
        raise ValueError(f"no candidates for gene={gene!r} label={label}")
    return pool.iloc[0]


def reconstruct_wt(mut_seq: str, row: pd.Series) -> str:
    """Reverse-apply a single point mutation to recover the WT sequence.

    The bundled FASTA contains mutant proteins; all derive from the same
    UniProt accession (P38398 for BRCA1). Replacing the alt_aa at
    `position` with the wt_aa recovers the canonical WT.
    """
    pos1 = int(row["position"])  # 1-indexed
    alt = row["alt_aa"]
    wt = row["wt_aa"]
    if mut_seq[pos1 - 1] != alt:
        raise ValueError(
            f"sanity check failed: mut FASTA position {pos1} is "
            f"{mut_seq[pos1 - 1]!r}, expected alt_aa {alt!r} "
            f"(variant {row['variation_id']})"
        )
    return mut_seq[: pos1 - 1] + wt + mut_seq[pos1:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--gene",
        default=DEFAULT_GENE,
        help=f"Gene to pick from. Default: {DEFAULT_GENE}.",
    )
    ap.add_argument(
        "--write-spec",
        type=Path,
        default=None,
        help="Path to a markdown file whose placeholder tokens should be "
        "replaced with the picked values. Idempotent.",
    )
    args = ap.parse_args()

    df = pd.read_csv(TSV_PATH, sep="\t")
    seqs = load_fasta(FASTA_PATH)
    tsv_sha = hashlib.sha256(TSV_PATH.read_bytes()).hexdigest()[:12]

    row_p = pick(df, gene=args.gene, label=1)
    row_b = pick(df, gene=args.gene, label=0)

    p_hgvs = hgvs(row_p)
    b_hgvs = hgvs(row_b)
    p_id = f"clinvar_{int(row_p['variation_id'])}"
    b_id = f"clinvar_{int(row_b['variation_id'])}"

    # Reconstruct WT from the pathogenic entry (any entry works; we pick one).
    if p_id not in seqs:
        raise SystemExit(f"FASTA missing entry for {p_id}")
    wt_sequence = reconstruct_wt(seqs[p_id], row_p)

    print(
        f"Pathogenic: {p_id:18s} {row_p['gene_symbol']:8s} "
        f"{p_hgvs:8s} (clinical_significance={row_p['clinical_significance']})"
    )
    print(
        f"Benign:     {b_id:18s} {row_b['gene_symbol']:8s} "
        f"{b_hgvs:8s} (clinical_significance={row_b['clinical_significance']})"
    )
    print(
        f"WT sequence reconstructed: {len(wt_sequence)} aa "
        f"(BRCA1 canonical UniProt P38398 expected: 1863 aa)"
    )

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "gene": args.gene,
        "pathogenic": {
            "variant_id": p_id,
            "gene": row_p["gene_symbol"],
            "hgvs": p_hgvs,
            "clinical_significance": row_p["clinical_significance"],
            "position": int(row_p["position"]),
            "wt_aa": row_p["wt_aa"],
            "alt_aa": row_p["alt_aa"],
        },
        "benign": {
            "variant_id": b_id,
            "gene": row_b["gene_symbol"],
            "hgvs": b_hgvs,
            "clinical_significance": row_b["clinical_significance"],
            "position": int(row_b["position"]),
            "wt_aa": row_b["wt_aa"],
            "alt_aa": row_b["alt_aa"],
        },
        "wt_sequence": wt_sequence,
        "source": {
            "tsv": str(TSV_PATH.relative_to(REPO_ROOT)),
            "fasta": str(FASTA_PATH.relative_to(REPO_ROOT)),
            "tsv_sha256_12": tsv_sha,
            "picker": "experiments/scripts/pick_demo_pair.py",
            "logic": (
                f"first BRCA1 label=1 + first BRCA1 label=0 from variants.tsv "
                f"(stable row order); WT reconstructed by reverse-applying "
                f"the pathogenic mutation to its mutant FASTA entry"
            ),
        },
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"  wrote {OUTPUT_JSON.relative_to(REPO_ROOT)} (tsv_sha256={tsv_sha})")

    if args.write_spec is not None:
        spec_path = args.write_spec.resolve()
        text = spec_path.read_text()
        replacements = {
            "<pathogenic_id>": p_id,
            "<P_HGVS>": p_hgvs,
            "<benign_id>": b_id,
            "<B_HGVS>": b_hgvs,
            "<pathogenic_gene>": row_p["gene_symbol"],
            "<benign_gene>": row_b["gene_symbol"],
        }
        any_present = any(token in text for token in replacements)
        if not any_present:
            print(f"  {spec_path.name}: placeholders already filled, no-op")
            return 0
        new_text = text
        for token, value in replacements.items():
            count = text.count(token)
            new_text = new_text.replace(token, value)
            if count:
                print(f"  {spec_path.name}: replaced {count}x {token!r} -> {value!r}")
        spec_path.write_text(new_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
