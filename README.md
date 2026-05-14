# The Biology of Agentic Research Engineering

### An Agent-Driven Variant Effect Prediction Workshop · Upper Bound 2026

You'll score genetic variants with a protein language model, scale the work
from one variant to hundreds, and learn how to organize a codebase so an AI
agent can drive it. The notebook below is the workshop. The
[CLAUDE.md](./CLAUDE.md) is for the agent.

<div align="center">

<pre>
   prompt   ──▶   harness   ──▶   experiment   ──▶   paper
                     │
                     ▼
            CLAUDE.md • ARCHITECTURE.md
            Hydra configs as prompts
            manylatents-omics (pinned submodule)
</pre>

</div>

---

## First time here? Start here.

You are a workshop attendee. Do these four things in order:

1. **Clone with submodules** —
   `git clone --recurse-submodules https://github.com/latent-reasoning-works/lrw-vep-ub2026`
2. **Confirm your install works** — pick one installer:
   ```bash
   cd experiments/notebooks
   # uv (recommended — uses pyproject.toml + uv.lock for bit-identical pins):
   uv sync && uv run python validate.py --quick

   # pip (works against the same floors via requirements-workshop.txt):
   pip install -r requirements-workshop.txt && python validate.py --quick
   ```
   ~10 s; PASS line if the env reproduces the demo-pair LLRs.
3. **Open the notebook** — either via Colab (button below) or any local
   Jupyter / VS Code. Run cells S1 → S2 → S3 → S4 in order.
4. **When you hit a 🤖 markdown cell, that's a *prompt*, not instructions.**
   The text inside is what you paste into a Claude Code session running in
   the same repo. Claude reads the harness and does the work; you keep
   running notebook cells once it lands its output.

That's the whole story. Everything below is detail.

---

## Quickstart

### Run the workshop notebook (primary path)

The Colab notebook is the workshop, executed cell-by-cell on a free T4 GPU.
Open it, run S1 → S2 → S3 → S4 in order, and you'll have a working
variant-effect-prediction prototype at the end.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/latent-reasoning-works/lrw-vep-ub2026/blob/main/experiments/notebooks/01_workshop_followalong.ipynb)

The notebook source is at
[`experiments/notebooks/01_workshop_followalong.ipynb`](./experiments/notebooks/01_workshop_followalong.ipynb)
if you'd rather run it locally. The `s1-install` cell brings the pip deps;
the rest is self-contained.

### Drive the harness with Claude Code

The 🤖 markdown cells inside the notebook are the agent prompts. Open
[Claude Code](https://claude.com/claude-code) in the repo root, paste a
prompt, watch it work, then continue with the next notebook cell:

```bash
cd lrw-vep-ub2026
claude
# in the Claude Code prompt, paste the contents of any 🤖 markdown cell
```

The agent reads [`CLAUDE.md`](./CLAUDE.md) →
[`ARCHITECTURE.md`](./ARCHITECTURE.md) →
[`experiments/CLAUDE.md`](./experiments/CLAUDE.md) and works from there.
Expect questions if the environment is missing pieces.

### See the whole "prompt → paper" pipeline end-to-end

`validate_paper.py` is a smoke test for the second half of the workshop
story — taking a real biological result and turning it into a 2-page LaTeX
preprint citing the methodology paper by DOI:

```bash
cd experiments/notebooks
python validate_paper.py --prepare       # cleans the workdir, writes PROMPT.md
# in your Claude Code session, paste:
#     read experiments/notebooks/_paper_validation_tmp/PROMPT.md and execute it
python validate_paper.py --fetch-tectonic  # builds the PDF and validates it
```

First run downloads tectonic (~50 MB; cached at `~/.cache/lrw-vep-ub2026/`,
never re-downloaded). Subsequent runs need no flag.

### Logging configuration

The notebook works without any cloud accounts. The Hydra harness logs to
[Weights & Biases](https://wandb.ai) by default, but you don't need an
account to run the demo — set `WANDB_MODE=offline` and runs log to a local
folder instead:

```bash
export WANDB_MODE=offline                          # no cloud account needed
# or, if you have your own wandb team:
export WANDB_ENTITY=<your-team>
export WANDB_PROJECT=<your-project>
```

The defaults are baked for the maintainer's team and will fail on a fresh
account — set one of the above before running the Hydra path.

### Just want to compile the paper

```bash
uv tool install git+https://github.com/cmvcordova/expaper
expaper build --open         # tectonic compiles paper/main.pdf
```

---

## What's where

| Path | What |
|---|---|
| [`experiments/notebooks/01_workshop_followalong.ipynb`](./experiments/notebooks/01_workshop_followalong.ipynb) | The workshop, runnable on Colab |
| [`experiments/data/clinvar/`](./experiments/data/clinvar/) | Pre-bundled ClinVar variants for BRCA1, BRCA2, TP53, PTEN, MLH1 — no NCBI download required |
| [`experiments/scripts/`](./experiments/scripts/) | `pick_demo_pair.py`, `cache_s3_scores.py`, plus tool-management helpers |
| [`experiments/tools/manylatents-omics/`](./experiments/tools/manylatents-omics/) | Pinned submodule: the upstream library with `manylatents.dogma.vep` and the encoders |
| [`paper/main.tex`](./paper/main.tex) | NeurIPS-style preprint scaffold |
| [`CLAUDE.md`](./CLAUDE.md) | Agent operation manual (for Claude Code, not for humans) |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Living orientation doc (11 sections, architecture.md spec) |

## Conventions

This repo follows two complementary conventions:

- **[architecture.md](https://architecture.md/)** — descriptive, agent-centric
  onboarding (`ARCHITECTURE.md` with 11 mandatory sections).
- **[expaper](https://github.com/cmvcordova/expaper)** — operational scaffolding
  (uv + Hydra + git-submodule tools + Overleaf via git subtree).

## Workshop

- **Venue:** Upper Bound 2026
- **Talk:** The Biology of Agentic Research Engineering — An Agent-Driven Variant Effect Prediction Workshop
- **Companion paper:** arXiv preprint (NeurIPS-style; venue TBD)

## Acknowledgments

- Matt Scicluna
- Aaron Wenteler
- Joey Ton (Amii)
- Anjana Puliyanda (Amii)
- LRW contributors
- **Amii** — institutional

## License

MIT — see [LICENSE](./LICENSE) once it lands (TBD this week per the workshop checklist).
