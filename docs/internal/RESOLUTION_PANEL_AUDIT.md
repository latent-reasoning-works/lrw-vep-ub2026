# Resolution panel — end-to-end audit chain

**Figure:** `experiments/analysis/figures/resolution_panels.pdf`
**Slide:** Part 2 "Resolution" (slide 11)
**Last regenerated:** _(filled in after the rebuild — see commit history of `experiments/PROVENANCE.md`)_

This document traces every number on the figure from a script in this
repo back to a sha-pinned input. The figure cites three numbers
(LLR values for the BRCA1 pair, AUROCs on the workshop set, Brandes
ceiling) — each has an entry below with the data file, the script that
produced it, and the upstream source.

The audit chain reads top-to-bottom: BRCA1 prototype → cross-gene
validation → literature ceiling. That's also the slide's narrative.

---

## Panel A — n=2, BRCA1 prototype

**Renders:** Benign P1859R LLR = +0.22, Pathogenic L1854P LLR = +0.87.

### Lineage

```
panel A bars
  └─ experiments/analysis/figures/resolution_panels.pdf
      └─ experiments/analysis/01_resolution_panels.py
          └─ experiments/analysis/data/demo_pair_scores.json
              └─ experiments/scripts/score_demo_pair.py
                  ├─ experiments/data/demo_pair.json
                  │   └─ experiments/scripts/pick_demo_pair.py
                  │       └─ experiments/data/clinvar/variants.tsv
                  │           └─ experiments/tools/manylatents-omics/scripts/download_clinvar.py
                  │               └─ NCBI variant_summary.txt.gz (cached, gene=BRCA1)
                  └─ vep_utils.ESM1bEncoder (HF transformers ESM-1b, fp32 on MPS)
                      └─ facebook/esm1b_t33_650M_UR50S weights
```

### Reproducibility commands

```bash
# 1. Pick the demo pair from BRCA1 ClinVar (writes experiments/data/demo_pair.json)
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/scripts/pick_demo_pair.py --write-spec

# 2. Score the pair through HF transformers ESM-1b on MPS (~25 s)
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/scripts/score_demo_pair.py

# 3. Render the figure (panel A reads the JSON above; ~5 s)
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/analysis/01_resolution_panels.py
```

### What's actually citable

- `demo_pair.json` records the source TSV's sha12 (`cc1a705696b2`),
  the WT BRCA1 sequence (1863 aa, reconstructed from the mutant
  FASTA by reverse-applying the pathogenic mutation), and the two
  picked variants with all ClinVar fields.
- `demo_pair_scores.json` records the encoder identity string
  (`vep_utils.ESM1bEncoder (HF transformers, fp32 on mps)`) and the
  source pair file path.

---

## Panel B — n=499, ClinVar workshop set across 437 genes

**Renders:** delta L2 norm AUROC = 0.6065, LLR AUROC = 0.6381.

### Lineage

```
panel B ROC curves
  └─ experiments/analysis/figures/resolution_panels.pdf
      └─ experiments/analysis/01_resolution_panels.py
          └─ experiments/notebooks/data/s3_scores.npz
              └─ experiments/scripts/cache_s3_scores.py
                  ├─ experiments/notebooks/data/workshop_set.tsv
                  ├─ experiments/notebooks/data/workshop_set_proteins.fasta
                  └─ experiments/notebooks/data/workshop_set_manifest.json
                      └─ experiments/scripts/build_validation_set.py
                          └─ experiments/cache/variant_summary.txt.gz
                              └─ NCBI ftp.ncbi.nlm.nih.gov clinvar/tab_delimited/
```

### Reproducibility commands

```bash
# 1. Re-spec the workshop set (~7 min cold cache; <1 min after)
#    Writes workshop_set.tsv + workshop_set_proteins.fasta + workshop_set_manifest.json
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/scripts/build_validation_set.py

# 2. Score the validation set through the same encoder as panel A (~12 min on MPS)
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/scripts/cache_s3_scores.py --force

# 3. Render the figure (panel B reads the npz; AUROCs computed live via sklearn)
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/analysis/01_resolution_panels.py
```

### What's actually citable

- `workshop_set_manifest.json` records: ClinVar dump sha256, all filter
  params (min review stars, accepted clinical significance set,
  canonical isoform filter), sampling params (per-gene cap, label
  balance, random seed), output sha256s, and the full gene→UniProt
  accession map for every gene in the draw.
- `s3_scores.npz` records: per-variant scores under the encoder
  identity baked into `cache_s3_scores.py`'s docstring (HF transformers
  ESM-1b via `vep_utils`).
- AUROCs are computed live in `01_resolution_panels.py` via
  `sklearn.metrics.roc_auc_score(y, score)` — never interpolated, never
  eyeballed. The CSV `analysis/results/resolution_panels.csv` carries
  the computed values for parse-and-cite.

### v0 (pre-re-spec) snapshot

The first version of `validation_variants.csv` was a pre-bundled
workshop asset with no producer script (mtime 2026-05-06). Preserved
at `experiments/notebooks/data/_archive/` for historical comparison.
The v0 AUROCs (0.6065 / 0.6381) were committed on 2026-05-11 and live
in git history; the new spec's AUROCs land in
`PROVENANCE.md::Validation set composition`.

---

## Panel C — n=36,537, Brandes et al. 2023 ceiling

**Renders:** ESM-1b zero-shot AUROC = 0.905 on ClinVar (one bar),
LLR floor at 0.64 (dashed reference, pulled from panel B).

### Lineage

```
panel C bar + reference line
  └─ experiments/analysis/figures/resolution_panels.pdf
      └─ experiments/analysis/01_resolution_panels.py
          ├─ BRANDES_2023_CLINVAR_AUROC = 0.905    (constant in source)
          ├─ BRANDES_2023_CLINVAR_N = 36_537       (constant in source)
          └─ panel B's auroc_llr scalar (the dashed reference)
```

### What's actually citable

- The Brandes value is a literature citation, not a local
  computation. The script does not own the underlying ROC curve and
  does not pretend to: it plots the cited scalar as a horizontal bar
  and labels the citation in-figure ("Brandes et al., Nat. Genet.
  2023, Fig 2B").
- The LLR reference line on panel C uses panel B's exact computed
  AUROC (`auroc_llr`), so if panel B changes, panel C's floor moves
  with it automatically.
- See `PROVENANCE.md::Resolution panels` for the full revision history
  of panel C (0.74 horizontal-line → ESM-1b vs EVE bars → single bar
  + LLR floor).

---

## What's missing for full reproducibility

1. **ClinVar dump versioning.** The new spec records the sha256 of
   the `variant_summary.txt.gz` it built against, but NCBI updates
   the file daily. Two months from now the same script may emit a
   different snapshot. The manifest's `clinvar_source.sha256` is the
   only honest answer: "this snapshot was built against this dump."
2. **UniProt drift.** The per-gene UniProt accession resolution
   caches whatever UniProt returns at fetch time. If UniProt changes
   a gene's canonical accession, a re-run would draw against a
   different protein. The cache files at `experiments/cache/uniprot_*.fa`
   and `experiments/cache/uniprot_map.tsv` pin the resolved
   accessions for the current snapshot; the manifest's
   `gene_to_uniprot` map records what was used.
3. **Encoder drift.** `vep_utils.ESM1bEncoder` loads
   `facebook/esm1b_t33_650M_UR50S` from HuggingFace. If the upstream
   weights change (unlikely for a final 2020 release), the AUROCs
   would shift. The encoder identity string is recorded in both
   `demo_pair_scores.json` and `cache_s3_scores.py`'s docstring; the
   weight sha is implicit in HuggingFace's release.

These are the residual unknowns the slide should not pretend to have
closed. They are honest limitations of any reproducibility claim
against live public resources.
