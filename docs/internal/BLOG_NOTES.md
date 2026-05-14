# Blog post fodder — "Why ManyLatents?" (or whatever you call it)

**Window:** the rationale fades fast. Capture today; write before June 1.
Friday's work is the post's spine — once the demo lands, the lessons
crystallize and then evaporate.

This doc is a scratchpad of moments worth narrating. None of this is
final copy. You write the post; the agent collected the receipts.

---

## Candidate spine: "Three seams a harness has to hide"

Three concrete moments from the last 72 hours where the harness paid
down a tax — each is a worked example, each ties back to a slide claim.

### Seam 1 — Two paths, one API surface

**The mismatch.** The workshop notebook (Path A) used a bespoke HF-
transformers `ESM1bEncoder` in `vep_utils.py`. The canonical Hydra
harness (Path B/C) used `manylatents.dogma.encoders.ESMEncoder` on
fair-esm. Same model weights, different tokenizers, different invocation
shapes. The slide that said "two paths merged" was half true.

**The fix (2.11 collapse).** ~20 lines on the encoder (`encode_with_logits`
+ `tok_id`), ~370 lines of pure-Python helpers ported from `vep_utils.py`
into a new `manylatents.dogma.vep`. Both paths now import from the same
module. The notebook becomes a deprecation shim.

**The lesson.** Library-vs-notebook drift is the most common "two paths"
failure in research-engineering. The instinct is to keep them separate
because "the notebook is for teaching, the library is for production."
But the library *is* the teaching surface once an attendee tries to fork
the work. Merging early saves the post-talk fork loop.

### Seam 2 — The data layer lies if you don't ask

**The mismatch.** The slides anchor on BRCA1 ("score the top 200 ClinVar
BRCA1 missense"). The workshop's validation CSV (S3, n=500) had **one**
BRCA1 entry — pathogenic, 1863 aa, filtered out by the notebook's
≤1024-aa length cap. The picker that selects the demo pair fell through
to CDIN1 + STXBP1, silently. The slide said BRCA1; the demo would have
shown two completely different genes.

**The fix.** Point the picker at `experiments/data/clinvar/variants.tsv`
(the same data the canonical harness consumes) and drop the length
filter (truncation handled at encode time). Same-gene BRCA1 pair
restored; B18's "now watch TP53" contrast survives.

**The lesson.** When the slide's claim and the data's reality
silently diverge, an audit catches it only if it's looking. **Parse-
and-cite isn't decoration** — the JSON sidecar (`demo_pair.json` with
the TSV SHA) makes the silent fall-through audible. The agent flagged
this in 20 lines of probe output; without the audit lens, the boss demo
would have shown a wrong gene.

### Seam 3 — The BOS-offset gotcha

**The mismatch.** ESM-1b's tokenizer prepends a BOS token at index 0.
A naive LLR implementation that reads `logits[mutation.position]` is
off by one if you forgot the BOS shift.

**The fix.** `compute_llr` reads `logits[mutation.position]` directly
(1-indexed sequence position maps to 1-indexed token index after BOS).
Two regression tests in `test_vep_utils.py`:
`test_compute_llr_uses_correct_bos_offset` — sets index 0 to garbage,
controls index 1, asserts `LLR ≈ 0`. Catches the off-by-one if anyone
"fixes" the indexing.

**The lesson.** Most VEP-on-pLM tutorials hand-wave the BOS offset.
Almost every research-grade implementation gets it wrong at some
point. The regression test is the harness's grip on it; without the
test, the code "looks right" because the LLR is finite and has a
plausible sign.

---

## Smaller moments worth a paragraph each

- **The wandb-auth gotcha.** Demo machine had `api_key: null`; default
  config baked the maintainer's entity. Would have died silently on a
  fresh login. `WANDB_MODE=offline` is the safety net; the README
  callout is the parse-and-cite for "what defaults can hurt."
- **PTEN benign sparsity (n=6).** Pre-bundled 5 genes for B18 ("audience
  picks the gene"). PTEN's clinical-significance distribution is
  pathology-heavy: 234 P / 6 B / 760 VUS. Visible contrast in a UMAP
  needs benign mass. The bundle work surfaced this; the runbook now
  steers the audience away from PTEN. Worth a sentence on "the gene
  list isn't the data."
- **The notebook's first-load problem.** Cell 8 (start of S2) was
  loading ESM-1b — that's a 60 s wait the audience sees. Move the load
  to S1 and the slide can honestly claim "<30 s after warm-up." Costs
  one line of code, recovers a slide.
- **Picker as parse-and-cite, applied to itself.** `pick_demo_pair.py
  --write-spec` rewrites the Friday spec with the picked IDs, plus
  writes a JSON sidecar with the TSV SHA. The spec is now a
  reproducible artifact: future-you opens the file, sees the IDs, runs
  the picker, gets the same IDs (or a clean diff if data changed).

---

## Hooks / opening lines (try, throw out, replace)

- *"The most common bug in agentic biology isn't the model. It's the
  silent fall-through three layers deep, in a file no one's looking at."*
- *"I built a harness to let an agent run a variant-effect prediction
  pipeline. The agent ran it correctly. The data was wrong, and the
  agent had no way to know."*
- *"BRCA1 is 1 863 amino acids long. ESM-1b's context is 1 024. That
  detail almost killed a demo."*

Pick one. None of these are slogans — they're spines.

---

## Audience priors

- **ML engineers** want to know what made the agent productive (the
  harness, not the model).
- **Biologists** want to know whether the variant-effect numbers are
  defensible (AUROC 0.61–0.64 on raw ESM-1b is honest, not impressive).
- **PMs / leadership** want the productivity claim: how long does
  research take with the harness vs without? Don't have a number; do
  have a story ("yesterday I shipped a demo that traces a number from
  slide to commit").

Three different paragraphs, same body of evidence.

---

## What NOT to put in the post

- The audit, the BEATS doc, the spec, the runbook. Those are
  scaffolding. Mentioning them turns the post into process content
  instead of insight content.
- The internal commits and pin bumps. Same reason.
- The slide deck contents. Link to the recording when it lands.

---

## When this is ready to write

When the Friday demo lands cleanly. The Friday recording becomes the
post's hero asset; the post explains what the recording shows. Trying
to write earlier produces process content; trying to write later loses
the rationale.

**Hard deadline:** June 1 — by then the urgency fades and the post
becomes work instead of opportunity.
