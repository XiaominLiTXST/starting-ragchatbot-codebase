# Frontend Changes

## Dark/Light Theme Toggle

Added a theme toggle button that lets users switch between dark (default) and light themes, with smooth transitions and persistent preference storage.

### Files Modified

#### `frontend/index.html`
- Added a `<button id="themeToggle">` element fixed to the top-right corner of the viewport.
- Contains two inline SVGs: a sun icon (visible in dark mode) and a moon icon (visible in light mode), controlled by CSS based on the active theme.
- Button is keyboard-navigable with `aria-label` and `title` attributes for accessibility.

#### `frontend/style.css`
- **Light theme CSS variables block** (`[data-theme="light"]`): overrides `--background`, `--surface`, `--surface-hover`, `--text-primary`, `--text-secondary`, `--border-color`, `--assistant-message`, `--shadow`, `--focus-ring`, `--welcome-bg/border`, and new variables `--source-chip-color`, `--source-chip-hover-color`, `--code-bg`, `--error-color`, `--success-color`, `--toggle-bg/hover-bg/border`.
- **New CSS variables in `:root`** (dark defaults): added `--source-chip-color`, `--source-chip-hover-color`, `--code-bg`, `--error-color`, `--success-color`, and theme-toggle-specific variables to avoid hardcoded colors.
- **Replaced hardcoded colors** in `.source-chip`, `.source-chip:hover`, `.message-content code/pre`, `.error-message`, and `.success-message` with the new CSS variables so they adapt to both themes.
- **Theme toggle button styles**: fixed position (top-right), circular (40×40 px), border + background from CSS variables, hover scale, focus ring, and active press-down animation.
- **Icon visibility rules**: `.sun-icon` shown by default (dark mode); `[data-theme="light"]` swaps to `.moon-icon`.
- **Smooth transition rules**: added `transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease` to `body`, sidebars, chat containers, inputs, message content, stat/suggested items, and headers so the theme switch animates instead of flashing.

#### `frontend/script.js`
- **`initTheme()`**: reads `localStorage.getItem('theme')` on load (defaults to `'dark'`) and sets `data-theme` on `<html>`.
- **`toggleTheme()`**: flips `data-theme` between `'dark'` and `'light'` on `<html>`, then persists the choice to `localStorage`.
- `initTheme()` is called immediately (before `DOMContentLoaded`) to prevent a flash of the wrong theme.
- The toggle button's `click` listener is wired up inside `DOMContentLoaded`.

---

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
