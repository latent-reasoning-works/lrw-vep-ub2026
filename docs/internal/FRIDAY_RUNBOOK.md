# Friday Runbook — Speaker Beats

> Target: 12-minute boss demo on César's M5 Pro local. **What to say,
> when to pause, what to highlight on screen.** Commands and expected
> outputs live in `FRIDAY_CODEALONG.md` — this doc references them by
> beat ID rather than duplicating.
>
> Beat IDs reference `WORKSHOP_BEATS.md`. Read this Friday morning;
> read the spec to verify the harness; do not read either to your boss.

## Friday morning ritual (T-2 h)

- [ ] Coffee. Phone on Do Not Disturb.
- [ ] Run pre-demo step 0 + checks 1–5 from `FRIDAY_CODEALONG.md`. Every
      one must pass. If any fails, slack the parallel agent and triage.
- [ ] Open three windows on the second monitor:
  1. VS Code with `CLAUDE.md` already at line 26.
  2. Terminal in repo root, encoder-warmed kernel ready.
  3. Jupyter Lab with `01_workshop_followalong.ipynb` open, S1 cells
     already executed.
- [ ] Slide deck open, advanced to slide 2.4. Slide remote tested.
- [ ] One TextEdit window with the **B9 fallback text** (pre-baked
      delta + LLR numbers for both variants — read off
      `experiments/data/demo_pair.json` after step 0 + a dry-run B9)
      ready to paste if the live run fails.
- [ ] Wandb open in a browser tab, filtered to `upper-bound-2026`.
- [ ] If B13 is in scope: Mila login session active, `srun --pty` shell
      open in a fourth terminal.
- [ ] **Confirm boss's familiarity with ESM-1b / protein language
      models.** This shifts B7 only; the live commands don't change.
  - **High** (ML researcher who knows pLMs): compress B7 to ~30 s; drop
    the "ESM-1b is the workhorse" framing and skip the formula
    paraphrase.
  - **Medium** (manages ML-adjacent areas): keep B7 as written.
  - **Low** (manages multiple research areas, no ML): expand B7 by
    ~30 s with one-line context — "ESM-1b is a protein language model:
    same architecture as the LMs that run ChatGPT, trained on amino
    acids instead of words." Land the analogy before the formula.

If the morning checks pass, you are green. The demo is now muscle
memory; the runbook below is for your nerves, not your reasoning.

### Per-beat budget at a glance

If you're behind on time at any beat, drop B13 first; it's the swing
item. B18 is the rhetorical mic-drop and stays even if B13 goes.

| Beat | Window | Budget | Drop priority |
|---|---|---|---|
| B6 | 0:00–1:00 | 1 min | keep |
| B7 | 1:00–2:00 | 1 min | keep (compress per boss-depth) |
| B8 + B9 | 2:00–5:00 | 3 min | keep (★) |
| B10 | 5:00–7:00 | 2 min | keep |
| B12 | 7:00–8:00 | 1 min | keep |
| B18 | 8:00–10:00 | 2 min | keep (★) |
| B13 | 10:00–12:00 | 2 min | **drop first if behind** |
| Close | 11:30–12:00 | 30 s if B13 ran; 2 min if B13 dropped | keep |

If you're behind at the end of B10, drop B13 — that buys back 2 min
and slides B18 forward into the slot. If you're behind at the end of
B18 too, close at "the harness made each of those one CLI flag away
from the last" and don't try to recover B13 in the closing minute.

---

## The 12-minute arc

The demo has one rhetorical arc: **prompt → number → harness → swap.**
Everything else is connective tissue. If the boss only remembers one
thing, it should be that the same prompt produced two different
predictions when the only thing that changed was the gene name.

### B6 — Where the agent enters (0:00–1:00)

**On screen:** slide 2.4. (If still title-only, switch to VS Code with
`CLAUDE.md`.)

**Say (paraphrase, not script):**

> "The whole demo today is one prompt. Watch — *score the top 200 BRCA1
> ClinVar missense variants with ESM-1b, plot a UMAP, log to wandb*.
> That's it. The agent reads the harness, picks the right command, and
> runs it. The harness is what makes this prompt resolve to two
> commands instead of two hours of figuring out a bioinformatics CLI."

**Pause:** 1 beat after "two hours." Let the framing land.

**Hand off:** "Here's what those two commands look like." Switch to the
terminal.

---

### B7 — ESM-1b LLR mechanic (1:00–2:00)

**On screen:** slide 2.5.

**Say:**

> "ESM-1b is the workhorse. We pull two log-probabilities out of it: how
> confident the model is in the wild-type residue at position p, and how
> confident it is in the mutant residue at the same position. The
> difference is the score. Bigger difference, more disruption."

**Pause:** none — keep moving. The boss doesn't need to derive the
formula; they need to know the score is real.

**Hand off:** "Let's run it on one variant."

---

### B8 — Variant pair chosen (2:00–2:30)

**On screen:** slide 2.6 with the locked pair.

**Say:**

> "I picked one pathogenic and one benign — both real BRCA1 ClinVar
> entries, picked reproducibly from the bundled clinvar TSV. Pathogenic
> BRCA1 L1854P vs benign BRCA1 P1859R. Same
> gene, different clinical labels. If the score works, the pathogenic
> should land higher."

**Pause:** none.

**Hand off:** "Let's see what we get." Switch to terminal.

---

### B9 — LIVE: prototype scores one pair (2:30–5:00) ★

**On screen:** terminal at repo root.

**Say (before pasting):**

> "Two-and-a-half lines, all imports from the published package.
> `manylatents.dogma.vep` — that's where the variant-effect API lives
> after this week's release."

**Run:** the B9 command from `FRIDAY_CODEALONG.md`.

**Wait:** ~10 s for the four forward passes. The boss sees nothing
during this; fill with one sentence:

> "Each call is one ESM-1b forward pass. We do four — wild-type and
> mutant for each variant."

**On output landing:**

> "Pathogenic delta is <X.XXX>, LLR is <+X.XXX>. Benign delta is
> <X.XXX>, LLR is <+X.XXX>. The ranking goes the way the slide said it
> would."

**Pause:** 2 beats. Let the numbers settle.

**Hand off:** "Two variants is a vibe. Five hundred is evidence."

**If the live run fails:** stay calm, say "looks like the network's
flaky — here's what it produced this morning," and read the fallback
text. Move on.

---

### B10 — Validation visible (5:00–7:00)

**On screen:** Jupyter Lab, scroll to cell 17. Run cells 17, 18, 20.

**Say (during cell 17 — instant if the cache hits):**

> "Five hundred ClinVar variants across 400 disease genes —
> label-balanced, 250 pathogenic and 250 benign. Same harness as the
> BRCA1 prototype; the prototype was one pair, this is cross-gene
> generalization. Brandes-matching label scope — we include
> Conflicting entries the way the literature does. Canonical isoforms
> validated. The cache is what's loading right now — the live run is
> about ten minutes on a free Colab T4, which is what attendees will
> see; for the boss demo we're fast-forwarding past that."

**On AUROC table (cell 18):**

> "Delta L2 norm gets us to 0.67 AUROC. LLR climbs to 0.925. Both
> with bootstrap CIs in the cache manifest."

**On ROC plot (cell 20):**

> "Both well above chance. The 0.925 LLR sits within 0.02 of Brandes
> 2023's 0.905 on n=36,537 — for our 500-variant slice, that's inside
> the standard error. Same harness reproduces the literature number at
> 1/73 the data."

**Pause:** 1 beat.

**Hand off:** "What's holding this together is the harness. Let me show
you the layers."

---

### B12 — The harness integrates (7:00–8:00)

**On screen:** slide 2.10 with the stack diagram. (Optional split-screen:
VS Code on the right showing `CLAUDE.md`.)

**Say:**

> "Five layers. Top to bottom:
> One — `CLAUDE.md`. Twelve thousand bytes that tell an agent what to do.
> Two — Hydra experiment configs. Configs as prompts. Each YAML is a
> structured form of a question.
> Three — `manylatents-omics`. Released this week. Encoders, dataset
> modules, the `vep` API I just used.
> Four — submitit launcher. The same config dispatches to a cluster.
> Five — wandb. Provenance for every number on the slides."

**Pause:** 1 beat.

**Hand off:** "Now watch what happens when I change one parameter."

---

### B18 — LIVE: tunable gene demo (8:00–10:00) ★

**On screen:** terminal.

**Say (before pasting):**

> "Same prompt as the BRCA1 run. One thing changes: I tell the harness
> the gene is TP53. The data layer swaps; the rest of the pipeline
> doesn't know."

**Run:** the B18 encode command from `FRIDAY_CODEALONG.md`. Wait ~15 s.

**During the wait:**

> "TP53 is shorter than BRCA1, so this is faster. The pre-bundle covers
> five tumor suppressors — BRCA1, BRCA2, TP53, PTEN, MLH1 — so we never
> hit NCBI during the demo."

**On wandb URL appearing:**

> "There's the run. Let me get the UMAP."

**Run:** the chained `00_demo_umap.py` command. Wait ~5 s.

**On figure path appearing:**

> "Here's the UMAP for TP53 missense — pathogenic in red, benign in
> teal. Same harness, same plotting code, completely different gene."

**Open the wandb run** in the browser tab. Show the run with TP53 tags
sitting next to the BRCA1 runs in the project.

**Pause:** 3 beats. **This is the rhetorical mic-drop.** Don't talk
over it.

**If the audience picks an unbundled gene:** redirect with one line —
"We pre-bundled five genes for the demo to avoid hitting NCBI live —
pick BRCA1, BRCA2, TP53, PTEN, or MLH1." Boss will understand.

---

### B13 — LIVE: cluster invocation (10:00–12:00, *optional / first to drop*)

**Skip this beat unless Phase-2 was validated earlier in the week.** If
B13 is unstable, your demo is already complete at B18 and you have
buffer to spare.

**On screen:** Mila login terminal.

**Say:**

> "Same prompt one more time. This time the harness dispatches to a
> Mila GPU instead of running locally. Watch the experiment name."

**Run:** the B13 dispatch command.

**On submitit confirmation:**

> "Job <id> queued. The encode runs on the cluster; the post-step still
> runs locally once the embeddings land. The boundary between local and
> cluster is one config override."

**Pause:** 2 beats.

**If B13 is fragile:** "Here's last week's Mila dispatch — same command,
same wandb URL pattern." Show the screenshot. Move on.

---

### Close (11:30–12:00 if B13 ran; 10:00–12:00 if B13 dropped)

**On screen:** back to slide 2.10 (the stack diagram) or close the deck.

**Say:**

> "One prompt, one number, then five hundred numbers, then the same
> prompt against a different gene, and the same prompt against the
> cluster. The harness made each of those one CLI flag away from the
> last. That's the bet."

**Pause.** Don't over-explain. Take questions.

---

## Recovery scripts (read these the night before, not on Friday)

**If B9 fails:** announce briefly ("network blip"), paste the fallback
text, move on. Do not retry live — the time budget can't afford it.

**If B10 cache is missing or cell errors:** open the pre-rendered ROC
PNG and read the AUROC numbers off the figure. Frame it as "here's last
night's run, reproduced this morning."

**If B18 fails on the audience-picked gene:** swap to TP53 (the most
robustly pre-bundled non-BRCA1 gene); reframe as "TP53 is what I
pre-staged — the bundling pattern extends to any gene with a UniProt
accession."

**If B13 fails:** drop B13 entirely, do not retry. The demo is complete
at B18.

**If everything fails:** the slide deck still tells the story. Walk
through `WORKSHOP_BEATS.md` slide-by-slide as a narrative. Say "the
live demo isn't cooperating today; let me walk you through what it
shows when it works." This is not the outcome you want, but it's not
the outcome you fear either.

---

## After the demo

- [ ] Note the boss's reaction beat-by-beat in a private file. The B9
      and B18 reactions are the data points worth keeping.
- [ ] Triage anything the boss said is missing. That feedback shifts
      the 🟡 TALK tier between Friday and 2026-05-23.
- [ ] Wipe demo runs from wandb if you want to keep the project log
      clean (see `FRIDAY_CODEALONG.md` post-demo cleanup).
- [ ] Update `WORKSHOP_BEATS.md` with confidence shifts for any beat
      that didn't land cleanly.
