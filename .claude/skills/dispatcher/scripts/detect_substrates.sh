#!/bin/bash
# detect_substrates.sh — combine local detection with reachable / unverified
# remote backends. Chain-aware: length-1 chains get a real reachability check;
# longer chains (e.g., ssh→salloc→ssh) are emitted as "unverified" because
# walking them at detection time would open interactive sessions.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Local substrates
local_json=$(bash "$SCRIPT_DIR/check_local.sh")

# Configured remote SLURM backends from personal overlay
backends_dir="$HOME/.claude/skills/dispatcher/backends"
backend_names=()
if [ -d "$backends_dir" ]; then
    for f in "$backends_dir"/*.json; do
        [ -e "$f" ] || continue
        name=$(basename "$f" .json)
        case "$name" in
            _template|example_*) continue ;;
        esac
        backend_names+=("$name")
    done
fi

# Walk each backend: parse manifest, classify chain length, optionally probe.
# Emits a single JSON object per backend on stdout, then we collect them.
reachable=()
unverified=()
unreachable=()
manifests_python_args=()

for name in ${backend_names[@]+"${backend_names[@]}"}; do
    manifest="$backends_dir/$name.json"
    # Extract chain length + first-hop ssh alias (if chain is length 1)
    read -r chain_len first_ssh <<<"$(python3 - "$manifest" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
chain = m.get("access_chain")
if chain is None:
    chain = [{"ssh": m.get("ssh_alias", "")}]
print(len(chain), (chain[0].get("ssh", "") if isinstance(chain[0], dict) else ""))
PY
)"

    if [ "$chain_len" = "1" ] && [ -n "$first_ssh" ]; then
        # Single-hop: real reachability check
        if ssh -o ConnectTimeout=5 -o BatchMode=yes "$first_ssh" sinfo --version >/dev/null 2>&1; then
            reachable+=("$name")
        else
            unreachable+=("$name")
        fi
    else
        # Multi-hop chain (or missing ssh): caller validates at dispatch time
        unverified+=("$name")
    fi
done

# Build configured array
if [ "${#backend_names[@]}" -gt 0 ]; then
    configured_json="[$(printf '"%s",' "${backend_names[@]}" | sed 's/,$//')]"
else
    configured_json="[]"
fi
if [ "${#reachable[@]}" -gt 0 ]; then
    reachable_json="[$(printf '"%s",' "${reachable[@]}" | sed 's/,$//')]"
else
    reachable_json="[]"
fi
if [ "${#unverified[@]}" -gt 0 ]; then
    unverified_json="[$(printf '"%s",' "${unverified[@]}" | sed 's/,$//')]"
else
    unverified_json="[]"
fi
if [ "${#unreachable[@]}" -gt 0 ]; then
    unreachable_json="[$(printf '"%s",' "${unreachable[@]}" | sed 's/,$//')]"
else
    unreachable_json="[]"
fi

# Compose final output. Embed manifests so route.py can read access_chain
# without re-opening the files.
python3 - "$local_json" "$configured_json" "$reachable_json" "$unverified_json" "$unreachable_json" "$backends_dir" <<'PY'
import json, sys, pathlib
local = json.loads(sys.argv[1])
configured = json.loads(sys.argv[2])
reachable = json.loads(sys.argv[3])
unverified = json.loads(sys.argv[4])
unreachable = json.loads(sys.argv[5])
backends_dir = pathlib.Path(sys.argv[6])

manifests = {}
for name in configured:
    p = backends_dir / f"{name}.json"
    if p.exists():
        manifests[name] = json.loads(p.read_text())

out = dict(local)
out["slurm"] = {
    "backends_configured": configured,
    "reachable": reachable,
    "unverified": unverified,
    "unreachable": unreachable,
    "manifests": manifests,
}
print(json.dumps(out, indent=2))
PY
