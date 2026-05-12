# Workshop Beats — Coordination Doc

Each beat is a load-bearing structural moment. Beats are non-negotiable;
between beats is freestyle. Confidence updates as the audit progresses.

Tier legend:
  🔴 FRI — must work by Friday for code-along / boss demo
  🟡 TALK — must work by 2026-05-23 for workshop
  🟢 NICE — talk works without it; cleaner with it

## Part 1 — Agents, Harnesses & You (conceptual; low gate burden)

### B1 — Builder's tax → harness pays it down
Tier: 🟡 TALK
Slides: "Builder's research engineering tax"
Code surface: none (rhetorical)
Failure mode: n/a
Confidence: HIGH (slides exist)

### B2 — Harness/model distinction lands (the +13.7 from LangChain)
Tier: 🟡 TALK
Slides: "If you're not the model, you're the harness"; "Engineer the harness"
Code surface: none
Confidence: HIGH

### B3 — Three things that must be true (legibility, guardrails, memory)
Tier: 🟡 TALK
Slides: "1. The codebase must be legible" / "2. Guardrails" / "3. Memory"
Code surface: CLAUDE.md, ARCHITECTURE.md, MEMORY.md pattern (referenced)
Confidence: HIGH

### B4 — Step-change framing (before/after table)
Tier: 🟡 TALK
Slides: "The early stages of a step change"
Code surface: none (table is conceptual)
Confidence: HIGH

## Part 2 — Variant Effect Prediction (heavy LIVE)

### B5 — Biology demands a harness (slides 2.1–2.3 land as a trio)
Tier: 🟡 TALK
Slides: "Why VEP matters", "VEP is the next frontier", "VEP is best estimated at scale"
Code surface: none directly; presupposes pLM literature
Failure mode: n/a (no LIVE)
Confidence: HIGH (slides done)

### B6 — Where the agent enters (the bridge)
Tier: 🟡 TALK
Slides: 2.4 "Where the agent enters" (currently TITLE ONLY — SD.1)
Code surface: none directly; references CLAUDE.md
Failure mode: slide is empty on talk day
Fallback: speaker beat over a placeholder slide
Confidence: LOW until SD.1 closes

### B7 — ESM-1b LLR mechanic (workhorse slide)
Tier: 🔴 FRI
Slides: 2.5 "ESM-1b: LLR workhorse"
Code surface: compute_llr, BOS-offset regression test
Audit gates: 2.5, 2.11 (post-collapse)
Failure mode: LLR formula on slide doesn't match code
Confidence: HIGH (formula is correct, regression test exists)

### B8 — Concrete variant pair chosen
Tier: 🔴 FRI
Slides: 2.6 "A variant pair: BRCA1" (placeholder)
Code surface: workshop_set.tsv with the chosen IDs baked in
Audit gates: 2.6 (placeholder fill)
Failure mode: slide says "BRCA1 [???]" on stage
Fallback: pick on the fly from the csv (workable but rough)
Confidence: LOW until pair locked

### B9 — LIVE: prototype scores one pair, returns a number  ★ KEY BEAT
Tier: 🔴 FRI
Slides: 2.7 "A variant pair: BRCA1 (LIVE)"
Code surface:
  - encode_variant in manylatents.dogma.vep (post-2.11 collapse)
    OR vep_utils.encode_variant (pre-collapse fallback)
  - workshop_set.tsv + workshop_set_proteins.fasta
  - ESM-1b weights downloadable
Audit gates: 2.0, 2.4, 2.5, 2.6, 2.11
Failure mode: cell errors, model OOM, network glitch
Fallback: pre-cached LLR output text for the chosen P/B pair
Confidence: MED (Path A stable; collapse adds uncertainty)

### B10 — Validation visible (n=500 AUROC + CIs)
Tier: 🔴 FRI
Slides: 2.8 "Scale matters / Resolution"
Code surface: notebook S3 + s3_scores.npz cache
Audit gates: 2.7
Failure mode: S3 cell takes >15 min on T4
Fallback: load from committed cache, present numbers from there
Confidence: HIGH after Q5 cache lands

### B11 — Resolution: n=2 / n=500 / Brandes anchor
Tier: 🟡 TALK
Slides: "Resolution" (currently empty body — duplicate exists)
Code surface: plot generation script that produces all three panels
Audit gates: 2.9
Failure mode: panel mismatch, axis inconsistency
Fallback: replace n=2,000 with literature anchor (Brandes Fig 2A or 2B)
Confidence: MED (plot script needs to be written)

### B12 — The harness integrates (stack diagram)
Tier: 🔴 FRI
Slides: 2.10 "What the harness integrates" (partial body)
Code surface: each layer of the diagram is a real artifact:
  - CLAUDE.md (file)
  - Hydra experiment configs (directory)
  - manylatents-omics (released package)
  - submitit launcher (config or wrapper)
  - wandb (env vars)
Audit gates: 2.10 (slide reword to drop "shop")
Failure mode: layer label has no referent
Confidence: HIGH after 2.11 collapse + slide reword

### B13 — LIVE: same prompt, cluster invocation
Tier: 🟡 TALK (Friday only if Phase-2 validated)
Slides: 2.11 "Scaling with agents"
Code surface: experiment=encode_esm1b_brca1_mila + submitit
Audit gates: 2.8, LD.2
Failure mode: dispatch fails on stage
Fallback: pre-recorded logs/screenshots
Confidence: LOW (CLAUDE.md flags 2.8 as untested)

### B14 — What you just did (Part 2 closer)
Tier: 🟡 TALK
Slides: 2.12 "What you just did" (TITLE ONLY)
Code surface: none (rhetorical recap)
Failure mode: slide empty on talk day
Confidence: LOW until drafted

## Part 3 — Consolidation & Integration

### B15 — What we generated (Part 3 opener)
Tier: 🟡 TALK
Slides: 3.1 "What we generated" (placeholder)
Code surface: intermediate consolidation files exist on disk
Audit gates: 3.1
Confidence: MED (depends on 3.1 implementation)

### B16 — LIVE: read artifacts, parse-and-cite
Tier: 🟡 TALK
Slides: 3.6 "Parse-and-cite discipline", 3.7 "LIVE: parse-and-cite in action"
Code surface: parse-and-cite tooling — CURRENTLY UNKNOWN STATUS
Audit gates: 3.2
Failure mode: tooling doesn't exist, demo doesn't work
Fallback: walk through artifacts manually, claim as future work
Confidence: LOW until 3.2 status confirmed

### B17 — LIVE: Overleaf push
Tier: 🟡 TALK
Slides: 3.9 "Overleaf wiring"
Code surface: expaper sync push against linked Overleaf project
Audit gates: 3.4
Failure mode: auth fails, sync errors, network blocks Overleaf git
Fallback: pre-recorded screenshots
Confidence: LOW until Q4 setup happens

### B18 — LIVE: tunable gene demo  ★ KEY BEAT
Tier: 🔴 FRI (promoted 2026-05-10 — strongest single beat for a single-viewer demo)
Slides: "Same harness, any gene" (NEW per recent draft)
Code surface: pre-cached genes (BRCA1, BRCA2, TP53, PTEN, MLH1)
Audit gates: 3.5, LD.4
Failure mode: audience-picked gene not pre-cached, NCBI lookup live fails
Fallback: 5 pre-staged genes, audience picks from them
Confidence: HIGH after Q6 bundle lands
Why FRI: parallel-path to the 2.11/REL.1 critical chain (data work, not API work). The Q6 bundle is ~3–4 min of wall time after the NCBI cache warms up. Rhetorical payoff: "watch this run on BRCA1, now watch the same prompt run on TP53 — the harness didn't know we were doing either."

### B19 — Part 3 closer (full research cycle)
Tier: 🟡 TALK
Slides: 3.10 "The full research cycle"
Code surface: none (diagram-based)
Confidence: HIGH

## Recap

### B20 — The pattern, named once
Tier: 🟡 TALK
Slides: NEW Recap.A (drafted, not pasted)
Confidence: MED (draft exists; needs paste)

### B21 — Step change table + caveats
Tier: 🟡 TALK
Slides: NEW Recap.B + "Words of caution" + "Too clever by half"
Confidence: HIGH

## Maintenance rules

- Slide change shifts a beat's claim → update beat → re-check gates → notify agent
- Code requirement fails → mark beat LOW → fix or activate fallback
- Beat LOW the day before talk → cut from demo, freestyle around fallback

## Friday code-along scope

The 🔴 FRI beats above. In aggregate, they prove:
  - Repo is legible (B6 — implicit, via CLAUDE.md)
  - Harness consumes prompt, produces a number (B9)
  - The number is real and reproducible (B7, B10)
  - The harness parameterizes — same prompt, different gene (B18, promoted 2026-05-10)
  - Stack diagram has real referents (B12)
  - Cluster handoff is real (B13 if validated; otherwise covered by 🟡 TALK timeline)

These are the beats your boss demo lands on. Target duration: 12 min
(midpoint of the 10–15 min budget). See `FRIDAY_CODEALONG.md` (engineering
spec) and `FRIDAY_RUNBOOK.md` (speaker beats) for the actual sequence.
