# Frontend Changes

## Dark/Light Mode Toggle Button

### Files Changed
- `frontend/index.html`
- `frontend/style.css`
- `frontend/script.js`

---

### What Was Added

#### `index.html`
- Added a `<button id="themeToggle">` element directly inside `<body>`, before `.container`.
- The button contains two inline SVGs: a sun icon (shown in dark mode) and a moon icon (shown in light mode).
- Both SVGs carry `aria-hidden="true"` since the button's text label is provided via `aria-label`.
- The `aria-label` and `title` attributes dynamically update to describe the *next* action ("Switch to light mode" / "Switch to dark mode").
- Bumped CSS/JS cache-busting version query strings to `?v=10`.

#### `style.css`
- **`html[data-theme="light"]` block**: full set of overriding CSS custom properties for light mode (background `#f8fafc`, surface `#ffffff`, text `#0f172a`, borders `#e2e8f0`, etc.).
- **Theme transitions**: a broad `transition` rule on `body`, `.sidebar`, `.chat-messages`, `.chat-input-container`, `.message-content`, `#chatInput`, `.theme-toggle`, and related elements to smoothly animate `background-color`, `color`, `border-color`, and `box-shadow` over 0.3 s.
- **`.theme-toggle` styles**: `position: fixed; top: 1rem; right: 1rem` floating button, 40 × 40 px circle, `z-index: 100`, using `--surface`, `--border-color`, `--text-primary` variables so it adapts to both themes.
- **Hover/focus/active states**: scale on hover, focus-visible outline with `--primary-color`, scale-down on active.
- **Icon animation**: both SVGs are `position: absolute` inside the button. In dark mode the sun is at `rotate(0deg) opacity(1)` and the moon is rotated out (`rotate(90deg) opacity(0)`). In light mode these states swap, driven by the `html[data-theme="light"]` selector. The transition uses `cubic-bezier(0.4, 0, 0.2, 1)` for a polished feel.

#### `script.js`
- **`initTheme()`**: reads `localStorage.getItem('theme')` (defaulting to `'dark'`) and calls `applyTheme()` on page load.
- **`applyTheme(theme)`**: sets `data-theme` on `<html>` and updates the button's `aria-label`/`title`.
- **`toggleTheme()`**: flips the current theme, calls `applyTheme()`, persists to `localStorage`.
- **`setupEventListeners()`**: wires `click` on `#themeToggle` to `toggleTheme`.
- **`DOMContentLoaded`**: calls `initTheme()` before the existing setup calls so the correct theme is applied before any rendering.

### Accessibility
- Button is a native `<button>` (keyboard-focusable by default).
- `aria-label` always describes the *action*, updated dynamically on each toggle.
- `focus-visible` outline provides a visible keyboard-focus indicator without affecting mouse users.
- SVGs carry `aria-hidden="true"` to avoid double-announcing with the button label.
- Theme preference persists across sessions via `localStorage`.
