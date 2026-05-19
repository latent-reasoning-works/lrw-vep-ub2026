# Workshop activity — your turn

Slides: <https://docs.google.com/presentation/d/14CGms9ehy0xH1d8UCTNtZiv9J1ZFs6GzahuD4fWy3pg/edit?usp=sharing>

About 30 minutes. Pick one or two tasks; you don't need to finish anything. The goal is to drive the notebook (or an agent) on something you find interesting and see what shakes loose. I'll be walking the room — flag me if something breaks or you want feedback.

## Before you start

If you're working on a gene other than BRCA1, confirm the LLR signal isn't inverted before you build on it:

```bash
uv run python experiments/notebooks/validate_genes.py --n 5
```

This runs the four bundled non-BRCA1 genes and prints PASS/FAIL per gene with the mean LLR gap. Look for your gene's row; PASS means pathogenic mean LLR < benign mean LLR on n=5 variants of each class.

The five bundled gene snapshots:

- `experiments/data/clinvar/` — BRCA1 (default; sits at the clinvar root, no subdirectory)
- `experiments/data/clinvar/tp53/`
- `experiments/data/clinvar/brca2/`
- `experiments/data/clinvar/pten/`
- `experiments/data/clinvar/mlh1/`

Each carries the same schema: `variants.tsv` + `protein.fasta` + `dna.fasta` + `rna.fasta`.

## Branch A — drive the notebook

Edit cells in `experiments/notebooks/01_workshop_followalong.ipynb` directly. Tasks reference cell IDs; click a cell and check the metadata pane (or just match the section comment at the top of each cell).

### A1. Swap the gene in the prototype

Modify `s2-pick-pair` to pick a pathogenic/benign pair from your gene instead of BRCA1, then rerun `s2-encode` and `s2-visualize` unchanged.

```python
# Replace the BRCA1 demo-pair load with a per-gene load.
import pandas as pd
GENE = "tp53"   # or brca2 / pten / mlh1
df = pd.read_csv(f"../data/clinvar/{GENE}/variants.tsv", sep="\t")
df = df[df.label.isin([0, 1])]
demo_pair = pd.DataFrame([
    df[df.label == 1].iloc[0],   # pathogenic
    df[df.label == 0].iloc[0],   # benign
])
```

Question: does the LLR ordering match the Brandes sign convention (pathogenic more negative than benign) on your pair? If it inverts, that's an interesting case to flag.

### A2. Rescale on a single gene

Adapt `s3-score-loop` to read from `experiments/data/clinvar/<gene>/variants.tsv` instead of the canonical 500-variant workshop set. The encode + `compute_llr` + `compute_delta_norm` body is unchanged; you're just feeding it a different table and reconstructing WT from the gene's `protein.fasta`.

Compute the AUROC on your gene-specific dataset and compare to the BRCA1-workshop number [TBD-NUMBER: workshop set LLR AUROC]. Cleaner gene? Worse? What about your gene (variant counts, sequence length, fraction of variants at conserved residues) could explain the gap?

### A3. Add cosine distance as a third scorer

`compute_cosine_distance(wt_emb, mut_emb)` is already in `experiments/notebooks/vep_utils.py`. Compute it per variant inside `s3-score-loop`, then add it to the scorers dict and replot `s3-distributions` with three KDEs.

```python
# In s3-score-loop (per-variant, alongside the LLR and delta_norm calls):
cos = compute_cosine_distance(wt_emb, mut_emb)

# In s3-auroc (extend the scorers dict — higher cosine distance = more disruptive):
scorers = {
    'LLR':           (scores_df['llr'].values,         -scores_df['llr'].values),
    'Delta L2 norm': (scores_df['delta_norm'].values,   scores_df['delta_norm'].values),
    'Cosine dist':   (scores_df['cosine_dist'].values,  scores_df['cosine_dist'].values),
}
```

Question: does cosine sit between delta_norm and LLR on AUROC, or elsewhere? Why?

### A4. Per-gene asymmetry

The workshop set's "pathogenic distribution is wider than benign" asymmetry is across 400 genes pooled. Filter `s3-distributions` to a single gene and see if the asymmetry holds. Only a handful of genes have ≥10 variants; check `scores_df.gene.value_counts().head(20)` to pick one.

```python
gene = "BRCA2"
sub   = scores_df[scores_df.gene == gene]
y_sub = sub['label'].values
# Replot s3-distributions using `sub` and `y_sub` in place of `scores_df` and `y`.
```

Question: does the asymmetry survive on a single gene, or is it an artifact of pooling many genes with different baseline distributions?

### A5. Sequence-length confounding

In `s3-seqlen`, color by gene to see whether any apparent length effect is actually a single-gene effect.

```python
import seaborn as sns
sns.scatterplot(
    data=scores_df, x="seq_len", y="llr",
    hue="gene", alpha=0.6, legend=False,
)
```

Question: are specific genes systematically scored higher or lower? Is the BRCA2 long-protein cluster (where truncation kicks in past 1022 aa) visible as its own band?

## Branch B — drive an agent

These tasks assume you have a Claude Code session running against the repo. Each task ends with a prompt to paste verbatim — adapt the bracketed values to your gene / results.

### B1. Layer × scorer sweep

Open the notebook to `s4-sweep-prompt` and copy the markdown cell's text into your Claude Code session. While the runs fire (3–10 min depending on substrate), make a prediction: which ESM-1b layer (out of 33) will peak for LLR? Early layers carry local sequence statistics; late layers carry global structural context. Bet a coffee with your neighbor before the runs land.

### B2. Disagreement diagnostic

Find variants where LLR and delta_norm disagree most strongly:

```python
import scipy.stats as ss
scores_df["llr_z"] = ss.zscore(-scores_df.llr)        # higher = more pathogenic
scores_df["dn_z"]  = ss.zscore(scores_df.delta_norm)  # higher = more pathogenic
disagree = (scores_df.llr_z - scores_df.dn_z).abs().nlargest(5)
print(scores_df.loc[disagree.index,
                    ['variant_id', 'gene', 'label', 'llr', 'delta_norm']])
```

Pick one disagreement case and paste into Claude Code:

> Variant `<variant_id>` in gene `<GENE>` has LLR `<llr>` (pathogenic-ranking) but delta_norm `<delta_norm>` (benign-ranking). Both come from ESM-1b on the same mutation. Walk me through what each scorer is actually measuring at the model level, and propose one biological reason they could disagree on this specific case. Cite anything from Brandes 2023 you can verify against the repo's references.

### B3. Methods paragraph for your gene

Adapt `s4-paper-prompt` to the gene-specific analysis you produced in A2. Paste:

> I want to extend `paper/main.tex` with a gene-specific paragraph in §Methods for `<YOUR_GENE>` (n=`<variant count>`, LLR AUROC=`<your A2 number>`). Match the existing voice — present tense, direct, no hedge words. Cite Brandes 2023 by DOI for the LLR formulation. Call out any methodological deviation from the canonical n=500 workshop set, e.g. truncation policy if your gene exceeds 1022 aa, or label-scope differences if your gene's ClinVar distribution looks unusual.

When the agent comes back, diff its paragraph against the existing `paper/main.tex` §Methods. Would the paragraph actually land in the paper?

### B4. Distribution hypothesis

From A4 you know your gene's pathogenic median LLR. Compare to BRCA1's [TBD-NUMBER: BRCA1 pathogenic median LLR]. Paste:

> My gene `<YOUR_GENE>` has pathogenic median LLR `<your value>`, vs BRCA1's `[TBD-NUMBER]`. ESM-1b is the same checkpoint, same scoring rule, same truncation policy in both cases. Walk through why a gene's pathogenic-distribution median might differ from another gene's — protein length, conservation pressure at the variant sites, fraction of variants at deeply conserved residues, ClinVar curation density, Mendelian-disease-gene tilt. Rank these explanations by which likely dominates for `<YOUR_GENE>` specifically.

## Branch C — inspect the harness

For engineers more interested in the harness than the biology.

### C1. PROVENANCE.md tracing

Open `PROVENANCE.md`. Pick one number — an AUROC, a CI bound, a sha256, anything specific. Trace it backward: figure → analysis script → input artifact (`s3_scores.npz` or `demo_pair_scores.json`) → producer script → ClinVar snapshot. How many hops to get to a raw input? At which hop does the audit trail get fuzzier than you'd want?

### C2. Skill stub

Open `.claude/skills/dispatcher/SKILL.md` and skim it (it's short). Then write a one-line description of a skill for something you actually do at least weekly — a repo-specific routine, a deploy-status check, a meeting-summary pattern, a figure-refresh pipeline. Keep it in your notes; if the trigger phrasing is compact enough, it's worth turning into an actual skill later.

### C3. CI failure thought experiment

Open `.github/workflows/validate.yml`. Without running anything: identify three things you could change in this repo that would break CI. Rank them by likelihood of happening by accident.

## Stretch / extra credit

If you finish faster than expected:

### S1. AlphaMissense cross-reference

Pull AlphaMissense scores for your gene's variants and compare to the ESM-1b LLR you computed. Where do the two methods agree? Where does one think pathogenic and the other benign? AlphaMissense is available via EBI's REST API or as a downloadable table from the AlphaFold DB.

### S2. Reproduce a Brandes panel

Pick one panel from Brandes et al. 2023, *Nat. Genet.* Figure 2, and reproduce it on your gene's variants. The supplementary methods describe the exact computation.

### S3. Make a figure that doesn't exist yet

Look at `experiments/analysis/figures/` and decide what's missing — a panel, a breakdown axis, a comparison the resolution-panels figure doesn't surface. Generate one figure that would belong there. Bonus if it's defensible enough to commit.
