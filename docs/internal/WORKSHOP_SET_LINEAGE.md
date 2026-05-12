# Workshop validation set — lineage and catch ledger

**Current canonical:** `workshop_set` (built with v2 spec, shipped 2026-05-11)
**Producer:** `experiments/scripts/build_validation_set.py --spec v2 --name workshop_set`
**LLR AUROC:** 0.925 (CI95 [0.900, 0.947]) — within noise of Brandes 2023's 0.905
**Manifest with full filter spec + sha256 + Brandes-anchor proof:**
`experiments/notebooks/data/workshop_set_manifest.json`

This document captures the four-revision history of the workshop's
n=500 validation set. Each revision was held back from shipping
because the parse-and-cite discipline caught a specific issue. The
journey itself is the strongest demonstration of the workshop's
thesis enacted on its own pipeline.

---

## The four revisions

### v0 — pre-bundled, opaque (2026-05-06, ~99% scored: 499/500)

**What it was.** A pre-bundled `validation_variants.csv` of 500
ClinVar missense variants, drawn before this repo's history began.
The CSV and matching FASTA were fetched by the notebook at runtime
from `raw.githubusercontent.com` — same files served raw from the
repo's GitHub mirror, but no producer script in the repo.

**LLR AUROC:** 0.638. Looked plausible against zero-shot ESM-1b
expectations for raw ClinVar variants.

**What was wrong.** The upstream draw was a black box. No record of
which ClinVar release, what filter rules, what seed, or — critically
— whether the protein FASTA's WT sequences matched the canonical
isoform that ClinVar's `ref_aa` was annotated against. Silent isoform
mismatch is plausible and would mean some variants were scored
against the wrong protein, producing near-random LLRs that polluted
the AUROC downward.

**Why it was held.** We couldn't honestly explain what the validation
set was. The slide narration would have read "AUROC 0.64 on a
500-variant ClinVar sample" with no way to back up where the sample
came from. Failed the parse-and-cite test on inputs.

**Archived at:** `experiments/notebooks/data/_archive/validation_variants_v0_2026-05-06.{csv,fasta}` + matching s3 scores npz.

---

### v1 in-flight — per-gene cap variant (2026-05-11, never shipped)

**What changed.** First version of `build_validation_set.py`. Added
deterministic ClinVar download + canonical-isoform validation +
label-balanced sample with seed 42. Also added a **per-gene cap of 6**
that I (the agent) introduced without sanction — intended to "preserve
diversity" but actually skewed the sample away from the natural
ClinVar gene distribution.

**LLR AUROC:** 0.9245. Big jump from v0's 0.638.

**What was wrong.** Two things: (a) the per-gene cap was an
unsanctioned addition that changed the spec without it being a
visible decision; (b) the AUROC jump triggered a verification cascade
(independent fair-esm cross-check + filter-effect quantification +
label-leakage check) before the user would let it ship.

**Why it was held.** "Change the validation set" deserves to be an
explicit decision, not a quiet one inside a panel update. User
correctly flagged this as a process issue regardless of whether the
number was right.

**Archived at:** `_archive/validation_variants_v1_in_flight_2026-05-11.{csv,fasta}` + s3 scores npz.

---

### v1 canonical-only — no per-gene cap (2026-05-11, deprecated by v2)

**What changed.** Removed the per-gene cap. Re-derived via
oversample-then-validate (rejection sampling, equivalent in
distribution to filter-universe-then-sample but ~100× cheaper than
the principled order on 15k genes).

**LLR AUROC:** 0.9444. Higher than v1 in-flight's 0.9245 — without
the per-gene cap, hot well-curated genes contributed multi-variant
signal that lifted the average.

**What was wrong.** The label scope still dropped Conflicting and
Uncertain ClinVar entries — exactly the cases that are uncertain
*because* they're hard to classify. Brandes 2023 keeps them via
ClinSigSimple binarization. Our 0.944 was on a strictly easier subset
than Brandes' 0.905 → the two numbers were not directly comparable.

**Why it was held.** The slide-10 ladder thesis depends on "same
harness reproduces literature methodology at workshop scale." If our
n=500 number is on an easier subset than the n=36,537 literature
number, the ladder reads as "we score an easier slice well" — a
defensible but smaller claim. The user pushed back: rebuild to match
Brandes' label scope rather than ship a defensive footnote.

**Archived at:** `_archive/workshop_set_v1_canonical-only_2026-05-11.{tsv,fasta,json,md}` — kept for audit comparison.

---

### workshop_set (v2 spec) — Brandes-matching label scope (2026-05-11, shipped)

**What changed.** Extended the binarization to match Brandes 2023's
methodology: include Conflicting entries, binarize them via ClinVar's
pre-computed `ClinSigSimple` field (1 = at least one submitter said
P; 0 = all submitters said B with no P). Pure Uncertain entries still
drop (no defensible label). All other filters unchanged: ≥1-star
review, canonical-isoform-validated, ClinVar SNV missense, GRCh38.

**LLR AUROC:** **0.9250** (CI95 [0.900, 0.947] via 10k-resample
bootstrap, seed 42). Brandes' **0.9050 sits inside our CI95**.

**Why this shipped.** The 0.020 gap to Brandes is inside small-sample
noise for n=500 binary AUROC. The "same harness reproduces literature
at workshop scale" claim is now numerically supported and methodology-
matched. Slide-10 ladder reads cleanly.

**Composition.** 250 P + 250 B exactly. 400 unique genes (84% are
singletons). Conflicting entries now make up 33% of the set, which
restores BRCA1 (5 rows) and BRCA2 (7 rows) to the validation set.

**Producer + manifest:**
- Script: `experiments/scripts/build_validation_set.py --spec v2`
- Manifest: `experiments/notebooks/data/workshop_set_manifest.json`
- TSV: `workshop_set.tsv` (sha256 `85aa5903d3d4…`)
- FASTA: `workshop_set_proteins.fasta` (sha256 `5df061810f48…`)
- Scored: `s3_scores.npz` (sha256 `87aa972a1e45…`)
- README: `workshop_set_README.md` (~200 words, paste-ready
  reproducibility instructions)

---

## What this lineage shows

Four revisions to ship a 500-variant validation set, each held back
by a different category of error:

1. **v0 → v1 in-flight:** missing producer + opaque isoform handling
   (a *correctness* failure).
2. **v1 in-flight → v1 canonical-only:** unsanctioned per-gene cap
   inside an unrelated panel-update task (a *process* failure).
3. **v1 canonical-only → workshop_set (v2 spec):** label scope
   mismatched Brandes, producing an inflated AUROC that wasn't
   directly comparable to the literature anchor (a *methodology*
   failure).
4. **workshop_set (v2 spec):** matches Brandes' label scope, ships
   within statistical noise of the literature number. Bootstrap CI95
   documented in the manifest.

The discipline that caught these wasn't the agent's autonomy — it
was the user's pushback at each step. *"Change the validation set"
deserves an explicit decision.* *"AUROC 0.92 on a label-filtered set
isn't comparable to 0.905 on unfiltered ClinVar."* *"The story landed
— ship v2."* Each correction was a parse-and-cite catch that didn't
make it to the slides.

## Catch ledger — workshop-prep session, 2026-05-11

Four substantive corrections to data, framing, and methodology in
one session, all caught by the parse-and-cite discipline applied
to the workshop's own pipeline:

1. **LLR sign convention.** Slide 6's narration had the LLR sign
   inverted. Caught from the demo-pair scores (pathogenic L1854P
   = +0.87, benign P1859R = +0.22; positive LLR = bigger confidence
   drop at the mutation site = pathogenic). Fixed before slides ship.

2. **AUROC 0.74 vs 0.905.** Panel C of the resolution figure initially
   cited Brandes' AUROC as 0.74 (an unverified recall from training
   data). Caught against Brandes Fig 2B — the correct number is
   0.905 for ESM-1b zero-shot on ClinVar. Replaced with explicit
   citation + revision-history note in PROVENANCE.

3. **BRCA1 vs multi-gene framing.** The original slide-10 ladder
   implied panel B was BRCA1 validation. Caught from the v0
   composition audit (1 BRCA1 row out of 500 across 437 genes —
   *not* BRCA1-specific). Slide narration rewritten to "ClinVar
   workshop set across N disease genes — cross-gene generalization,
   not BRCA1-specific performance."

4. **v0's silent isoform mismatch.** Pre-bundled v0 set was scoring
   variants against opaque protein sequences with no canonical-
   isoform validation. Caught by the v0 → v2 rebuild path, where
   each revision held back until the methodology was both correct
   and comparable to literature. Final v2 ships with full
   reproducibility + bootstrap CI inside Brandes' anchor.

None of these made it to a published slide. The discipline is working.

## How to reproduce workshop_set

```bash
# From repo root. Cold-cache ~10 min (UniProt fetches); warm <1 min.
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/scripts/build_validation_set.py --spec v2

# Score through ESM-1b (~4 min on Apple Silicon MPS)
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/scripts/cache_s3_scores.py --force

# Regenerate figure
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/analysis/01_resolution_panels.py
```

Manifest at `experiments/notebooks/data/workshop_set_manifest.json`
records the ClinVar dump sha256, all filter rules, sampling seed,
output sha256s, the gene→UniProt map, and the bootstrap CI95 with
Brandes-anchor verification. Anyone reading that file can re-derive
every number in panel B from a known input.
