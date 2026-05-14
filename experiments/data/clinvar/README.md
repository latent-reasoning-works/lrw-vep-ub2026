# Bundled ClinVar missense variants — BRCA1 + 4 audience-pick genes

Pre-cached so the workshop demo doesn't depend on a 440 MB download from
NCBI when the conference Wi-Fi is shaky. ~10 MB committed total.

## What's here

### BRCA1 (default, at this directory's root)

| File | Bytes | Contents |
|---|---|---|
| `variants.tsv` | 196 KB | 1 000 BRCA1 missense rows (per `ClinVarDataModule` schema). 316 are P/B (pathogenic + benign); 684 are VUS and get dropped at load time when `pathogenicity=all`. |
| `protein.fasta` | 1.8 MB | 1 000 mutant BRCA1 proteins, each 1 863 aa, FASTA-keyed by `clinvar_<id>`. Built by injecting the missense at the parsed HGVS.p position into UniProt **P38398** (canonical BRCA1). |
| `dna.fasta` | 17 KB | Stub (`>id\nN`). The workshop demo is protein-only; the data module just requires the file to exist and ids to match. |
| `rna.fasta` | 17 KB | Stub, same reason. |

Pulled from NCBI's `variant_summary.txt.gz` on **2026-05-07**, GRCh38, ≥ 1-star
review status, single-nucleotide missense.

### Audience-pick genes (subdirectories, added 2026-05-10)

Same schema, same NCBI snapshot, one subdirectory per gene. Built for
B18 ("Same harness, any gene") so audience picks never hit NCBI live.

| Subdir | UniProt | aa  | P / B / VUS    | Notes |
|--------|---------|-----|----------------|-------|
| `tp53/`  | P04637  | 393  | 206 / 82 / 712  | rich both sides; strongest live demo after BRCA1 |
| `brca2/` | P51587  | 3418 | 54 / 172 / 774  | mostly benign; long sequence, exercises truncation |
| `pten/`  | P60484  | 403  | 234 / 6 / 760   | **thin benign set (n=6) — redirect if too sparse** |
| `mlh1/`  | P40692  | 756  | 135 / 32 / 833  | balanced; medium sequence |

### Running the Phase-1 demo on a different gene

Override the experiment config's `data.data_dir` (the leaf) — *not* the
top-level `data_dir`. The `clinvar` data config does
`data.data_dir: ${data_dir}/clinvar`, so the top-level gets `/clinvar`
appended, and the bundled per-gene dirs live at
`experiments/data/clinvar/<gene>/`, not `…/clinvar/<gene>/clinvar/`.

Example — TP53, `max_variants=50` (~15-20 s on Apple Silicon MPS):

```bash
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
    --config-path=$(pwd)/experiments/configs/manylatents-omics \
    experiment=encode_esm1b_brca1 \
    data.genes=[TP53] \
    data.data_dir=$(pwd)/experiments/data/clinvar/tp53 \
    name=encode_esm1b_tp53 \
    algorithms.latent.encoder_config.device=mps \
    data.max_variants=50
```

Override map for the five pre-bundled genes:

| Gene  | `data.data_dir` override                          |
|-------|---------------------------------------------------|
| BRCA1 | `$(pwd)/experiments/data/clinvar` (default)       |
| TP53  | `$(pwd)/experiments/data/clinvar/tp53`            |
| BRCA2 | `$(pwd)/experiments/data/clinvar/brca2`           |
| PTEN  | `$(pwd)/experiments/data/clinvar/pten`            |
| MLH1  | `$(pwd)/experiments/data/clinvar/mlh1`            |

PTEN's benign set is thin (n=6) — if the audience picks PTEN and the
encode finishes too fast for the UMAP to be visually compelling,
redirect to BRCA2 or MLH1 for a richer P-vs-B contrast.

## Refreshing or expanding

To re-pull (different gene, more variants, fresher snapshot), use the
upstream script:

```bash
python3 experiments/tools/manylatents-omics/scripts/download_clinvar.py \
    --gene BRCA1 --max-variants 5000 \
    --data-dir experiments/data/clinvar
```

Built-in UniProt mappings: BRCA1, BRCA2, TP53, PTEN, MLH1, MSH2. For other
genes, pass `--uniprot <accession>` (any reviewed entry on
[uniprot.org](https://www.uniprot.org)). First run downloads ~440 MB into
`./data/_cache/`; subsequent runs use the cache.

## Why bundle, not regenerate

- Conference Wi-Fi is unreliable.
- NCBI's tab-delimited dump is ~440 MB and serves over plain FTP — slow and
  flaky.
- The workshop runs in a fixed time slot; we can't afford a 5-minute
  download for one part of the demo to fail silently.

The trade-off: when ClinVar adds new BRCA1 variants, this snapshot ages.
For workshop reproduction, that's fine; for ongoing research, refresh.
