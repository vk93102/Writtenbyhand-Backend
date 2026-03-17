#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY_BIN=""
for candidate in python python3 /usr/bin/python3; do
	if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -V >/dev/null 2>&1; then
		PY_BIN="$candidate"
		break
	fi
done

if [[ -z "$PY_BIN" ]]; then
	echo "Python not found. Install python/python3 and retry."
	exit 1
fi

echo "Running Django smoke check with minimal settings..."
export DJANGO_SETTINGS_MODULE=handtotext_ai.settings_minimal
if ! "$PY_BIN" -c "import django" >/dev/null 2>&1; then
	echo "Django is not installed in current environment. Skipping smoke check."
	exit 0
fi
"$PY_BIN" manage.py check

echo "Smoke check passed."
