#!/bin/bash
# Run all code quality checks (non-destructive, exits non-zero on failure)

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Black: checking Python formatting ==="
cd "$ROOT_DIR/backend"
uv run --with black black --check .
echo "  Black: OK"

echo ""
echo "=== Ruff: linting Python ==="
uv run --with ruff ruff check .
echo "  Ruff: OK"

echo ""
echo "=== Pytest: running tests ==="
uv run pytest "$ROOT_DIR/backend/tests" -q
echo "  Tests: OK"

echo ""
echo "All quality checks passed."
