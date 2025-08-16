#!/usr/bin/env sh
set -eu

CONFIG_PATH=/data/options.json

# Read options with jq; use defaults if file missing
if [ -f "$CONFIG_PATH" ]; then
  LOG_LEVEL=$(jq -r '.log_level // "INFO"' "$CONFIG_PATH")
  BUFFER_SIZE=$(jq -r '.buffer_size // 100' "$CONFIG_PATH")
  INCIDENT_DIR=$(jq -r '.problem_dir // "/data/problems"' "$CONFIG_PATH")
  LLM_BACKEND=$(jq -r '.llm_backend // ""' "$CONFIG_PATH")
  OPENAI_API_KEY=$(jq -r '.openai_api_key // ""' "$CONFIG_PATH")
  HA_WS_URL=$(jq -r '.ha_ws_url // ""' "$CONFIG_PATH")
else
  LOG_LEVEL=${LOG_LEVEL:-INFO}
  BUFFER_SIZE=${BUFFER_SIZE:-100}
  INCIDENT_DIR=${INCIDENT_DIR:-/data/problems}
  LLM_BACKEND=${LLM_BACKEND:-}
  OPENAI_API_KEY=${OPENAI_API_KEY:-}
  HA_WS_URL=${HA_WS_URL:-}
fi

LLM_BACKEND=$(echo "$LLM_BACKEND" | tr '[:lower:]' '[:upper:]')
HA_WS_URL=${HA_WS_URL:-ws://supervisor/core/websocket}

export LOG_LEVEL BUFFER_SIZE INCIDENT_DIR LLM_BACKEND OPENAI_API_KEY HA_WS_URL

echo "[INFO] Starting HA LLM Ops agent"  
exec python3 -m agent
