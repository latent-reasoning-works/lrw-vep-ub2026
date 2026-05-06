# Experiment Log — lrw-vep-ub2026

Append-only chronicle of non-trivial runs. One entry per run that produced shipped data.

Format:

```markdown
## YYYY-MM-DD — NN_<name> <smoke|run>

- **Pin:** <tool> commit `<sha>`, version `x.y.z`
- **Cmd:** `.venv/bin/python3 ../../analysis/NN_<name>.py [...]`
- **Output:** `results/<name>.csv` (N rows)
- **Notes:** <what you actually learned>
```
