---
name: dispatcher
description: >
  Compute dispatcher — picks the right substrate (local CPU, local GPU, Apple
  MPS, or a SLURM cluster) for a parallel workload and emits a dispatch plan.
  Triggers on: "run this in parallel", "scale this out", "dispatch", "submit
  job", "sweep", "sbatch", "how should I run N items", "which cluster",
  "should I use my laptop or the cluster", "check availability", "queue
  depth", "where should this run", "SSH config", "register a backend", any
  question about choosing between local execution and a SLURM cluster.
  Also triggers when planning multi-GPU sharding, batching N items across
  N workers, or routing the same workload to a different machine. Use this
  skill before writing parallel-execution code — the dispatcher's
  recommendation determines the shape of what you write.
---

# Compute dispatcher

Given a **workload** (N parallel items, per-item resource needs), this
skill picks the best **substrate** to run it on and emits a **dispatch
plan**. The dispatcher does not run the workload — it tells you how to
run it, so the caller (or the agent) can dispatch in a visible step.

> **Same workload, different substrates, harness picks.** Run on a
> laptop's 8 cores → `local_cpu`. Plug in your workstation's 4 GPUs →
> `local_gpu`. Configure a SLURM cluster → `slurm`. The dispatcher
> reads what's available, matches it to what the workload needs, and
> returns the plan.

## The four substrates (MVP)

| Substrate | Detected by | Picked when… |
|---|---|---|
| `local_cpu` | always present | CPU-only workload OR no GPU substrate fits |
| `local_gpu` | `nvidia-smi` exits 0 | workload fits in local GPU memory |
| `mps` (Apple Silicon) | `sysctl -n hw.model` matches `Mac*` and Metal available | Mac workload, GPU helpful, no CUDA needed |
| `slurm` | a backend manifest exists *and* `ssh <alias> sinfo` works | workload exceeds local capacity OR you opted in |

Future substrates (Ray, cloud, Kubernetes) plug into the same backend-manifest
contract; not implemented in MVP.

## Workload spec

The dispatcher consumes a JSON object describing the work:

```json
{
  "n_items": 60,
  "requires_gpu": true,
  "gpu_memory_gb": 16,
  "per_item_memory_gb": 12,
  "per_item_time_s": 60,
  "internet_required": false
}
```

| Field | Required when | Meaning |
|---|---|---|
| `n_items` | always | Number of independent parallel work units |
| `requires_gpu` | always | Whether items need a GPU at all |
| `gpu_memory_gb` | `requires_gpu=true` | Min GPU memory per item (drives substrate fit) |
| `per_item_memory_gb` | always | Peak host RAM per item |
| `per_item_time_s` | optional | Used to estimate wall time / pick batch size |
| `internet_required` | optional (default `false`) | If true, eliminates SLURM clusters with no compute-node internet |

Heuristic: if `per_item_time_s` is missing, dispatcher assumes 60s and
flags the assumption in its plan. If `gpu_memory_gb` is missing when
`requires_gpu=true`, the dispatcher fails fast — that's load-bearing.

**Don't include a `device` field.** The workload spec is
substrate-agnostic. The dispatcher decides which substrate fits; once
the substrate is picked, the dispatcher derives the device
(`cpu` / `cuda` / `mps`) and emits it in the plan as `device_override`.
If you want to pin a device explicitly, call your library
(e.g., `manylatents`) directly and skip the dispatcher. The dispatcher
owns substrate-and-device-from-substrate; it does not negotiate with a
caller's device preference. Three layers, one concern each:

- **dispatcher**: substrate + device (which node, how parallel, what device)
- **manylatents** (or your library): device + module (actual torch device handling)
- **kernel** (future, e.g. Geomancer): which CUDA kernel for this op on this device

## Workflow

### 1. Detect what's available

```bash
bash scripts/detect_substrates.sh
```

Returns JSON like:
```json
{
  "local_cpu": {"cores": 12, "ram_gb": 36, "available": true},
  "local_gpu": {"available": false, "reason": "no nvidia-smi"},
  "mps":       {"available": true, "ram_gb": 36, "device": "Apple M2 Pro"},
  "slurm":     {"backends_configured": ["my-cluster"], "reachable": ["my-cluster"]}
}
```

### 2. Route the workload

```bash
python3 scripts/route.py --workload workload.json
```

Returns the plan — substrate, device override, parallelism count, and a
per-worker invocation template:

```json
{
  "substrate": "mps",
  "parallel_workers": 1,
  "device_override": "mps",
  "per_worker_invocation": "python -m <your.module> <hydra args> device={device_override} shard={i} n_shards={parallel_workers}",
  "extras": {"note": "Apple Silicon unified memory"}
}
```

The `device_override` is what the dispatcher tells the worker layer
(e.g., `manylatents`) to use. Substrate → device:

| Substrate | Device |
|---|---|
| `local_cpu` | `cpu` |
| `local_gpu` | `cuda` |
| `mps` | `mps` |
| `slurm` | `cuda` (SLURM nodes have NVIDIA GPUs in MVP) |

The `per_worker_invocation` is a template; the caller substitutes `{i}`
(item / shard index) and `{parallel_workers}` (total shards). For Hydra-
configured workers, the device override is passed as a CLI argument
(`device=mps`); for direct-Python workers, as a kwarg.

### 3. Dispatch (caller's responsibility)

The dispatcher *emits* the plan; it does *not* execute. The agent (or
the human) runs the dispatch script in a visible step. This keeps the
substrate choice auditable and the side effects under the caller's
control.

## Routing decision tree

```
if workload.requires_gpu:
    if mps available and gpu_memory_gb <= mps.ram_gb and not internet_required_unmet:
        pick mps                                 # Mac workshop laptop, no manifest needed
    elif local_gpu available and gpu_memory_gb <= local_gpu.memory_gb:
        pick local_gpu                           # workstation with CUDA
    elif any reachable slurm backend has gpu_memory_gb available:
        pick slurm (best by queue depth / wall time / cost)
    else:
        FAIL with no-fit error
else:
    if n_items × per_item_memory_gb fits in local_cpu.ram_gb:
        pick local_cpu                           # universal fallback
    else:
        pick slurm or FAIL
```

For SLURM picks: pick the backend with the lowest queue depth among those
whose `gpu_types` includes a GPU large enough. Tie-break on
`max_wall` ≥ estimated wall time.

## Reaching a backend via a chain

Sometimes a SLURM cluster isn't reachable via a single SSH hop. The
dispatcher models this with an `access_chain`: an ordered list of
steps the caller walks to reach the backend's scheduler. Two step
types:

| Step | Shape | Effect |
|---|---|---|
| SSH hop | `{"ssh": "<alias>"}` | SSH into a host (alias resolves via `~/.ssh/config`; ProxyJump handled transparently) |
| SLURM allocation | `{"salloc": "<args>"}` | Open an interactive SLURM session on the current host (literal `salloc` arg string — your cluster, your dialect) |

The plan now includes `access_chain` alongside `per_worker_invocation`.
The caller walks the chain top-to-bottom, then runs the invocation on
the final host. The dispatcher does NOT walk the chain itself — emit-
only contract holds.

### Common patterns

**Direct SSH (length-1):** the shorthand `ssh_alias` field is
equivalent; the dispatcher synthesizes the chain.
```json
"ssh_alias": "my-cluster"
// equivalent to:
"access_chain": [{"ssh": "my-cluster"}]
```

**Allocate-then-hop (length-3):** when reaching the target requires
being inside an interactive compute session on an intermediate
cluster (e.g., for bandwidth, internal routing, proxy constraints):
```json
"access_chain": [
  {"ssh": "intermediate-cluster"},
  {"salloc": "--gres=gpu:rtx8000:1 --time=4:00:00"},
  {"ssh": "target-cluster"}
]
```

See `references/backends/example_chained.json` for a full anonymized
example. Full schema in `references/backend_schema.md`.

### Reachability for chained backends

Length-1 chains get a live `ssh <alias> sinfo --version` probe during
detection. Longer chains are emitted as **unverified** — walking
`salloc` at detection time would open interactive sessions, which is
slow and stateful. The router includes unverified backends in routing
decisions but flags them so the caller knows to validate the chain at
dispatch time.

The router's priority: `reachable` > `unverified` > no-fit.

## Registering a remote backend

Drop a manifest at `~/.claude/skills/dispatcher/backends/<name>.json`.
The skill checks the personal overlay before bundled examples; nothing
private goes in the public skill.

Minimum manifest:
```json
{
  "name": "my-cluster",
  "substrate": "slurm",
  "ssh_alias": "my-cluster",
  "allocation": "flexible",
  "max_gpus_per_node": 4,
  "gpu_types": ["a100"],
  "max_wall": "24h",
  "internet": true
}
```

Full schema: `references/backend_schema.md`. Anonymized worked example:
`references/backends/example_slurm.json`.

For SSH: the dispatcher expects `ssh <alias> sinfo` to work. Set up
ControlMaster once (`references/ssh_template.md`), then the dispatcher
calls your cluster's `sinfo` without re-authenticating per query.

## No-fit failure

If the workload doesn't fit any reachable substrate, the dispatcher
**fails hard** with a structured error:

```json
{
  "error": "no substrate fits",
  "checked": ["local_cpu", "mps"],
  "workload_requires": {"gpu_memory_gb": 40, "internet_required": false},
  "would_unblock": [
    "register a SLURM backend with gpu_types containing >=40GB",
    "reduce gpu_memory_gb if model can shard"
  ]
}
```

No silent fallback. Silent fallback to a smaller GPU has cost the
maintainer more than one wasted day.

## Anti-patterns

- **Don't dispatch from the dispatcher.** It plans; the caller runs.
  Emit-only keeps the substrate choice auditable.
- **Don't infer `gpu_memory_gb` from `n_items`.** Per-item GPU memory is
  a property of the workload, not the parallelism. If you don't know,
  the dispatcher fails fast — that's correct.
- **Don't add cluster manifests to the public skill repo.** Personal
  configs go in `~/.claude/skills/dispatcher/backends/`. The public
  skill ships schema + anonymized examples only.
- **Don't write substrate-specific code in the workload.** The workload
  spec is a substrate-agnostic description. Substrate-specific glue
  lives in the dispatch script templates the router emits.
- **Don't bypass the worker library's device handling.** The dispatcher
  emits `device_override`; the worker layer (`manylatents`, your library,
  raw torch) takes it as a Hydra override or kwarg. Re-routing the device
  inside the dispatcher (e.g., calling `.to(device)` here) duplicates
  logic the library already owns and creates two sources of truth.
  Dispatcher knows substrate; library knows device.
- **Don't bypass the no-fit error.** If nothing fits, report it; let the
  caller decide whether to relax constraints, register a new backend,
  or reshape the workload.

## What this skill is NOT

- **Not a job scheduler.** It picks WHERE work runs; SLURM (or the local
  shell) actually schedules it.
- **Not a model-sharding library.** It tells you how many GPUs you can
  use; how to shard your model across them is the model's concern.
- **Not a cost optimizer.** Future: rank substrates by `cost_per_hour`
  field in the backend manifest. MVP picks by availability and fit.
