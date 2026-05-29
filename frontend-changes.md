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
