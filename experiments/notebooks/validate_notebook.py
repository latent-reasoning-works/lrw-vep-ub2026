#!/usr/bin/env python3
"""validate_notebook.py — execute 01_workshop_followalong.ipynb end-to-end.

The third validator in the trinity:
  - `validate.py`         — harness logic reproduces canonical numbers
  - `validate_paper.py`   — agent prompt → 2-page paper
  - `validate_notebook.py`— literal notebook cells all run without error

Catches a different class of bugs from `validate.py`: typo in a code
cell, broken import, non-interactive matplotlib glitch, stale variable
reference between cells. Numbers come from `validate.py`; this is the
"cells don't explode" smoke test.

Usage:
  python validate_notebook.py [--timeout SECS]

Exits 0 on PASS, non-zero on FAIL. Wall clock ~30-90s when the
`s3-score-loop` cache short-circuit fires (the common case); up to
~4 min if the cache is stale and the loop re-encodes.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

import nbformat
from nbconvert.preprocessors import CellExecutionError, ExecutePreprocessor

NB_DIR = Path(__file__).resolve().parent
NB_PATH = NB_DIR / "01_workshop_followalong.ipynb"
FIG_DIR = NB_DIR.parent / "analysis" / "figures"


def _cell_errored(cell) -> bool:
    return any(o.get("output_type") == "error" for o in cell.get("outputs", []))


def _save_cell_figures(nb, fig_dir: Path) -> list[Path]:
    """Walk the executed notebook; dump every cell's image/png output to disk.

    Returns the list of paths written. Cells that produce multiple images get
    suffixes _0, _1, etc. Cell ids with no figures are skipped silently.
    """
    fig_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for c in nb.cells:
        if c.cell_type != "code":
            continue
        cell_id = c.get("id", "noid")
        imgs: list[bytes] = []
        for o in c.get("outputs", []):
            data = o.get("data", {})
            png_b64 = data.get("image/png")
            if png_b64:
                imgs.append(base64.b64decode(png_b64))
        for i, raw in enumerate(imgs):
            suffix = "" if len(imgs) == 1 else f"_{i}"
            out = fig_dir / f"notebook_{cell_id}{suffix}.png"
            out.write_bytes(raw)
            saved.append(out)
    return saved


def main(timeout: int = 600, save_figures: bool = False) -> int:
    if not NB_PATH.exists():
        print(f"FAIL  notebook not found: {NB_PATH}")
        return 2

    print(f"Executing {NB_PATH.name}")
    print(f"  cwd:     {NB_DIR}")
    print(f"  timeout: {timeout}s per cell")
    print()

    t0 = time.time()
    nb = nbformat.read(NB_PATH, as_version=4)
    ep = ExecutePreprocessor(timeout=timeout, kernel_name="python3")

    try:
        ep.preprocess(nb, {"metadata": {"path": str(NB_DIR)}})
        cell_error = None
    except CellExecutionError as exc:
        cell_error = exc

    elapsed = time.time() - t0

    code_cells = [c for c in nb.cells if c.cell_type == "code"]
    failed = [c for c in code_cells if _cell_errored(c)]

    print("Cell-by-cell run summary")
    print("=" * 56)
    for c in code_cells:
        cell_id = c.get("id", "<no-id>")
        tag = "FAIL" if _cell_errored(c) else "PASS"
        print(f"  [{tag}] {cell_id}")

    print()
    if cell_error or failed:
        print(f"FAIL  {len(failed)}/{len(code_cells)} code cells errored ({elapsed:.1f}s)")
        for c in failed:
            err = next((o for o in c.get("outputs", []) if o.get("output_type") == "error"), None)
            if not err:
                continue
            cell_id = c.get("id", "<no-id>")
            src_head = "".join(c.source).splitlines()
            head = src_head[0] if src_head else "<empty>"
            print(f"\n  Failed cell: {cell_id}")
            print(f"  First line:  {head[:100]}")
            print(f"  Error:       {err.get('ename')}: {err.get('evalue')}")
        return 1

    print(f"PASS  {len(code_cells)}/{len(code_cells)} code cells ran clean ({elapsed:.1f}s)")

    if save_figures:
        saved = _save_cell_figures(nb, FIG_DIR)
        if saved:
            print(f"\nFallback figures saved ({len(saved)}):")
            for p in saved:
                print(f"  {p.relative_to(NB_DIR.parent.parent)}")
        else:
            print("\nNo cell output figures detected.")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--timeout", type=int, default=600,
                   help="seconds per cell (default 600 = 10 min, generous)")
    p.add_argument("--save-figures", action="store_true",
                   help=(
                       "after execution, walk the executed notebook and dump "
                       "every cell's image/png output to "
                       "experiments/analysis/figures/notebook_<cell-id>.png "
                       "(fallback bundle for workshop day)"
                   ))
    args = p.parse_args()
    sys.exit(main(timeout=args.timeout, save_figures=args.save_figures))
