#!/bin/bash
# check_local.sh — detect local CPU / GPU / MPS substrates. Emits one JSON object.
set -uo pipefail

# CPU + RAM
if command -v nproc >/dev/null; then
    cores=$(nproc)
elif command -v sysctl >/dev/null; then
    cores=$(sysctl -n hw.ncpu 2>/dev/null || echo 1)
else
    cores=1
fi

ram_bytes=""
if [ -r /proc/meminfo ]; then
    ram_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
    ram_bytes=$((ram_kb * 1024))
elif command -v sysctl >/dev/null; then
    ram_bytes=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
fi
ram_gb=$((${ram_bytes:-0} / 1024 / 1024 / 1024))

cpu_block="{\"available\":true,\"cores\":$cores,\"ram_gb\":$ram_gb}"

# Local GPU (CUDA)
if command -v nvidia-smi >/dev/null 2>&1; then
    # Returns lines like: "NVIDIA H100 80GB HBM3, 81559"
    gpu_lines=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null)
    if [ -n "$gpu_lines" ]; then
        n_gpus=$(echo "$gpu_lines" | wc -l | tr -d ' ')
        # First GPU's memory as representative
        first_mem_mb=$(echo "$gpu_lines" | head -1 | awk -F', ' '{print $2}')
        first_mem_gb=$((first_mem_mb / 1024))
        first_name=$(echo "$gpu_lines" | head -1 | awk -F', ' '{print $1}')
        gpu_block="{\"available\":true,\"n_gpus\":$n_gpus,\"memory_gb_per_gpu\":$first_mem_gb,\"device\":\"$first_name\"}"
    else
        gpu_block='{"available":false,"reason":"nvidia-smi exited 0 but no GPUs reported"}'
    fi
else
    gpu_block='{"available":false,"reason":"no nvidia-smi"}'
fi

# Apple MPS
mps_block='{"available":false}'
if command -v sysctl >/dev/null; then
    model=$(sysctl -n hw.model 2>/dev/null || echo "")
    if echo "$model" | grep -qi "^Mac"; then
        # Apple Silicon: arm64 + Mac model
        arch=$(uname -m 2>/dev/null || echo "")
        if [ "$arch" = "arm64" ]; then
            mps_block="{\"available\":true,\"ram_gb\":$ram_gb,\"device\":\"$model\",\"note\":\"unified memory; ram_gb is total system RAM accessible to MPS\"}"
        fi
    fi
fi

cat <<EOF
{
  "local_cpu": $cpu_block,
  "local_gpu": $gpu_block,
  "mps":       $mps_block
}
EOF
