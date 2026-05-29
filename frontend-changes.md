# Code Quality Tools — Changes

## Overview
Added essential code quality tooling to enforce consistent formatting and catch lint issues across the codebase.

## Files Changed / Added

### `pyproject.toml`
- Added `[dependency-groups] dev` with `black`, `ruff`, `pytest`, `pytest-asyncio`.
- Added `[tool.black]` config: 88-char line length, Python 3.13 target.
- Added `[tool.ruff]` and `[tool.ruff.lint]` config: `E`, `F`, `I` rule sets, `E501` ignored (black owns line length), `E402` suppressed per-file for `app.py` (intentional `warnings` call before imports).
- Added `[tool.pytest.ini_options]` to centralize test discovery config.

### `.editorconfig` (new)
Defines consistent whitespace rules for all file types:
- Python: 4-space indent
- JS / CSS / HTML: 2-space indent
- JSON / YAML / TOML: 2-space indent
- LF line endings, UTF-8, trailing-whitespace trimming, final newline everywhere (except Markdown).

### `scripts/format.sh` (new)
Applies formatting in one command: runs `black` then `ruff --fix` on the `backend/` tree.

### `scripts/check.sh` (new)
CI-safe quality gate (exits non-zero on failure): runs `black --check`, `ruff check`, and `pytest` in sequence.

### Python backend files (reformatted by black)
`app.py`, `ai_generator.py`, `config.py`, `models.py`, `rag_system.py`, `search_tools.py`, `session_manager.py`, `vector_store.py`, and all test files — reformatted to black's canonical style (string quotes, trailing commas, blank lines between top-level definitions).

### `backend/vector_store.py` (lint fix)
Renamed loop variable `l` → `lesson` to resolve ruff `E741` (ambiguous variable name).

## Usage

```bash
# Check formatting + lint + tests (non-destructive)
./scripts/check.sh

# Apply formatting
./scripts/format.sh
```
