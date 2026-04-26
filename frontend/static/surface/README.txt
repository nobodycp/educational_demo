Surface (سطح العرض) — design only
================================
This folder is the visual layer for the lab UI. It is separate from:
  - frontend/static/js/  → behavior (fingerprint, gate, Bango)
  - backend/             → server rules, APIs, Telegram

If you only change colors/fonts/spacing, edit 10-tokens.css or add a new theme
and swap the @import in index.css. Do not rename “stable hooks” used by JS:

  - HTML ids: e.g. bango form fields, bango-loading-overlay, …
  - Bango behavior: bango-lab.js + lab-busy.js
  - Overlay: .lab-glass-overlay, .lab-glass-overlay__text (lab-busy.js)
  - Spinner: .lab-spinner (classes only; no logic in CSS)

Debug dashboard styling stays in ../css/lab-debug-only.css (separate on purpose).
