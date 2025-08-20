#!/usr/bin/env sh
set -eu

CONFIG_PATH=/data/options.json

# Read options with jq; use defaults if file missing
if [ -f "$CONFIG_PATH" ]; then
  LOG_LEVEL=$(jq -r '.log_level // "INFO"' "$CONFIG_PATH")
  BUFFER_SIZE=$(jq -r '.buffer_size // 100' "$CONFIG_PATH")
  ANALYSIS_RATE_SECONDS=$(jq -r '.analysis_rate_seconds // 300' "$CONFIG_PATH")
  ANALYSIS_MAX_LINES=$(jq -r '.analysis_max_lines // 2000' "$CONFIG_PATH")
  OPENAI_API_KEY=$(jq -r '.openai_api_key // ""' "$CONFIG_PATH")
  SUPERVISOR_TOKEN=$(jq -r '.supervisor_token // ""' "$CONFIG_PATH")
else
  LOG_LEVEL=${LOG_LEVEL:-INFO}
  BUFFER_SIZE=${BUFFER_SIZE:-100}
  ANALYSIS_RATE_SECONDS=${ANALYSIS_RATE_SECONDS:-300}
  ANALYSIS_MAX_LINES=${ANALYSIS_MAX_LINES:-2000}
  OPENAI_API_KEY=${OPENAI_API_KEY:-}
  SUPERVISOR_TOKEN=${SUPERVISOR_TOKEN:-}
fi

export LOG_LEVEL BUFFER_SIZE ANALYSIS_RATE_SECONDS ANALYSIS_MAX_LINES OPENAI_API_KEY SUPERVISOR_TOKEN

echo "[INFO] Starting HA LLM Ops agent"
exec python3 -m agent
