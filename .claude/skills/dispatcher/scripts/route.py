#!/usr/bin/env python3
"""Dispatcher router. Reads a workload spec, picks a substrate, emits a plan.

Usage:
    python3 route.py --workload workload.json
    python3 route.py < workload.json    # stdin

Output: JSON plan on stdout. No side effects.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


REQUIRED_FIELDS = {"n_items", "requires_gpu", "per_item_memory_gb"}

# Bridge between dispatcher layer (substrate) and worker layer (manylatents /
# torch / your library). Dispatcher's authority ends here; the worker takes
# the device_override and routes the actual torch.device() call.
SUBSTRATE_TO_DEVICE = {
    "local_cpu": "cpu",
    "local_gpu": "cuda",
    "mps":       "mps",
    "slurm":     "cuda",  # SLURM backends in MVP are NVIDIA-GPU clusters
}

# Per-substrate worker-invocation templates. {device}, {i}, {parallel_workers}
# are substituted by the caller. Hydra-configured workers (e.g., manylatents)
# accept device=<x> as a CLI override; direct-Python workers take it as a
# kwarg. The dispatcher does not execute these — the caller does.
INVOCATION_TEMPLATES = {
    "local_cpu":
        "python -m <your.module> <args> device={device} shard={i} n_shards={parallel_workers}",
    "local_gpu":
        "CUDA_VISIBLE_DEVICES={i} python -m <your.module> <args> device={device} shard={i} n_shards={parallel_workers}",
    "mps":
        "python -m <your.module> <args> device={device} shard={i} n_shards={parallel_workers}",
    "slurm":
        "sbatch --array=0-{last_i} --gpus=1 --wrap='python -m <your.module> <args> device={device} shard=$SLURM_ARRAY_TASK_ID n_shards={parallel_workers}'",
}


def detect_substrates() -> dict:
    script = Path(__file__).parent / "detect_substrates.sh"
    return json.loads(subprocess.check_output(["bash", str(script)], text=True))


def validate(workload: dict) -> None:
    missing = REQUIRED_FIELDS - set(workload)
    if missing:
        raise SystemExit(json.dumps({
            "error": "workload spec missing required fields",
            "missing": sorted(missing),
        }))
    if workload.get("requires_gpu") and "gpu_memory_gb" not in workload:
        raise SystemExit(json.dumps({
            "error": "requires_gpu=true but gpu_memory_gb is missing",
            "fix": "per-item GPU memory is load-bearing for substrate fit; set it explicitly",
        }))


def route(workload: dict, substrates: dict) -> dict:
    n = workload["n_items"]
    needs_gpu = workload["requires_gpu"]
    per_item_ram = workload["per_item_memory_gb"]
    per_item_time = workload.get("per_item_time_s", 60)
    net = workload.get("internet_required", False)
    gpu_mem = workload.get("gpu_memory_gb", 0)

    checked = []
    if needs_gpu:
        mps = substrates.get("mps", {})
        if mps.get("available") and gpu_mem <= mps.get("ram_gb", 0):
            return _plan("mps", workload, substrates,
                         n_workers=1,  # MPS is one logical device
                         note="Apple Silicon unified memory")
        checked.append("mps")

        lg = substrates.get("local_gpu", {})
        if lg.get("available") and gpu_mem <= lg.get("memory_gb_per_gpu", 0):
            return _plan("local_gpu", workload, substrates,
                         n_workers=lg.get("n_gpus", 1),
                         note=f"{lg.get('n_gpus')}x {lg.get('device')}")
        checked.append("local_gpu")

        # SLURM fallback: prefer reachable > unverified (chained) backends.
        slurm = substrates.get("slurm", {})
        for tier in ("reachable", "unverified"):
            for backend_name in slurm.get(tier, []):
                tier_note = "verified reachable" if tier == "reachable" else "chained backend; caller validates access at dispatch time"
                return _plan("slurm", workload, substrates,
                             n_workers=n,
                             backend=backend_name,
                             note=f"SLURM backend {backend_name}; array job, one task per item ({tier_note})")
        checked.append("slurm")

        return _no_fit(workload, checked,
                       ["register a SLURM backend with sufficient gpu_memory",
                        "reduce gpu_memory_gb if the model can shard or quantize"])

    # CPU-only path
    cpu = substrates.get("local_cpu", {})
    total_ram_needed = n * per_item_ram
    if cpu.get("available") and total_ram_needed <= cpu.get("ram_gb", 0):
        return _plan("local_cpu", workload, substrates,
                     n_workers=cpu.get("cores", 1),
                     note=f"{cpu.get('cores')} cores, {cpu.get('ram_gb')}GB RAM")
    checked.append("local_cpu")

    slurm = substrates.get("slurm", {})
    for tier in ("reachable", "unverified"):
        for backend_name in slurm.get(tier, []):
            tier_note = "verified reachable" if tier == "reachable" else "chained backend; caller validates access at dispatch time"
            return _plan("slurm", workload, substrates,
                         n_workers=n,
                         backend=backend_name,
                         note=f"local RAM insufficient ({total_ram_needed}GB needed); routing to {backend_name} ({tier_note})")
    checked.append("slurm")
    return _no_fit(workload, checked,
                   ["register a SLURM backend",
                    "reduce per_item_memory_gb or n_items"])


def _resolve_access_chain(backend_name: str, substrates: dict) -> list:
    """Extract the backend's access_chain from its manifest.

    Falls back to a synthesized length-1 chain from ssh_alias (or the backend
    name itself) when access_chain is not set explicitly.
    """
    manifests = substrates.get("slurm", {}).get("manifests", {}) or {}
    m = manifests.get(backend_name, {})
    chain = m.get("access_chain")
    if chain:
        return chain
    return [{"ssh": m.get("ssh_alias") or backend_name}]


def _plan(substrate: str, workload: dict, substrates: dict, **extras) -> dict:
    # parallel_workers may be passed in extras (n_workers); default to 1.
    n_workers = extras.get("n_workers", 1)
    device = SUBSTRATE_TO_DEVICE[substrate]
    template = INVOCATION_TEMPLATES[substrate].format(
        device=device,
        i="{i}",                          # placeholder kept for the caller
        last_i=max(workload["n_items"] - 1, 0),
        parallel_workers=n_workers,
    )
    plan = {
        "substrate": substrate,
        "parallel_workers": n_workers,
        "device_override": device,
        "per_worker_invocation": template,
        "workload": workload,
        "extras": extras,
    }

    # For SLURM, include the access_chain so the caller knows how to reach
    # the backend (single SSH, ssh→salloc→ssh, etc.). For non-SLURM
    # substrates, no chain — execution happens on the current host.
    if substrate == "slurm":
        backend_name = extras.get("backend")
        if backend_name:
            plan["access_chain"] = _resolve_access_chain(backend_name, substrates)

    return plan


def _no_fit(workload: dict, checked: list, would_unblock: list) -> dict:
    return {
        "error": "no substrate fits",
        "checked": checked,
        "workload_requires": {
            k: workload[k] for k in ("requires_gpu", "gpu_memory_gb", "per_item_memory_gb", "internet_required")
            if k in workload
        },
        "would_unblock": would_unblock,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workload", type=Path, help="Path to workload JSON (else stdin)")
    args = ap.parse_args()

    if args.workload:
        workload = json.loads(args.workload.read_text())
    else:
        workload = json.load(sys.stdin)

    validate(workload)
    substrates = detect_substrates()
    plan = route(workload, substrates)
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
