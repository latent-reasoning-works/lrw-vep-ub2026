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
| Encoder protocol, prototype-vs-library API table | [`ARCHITECTURE.md`](./ARCHITECTURE.md) §3 |
| External CLIs (`expaper`, `expstash`, `expanalysis`) | [`ARCHITECTURE.md`](./ARCHITECTURE.md) §3 |
| Conventions (bootstrap seed, wandb schema, hosted encoders, figure paths) | [`ARCHITECTURE.md`](./ARCHITECTURE.md) §5 |
| Sweep launcher (submitit_slurm / joblib) | [`ARCHITECTURE.md`](./ARCHITECTURE.md) §6 |
| How an agent should behave when handoffs land | this file → *Operating principles* |

## Operating principles

Behavioral rules. Reference content (paths, signatures, schemas) lives
in `ARCHITECTURE.md` — pull facts from there, not from this file.

- **The prototype is the live demo; the library is the handoff.** S1–S3
  of the notebook use `experiments/notebooks/vep_utils.py`. S4 agent
  handoffs target `manylatents.dogma.{encoders,vep}`. The two surfaces
  are compatible by design — see `ARCHITECTURE.md` §3.
- **Truncate before you encode.** ESM-1b's effective max input is 1022
  residues. Neither `encode_variant` truncates internally; the caller
  does, via `truncate_around_mutation(seq, pos1, window=max_length)`.
  Skip this and you'll hit `ValueError` from `apply_mutation` on any
  protein longer than 1022 aa.
- **Don't reimplement what the library already provides.** If you need
  layer-specific outputs, `ESMEncoder(repr_layer=k)` already does that.
  If you need a score function by name, `score_variant_report` already
  composes them. Check `ARCHITECTURE.md` §3 and the
  `manylatents.dogma.vep` module before writing new code.
- **Don't bypass the harness CLIs.** `expaper`, `expstash`, `expanalysis`
  enforce conventions (figure paths, wandb schema, sweep launchers)
  that downstream aggregators depend on. Reach for them first; see
  `ARCHITECTURE.md` §3 for paths and command surfaces.
- **Follow the conventions** (bootstrap seed, wandb log schema, sweep
  launcher rules, figure output paths) documented in
  `ARCHITECTURE.md` §5 *Conventions for external systems* and §6
  *Sweep launcher convention*. New runs that invent alternative schemas
  won't be picked up by aggregators.

## The workshop demo

### Phase 1 — local agentic run

> **All commands run from the project root** (`lrw-vep-ub2026/`). The
> experiment config pins `data_dir` and `hydra.run.dir` against
> `${hydra:runtime.cwd}` — running from anywhere else lands files in the
> wrong place.
>
> **Sandbox fallback:** if your environment blocks direct `.venv/bin/python`
> invocation (some Claude Code sandboxes do), swap in
> `uv run --project experiments/tools/manylatents-omics --extra workshop python`
> for the `experiments/tools/manylatents-omics/.venv/bin/python` prefix in
> both commands below. Same args after the prefix.

```bash
# 0. Sync the venv (workshop extra brings fair-esm + umap-learn).
#    Variant data is ALREADY in the repo at experiments/data/clinvar/
#    (~2 MB, see that dir's README). No NCBI download needed.
(cd experiments/tools/manylatents-omics && uv sync --extra workshop)

# 1. Encode ESM-1b on top 200 BRCA1 missense, log to wandb. Mac users:
#    add `algorithms.latent.encoder_config.device=mps` for ~5x speedup over
#    the cpu default. For a faster live demo (~15s on MPS, ~75s on CPU),
#    append `data.max_variants=50`. The --config-path is required: our
#    experiment YAMLs live outside the manylatents pkg search path. Use
#    `experiment=...` (override) not `+experiment=...` (add) — `experiment`
#    is already in the base config's defaults.
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
    --config-path=$(pwd)/experiments/configs/manylatents-omics \
    experiment=encode_esm1b_brca1

# 2. UMAP + scatter plot + wandb image (separate run under same project)
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/analysis/00_demo_umap.py
```

**Want a different gene or a fresher snapshot?** The bundled data is the
2026-05-07 BRCA1 pull. To regenerate (requires a ~440 MB NCBI download
on the first run; cached after):

```bash
python3 experiments/tools/manylatents-omics/scripts/download_clinvar.py \
    --gene <GENE> --max-variants 1000 \
    --data-dir experiments/data/clinvar
```

See `experiments/data/clinvar/README.md` for built-in UniProt mappings
(BRCA1, BRCA2, TP53, PTEN, MLH1, MSH2) and the `--uniprot <accession>`
flag for everything else.

Both commands read `WANDB_ENTITY` / `WANDB_PROJECT` from env (defaults
`cesar-valdez-mcgill-university` / `upper-bound-2026`, baked via
`${oc.env:...}` in the experiment config). Output: a wandb run under
[`cesar-valdez-mcgill-university/upper-bound-2026`](https://wandb.ai/cesar-valdez-mcgill-university/upper-bound-2026)
with a UMAP scatter image, a coordinates table, and pathogenic/benign counts.
Local artifacts at `experiments/analysis/figures/demo_umap_brca1.pdf` and
`experiments/analysis/results/demo_umap_brca1.csv`.

**If the user changes the gene** (e.g. "do TP53 instead"), they need to
regenerate the bundled data first (BRCA1 is what's pre-cached):

```bash
python3 experiments/tools/manylatents-omics/scripts/download_clinvar.py \
    --gene TP53 --max-variants 1000 \
    --data-dir experiments/data/clinvar
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
    --config-path=$(pwd)/experiments/configs/manylatents-omics \
    experiment=encode_esm1b_brca1 \
    data.genes=[TP53] name=encode_esm1b_tp53
experiments/tools/manylatents-omics/.venv/bin/python \
    experiments/analysis/00_demo_umap.py --experiment encode_esm1b_tp53
```

Append an entry to [`experiments/EXPERIMENT_LOG.md`](./experiments/EXPERIMENT_LOG.md)
with the wandb run URL — that's the demo's reproducibility evidence.

### Phase 2 — cluster handoff

Two paths, depending on workload shape:

**Hydra-config path** (workshop-native; same shape as Phase 1).
`experiment=encode_esm1b_brca1_slurm_template` inherits Phase 1 and expects
the caller to supply a cluster + launcher for their environment. The repo
does not ship a canonical cluster default — the maintainer's cluster configs
live in their personal overlay, not in the public wiring. Override at the CLI:

```bash
# From the project root, on your SLURM cluster's login node:
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main \
    --config-path=$(pwd)/experiments/configs/manylatents-omics \
    experiment=encode_esm1b_brca1_slurm_template \
    cluster=<your-cluster> launcher=<your-cluster>_launcher
```

You provide `cluster/<your-cluster>.yaml` + `launcher/<your-cluster>_launcher.yaml`
under `experiments/configs/manylatents-omics/`. The post-step
(`00_demo_umap.py`) still runs locally once the sbatch finishes and
embeddings land in `experiments/outputs/`.

**Dispatcher-skill path** (substrate-agnostic; for workloads that aren't
Hydra-shaped — S4-sweep, ad-hoc scoring, anything outside the notebook's
pre-wired flows). A workshop mirror of the skill ships in this repo at
`.claude/skills/dispatcher/`. Drop a backend manifest at
`.claude/skills/dispatcher/references/backends/<your-name>.json` (or the
user-global path; see below); `route.py` picks the substrate and emits the
sbatch plan. The dispatcher knows about local CPU/GPU/MPS too, so the same
workload can target your laptop or your cluster depending on what's
available.

The bundled mirror runs out of the box (Bash-direct invocation works in any
environment):

```bash
echo '{"n_items": 60, "requires_gpu": true, "gpu_memory_gb": 16, "per_item_memory_gb": 8}' \
    | python3 .claude/skills/dispatcher/scripts/route.py
```

For Claude Code's Skill tool to discover the dispatcher across *any*
session on your machine (not just sessions opened in this repo), copy to
the user-global skills dir once:

```bash
mkdir -p ~/.claude/skills && \
cp -r .claude/skills/dispatcher ~/.claude/skills/
```

After that, future Claude Code sessions list `dispatcher` in their
available-skills set and invoke via the Skill tool natively. The bundled
mirror tracks the upstream `dispatcher` skill (`latent-reasoning-works/shop`,
private as of 2026-05-13); for full schema docs, anonymized backend
examples, and SSH-config templates see upstream once it's public.

### Generic multi-modal pattern

For deeper experimentation (cross-modal alignment), the harness also supports
the encode/encode/align flow inherited from merging-dogma. Same invocation
pattern (`--config-path=...` + `experiment=<name>`, from project root):

```bash
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main --config-path=$(pwd)/experiments/configs/manylatents-omics experiment=encode_evo2          # DNA
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main --config-path=$(pwd)/experiments/configs/manylatents-omics experiment=encode_esm3          # protein
experiments/tools/manylatents-omics/.venv/bin/python -m manylatents.main --config-path=$(pwd)/experiments/configs/manylatents-omics experiment=alignment_matrix     # k-NN Jaccard
```

Configs at `experiments/configs/manylatents-omics/experiment/`. **NB:** these
inherited configs were *not* hardened with the Phase-1 fixes (data_dir pin,
`_recursive_: false`, dropping the `/config` self-reference). They likely
need the same treatment before they'll run cleanly — start from
`encode_esm1b_brca1.yaml` as the working template.

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
