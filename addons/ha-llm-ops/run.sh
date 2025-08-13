#!/usr/bin/env sh
set -eu

CONFIG_PATH=/data/options.json

# Read options with jq; use defaults if file missing
if [ -f "$CONFIG_PATH" ]; then
  LOG_LEVEL=$(jq -r '.log_level // "INFO"' "$CONFIG_PATH")
  BUFFER_SIZE=$(jq -r '.buffer_size // 100' "$CONFIG_PATH")
  INCIDENT_DIR=$(jq -r '.incident_dir // "/data/incidents"' "$CONFIG_PATH")
else
  LOG_LEVEL=${LOG_LEVEL:-INFO}
  BUFFER_SIZE=${BUFFER_SIZE:-100}
  INCIDENT_DIR=${INCIDENT_DIR:-/data/incidents}
fi

export LOG_LEVEL BUFFER_SIZE INCIDENT_DIR

echo "[INFO] Starting HA LLM Ops agent"  
exec python3 -m agent
