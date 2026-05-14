# Backend manifest schema

Each remote backend the skill knows about is described by a JSON backend
manifest. The skill's `check_slurm.sh` reads the manifest to populate the
`meta` block in its JSON output; the router in `scripts/route.py` reads it
to decide whether a workload fits.

**Adding a new backend = dropping a new JSON file.** No code changes required.

## Where manifests live

The skill looks up manifests in this order:

1. **Personal overlay (preferred):** `~/.claude/skills/dispatcher/backends/<name>.json`
   — your private cluster configs go here. Nothing private should land
   in the public skill repo.
2. **Bundled examples:** `references/backends/<name>.json` — anonymized
   examples that ship with the skill (see `example_slurm.json`).

Local substrates (`local_cpu`, `local_gpu`, `mps`) are auto-detected by
`scripts/check_local.sh` and do **not** need a manifest. Manifests are
only required for remote backends (currently: SLURM clusters).

## Required fields

| Field | Type | Description |
|---|---|---|
| `name` | string | Canonical backend name (matches the filename: `<name>.json`). Lowercase. |
| `substrate` | `"slurm"` \| `"local_cpu"` \| `"local_gpu"` \| `"mps"` | Which substrate driver handles this backend. Local substrates rarely need a manifest; this field disambiguates if you do write one (e.g. to pin a specific local GPU). |
| `allocation` | `"flexible"` \| `"full_node"` \| `"unknown"` | How GPUs can be requested. Full-node backends require all GPUs; flexible allow 1..N. |
| `max_gpus_per_node` | int | Largest GPU count on any node. Used for sharding decisions. |
| `gpu_types` | array of strings | SLURM `--gpus=<type>:N` type names available (e.g. `["h100","h200"]`, `["a100","l40s","rtx8000"]`). |
| `internet` | bool | Whether compute nodes have outbound internet. Drives the "must pre-transfer models" decision. |

## Recommended fields

| Field | Type | Description |
|---|---|---|
| `ssh_alias` | string | SSH alias the dispatcher uses to reach the backend (`ssh <alias> sinfo`). Must resolve via your `~/.ssh/config`. Shorthand for a length-1 `access_chain` (see below). |
| `access_chain` | array of step objects | The hops to reach the backend's SLURM scheduler. Use when reaching the backend requires more than one SSH (e.g., must allocate a compute session on a jumphost first). If omitted, the dispatcher synthesizes `[{"ssh": ssh_alias}]`. See "Access chain" below. |
| `max_wall` | string | Max wall time, human-readable (`"24h"`, `"7d"`, `"unlimited"`). Used for wall-time-estimation sanity check. |
| `login_host` | string | DNS/hostname to SSH into. |
| `automation_host` | string \| null | Separate hostname for scripted/cron-like access. Null if same as login. |
| `hostname_patterns` | array of strings | Glob patterns that `hostname -f` matches when running on this backend. Used by the script's hostname-based detection fallback. |
| `gotchas` | array of strings | Backend-specific anti-patterns. Surfaced when the skill recommends this backend (e.g. `"HF_HUB_OFFLINE=1 required"`, `"Use --switches=1 for tightly-coupled jobs"`). |

## Optional fields (extend as needed)

| Field | Type | Description |
|---|---|---|
| `partition` | string | Default SLURM partition. |
| `account` | string | Default SLURM `--account`. |
| `ssh_port` | int | Override default SSH port. |
| `proxy_jump` | string | If compute nodes need ProxyJump through login. |
| `storage_paths` | object | `{"home": "$HOME", "scratch": "...", "project": "..."}` — handles non-standard layouts. |
| `legacy` | bool | If true, skill warns "being phased out; prefer <successor>". |
| `notes` | string | Free-form prose for human readers; ignored by the script. |

## Minimal example

A SLURM backend called `my-uni` with 4 A100s per node, flexible allocation, internet on compute:

```json
{
  "name": "my-uni",
  "substrate": "slurm",
  "ssh_alias": "my-uni",
  "allocation": "flexible",
  "max_gpus_per_node": 4,
  "gpu_types": ["a100"],
  "max_wall": "24h",
  "internet": true,
  "login_host": "slurm.my-uni.edu",
  "hostname_patterns": ["*my-uni.edu", "compute-*.my-uni.edu"]
}
```

Drop this at `~/.claude/skills/dispatcher/backends/my-uni.json` (personal
overlay). The skill auto-detects when run on `my-uni` and uses the
manifest for routing.

## Access chain

A backend's `access_chain` is an ordered list of steps the dispatcher
emits for the caller to walk in order to reach the backend's SLURM
scheduler. Two step types:

| Step | Shape | Semantics |
|---|---|---|
| SSH hop | `{"ssh": "<alias>"}` | SSH to a host. The alias resolves via `~/.ssh/config`. SSH `ProxyJump` is handled transparently by OpenSSH; no extra dispatcher logic. |
| SLURM allocation | `{"salloc": "<args>"}` | Request an interactive SLURM session on the current host. `args` is a literal sbatch/salloc args string (e.g. `"--gres=gpu:rtx8000:1 --time=4:00:00"`). The dispatcher does not parse it — your cluster, your dialect. |

The chain executes top-to-bottom. After each step, the *current host*
changes:
- `ssh` ⟶ current host becomes the SSH target.
- `salloc` ⟶ current host is now a SLURM compute node assigned by the
  scheduler (interactive session opens).

The dispatcher emits the chain in the plan; it does **not** walk the
chain itself. The caller (or agent) opens each session in order. This
matches the emit-only contract: the dispatcher plans, the caller runs.

### Length-1 chain (most common)

Just SSH to the cluster's login node. The shorthand `ssh_alias` is
equivalent:

```json
"access_chain": [{"ssh": "my-cluster"}]
```

### Length-2: ProxyJump-style chained logins

If your cluster's login is only reachable through a bastion *and* SSH
`ProxyJump` doesn't handle it (most do — try that first), explicit
chain:

```json
"access_chain": [{"ssh": "bastion"}, {"ssh": "target"}]
```

### Length-3: allocate-then-hop (e.g., jumphost via compute session)

When reaching the target requires being inside a compute allocation on
an intermediate cluster (e.g., for bandwidth, internal routing, or
proxy reasons):

```json
"access_chain": [
  {"ssh": "intermediate-cluster"},
  {"salloc": "--gres=gpu:rtx8000:1 --time=4:00:00"},
  {"ssh": "target-cluster"}
]
```

See `backends/example_chained.json` for a complete worked example.

### Reachability checking

For length-1 chains, the dispatcher tries `ssh <alias> sinfo --version`
at detection time and marks the backend `reachable` or `unreachable`.

For chains of length > 1, the dispatcher does **not** walk the chain
during detection (would require opening an interactive `salloc`
session, which is slow and stateful). Chained backends are marked
`unverified` — the dispatcher will still include them in routing
decisions, but the caller validates the chain at dispatch time.

The decision tree prefers `reachable` backends over `unverified` ones
when both fit a workload.

## Schema evolution

Add new fields freely — `check_slurm.sh` ignores unknown keys. Keep the
**required** fields stable; if you need to deprecate one, surface it via a
`gotchas` entry first.
