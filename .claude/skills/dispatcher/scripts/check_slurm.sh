#!/bin/bash
# check_slurm.sh — query a SLURM backend's state and emit a JSON snapshot.
#
# Usage:
#   bash check_slurm.sh <backend_name>            # local invocation
#   ssh <alias> 'bash -s' < check_slurm.sh <backend_name>   # remote invocation
#
# Backend name resolution order:
#   1. $1 (CLI arg)
#   2. $SLURM_CLUSTER_NAME (env)
#   3. `scontrol show config | awk '/ClusterName/ {print $3}'`
#
# Manifest lookup order (for the meta block):
#   1. $HOME/.claude/skills/dispatcher/backends/<name>.json  (personal)
#   2. <skill_root>/references/backends/<name>.json          (bundled)
#   3. fall back to {"allocation":"unknown","warnings":["no manifest for <name>"]}

set -uo pipefail

NAME="${1:-${SLURM_CLUSTER_NAME:-}}"
if [ -z "$NAME" ]; then
    if command -v scontrol >/dev/null 2>&1; then
        NAME=$(scontrol show config 2>/dev/null | awk '/ClusterName/ {print $3}')
    fi
fi
if [ -z "$NAME" ]; then
    echo '{"error":"no cluster name; pass as $1 or set $SLURM_CLUSTER_NAME"}'
    exit 1
fi

if ! command -v sinfo &>/dev/null; then
    echo '{"error":"sinfo not found — not on a SLURM cluster"}'
    exit 1
fi

USER_NAME=$(whoami)

# Resolve manifest path (personal overlay first, then bundled).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERSONAL_MANIFEST="$HOME/.claude/skills/dispatcher/backends/${NAME}.json"
BUNDLED_MANIFEST="$SCRIPT_DIR/../references/backends/${NAME}.json"
MANIFEST=""
if [ -r "$PERSONAL_MANIFEST" ]; then
    MANIFEST="$PERSONAL_MANIFEST"
elif [ -r "$BUNDLED_MANIFEST" ]; then
    MANIFEST="$BUNDLED_MANIFEST"
fi

# Read meta fields from the manifest with python3 (always present on SLURM nodes).
cluster_meta() {
    if [ -z "$MANIFEST" ]; then
        printf '{"allocation":"unknown","warnings":["no manifest for %s"]}' "$NAME"
        return
    fi
    python3 - "$MANIFEST" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    m = json.load(f)
keep = ["allocation", "max_gpus_per_node", "gpu_types", "max_wall",
        "internet", "partition", "account", "ssh_alias", "gotchas",
        "legacy", "substrate"]
out = {k: m[k] for k in keep if k in m}
print(json.dumps(out))
PY
}

parse_gpu_nodes() {
    sinfo -N --format="%T %G" --noheader 2>/dev/null | \
    awk '{
        state = $1
        gpu_spec = $2
        gsub(/[-*~#!%]$/, "", state)
        if (match(gpu_spec, /gpu:([a-zA-Z0-9_]+):([0-9]+)/, arr)) {
            gpu_type = arr[1]
            gpu_count = arr[2]
            key = gpu_type "|" gpu_count "|" state
            counts[key]++
            types[gpu_type "|" gpu_count] = 1
        }
    }
    END {
        first_type = 1
        printf "["
        for (tk in types) {
            split(tk, tp, "|")
            gtype = tp[1]
            gpus_per_node = tp[2]
            idle = 0; mixed = 0; allocated = 0; drained = 0; other = 0
            for (k in counts) {
                split(k, parts, "|")
                if (parts[1] == gtype && parts[2] == gpus_per_node) {
                    s = parts[3]
                    if (s == "idle") idle = counts[k]
                    else if (s == "mixed") mixed = counts[k]
                    else if (s == "allocated") allocated = counts[k]
                    else if (s == "drained" || s == "down") drained = counts[k]
                    else other += counts[k]
                }
            }
            total = idle + mixed + allocated + drained + other
            if (!first_type) printf ","
            first_type = 0
            printf "{\"gpu_type\":\"%s\",\"gpus_per_node\":%d,\"idle\":%d,\"mixed\":%d,\"allocated\":%d,\"drained\":%d,\"total\":%d}",
                   gtype, gpus_per_node, idle, mixed, allocated, drained, total
        }
        printf "]"
    }'
}

queue_stats() {
    local pending=$(squeue --state=PENDING --noheader 2>/dev/null | wc -l)
    local running=$(squeue --state=RUNNING --noheader 2>/dev/null | wc -l)
    printf '{"pending":%d,"running":%d}' "$pending" "$running"
}

user_jobs() {
    local user_pending=$(squeue --me --state=PENDING --noheader 2>/dev/null | wc -l)
    local user_running=$(squeue --me --state=RUNNING --noheader 2>/dev/null | wc -l)
    printf '{"pending":%d,"running":%d}' "$user_pending" "$user_running"
}

storage_info() {
    printf "{"
    first=1
    for var in HOME SCRATCH PROJECT; do
        dir="${!var:-}"
        if [ -n "$dir" ] && [ -d "$dir" ]; then
            avail=$(df -BG "$dir" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G')
            total=$(df -BG "$dir" 2>/dev/null | tail -1 | awk '{print $2}' | tr -d 'G')
            if [ "$first" -eq 0 ]; then printf ","; fi
            first=0
            printf "\"%s\":{\"path\":\"%s\",\"avail_gb\":%s,\"total_gb\":%s}" \
                   "$var" "$dir" "${avail:-0}" "${total:-0}"
        fi
    done
    if [ -d "$HOME/links/scratch" ] && [ "$first" -eq 1 -o ! -v SCRATCH ]; then
        avail=$(df -BG "$HOME/links/scratch" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G')
        total=$(df -BG "$HOME/links/scratch" 2>/dev/null | tail -1 | awk '{print $2}' | tr -d 'G')
        if [ "$first" -eq 0 ]; then printf ","; fi
        first=0
        printf "\"SCRATCH\":{\"path\":\"%s/links/scratch\",\"avail_gb\":%s,\"total_gb\":%s}" \
               "$HOME" "${avail:-0}" "${total:-0}"
    fi
    printf "}"
}

internet_check() {
    if curl -s --max-time 3 https://huggingface.co > /dev/null 2>&1; then
        echo "true"
    else
        echo "false"
    fi
}

META=$(cluster_meta)
GPU_NODES=$(parse_gpu_nodes)
QUEUE=$(queue_stats)
USER_JOBS=$(user_jobs)
STORAGE=$(storage_info)
INTERNET=$(internet_check)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat <<EOF
{
  "cluster": "${NAME}",
  "user": "${USER_NAME}",
  "timestamp": "${TIMESTAMP}",
  "meta": ${META},
  "gpu_types": ${GPU_NODES},
  "queue": ${QUEUE},
  "user_jobs": ${USER_JOBS},
  "storage": ${STORAGE},
  "internet": ${INTERNET}
}
EOF
