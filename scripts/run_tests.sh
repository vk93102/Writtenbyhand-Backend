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

echo "Running unit tests from ./test ..."
"$PY_BIN" -m unittest discover -s test -p "test_*.py" -v

echo "All tests completed."
