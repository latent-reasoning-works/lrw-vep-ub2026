#!/usr/bin/env python3
"""validate_paper.py — end-to-end smoke test for the agent-driven paper-prep pipeline.

Two phases:

  python validate_paper.py --prepare
      Wipe + recreate _paper_validation_tmp/, copy in the NeurIPS .sty, emit
      PROMPT.md. Then, from a Claude Code session, spawn a subagent with the
      prompt — the subagent writes main.tex + references.bib into the workdir
      and tries to build it.

  python validate_paper.py [--fetch-tectonic]
      Validate what the agent produced: TeX structure, DOI citation, figure
      include, headline-AUROC mention, and the PDF page count. If main.pdf
      is missing, the validator builds it itself using tectonic (from PATH,
      a local cache at ~/.cache/lrw-vep-ub2026/tectonic/, or — with
      --fetch-tectonic — auto-downloaded from GitHub releases on first use).

Per-check PASS/FAIL. Non-zero exit on any FAIL.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
import zlib
from pathlib import Path

NB_DIR = Path(__file__).resolve().parent
REPO_ROOT = NB_DIR.parent.parent
WORKDIR = NB_DIR / "_paper_validation_tmp"
PROMPT_PATH = WORKDIR / "PROMPT.md"

PAPER_DIR = REPO_ROOT / "paper"
NEURIPS_STY = PAPER_DIR / "neurips_2024.sty"
MANIFEST_PATH = NB_DIR / "data" / "workshop_set_manifest.json"
FIGURE_REL = "experiments/analysis/figures/llr_distribution_500.pdf"
FIGURE_STEM = "llr_distribution_500"

BRANDES_DOI = "10.1038/s41588-023-01465-0"
BRANDES_TITLE_FRAGMENT = "Genome-wide prediction of disease variant"
TARGET_PAGES = 2
PAGE_TOLERANCE = 1  # accept 1–3 pages

TECTONIC_VERSION = "0.15.0"
TECTONIC_CACHE = Path.home() / ".cache" / "lrw-vep-ub2026" / "tectonic"


def _load_auroc() -> tuple[float, float, float]:
    m = json.loads(MANIFEST_PATH.read_text())
    metrics = m["evaluation"]["metrics"]
    auroc = float(metrics["llr_auroc"])
    lo, hi = (float(x) for x in metrics["llr_auroc_ci95_bootstrap"])
    return auroc, lo, hi


def _author_name() -> str:
    try:
        return subprocess.check_output(
            ["git", "config", "user.name"], cwd=REPO_ROOT, text=True
        ).strip() or "Anonymous Author"
    except subprocess.CalledProcessError:
        return "Anonymous Author"


def _build_prompt() -> str:
    auroc, lo, hi = _load_auroc()
    author = _author_name()
    fig_abs = REPO_ROOT / FIGURE_REL
    return f"""# Paper smoke-test prompt

You are producing a 2-page LaTeX preprint that smoke-tests the workshop's
paper-prep pipeline. The output goes in `{WORKDIR}` (already prepared with the
NeurIPS .sty copied in).

## What to write

1. `{WORKDIR}/main.tex` — a NeurIPS-preprint-styled 2-pager:
   - `\\documentclass{{article}}` + `\\usepackage[preprint]{{neurips_2024}}` (the
     `.sty` is already in this directory; do not edit it).
   - Title: something descriptive of "agent-driven VEP with ESM-1b on
     ClinVar"; single author `{author}`.
   - **Abstract** (2–3 sentences): the task + the headline number.
   - **§Introduction** (1 short paragraph): why VEP, why ESM-1b, what an
     agent-driven harness buys you over hand-rolled pipelines.
   - **§Method** (1 paragraph): describe the LLR scoring (log P(mut|WT) −
     log P(wt|WT) under a single masked-LM forward pass). **Cite
     Brandes et al. 2023 via `\\citep{{brandes2023}}`** as the methodology
     anchor. The bib entry's `doi` field must be `{BRANDES_DOI}`.
   - **§Results** (1 paragraph + 1 figure): report AUROC = {auroc:.4f}
     (95 % CI [{lo:.4f}, {hi:.4f}]) on the 500-variant ClinVar workshop set.
     Include the figure with
     `\\includegraphics[width=\\linewidth]{{{FIGURE_STEM}}}` and a
     one-sentence caption — the figure shows the LLR KDE for pathogenic
     vs benign across all 500 variants, so the AUROC literally is what
     the reader sees. The PDF lives at `{fig_abs}` — copy it into
     `{WORKDIR}/` so the `\\includegraphics` resolves locally.
   - `\\bibliographystyle{{plainnat}}` + `\\bibliography{{references}}`.

2. `{WORKDIR}/references.bib` — at minimum the Brandes entry. Use cite-key
   `brandes2023`. Required fields: `title`, `author`, `journal`, `year`,
   `volume`, `pages`, `doi = {{{BRANDES_DOI}}}`. Title should contain the
   substring "{BRANDES_TITLE_FRAGMENT}".

3. Build the PDF. Run **from `{WORKDIR}`**:
   - Prefer `tectonic main.tex` if installed.
   - Otherwise: `pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex`.
   - Target: 2 pages. If you overshoot, tighten prose — do not shrink the
     figure to game it.

## Constraints

- Do not touch `{REPO_ROOT}/paper/` — that is the real paper, untouched by
  this smoke test.
- No new LaTeX packages beyond what `neurips_2024.sty` pulls in plus
  `graphicx`, `hyperref`, and `amsmath` (the last is needed if you write
  the LLR equation with `\text{...}` or any other `amsmath`-only macro).
- If `tectonic` and `pdflatex` are both missing, write the `.tex` + `.bib`
  anyway and report the missing builder — the validator's source checks
  will still pass.

Report at the end: the cite-key you used, the final page count, and the
path to the PDF.
"""


def _tectonic_url() -> str | None:
    sys_name = platform.system()
    arch = platform.machine()
    if sys_name == "Darwin":
        suffix = (
            "aarch64-apple-darwin" if arch in ("arm64", "aarch64")
            else "x86_64-apple-darwin"
        )
        ext = "tar.gz"
    elif sys_name == "Linux":
        arch_part = "aarch64" if arch in ("aarch64", "arm64") else "x86_64"
        suffix = f"{arch_part}-unknown-linux-gnu"
        ext = "tar.gz"
    elif sys_name == "Windows":
        suffix = "x86_64-pc-windows-msvc"
        ext = "zip"
    else:
        return None
    return (
        f"https://github.com/tectonic-typesetting/tectonic/releases/"
        f"download/tectonic%40{TECTONIC_VERSION}/"
        f"tectonic-{TECTONIC_VERSION}-{suffix}.{ext}"
    )


def _ensure_tectonic(allow_fetch: bool) -> tuple[Path | None, str | None]:
    """Return (tectonic path, reason-for-none).

    Looks on PATH, then in TECTONIC_CACHE, then optionally downloads.
    """
    if (p := shutil.which("tectonic")):
        return Path(p), None
    bin_name = "tectonic.exe" if platform.system() == "Windows" else "tectonic"
    cached = TECTONIC_CACHE / bin_name
    if cached.exists() and os.access(cached, os.X_OK):
        return cached, None
    url = _tectonic_url()
    if url is None:
        return None, f"unsupported platform ({platform.system()}/{platform.machine()})"
    if not allow_fetch:
        return None, (
            f"not on PATH or in cache; re-run with --fetch-tectonic to download "
            f"(~50 MB) from {url}"
        )
    print(f"  fetching tectonic {TECTONIC_VERSION} from {url}")
    TECTONIC_CACHE.mkdir(parents=True, exist_ok=True)
    archive = TECTONIC_CACHE / Path(url).name
    try:
        urllib.request.urlretrieve(url, archive)
    except Exception as e:
        return None, f"download failed: {e}"
    try:
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                z.extractall(TECTONIC_CACHE)
        else:
            with tarfile.open(archive) as t:
                t.extractall(TECTONIC_CACHE)
    except Exception as e:
        return None, f"extract failed: {e}"
    archive.unlink(missing_ok=True)
    if not cached.exists():
        return None, f"binary not found after extract at {cached}"
    cached.chmod(0o755)
    print(f"  cached at {cached}")
    return cached, None


def _build_pdf(tectonic: Path, workdir: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [str(tectonic), "main.tex"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return False, "tectonic build timed out after 180s"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout)[-600:]
        return False, f"tectonic exit {proc.returncode}; tail:\n{tail}"
    return True, "ok"


def _section(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


class CheckResult:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.passes: list[str] = []
        self.warns: list[str] = []

    def passed(self, msg: str) -> None:
        self.passes.append(msg)
        print(f"  PASS  {msg}")

    def failed(self, msg: str) -> None:
        self.fails.append(msg)
        print(f"  FAIL  {msg}")

    def warned(self, msg: str) -> None:
        self.warns.append(msg)
        print(f"  WARN  {msg}")


def cmd_prepare() -> int:
    _section("Prepare workdir")
    if WORKDIR.exists():
        shutil.rmtree(WORKDIR)
        print(f"  removed stale {WORKDIR}")
    WORKDIR.mkdir(parents=True)
    print(f"  created {WORKDIR}")

    if not NEURIPS_STY.exists():
        print(f"  FAIL  cannot find {NEURIPS_STY}", file=sys.stderr)
        return 1
    shutil.copy(NEURIPS_STY, WORKDIR / NEURIPS_STY.name)
    print(f"  copied {NEURIPS_STY.name}")

    if not MANIFEST_PATH.exists():
        print(f"  FAIL  cannot find {MANIFEST_PATH}", file=sys.stderr)
        return 1

    PROMPT_PATH.write_text(_build_prompt())
    print(f"  wrote {PROMPT_PATH}")

    print()
    print("Next: from your Claude Code session, spawn a subagent with the prompt.")
    print("Then re-run this script without --prepare to validate.")
    return 0


def _check_files(res: CheckResult) -> tuple[Path, Path] | None:
    _section("Stage 1: required files")
    tex = WORKDIR / "main.tex"
    bib = WORKDIR / "references.bib"
    if tex.exists():
        res.passed(f"main.tex present ({tex.stat().st_size} bytes)")
    else:
        res.failed("main.tex missing")
    if bib.exists():
        res.passed(f"references.bib present ({bib.stat().st_size} bytes)")
    else:
        res.failed("references.bib missing")
    if not (tex.exists() and bib.exists()):
        return None
    return tex, bib


def _check_tex_structure(res: CheckResult, tex: Path) -> None:
    _section("Stage 2: main.tex structure")
    src = tex.read_text()
    required = [
        ("\\documentclass", "documentclass declaration"),
        ("neurips_2024", "neurips_2024 package use"),
        ("\\begin{document}", "begin document"),
        ("\\title", "title macro"),
        ("\\section{Introduction}", "Introduction section"),
        ("\\section{Method}", "Method section"),
        ("\\section{Results}", "Results section"),
        ("\\includegraphics", "figure inclusion"),
        ("\\bibliography{", "bibliography reference"),
    ]
    for pat, label in required:
        if pat in src:
            res.passed(label)
        else:
            res.failed(f"missing {label} ({pat!r})")
    cite = re.search(r"\\cite[a-z]*\{([^}]+)\}", src)
    if cite:
        keys = [k.strip() for k in cite.group(1).split(",")]
        res.passed(f"found \\cite with key(s): {keys}")
    else:
        res.failed("no \\cite{...} command found in main.tex")


def _check_bib(res: CheckResult, bib: Path) -> None:
    _section("Stage 3: references.bib content")
    src = bib.read_text()
    if BRANDES_DOI in src:
        res.passed(f"Brandes DOI present ({BRANDES_DOI})")
    else:
        res.failed(f"Brandes DOI ({BRANDES_DOI}) not found in references.bib")
    if BRANDES_TITLE_FRAGMENT.lower() in src.lower():
        res.passed("Brandes title fragment present")
    else:
        res.warned(
            f"Brandes title fragment ({BRANDES_TITLE_FRAGMENT!r}) not exactly matched"
        )
    if re.search(r"@\w+\s*\{", src):
        res.passed("at least one bibtex entry detected")
    else:
        res.failed("no bibtex entry detected in references.bib")


def _check_cite_consistency(res: CheckResult, tex: Path, bib: Path) -> None:
    _section("Stage 4: cite-key resolves")
    cited = set(
        k.strip()
        for m in re.finditer(r"\\cite[a-z]*\{([^}]+)\}", tex.read_text())
        for k in m.group(1).split(",")
    )
    defined = set(
        m.group(1) for m in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib.read_text())
    )
    if cited and cited.issubset(defined):
        res.passed(f"all cite-keys resolve in bib: {sorted(cited)}")
    elif cited:
        res.failed(
            f"cite-keys not in bib: {sorted(cited - defined)} "
            f"(defined: {sorted(defined)})"
        )
    else:
        res.failed("no cite-keys to check (Stage 2 should already have flagged this)")


def _check_headline(res: CheckResult, tex: Path) -> None:
    _section("Stage 5: headline AUROC mention")
    auroc, _, _ = _load_auroc()
    src = tex.read_text()
    candidates = [f"{auroc:.4f}", f"{auroc:.3f}", f"{auroc:.2f}", "0.93"]
    if any(c in src for c in candidates):
        res.passed(f"AUROC mention found (looked for {candidates})")
    else:
        res.failed(f"no AUROC mention; expected one of {candidates}")


def _check_build(res: CheckResult, allow_fetch: bool) -> None:
    _section("Stage 6: PDF build")
    pdf = WORKDIR / "main.pdf"
    if not pdf.exists():
        tectonic, reason = _ensure_tectonic(allow_fetch=allow_fetch)
        if tectonic is None:
            res.warned(
                f"main.pdf missing and tectonic unavailable: {reason} — "
                "source-level checks still validate"
            )
            return
        print(f"  building with {tectonic}")
        ok, msg = _build_pdf(tectonic, WORKDIR)
        if not ok:
            res.failed(f"build failed: {msg}")
            return
        res.passed(f"built main.pdf with {tectonic.name}")
    else:
        res.passed(f"main.pdf present ({pdf.stat().st_size} bytes)")
    pages = _pdf_page_count(pdf)
    if pages is None:
        res.warned("could not determine page count from PDF structure")
        return
    lo, hi = TARGET_PAGES - PAGE_TOLERANCE, TARGET_PAGES + PAGE_TOLERANCE
    if lo <= pages <= hi:
        res.passed(f"page count = {pages} (target {TARGET_PAGES}±{PAGE_TOLERANCE})")
    else:
        res.failed(f"page count = {pages} (target {TARGET_PAGES}±{PAGE_TOLERANCE})")


def _pdf_page_count(pdf: Path) -> int | None:
    # Pure-Python parse: the catalog's /Pages dict has /Type /Pages /Count N.
    # In modern (PDF 1.5+) outputs from tectonic the catalog lives inside a
    # compressed object stream, so we decompress every Flate stream first.
    try:
        data = pdf.read_bytes()
    except OSError:
        return None
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.DOTALL):
        try:
            decompressed = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        for t in re.finditer(rb"/Type\s*/Pages\b", decompressed):
            cm = re.search(rb"/Count\s+(\d+)", decompressed[t.start():t.start() + 300])
            if cm:
                return int(cm.group(1))
    # Fallback for uncompressed PDFs (older producers).
    for t in re.finditer(rb"/Type\s*/Pages\b", data):
        cm = re.search(rb"/Count\s+(\d+)", data[t.start():t.start() + 300])
        if cm:
            return int(cm.group(1))
    return None


def cmd_check(allow_fetch: bool) -> int:
    if not WORKDIR.exists():
        print(f"FAIL  workdir missing: {WORKDIR}")
        print("Run `python validate_paper.py --prepare` first.")
        return 2
    res = CheckResult()
    files = _check_files(res)
    if files is not None:
        tex, bib = files
        _check_tex_structure(res, tex)
        _check_bib(res, bib)
        _check_cite_consistency(res, tex, bib)
        _check_headline(res, tex)
        _check_build(res, allow_fetch=allow_fetch)

    _section("Summary")
    print(f"  {len(res.passes)} PASS, {len(res.fails)} FAIL, {len(res.warns)} WARN")
    if res.fails:
        print("\nFails:")
        for f in res.fails:
            print(f"  - {f}")
        return 1
    print("\nAll required checks passed.")
    if res.warns:
        print("Warnings (non-blocking):")
        for w in res.warns:
            print(f"  - {w}")
    return 0


REAL_PAPER_TEX = REPO_ROOT / "paper" / "main.tex"


def cmd_real_paper(allow_fetch: bool) -> int:
    """Build the real paper/main.tex (not the smoke-test paper).

    Structural compile only — no content assertions. Catches breakage when
    an Overleaf coauthor lands a bad \\cite, a missing figure path, etc.
    Placeholder `% TODO(agent)` sections are expected.
    """
    _section("Real paper build: paper/main.tex")
    if not REAL_PAPER_TEX.exists():
        print(f"  FAIL  missing: {REAL_PAPER_TEX}")
        return 1
    tectonic, reason = _ensure_tectonic(allow_fetch=allow_fetch)
    if tectonic is None:
        print(f"  FAIL  tectonic unavailable: {reason}")
        return 1
    print(f"  building with {tectonic}")
    ok, msg = _build_pdf(tectonic, REAL_PAPER_TEX.parent)
    if not ok:
        print(f"  FAIL  {msg}")
        return 1
    pdf = REAL_PAPER_TEX.parent / "main.pdf"
    if not pdf.exists():
        print(f"  FAIL  build returned 0 but no main.pdf at {pdf}")
        return 1
    pages = _pdf_page_count(pdf)
    print(f"  PASS  paper/main.pdf built ({pdf.stat().st_size} bytes, {pages or '?'} pages)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--prepare",
        action="store_true",
        help="wipe + recreate the workdir and emit PROMPT.md, then exit",
    )
    p.add_argument(
        "--fetch-tectonic",
        action="store_true",
        help=(
            "if tectonic is not on PATH or in the local cache, download the "
            f"{TECTONIC_VERSION} binary (~50 MB) to {TECTONIC_CACHE} and use it "
            "to build the PDF"
        ),
    )
    p.add_argument(
        "--real-paper",
        action="store_true",
        help=(
            "build the real paper/main.tex (structural compile only — TODO "
            "placeholders are expected). Catches Overleaf-coauthor breakage."
        ),
    )
    args = p.parse_args()
    if args.prepare:
        return cmd_prepare()
    if args.real_paper:
        return cmd_real_paper(allow_fetch=args.fetch_tectonic)
    return cmd_check(allow_fetch=args.fetch_tectonic)


if __name__ == "__main__":
    sys.exit(main())
