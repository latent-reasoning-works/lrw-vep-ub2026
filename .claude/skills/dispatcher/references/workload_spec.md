# Workload spec

The dispatcher consumes a JSON object describing the work. The spec is
**substrate-agnostic** — it describes what each item needs, not how to
run them. The router translates the spec into a substrate + dispatch
template.

## Fields

| Field | Required when | Meaning |
|---|---|---|
| `n_items` | always | Number of independent parallel work units |
| `requires_gpu` | always | Whether items need a GPU at all |
| `gpu_memory_gb` | `requires_gpu=true` | Min GPU memory per item; drives substrate fit |
| `per_item_memory_gb` | always | Peak host RAM per item |
| `per_item_time_s` | optional (default 60) | Used to estimate wall time and pick batch size |
| `internet_required` | optional (default `false`) | If true, eliminates SLURM backends with no compute-node internet |

Missing-field rules:

- If `gpu_memory_gb` is missing when `requires_gpu=true`, the dispatcher
  **fails fast**. Per-item GPU memory is load-bearing for substrate fit;
  guessing it is worse than refusing.
- If `per_item_time_s` is missing, the router assumes 60s and flags the
  assumption in the plan.

## Don't include a `device` field

The spec is **substrate-agnostic** by design. There is no `device`
field, no `device_preference`, no `prefer_gpu_type`. The dispatcher
owns substrate selection; once a substrate is picked, the dispatcher
derives the device (`cpu` / `cuda` / `mps`) and emits it in the plan
as `device_override`.

If you want to pin a device explicitly, **call your worker library
directly** (e.g., `python -m manylatents.main device=mps ...`) and
skip the dispatcher. The dispatcher's contract is: agents describe
what they need; the dispatcher decides where it runs and what device
to use. Three layers, one concern each:

| Layer | Concern |
|---|---|
| dispatcher | substrate (which node, how parallel) + device-from-substrate |
| your library (e.g. `manylatents`) | device + module (actual torch.device handling) |
| kernel layer (future, e.g. Geomancer) | which CUDA kernel for this op on this device |

A workload spec that includes a `device` field is ignored — and if the
field name suggests the user thinks the dispatcher should negotiate it,
that's a bug in the agent's framing, not in the dispatcher. Fix the
agent's prompt to not over-specify.

## Examples

### Single-GPU sweep (16GB per item)

Score 200 protein variants through ESM-1b. Each item needs ~16GB GPU
memory, runs ~30s, no internet on compute needed.

```json
{
  "n_items": 200,
  "requires_gpu": true,
  "gpu_memory_gb": 16,
  "per_item_memory_gb": 8,
  "per_item_time_s": 30,
  "internet_required": false
}
```

Likely routes to: `mps` on Apple Silicon (if 16GB ≤ system RAM) or
`local_gpu` (if any local CUDA device has ≥16GB), otherwise the first
reachable SLURM backend.

### CPU-only parallel batch

Run 5000 short bioinformatics scripts; no GPU, each needs ~1GB RAM,
~10s each.

```json
{
  "n_items": 5000,
  "requires_gpu": false,
  "per_item_memory_gb": 1,
  "per_item_time_s": 10
}
```

Likely routes to: `local_cpu` (RAM budget: `5000 × 1 = 5000GB` — way too
much in aggregate, but the router checks against `cores × per_item_ram`
once batched, not naively `n_items × per_item_ram`. If you have 12 cores
and 32GB RAM, the batch fits — 12 in flight at a time, each holding 1GB).
Falls back to SLURM if local RAM truly cannot host one batch.

### Large GPU workload (80GB)

Fine-tune a 70B model that needs 80GB of GPU memory.

```json
{
  "n_items": 1,
  "requires_gpu": true,
  "gpu_memory_gb": 80,
  "per_item_memory_gb": 32,
  "per_item_time_s": 14400,
  "internet_required": false
}
```

Likely routes to: `slurm` — a backend whose `gpu_types` includes an
80GB+ device (H100, A100-80GB, H200). If no local GPU has ≥80GB and no
SLURM backend with sufficient memory is reachable, the dispatcher
returns a `no_fit` error.

## Output

The router emits a plan, not a side effect. The caller dispatches.
See `SKILL.md` § "Workflow" for the full output shape.
