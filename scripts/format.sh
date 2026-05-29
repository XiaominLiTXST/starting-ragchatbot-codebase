#!/bin/bash
# Apply automatic code formatting to the entire codebase

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Black: formatting Python ==="
cd "$ROOT_DIR/backend"
uv run --with black black .
echo "  Black: done"

echo ""
echo "=== Ruff: auto-fixing lint issues ==="
uv run --with ruff ruff check --fix .
echo "  Ruff: done"

echo ""
echo "Formatting complete."
