#!/usr/bin/env python3
"""build_validation_set.py — Build the canonical workshop validation set.

Produces `workshop_set_v1.*` files. Label-balanced random draw on the
universe of canonical-isoform-validated, high-confidence ClinVar
missense variants. Replaces both the pre-bundled v0 (no producer) and
the in-flight v1 (per-gene capped, sampled-before-isoform-validated).

## Canonical spec (workshop_set_v1, frozen 2026-05-11)

**Source.** NCBI `variant_summary.txt.gz`, cached at
`experiments/cache/variant_summary.txt.gz` (gitignored, ~440 MB). The
manifest records the sha256 of the dump the set was built against.

**Universe (filter applied before sampling).**
  * `Type == "single nucleotide variant"`, `Assembly == "GRCh38"`
  * Parses as a real missense (HGVS.p ref/pos/alt; drops synonymous,
    nonsense, unknown, low-penetrance, drug-response, risk-factor)
  * `ReviewStatus` ≥ 1 star (configurable via `--min-stars`)
  * `ClinicalSignificance` ∈ {Pathogenic, Likely_pathogenic,
    Pathogenic/Likely_pathogenic, Benign, Likely_benign, Benign/Likely_benign}
    — drops "Uncertain", "Conflicting", and everything else
  * Gene symbol resolves to a UniProt human reviewed accession
    (built-in map + UniProt REST `gene_exact AND reviewed AND organism_id:9606`)
  * Canonical isoform validated: `WT[pos-1] == ref_aa` on the UniProt
    canonical sequence; drop on mismatch
  * `1 <= pos <= sequence_length`

**Sampling.**
  * Stratified random within label class, NO per-gene cap
  * `N = 500` total: 250 pathogenic + 250 benign
  * Seed: 42 (`random.Random(seed).sample` — without replacement)

**Implementation: rejection sampling on a bounded oversample.**
"Filter universe then sample uniformly" and "draw an oversample then
rejection-validate" produce the same distribution — both are uniform
over the validated universe. We use the latter to avoid 15k UniProt
fetches when 99% of variants would never be sampled anyway. Empirical
pass rate ~98% (UniProt success + canonical-isoform match), so a 3x
oversample (1500 candidates → 1470+ passes) safely yields the 500
final sample. Phase 2 draws stratified oversample; phase 3 resolves
UniProt for the ~few hundred genes that appear in the oversample;
phase 4 validates and takes 250 P + 250 B in order. The oversample
itself is `rng.sample(pool, K)` — already random — so "first 250 valid"
is statistically the same as "random 250 valid."

**Outputs (under <output-dir>/, default `experiments/notebooks/data/`):**
  * `workshop_set_v1.tsv` — `variant_id, gene, uniprot_id, position
    (1-indexed), ref_aa, alt_aa, clinsig_raw, label (0/1), isoform_validated`
  * `workshop_set_v1_proteins.fasta` — WT canonical sequence per
    variant_id (header is variant_id; sequences are repeated per
    variant for notebook lookup convenience)
  * `workshop_set_v1_manifest.json` — ClinVar sha, all filter rules
    verbatim, seed, sampling timestamp, ClinVar release date if
    available, output sha256s, gene_to_uniprot map
  * `workshop_set_v1_README.md` — ~200 words on what's in the set,
    how to re-derive, what it does NOT claim

## Usage

```bash
# First-run cold (~7 min: download ClinVar + UniProt fetches; cached after)
experiments/tools/manylatents-omics/.venv/bin/python \\
    experiments/scripts/build_validation_set.py

# Smoke / quick test (uses cached ClinVar)
experiments/tools/manylatents-omics/.venv/bin/python \\
    experiments/scripts/build_validation_set.py \\
    --n-pathogenic 25 --n-benign 25 --output-dir /tmp/vset_smoke
```

UniProt accession lookups are cached at `experiments/cache/uniprot_map.tsv`
(per-gene) and `experiments/cache/uniprot_<accession>.fa` (per-protein),
so re-runs after the first are cheap.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import random
import sys
import threading
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = REPO_ROOT / "experiments" / "cache"
DEFAULT_OUTPUT = REPO_ROOT / "experiments" / "notebooks" / "data"
CLINVAR_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
)

sys.path.insert(
    0, str(REPO_ROOT / "experiments" / "tools" / "manylatents-omics" / "scripts")
)
from download_clinvar import (  # type: ignore  # noqa: E402
    DEFAULT_UNIPROT,
    REVIEW_STAR,
    classify_significance,
    fetch_uniprot_protein,
    fetch_variant_summary,
    parse_missense,
)


# ---- v1 binarization (strict canonical-only) -------------------------------
# Drops Uncertain, Conflicting, low-penetrance, drug-response, risk-factor.
# Used by `--spec v1` for backward compat with workshop_set_v1.
V1_ACCEPTED_CLINSIGS = {
    "Pathogenic",
    "Likely_pathogenic",
    "Pathogenic/Likely_pathogenic",
    "Benign",
    "Likely_benign",
    "Benign/Likely_benign",
}


# ---- v2 binarization (Brandes-matching, includes Conflicting with lean) ----
# Canonical labels (P*/B*) bind to their text class directly.
# Conflicting* entries bind to ClinSigSimple (1 if any submitter said P, 0 if
# all said B). Uncertain* drops. Non-disease categories (drug response, risk
# factor, etc.) drop.
_V2_DROP_PREFIXES = (
    "Uncertain",
    "drug response",
    "association",
    "risk factor",
    "protective",
    "Affects",
    "other",
    "no classification",
    "no interpretation",
)


def normalize_clinsig(s: str) -> str:
    return s.strip().replace(" ", "_")


def classify_v1(sig: str, css: str) -> int:
    """v1: strict canonical-only labels."""
    sig_norm = normalize_clinsig(sig)
    if sig_norm not in V1_ACCEPTED_CLINSIGS:
        return -1
    s = sig.lower()
    if "pathogenic" in s and "non-pathogenic" not in s:
        return 1
    if "benign" in s:
        return 0
    return -1


def classify_v2(sig: str, css: str) -> int:
    """v2: canonical + Conflicting (via ClinSigSimple). Drops Uncertain, non-disease.

    Returns 1 (pathogenic), 0 (benign), or -1 (drop).
    """
    # Drop drop-list categories (Uncertain, drug response, etc.)
    for pfx in _V2_DROP_PREFIXES:
        if sig.startswith(pfx):
            return -1
    # Canonical Pathogenic-family
    if sig.startswith("Pathogenic") or sig.startswith("Likely pathogenic"):
        return 1
    # Canonical Benign-family
    if sig.startswith("Benign") or sig.startswith("Likely benign"):
        return 0
    # Conflicting: trust ClinSigSimple's "any-P" lean
    if sig.startswith("Conflicting"):
        if css == "1":
            return 1
        if css == "0":
            return 0
        return -1
    # Anything else drops
    return -1


CLASSIFIERS = {"v1": classify_v1, "v2": classify_v2}


def _load_uniprot_cache(path: Path) -> dict[str, str | None]:
    seen: dict[str, str | None] = {}
    if not path.exists():
        return seen
    for line in path.read_text().splitlines():
        if not line or "\t" not in line:
            continue
        g, acc = line.split("\t", 1)
        seen[g] = acc.strip() or None
    return seen


_UNIPROT_LOCK = threading.Lock()


def uniprot_for_gene(gene: str, cache_dir: Path, cache: dict[str, str | None]) -> str | None:
    """Resolve gene symbol -> UniProt accession, with disk + in-memory cache.

    Thread-safe: in-memory `cache` reads/writes and the appended on-disk
    `uniprot_map.tsv` are guarded by a module-level lock. Network call
    is outside the lock so threads can fetch concurrently.
    """
    with _UNIPROT_LOCK:
        if gene in cache:
            return cache[gene]
    acc = DEFAULT_UNIPROT.get(gene.upper())
    if not acc:
        url = (
            "https://rest.uniprot.org/uniprotkb/search"
            f"?query=gene_exact:{gene}+AND+organism_id:9606+AND+reviewed:true"
            "&format=tsv&fields=accession&size=1"
        )
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                lines = r.read().decode("utf-8").splitlines()
            acc = lines[1].strip() if len(lines) > 1 else None
        except Exception:
            acc = None
    with _UNIPROT_LOCK:
        cache[gene] = acc
        with (cache_dir / "uniprot_map.tsv").open("a") as fh:
            fh.write(f"{gene}\t{acc or ''}\n")
    return acc


def get_wt_sequence(acc: str | None, cache_dir: Path) -> str | None:
    """Fetch and cache the canonical protein FASTA for a UniProt accession.

    Thread-safe by virtue of per-accession files: each accession writes
    to its own path, so concurrent calls for different genes never
    collide. An empty file is the "tried and failed" sentinel.
    """
    if not acc:
        return None
    cache = cache_dir / f"uniprot_{acc}.fa"
    if cache.exists():
        seq = cache.read_text().strip()
        return seq or None
    try:
        seq = fetch_uniprot_protein(acc)
    except Exception:
        cache.write_text("")
        return None
    cache.write_text(seq + "\n")
    return seq


def resolve_gene(gene: str, cache_dir: Path,
                 uniprot_cache: dict[str, str | None]) -> tuple[str, str | None, str | None]:
    """Compose uniprot_for_gene + get_wt_sequence for one gene.

    Returns (gene, accession_or_none, sequence_or_none). Used as the
    parallel unit of work in the thread pool.
    """
    acc = uniprot_for_gene(gene, cache_dir, uniprot_cache)
    if not acc:
        return gene, None, None
    seq = get_wt_sequence(acc, cache_dir)
    return gene, acc, seq


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--spec", choices=["v1", "v2"], default="v2",
        help="Binarization spec. v1: strict canonical-only (drops Conflicting). "
             "v2: includes Conflicting via ClinSigSimple lean (Brandes-matching). "
             "Default v2 (current canonical).",
    )
    p.add_argument(
        "--name", default=None,
        help="Output basename (default: workshop_set_<spec>).",
    )
    p.add_argument("--n-pathogenic", type=int, default=250)
    p.add_argument("--n-benign", type=int, default=250)
    p.add_argument("--min-stars", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    p.add_argument(
        "--clinvar-sha256",
        default=None,
        help="Pin upstream variant_summary.txt.gz to this sha256. "
        "If unset, accept whatever NCBI currently serves and record it.",
    )
    p.add_argument(
        "--max-genes",
        type=int,
        default=None,
        help="Cap genes considered in phase 2 (smoke / debug only).",
    )
    p.add_argument(
        "--threads", type=int, default=8,
        help="Concurrent UniProt fetches. UniProt's REST allows ~100 req/s "
             "for unauthenticated; 8 is safely below the limit. Default 8.",
    )
    args = p.parse_args()

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    classify = CLASSIFIERS[args.spec]
    name = args.name or f"workshop_set_{args.spec}"
    print(f"[INFO] spec={args.spec}  output_basename={name}", flush=True)

    # ---- Phase 0: download (cached) -----------------------------------------
    summary_gz = args.cache_dir / "variant_summary.txt.gz"
    fetch_variant_summary(summary_gz)
    sha = hashlib.sha256(summary_gz.read_bytes()).hexdigest()
    print(f"[OK] variant_summary.txt.gz sha256: {sha[:12]}", flush=True)
    if args.clinvar_sha256 and sha != args.clinvar_sha256:
        print(
            f"[ERR] ClinVar sha mismatch: expected {args.clinvar_sha256[:12]}, "
            f"got {sha[:12]}",
            file=sys.stderr,
        )
        return 1

    # ---- Phase 1: stream + filter -------------------------------------------
    print(f"[INFO] phase 1: streaming variant_summary, applying {args.spec} filter...",
          flush=True)
    per_gene: dict[str, list[dict]] = defaultdict(list)
    n_total = n_kept = 0
    label_counts = {0: 0, 1: 0}
    with gzip.open(summary_gz, "rt", encoding="utf-8", errors="replace") as fh:
        header = fh.readline().lstrip("#").rstrip("\n").split("\t")
        idx = {col: i for i, col in enumerate(header)}
        for line in fh:
            n_total += 1
            f = line.rstrip("\n").split("\t")
            if len(f) < len(header):
                continue
            if f[idx["Type"]] != "single nucleotide variant":
                continue
            if f[idx["Assembly"]] != "GRCh38":
                continue
            stars = REVIEW_STAR.get(f[idx["ReviewStatus"]].lower(), 0)
            if stars < args.min_stars:
                continue
            mis = parse_missense(f[idx["Name"]])
            if mis is None:
                continue
            sig_text = f[idx["ClinicalSignificance"]]
            css = f[idx["ClinSigSimple"]] if "ClinSigSimple" in idx else ""
            label = classify(sig_text, css)
            if label == -1:
                continue
            gene = f[idx["GeneSymbol"]].strip()
            if not gene or ";" in gene:
                continue
            vid = f[idx["VariationID"]] if "VariationID" in idx else ""
            if not vid and "AlleleID" in idx:
                vid = f[idx["AlleleID"]]
            if not vid:
                continue
            n_kept += 1
            label_counts[label] += 1
            per_gene[gene].append(
                {
                    "variant_id": f"clinvar_{vid}",
                    "gene": gene,
                    "ref_aa": mis[0],
                    "pos": mis[1],
                    "alt_aa": mis[2],
                    "label": label,
                    "clinsig": normalize_clinsig(sig_text),
                    "clinsig_simple": css,
                    "stars": stars,
                }
            )
    print(
        f"[OK] kept {n_kept} pre-isoform variants across {len(per_gene)} genes "
        f"({label_counts[1]} P + {label_counts[0]} B; scanned {n_total} rows)",
        flush=True,
    )

    # ---- Phase 2: stratified random oversample ------------------------------
    # Rejection sampling: draw 3x the target per label class from the
    # pre-isoform pool. Empirical UniProt + canonical-isoform pass rate
    # is ~98%, so 3x is conservative — the 500 final picks are an
    # unbiased random draw from the validated universe, identical in
    # distribution to "validate-then-sample" but ~100x cheaper.
    p_pool = [r for r in (v for vs in per_gene.values() for v in vs) if r["label"] == 1]
    b_pool = [r for r in (v for vs in per_gene.values() for v in vs) if r["label"] == 0]
    OVERSAMPLE = 3
    n_p_over = args.n_pathogenic * OVERSAMPLE
    n_b_over = args.n_benign * OVERSAMPLE
    print(
        f"[INFO] phase 2: stratified oversample "
        f"({n_p_over}P + {n_b_over}B = {OVERSAMPLE}x target, "
        f"seed {args.seed}, no per-gene cap, no replacement)",
        flush=True,
    )
    print(f"     pre-isoform pool: {len(p_pool)} P + {len(b_pool)} B", flush=True)
    if len(p_pool) < n_p_over or len(b_pool) < n_b_over:
        print(
            f"[ERR] pool too small for {OVERSAMPLE}x oversample",
            file=sys.stderr,
        )
        return 1
    p_over = rng.sample(p_pool, n_p_over)
    b_over = rng.sample(b_pool, n_b_over)
    oversample = p_over + b_over
    # Shuffle so "first 250 valid" is statistically random across labels
    # within each class (rng.sample is already random, but combining
    # P and B and shuffling makes downstream iteration order independent
    # of class ordering — defensive).
    rng.shuffle(p_over)
    rng.shuffle(b_over)
    over_genes = {r["gene"] for r in oversample}
    print(
        f"     oversample: {len(oversample)} variants across {len(over_genes)} unique genes",
        flush=True,
    )

    # ---- Phase 3: resolve UniProt for oversample genes only -----------------
    uniprot_cache = _load_uniprot_cache(args.cache_dir / "uniprot_map.tsv")
    over_gene_list = sorted(over_genes)
    if args.max_genes:
        over_gene_list = over_gene_list[: args.max_genes]
    print(
        f"[INFO] phase 3: resolve UniProt for {len(over_gene_list)} oversample genes "
        f"(cached: {sum(1 for g in over_gene_list if g in uniprot_cache)}, "
        f"threads={args.threads})",
        flush=True,
    )
    gene_to_uniprot: dict[str, str] = {}
    gene_to_seq: dict[str, str] = {}
    n_done = 0
    n_no_uniprot = 0
    with ThreadPoolExecutor(max_workers=args.threads) as pool_ex:
        futures = {
            pool_ex.submit(resolve_gene, gene, args.cache_dir, uniprot_cache): gene
            for gene in over_gene_list
        }
        for fut in as_completed(futures):
            gene, acc, seq = fut.result()
            n_done += 1
            if acc and seq:
                gene_to_uniprot[gene] = acc
                gene_to_seq[gene] = seq
            else:
                n_no_uniprot += 1
            if n_done % 100 == 0:
                print(
                    f"  [{n_done}/{len(over_gene_list)}] oversample genes resolved "
                    f"({len(gene_to_seq)} success, {n_no_uniprot} fail)",
                    flush=True,
                )
    print(
        f"[OK] resolved {len(gene_to_seq)} / {len(over_gene_list)} oversample genes "
        f"({n_no_uniprot} failed UniProt lookup)",
        flush=True,
    )

    # ---- Phase 4: isoform-validate + take first N valid per label class -----
    print(
        f"[INFO] phase 4: isoform-validate oversample, take first "
        f"{args.n_pathogenic}P + {args.n_benign}B",
        flush=True,
    )
    p_picks: list[tuple[dict, str]] = []
    b_picks: list[tuple[dict, str]] = []
    n_no_uniprot_drop = 0
    n_isoform_drop = 0
    n_oob_drop = 0

    def _validate(r: dict) -> tuple[bool, str]:
        seq = gene_to_seq.get(r["gene"])
        if not seq:
            return False, "no_uniprot"
        if not (1 <= r["pos"] <= len(seq)):
            return False, "oob"
        if seq[r["pos"] - 1] != r["ref_aa"]:
            return False, "isoform"
        return True, ""

    for r in p_over:
        if len(p_picks) >= args.n_pathogenic:
            break
        ok, reason = _validate(r)
        if not ok:
            if reason == "no_uniprot": n_no_uniprot_drop += 1
            elif reason == "isoform": n_isoform_drop += 1
            elif reason == "oob": n_oob_drop += 1
            continue
        r["uniprot_id"] = gene_to_uniprot[r["gene"]]
        r["isoform_validated"] = True
        p_picks.append((r, r["uniprot_id"]))
    for r in b_over:
        if len(b_picks) >= args.n_benign:
            break
        ok, reason = _validate(r)
        if not ok:
            if reason == "no_uniprot": n_no_uniprot_drop += 1
            elif reason == "isoform": n_isoform_drop += 1
            elif reason == "oob": n_oob_drop += 1
            continue
        r["uniprot_id"] = gene_to_uniprot[r["gene"]]
        r["isoform_validated"] = True
        b_picks.append((r, r["uniprot_id"]))

    final = p_picks + b_picks
    rng.shuffle(final)
    print(
        f"     dropped from oversample: "
        f"{n_no_uniprot_drop} no-UniProt + {n_isoform_drop} isoform-mismatch + "
        f"{n_oob_drop} position-out-of-bounds",
        flush=True,
    )
    if len(p_picks) < args.n_pathogenic or len(b_picks) < args.n_benign:
        print(
            f"[ERR] short of target: drew {len(p_picks)}P + {len(b_picks)}B "
            f"(target {args.n_pathogenic}P + {args.n_benign}B). "
            f"Bump OVERSAMPLE in the script — current pass rate insufficient.",
            file=sys.stderr,
        )
        return 1
    print(f"     final: {len(p_picks)} P + {len(b_picks)} B = {len(final)}", flush=True)

    # ---- Phase 5: write outputs ---------------------------------------------
    tsv_path = args.output_dir / f"{name}.tsv"
    fa_path = args.output_dir / f"{name}_proteins.fasta"
    manifest_path = args.output_dir / f"{name}_manifest.json"
    readme_path = args.output_dir / f"{name}_README.md"

    with tsv_path.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(
            ["variant_id", "gene", "uniprot_id", "position",
             "ref_aa", "alt_aa", "clinsig_raw", "label", "isoform_validated"]
        )
        for r, acc in final:
            w.writerow([
                r["variant_id"], r["gene"], acc,
                r["pos"],  # 1-indexed per spec
                r["ref_aa"], r["alt_aa"],
                r["clinsig"], r["label"],
                str(r["isoform_validated"]).lower(),
            ])

    with fa_path.open("w") as fh:
        for r, _acc in final:
            seq = gene_to_seq[r["gene"]]
            fh.write(f">{r['variant_id']}\n{seq}\n")

    tsv_sha = hashlib.sha256(tsv_path.read_bytes()).hexdigest()
    fa_sha = hashlib.sha256(fa_path.read_bytes()).hexdigest()

    final_genes = {r["gene"] for r, _ in final}
    n_genes_final = len(final_genes)
    n_singletons = sum(
        1
        for g in final_genes
        if sum(1 for x, _ in final if x["gene"] == g) == 1
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    binarization_doc = {
        "v1": {
            "rule": "strict canonical-only",
            "accepted_clinsigs": sorted(V1_ACCEPTED_CLINSIGS),
            "label_source": "ClinicalSignificance text class",
            "dropped": "Uncertain*, Conflicting*, low_penetrance, drug_response, risk_factor, other",
        },
        "v2": {
            "rule": "Brandes-matching: canonical text + Conflicting via ClinSigSimple lean",
            "label_source": (
                "ClinicalSignificance text for canonical Pathogenic*/Benign* entries; "
                "ClinSigSimple (NCBI pre-computed 'any-P' binary) for Conflicting* entries"
            ),
            "dropped": (
                "Uncertain*, drug response, risk factor, protective, Affects, "
                "association, other, no classification, no interpretation"
            ),
        },
    }[args.spec]

    manifest = {
        "spec_version": "1.0.0",
        "spec": args.spec,
        "name": name,
        "generated_utc": timestamp,
        "script": "experiments/scripts/build_validation_set.py",
        "clinvar_source": {
            "url": CLINVAR_URL,
            "sha256": sha,
            "cached_at": str(summary_gz.relative_to(REPO_ROOT)),
        },
        "universe_filters": {
            "variant_type": "single nucleotide variant",
            "assembly": "GRCh38",
            "missense": "HGVS.p parsed (ref!=alt, alt!=*, ref/alt resolvable in 20 AA)",
            "min_review_stars": args.min_stars,
            "binarization": binarization_doc,
            "uniprot_resolution": (
                "built-in map (BRCA1/BRCA2/TP53/PTEN/MLH1/MSH2) + "
                "UniProt REST search: gene_exact AND reviewed AND organism_id:9606"
            ),
            "canonical_isoform_validated": True,
            "position_in_bounds_required": True,
        },
        "sampling": {
            "method": "stratified random within label class",
            "n_pathogenic": sum(1 for r in final if r[0]["label"] == 1),
            "n_benign": sum(1 for r in final if r[0]["label"] == 0),
            "n_total": len(final),
            "per_gene_cap": None,
            "replacement": False,
            "random_seed": args.seed,
            "rng": (
                "random.Random(seed).sample(pool, K) for stratified oversample, "
                "then iterate-and-validate (rejection sampling) to take first "
                "N valid per label class. Equivalent in distribution to "
                "rng.sample(validated_universe, N)."
            ),
            "phase_order": (
                "1: stream-filter ClinVar (197k variants, ~15k genes); "
                "2: stratified random oversample (3x target per label class); "
                "3: resolve UniProt for genes in oversample (~few hundred); "
                "4: rejection-validate oversample, take first N valid per class"
            ),
        },
        "outputs": {
            f"{name}.tsv": {"sha256": tsv_sha, "n_rows": len(final)},
            f"{name}_proteins.fasta": {"sha256": fa_sha, "n_seqs": len(final)},
        },
        "composition": {
            "total_variants": len(final),
            "unique_genes": n_genes_final,
            "singleton_genes": n_singletons,
            "top_genes": dict(
                sorted(
                    ((g, sum(1 for x, _ in final if x["gene"] == g)) for g in final_genes),
                    key=lambda kv: -kv[1],
                )[:10]
            ),
        },
        "gene_to_uniprot": dict(sorted(gene_to_uniprot.items())),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    # README — paste-ready 200-word description
    if args.spec == "v2":
        clinsig_blurb = (
            "Label binarization matches Brandes et al. 2023 (Nat. Genet.): "
            "canonical Pathogenic*/Benign* text classes are used directly; "
            "Conflicting* entries are binarized via ClinVar's `ClinSigSimple` "
            "field (1 if any submitter classified as pathogenic, 0 if all "
            "classified as benign). Uncertain*, drug-response, risk-factor, "
            "protective, association, and \"other\" entries are dropped."
        )
        comparability = (
            "Comparable in methodology to Brandes' AUROC reporting on "
            "ClinVar — same label-scope rule (`ClinSigSimple`-based "
            "binarization of conflicts), same canonical-isoform "
            "discipline. AUROC on this 500-variant slice should land "
            "in the same regime as Brandes' n=36,537 number, modulo "
            "small-sample variance."
        )
    else:
        clinsig_blurb = (
            "Label binarization restricted to canonical clinical "
            "significance categories: {Pathogenic, Likely_pathogenic, "
            "P/LP} → 1; {Benign, Likely_benign, B/LB} → 0. All other "
            "categories (Uncertain, Conflicting, low_penetrance, "
            "drug_response, risk_factor, other) are dropped."
        )
        comparability = (
            "NOT directly comparable to Brandes 2023. Our set drops "
            "Conflicting and Uncertain entries (the harder cases); "
            "Brandes keeps them via `ClinSigSimple` binarization. Use "
            "`workshop_set_v2` for a Brandes-matching comparison."
        )

    readme = f"""# {name} — ClinVar workshop validation set ({args.spec})

**Generated:** {timestamp}
**Script:** `experiments/scripts/build_validation_set.py --spec {args.spec}`
**Manifest:** `{name}_manifest.json` (canonical record;
read it for filter rules, seed, ClinVar sha, gene→UniProt map)

## What's in the set

`{len(final)}` ClinVar missense variants across `{n_genes_final}`
unique disease genes (`{n_singletons}` singletons). Label-balanced:
`{sum(1 for r in final if r[0]['label'] == 1)}` pathogenic +
`{sum(1 for r in final if r[0]['label'] == 0)}` benign, drawn by
stratified random sampling (seed `{args.seed}`, no replacement,
no per-gene cap).

Every variant is canonical-isoform-validated against the UniProt
reviewed human entry for its gene: `WT[pos-1] == ref_aa` is required
to enter the universe.

{clinsig_blurb}

## How to re-derive

```bash
experiments/tools/manylatents-omics/.venv/bin/python \\
    experiments/scripts/build_validation_set.py --spec {args.spec}
```

Cold-cache runtime ~10 min (depends on ClinVar dump download +
UniProt REST throughput). Cached runs <1 min.

## What this set does NOT claim

- **Not gene-stratified.** Hot genes (BRCA1, TP53, BRCA2, etc.) are
  over-represented in proportion to their ClinVar density.
- **Not BRCA1-specific.** Panel A of `resolution_panels.pdf` uses a
  separate BRCA1 demo pair; this is a multi-gene workshop set.

{comparability}

## Deprecated predecessors

- `_archive/validation_variants_v0_2026-05-06.csv` — pre-bundled set
  with no producer script; isoform handling opaque.
- `_archive/validation_variants_v1_in_flight_2026-05-11.csv` —
  per-gene-capped variant; rolled back because the cap was
  unsanctioned and skewed the gene distribution.
- `workshop_set_v1.tsv` (still on disk) — strict canonical-only
  binarization; replaced by v2 for Brandes comparability.
"""
    readme_path.write_text(readme)

    print(f"[OK] wrote {tsv_path.relative_to(REPO_ROOT)}  sha256 {tsv_sha[:12]}")
    print(f"[OK] wrote {fa_path.relative_to(REPO_ROOT)}   sha256 {fa_sha[:12]}")
    print(f"[OK] wrote {manifest_path.relative_to(REPO_ROOT)}")
    print(f"[OK] wrote {readme_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
