#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[CI] Step 1/3: Deploy config validation"
./tests/deploy_check.sh

echo "[CI] Step 2/3: Python test suite"
./tests/run_tests.sh

echo "[CI] Step 3/3: Django smoke check"
./tests/smoke_check.sh

echo "[CI] Pipeline completed successfully."
