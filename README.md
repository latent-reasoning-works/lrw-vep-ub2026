# lrw-vep-ub2026

Research project combining experiments and paper writing.

## Structure

```
lrw-vep-ub2026/
├── experiments/          # experimentStash structure
│   ├── configs/          # Hydra configs
│   ├── tools/            # Git submodules
│   ├── scripts/          # add_tool, run_experiment, snapshot_experiment
│   ├── notebooks/        # Analysis notebooks
│   └── outputs/          # Experiment outputs
├── paper/                # Overleaf-synced paper
├── shared/               # Shared resources
│   ├── bib/              # Bibliography
│   └── figures/          # Figures for paper
└── CLAUDE.md             # AI context + writing directives (tune before writing)
```

## Writing directives

`CLAUDE.md` includes a **Writing directives** section at the bottom.
**Tune it before writing**: set your target venue (NeurIPS / ICML / blog),
delete the format you're not using, and add co-author style preferences.

## Experiment Commands

```bash
# Add a tool
python3 experiments/scripts/add_tool <name> <repo_url>

# Run an experiment (direct invocation from tool directory)
cd experiments/tools/<tool>
python3 -m <module>.main --config-path=../../configs/<tool> experiment=<name>

# Snapshot for reproducibility
python3 experiments/scripts/snapshot_experiment <tool> <experiment> --tag <tag>
```

## Overleaf Sync

```bash
# Pull collaborator changes
expaper sync pull

# Push local changes
expaper sync push
```
