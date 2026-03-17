#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${RENDER_DEPLOY_HOOK_URL:-}" ]]; then
  echo "RENDER_DEPLOY_HOOK_URL is not set. Skipping Render deploy trigger."
  exit 0
fi

echo "Triggering Render deploy hook..."
curl -fsS -X POST "$RENDER_DEPLOY_HOOK_URL"
echo "Render deploy trigger sent."
