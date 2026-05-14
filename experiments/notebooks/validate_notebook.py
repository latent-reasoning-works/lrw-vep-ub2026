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
import sys
import time
from pathlib import Path

import nbformat
from nbconvert.preprocessors import CellExecutionError, ExecutePreprocessor

NB_DIR = Path(__file__).resolve().parent
NB_PATH = NB_DIR / "01_workshop_followalong.ipynb"


def _cell_errored(cell) -> bool:
    return any(o.get("output_type") == "error" for o in cell.get("outputs", []))


def main(timeout: int = 600) -> int:
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
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--timeout", type=int, default=600,
                   help="seconds per cell (default 600 = 10 min, generous)")
    args = p.parse_args()
    sys.exit(main(timeout=args.timeout))
