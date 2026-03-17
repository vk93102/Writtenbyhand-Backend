#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Validating deploy essentials..."

[[ -f "render.yaml" ]] || { echo "Missing render.yaml"; exit 1; }
[[ -f "requirements.txt" ]] || { echo "Missing requirements.txt"; exit 1; }
[[ -f "manage.py" ]] || { echo "Missing manage.py"; exit 1; }
[[ -d "handtotext_ai" ]] || { echo "Missing handtotext_ai package"; exit 1; }

echo "Deploy essentials look good."
