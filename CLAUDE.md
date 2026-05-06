# lrw-vep-ub2026

> Workshop harness for Upper Bound 2026. The repo IS the argument: a
> well-plugged-in harness lets an agent drive biological research tasks
> automagically — text prompt → real biological prediction → paper edit —
> without the human reading the bioinformatics manual first.

If you are an agent (Claude Code or otherwise), read this file, then read
[`ARCHITECTURE.md`](./ARCHITECTURE.md) to orient on the system, then read
[`experiments/CLAUDE.md`](./experiments/CLAUDE.md) for the tool API
contract. The submodule at
`experiments/tools/manylatents-omics/` ships its own `ARCHITECTURE.md` and
`CLAUDE.md` — defer to those for tool internals.

## Where to look first

| If you need… | Read |
|---|---|
| What this repo is and how it's laid out | [`ARCHITECTURE.md`](./ARCHITECTURE.md) |
| How to run an experiment | [`experiments/CLAUDE.md`](./experiments/CLAUDE.md) |
| How `manylatents-omics` works internally | `experiments/tools/manylatents-omics/CLAUDE.md` |
| What's been run | [`experiments/EXPERIMENT_LOG.md`](./experiments/EXPERIMENT_LOG.md) |
| What figure came from where | [`experiments/PROVENANCE.md`](./experiments/PROVENANCE.md) |
| How to compile / sync the paper | this file → *Overleaf sync* |

## The workshop demo (canonical task list)

Whether the demo runs through Claude Code or through the Colab notebook
(`experiments/notebooks/01_workshop_followalong.ipynb`), the **task list is
identical**. The notebook is one cell per step; the agent is one prompt for
all six.

1. **Smoke-test the environment.** `cd experiments/tools/manylatents-omics &&
   uv sync && .venv/bin/python -c "import manylatents; print(manylatents.__version__)"`.
   Bail out and report if the import fails.
2. **Encode DNA.** `.venv/bin/python -m manylatents.main +experiment=encode_evo2 data.preset=brca1`.
   Output: per-variant Evo2 embeddings under `experiments/outputs/`.
3. **Encode protein.** `.venv/bin/python -m manylatents.main +experiment=encode_esm3 data.preset=brca1`.
4. **Compute cross-modal alignment.** `.venv/bin/python -m manylatents.main +experiment=alignment_matrix`.
   Output: a 2×2 alignment matrix and per-sample $k$-NN Jaccard scores.
5. **Generate Figure 1.** Plot the alignment heatmap to
   `experiments/analysis/figures/alignment_heatmap.pdf`. (When `analysis/`
   has a `NN_figures.py`, call it; otherwise, write a one-off script.)
6. **Update the paper.** Fill in `paper/main.tex` §Results with the headline
   number from step 4, point Figure 1 at the new PDF, then `expaper build
   --open` to compile locally (or `expaper sync push` to publish to Overleaf
   if linked).

A successful run produces an entry in `experiments/EXPERIMENT_LOG.md` and a
`PROVENANCE.md` line for the figure. The agent should make these entries
itself — they are the demo's reproducibility evidence.

## Working with this project

- **Use `uv`**, never bare `pip install`. Tool deps live in each tool's
  `.venv` (`experiments/tools/<tool>/.venv`); the project root has no Python
  env of its own.
- **Use `python3`**, not `python`, on cluster environments.
- **Snapshot before any milestone:**
  `python3 experiments/scripts/snapshot_experiment manylatents-omics <experiment_name> --tag <tag>`.
- **Submodule pin discipline:** if you bump
  `experiments/tools/manylatents-omics`, commit the new SHA and update
  `EXPERIMENT_LOG.md` so the change is visible.

## Overleaf sync

```bash
expaper link-overleaf https://git.overleaf.com/<project-id>   # one-time
expaper sync pull                                             # before edits
expaper sync push                                             # after edits
expaper build --open                                          # local tectonic build, no Overleaf needed
```

If Overleaf isn't linked yet (workshop default), `expaper build` is the only
path; the PDF lands at `paper/main.pdf`.

---

## Writing directives

> Default venue for this repo is **arXiv preprint, NeurIPS-style** (the
> `[preprint]` option of `neurips_2024.sty`). Switch to `[final]` for
> camera-ready, or remove the option for anonymous submission.

### Format — conference paper, NeurIPS / ICML / ICLR tier

- Structure: abstract → intro → background → method → experiments →
  discussion → limitations → conclusion.
- Length: 8–9 pages main body + unlimited references (NeurIPS 2024 budget).
- Citations: `\citep{}` / `\citet{}` (natbib loaded by `neurips_2024.sty`).
- Quotation marks: LaTeX style — ` ``...'' ` or `\enquote{}` (csquotes).
- Heading case: sentence case (NeurIPS convention; not Title Case).
- Figures: each must stand alone. Caption = one sentence on what it shows +
  one sentence on the takeaway. A reader skimming figures should be able to
  reconstruct the paper's argument.

### Voice

Write for two readers simultaneously: a domain expert who will stress-test
the claims, and a researcher from an adjacent field who needs the stakes
explained.

- **Active voice.** "We show that X" not "It was shown that X."
- **Concrete over abstract.** Cite numbers. "Accuracy improved 4.2%" not
  "performance improved."
- **Short sentences win.** If a sentence needs two em dashes and a
  subordinate clause, split it.
- **Define jargon on first use**, briefly, inline. After that, use the term
  freely.

### Structure

**Abstract**: State the problem, what you did, and the headline result. One
paragraph — not bullets. The reader should know whether to keep reading
after the first four sentences.

**Introduction**: Lead with the stakes. Why this problem, why now? Establish
the gap your work closes before describing your approach.

**Method**: Explain the intuition before the formalism. A reader who
understands *why* a design choice was made will forgive notation they have
to look up.

**Results**: State what the numbers show in prose — don't make the reader
interpret tables alone. Lead with the headline result, then ablations and
failure modes.

**Limitations**: Visible, not buried. One honest paragraph beats three
paragraphs of hedged optimism.

### Numbers and punctuation

Numbers: spell out one through nine; numerals for 10 and above. Use %, not
"percent."

Em dashes (—) no spaces, for sharp asides only — use sparingly. En dashes
(–) for ranges only.

### Patterns to avoid

- **Zombie nouns.** "An investigation of X was conducted" → "We investigated X."
- **Throat-clearing.** Delete: "It is important to note that…" / "In today's
  rapidly evolving landscape…"
- **Intensifiers that insist.** "This genuinely works," "This is truly novel"
  — the evidence makes the claim, not the adverb.
- **The "not X — it's Y" construction.** Never.
- **Academese.** "The prevention of neurogenesis was observed to result in
  the diminishment of fear extinction" → "Blocking neurogenesis made mice
  worse at unlearning fear."
- **Puffed-up synonyms.** utilize → use. leverage → use. facilitate → help.
  demonstrate → show.

### Honesty

Acknowledge limitations clearly and early — not in a footnote, not in the
last line of the conclusion. A reader who discovers an unacknowledged
limitation will distrust the rest; one who sees you flag it first will
trust your results more.

### Overleaf sync workflow

Treat `overleaf/master` as a live coauthor. Between any two of your local
commits, collaborators may have written into Overleaf.

- **Always pull before pushing.** Run `expaper sync pull` before any
  `expaper sync push`. The CLI refuses to push when `overleaf/master` has
  unabsorbed commits — do not work around the gate.
- **Never paste/replace `paper/main.tex` end-to-end.** Make scoped edits to
  specific sections so the Overleaf diff log shows specific revisions. A
  diff that marks nearly all old lines deleted and nearly all new lines
  added is a clobber pattern, not a revision.
- **When merging incoming Overleaf edits, default to keeping their
  version** for any section you did not intentionally touch. Re-apply your
  local edits manually after the merge if needed.
- **Respect section locks.** If a coauthor says "I'm rewriting §X, don't
  touch it," leave §X alone — even when tightening adjacent sections.

<!-- Tuning: set venue in the Format block above, add co-author preferences here -->
