# Readability feedback — 2026-05-10

Different lens than `WORKSHOP_READINESS.md`. The audit asks *does it work?*
This doc asks *if a stranger lands here cold, would they get it?* Two
audiences:

- **Workshop attendee, May 23 onward.** Scanned the QR code, opened the
  notebook, followed Part 2, wants to try this on their own gene a week
  later.
- **Passerby, May 24.** Saw the repo linked somewhere. Has 30 seconds to
  decide if it's worth their time.

Both audiences read without the slides in front of them.

## Items and status

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | README leads with notebook (not Claude Code); intro paragraph; drop "harness IS the argument" agent-speak | ✅ done 2026-05-10 | README.md restructured. Quickstart now opens with the Colab badge. |
| 2 | Glossary cell at top of notebook — VEP / ESM-1b / LLR / Harness / manylatents | ✅ done 2026-05-10 | Cell inserted at position 1 (between intro and S1). |
| 4 | Internal coordination docs out of `experiments/` | ✅ done 2026-05-10 | Moved to `docs/internal/`. README's "What's where" table flags them as internal. EXPERIMENT_LOG.md trimmed to public-friendly with a pointer here. |
| 3 | "Now you try" exits at the end of S2 / S3 / S4 | ❌ pending — user-owned | The user's voice in the notebook's teaching cells. **Do not delegate** — user rewrites in a sitting. |
| 5 | Agent-speak cleanup in remaining user-facing docs | 🟡 partial | Done for README. Notebook's teaching cells are user-owned (#3 same constraint). CLAUDE.md and ARCHITECTURE.md stay as agent docs. |
| 6 | `docs/provenance.md` — trace one number (AUROC 0.64) end-to-end | ❌ pending | One worked example: AUROC → `notebooks/data/s3_scores.npz` → `scripts/cache_s3_scores.py` → `data/clinvar/variants.tsv` (SHA). Concrete, ~20 lines. |

## "Now you try" exit copy (user's draft — pending insertion)

The user supplied these. They're staged here so the user can paste them
into the notebook in their own voice rather than having the agent default
to "carefully but not warmly." **The agent should not write to the
notebook's teaching cells.**

- **After S2:** "Try a variant of your own. Pass any protein sequence and
  a mutation string like `A23T` to `score_variant`. The structure is the
  same."
- **After S3:** "Try another gene. The harness accepts BRCA1, BRCA2, TP53,
  PTEN, and MLH1 out of the box. For anything else, use
  `--uniprot <accession>`."
- **After S4:** "Take this home. Fork the repo, swap in your dataset,
  edit CLAUDE.md to describe it. You'll have a working pipeline in an
  afternoon."

## Hard veto (from the 2026-05-10 discussion)

The notebook's teaching cells — why we prototype small before validating,
why one variant is a hint and 500 is a result, why the harness matters at
scale — are the most teaching-load-bearing thing in the repo. The user
rewrites these by hand; the agent does not touch them.

If a future agent reads this doc and is tempted to rewrite the notebook's
markdown cells: don't. Surface the suggestion in chat and let the user
do it.
