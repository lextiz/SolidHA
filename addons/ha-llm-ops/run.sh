#!/usr/bin/env sh
set -e

if [ -f /data/options.json ]; then
  LOG_LEVEL=$(jq -r '.log_level // "info"' /data/options.json)
  BUFFER_SIZE=$(jq -r '.buffer_size // 100' /data/options.json)
  INCIDENT_DIR=$(jq -r '.incident_dir // "/data/incidents"' /data/options.json)
else
  LOG_LEVEL="info"
  BUFFER_SIZE=100
  INCIDENT_DIR="/data/incidents"
fi

echo "[ha-llm-ops] log_level=$LOG_LEVEL buffer_size=$BUFFER_SIZE incident_dir=$INCIDENT_DIR"

env LOG_LEVEL="$LOG_LEVEL" BUFFER_SIZE="$BUFFER_SIZE" INCIDENT_DIR="$INCIDENT_DIR" \
    exec python -m agent.main
