# UI/UX Layout Fix Plan

Date: 2026-06-02

## Context

- `directions/` is missing. Per DOE, base Direction documents should be created before broader project work.
- Current architecture context was taken from `CLAUDE.md`.
- No project lessons/known-issues file was found.
- The current working directory is not a git repository, despite the user mentioning an initial commit. Changes need extra care because there is no local git safety net in this folder.

## Skills Used For Planning

- `brainstorming`: required before creative/UI behavior work.
- `frontend-design`: requested by user, used to frame production-grade dashboard UI fixes.
- `frontend-aesthetics`: used to avoid generic or inconsistent visual treatment.
- `responsive-design`: used because mobile/tablet screenshots show structural overflow.
- `accessibility-compliance`: used for touch target, focus, form, and modal constraints.
- `webapp-testing`: used for Playwright-based visual and overflow audit.

## Observed Issues

Playwright screenshots were captured under `/private/tmp/hh-ui-audit/`.

1. CSS token mismatch
   - `style.css` defines modern tokens like `--text-dim`, `--success`, `--danger`.
   - HTML/JS still use legacy tokens like `--dim`, `--bg`, `--bg-card2`, `--cyan`, `--green`, `--yellow`, `--red`, `--magenta`.
   - Result: many inline styles resolve invalid colors/backgrounds and several controls look unstyled.

2. Broken campaign configurator behavior
   - `#campaign-configurator` is styled as absolute centered overlay in both inline CSS and `style.css`.
   - In the Apply tab it renders over the dashboard instead of behaving like normal tab content or a real modal with active backdrop.
   - Form content can extend beyond the visible viewport.

3. Invalid HTML nesting
   - Campaign checkbox `campaign-strict-match` opens a `<label>` but closes a `<div>`.
   - Several settings toggles have nested/mismatched `label`/`div` tags.
   - Browser repair of this markup causes later settings/LLM sections to appear in wrong flow positions.

4. Missing styles for actual dashboard components
   - `settings-layout`, `settings-sidebar`, `settings-content`, `settings-subpanel`, `q-section`, `toggle-switch`, `applied-header`, `#main-layout`, `#accounts-grid`, and account-card classes are mostly unstyled or under-styled.
   - Settings page currently appears as raw document flow rather than a dashboard panel.

5. Mobile layout is unusable
   - Fixed 250px sidebar leaves only about 140px content on a 390px viewport.
   - Header stats/actions shift left out of viewport.
   - Text wraps into narrow columns and controls overflow.

6. Tables and action bars need responsive containers
   - Data tables need horizontal scroll containers on narrow widths.
   - Header/filter/action bars should wrap without compressing controls below readable widths.

## Proposed Direction

Use a quiet, utilitarian operations-dashboard design:

- Keep the existing light dashboard palette and sidebar navigation.
- Fix structural layout first, then visual polish.
- Avoid a broad redesign; preserve existing tab names, workflow, and vanilla JS structure.
- Prioritize predictable scanning, compact density, and no overlapping content.

## Implementation Steps

1. Add DOE support docs for this task
   - Create `execution/logs/` for verification output.
   - Create a lessons/known-issues file after implementation if a root cause is confirmed.

2. Repair HTML structure in `static/index.html`
   - Fix malformed campaign checkbox label.
   - Fix nested/mismatched labels in settings toggle rows.
   - Remove duplicated inline modal CSS where it conflicts with `style.css`.
   - Give repeated inline layout blocks stable classes where useful, without broad markup rewrites.

3. Normalize design tokens in `static/css/style.css`
   - Add aliases for legacy variables used by JS/HTML.
   - Add missing text utility classes such as `text-sm`, `text-md`, `text-dim`, and color helpers used by markup.

4. Rebuild core responsive shell
   - Desktop: sidebar + topbar + scrollable content stays as current mental model.
   - Tablet/mobile: sidebar becomes a horizontal/scrollable top nav or compact full-width nav; content gets full width.
   - Header stats/actions wrap and remain visible.

5. Fix dashboard sections
   - Main: make account grid and stats sidebar responsive.
   - Applied/DB/Tests/LLM: wrap tables in scroll containers, keep filters and action buttons readable.
   - Views: wrap audit/action rows, prevent long inputs from crowding buttons.
   - Settings: implement two-column settings layout on desktop and single-column on mobile.

6. Fix campaign configurator
   - Make it normal Apply-tab content by default.
   - If modal behavior is needed via `showCampaignConfigurator`, use `.active` plus backdrop consistently.
   - Ensure max-height, internal scrolling, and mobile form rows stack correctly.
   - Fix segment controls to use the existing `.segment-btn` class or update JS selectors to match current buttons.

7. Accessibility/UI polish
   - Add visible focus states.
   - Ensure button/input touch targets are at least 40px where practical.
   - Make long labels wrap cleanly.
   - Avoid text clipping and accidental horizontal body scroll.

8. Verification
   - Run the app locally.
   - Re-run Playwright screenshots at 1440x900, 900x900, and 390x844.
   - Log before/after findings in `execution/logs/ui-layout-audit-2026-06-02.md`.

## Approval Gate

No UI code changes should start until this plan is approved.

## Auth Flow Follow-Up

Approved by user request on 2026-06-02.

1. Before authorization, show the authorization experience as the primary screen, not as one tab inside the dashboard.
2. After authorization, hide the `Авторизация` navigation item and switch to the main dashboard.
3. Keep auth form text/buttons readable on mobile and desktop; avoid narrow single-word columns.
4. Preserve existing auth IDs and API calls.
