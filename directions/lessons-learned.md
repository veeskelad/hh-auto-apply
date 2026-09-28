# Lessons Learned

Known issues and anti-patterns discovered during project work.

### Mixed CSS Tokens Break Dashboard Styling
- **Error**: UI controls and status text rendered with invalid colors/backgrounds.
- **Cause**: HTML/JS used legacy CSS variables such as `--dim`, `--cyan`, `--bg`, `--green`, while `style.css` only defined newer names such as `--text-dim`, `--success`, and `--bg-main`.
- **Solution**: Keep compatibility aliases in `:root` when old inline styles still exist, then migrate markup gradually.

### Inline Display State Can Defeat Tab Classes
- **Error**: Hidden panels still occupied layout space in Playwright and internal tab switches.
- **Cause**: The click handler cleared inline `display`, but `window.switchTab()` did not. Internal calls used `window.switchTab()`.
- **Solution**: Centralize tab cleanup in `window.switchTab()` so all tab changes clear stale inline display state.

### Invalid Label Nesting Corrupts Later Layout
- **Error**: Settings sections appeared as raw document flow and unrelated blocks surfaced on other tabs.
- **Cause**: Several toggle rows opened `<label>` tags and closed `</div>`, forcing browser HTML repair.
- **Solution**: Use a wrapper `div` plus a separate `.toggle-switch` label and text span for toggle rows.

### Generic Form Rows Break Dashboard Cards
- **Error**: Account card content collapsed into a narrow vertical text column and header controls spread unpredictably.
- **Cause**: The card header used duplicated `class` attributes and inherited `.form-row` behavior instead of having a card-specific layout.
- **Solution**: Give dashboard cards dedicated header/tool/stat/action classes and responsive CSS; do not reuse form layout classes for dense operational cards.
