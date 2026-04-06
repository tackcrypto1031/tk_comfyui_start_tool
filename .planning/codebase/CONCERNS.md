# Codebase Concerns

**Analysis Date:** 2026-04-06

## Tech Debt

**Untyped JavaScript Frontend:**
- Issue: The entire web UI is written in vanilla JavaScript without type checking or TypeScript
- Files: `src/gui/web/js/app.js`, `src/gui/web/js/bridge.js`, `src/gui/web/js/i18n.js`, all page files in `src/gui/web/js/pages/`
- Impact: No compile-time type safety, refactoring difficult, IDE support limited, higher bug risk during feature development
- Fix approach: Migrate to TypeScript or use JSDoc type annotations for at least critical files (bridge.js, app.js)

**Home Page Not Implemented:**
- Issue: Homepage is completely empty with no content or functionality
- Files: `src/gui/web/js/pages/home.js` (11 lines, only renders empty container)
- Impact: First page users see is blank; missing opportunity for status overview, quick actions, or onboarding
- Fix approach: Implement actual homepage with environment status summary, quick links, system info

**Missing Test Coverage:**
- Issue: No tests detected for any JavaScript modules
- Files: All files in `src/gui/web/js/` (834 total lines of code)
- Impact: Cannot safely refactor or enhance UI; bugs only discovered at runtime; no regression protection
- Fix approach: Add Jest or Vitest configuration, write unit tests for bridge.js and app.js (critical modules), add integration tests for page modules

## Error Handling Issues

**Silent Error Swallowing in Launcher Polling:**
- Issue: Poll errors are silently ignored with empty catch block
- Files: `src/gui/web/js/pages/launcher.js` line 169-171
- Impact: User won't know if status polling fails; app appears frozen while actually broken
- Workaround: Status eventually becomes stale, not real-time
- Recommendation: Log or show warning toast for repeated poll failures, implement exponential backoff or retry logic

**Inadequate Error Messages in Promise Chains:**
- Issue: Many catch blocks just stringify errors without context
- Files: `src/gui/web/js/pages/environments.js` line 96, `src/gui/web/js/pages/plugins.js` line 75, line 98
- Impact: Users see raw error strings that aren't localized; "Failed to parse result" doesn't tell user what went wrong
- Recommendation: Wrap errors with context, provide user-friendly messages via i18n, log details to console for debugging

**Modal Rendering Race Condition:**
- Issue: Modal event handlers are bound inside setTimeout() in showCreateDialog()
- Files: `src/gui/web/js/pages/environments.js` lines 150-188
- Impact: If modal is dismissed before setTimeout fires (100ms), event handlers never bind; subsequent clicks on versions fetch fail silently
- Fix approach: Bind handlers immediately after showModal() completes, or wait for modal render callback instead of arbitrary timeout

## Security Concerns

**XSS Prevention Inconsistency:**
- Issue: Some places use escapeHtml() but many don't; innerHTML assignments from user input exist
- Files: 
  - `src/gui/web/js/pages/environments.js` lines 82-86 (uses escapeHtml for env names)
  - `src/gui/web/js/pages/environments.js` line 251 (innerHTML with unescaped source variable in clone dialog)
  - `src/gui/web/js/pages/plugins.js` line 119 (unescaped plugin_name in risk banner)
- Impact: If backend sends malicious data, XSS possible; plugin names/paths from users could inject scripts
- Recommendation: Audit all innerHTML assignments, use escapeHtml() consistently, prefer textContent for untrusted data

**QWebChannel Message Parsing:**
- Issue: JSON parsing doesn't validate schema before using fields
- Files: `src/gui/web/js/bridge.js` lines 29-40, lines 89-95
- Impact: Malformed responses from Python backend could crash JS or cause unexpected behavior
- Recommendation: Add schema validation for bridge responses, handle missing required fields gracefully

## Performance Bottlenecks

**Synchronous Modal Render with 100ms Delay:**
- Issue: Modal event binding uses arbitrary 100ms setTimeout() instead of waiting for actual render
- Files: `src/gui/web/js/pages/environments.js` line 150
- Impact: Version list fetch (BridgeAPI.listRemoteVersions) waits 100ms before starting; UI feels sluggish
- Improvement path: Use MutationObserver to detect modal DOM insertion, or add callback to showModal()

**Polling Inefficiency in Launcher:**
- Issue: Background polling runs every 5 seconds unconditionally, even when tab is not visible
- Files: `src/gui/web/js/pages/launcher.js` lines 174-177
- Impact: Wasted network requests, unnecessary CPU/battery drain on backgrounds tabs
- Improvement path: Pause polling on visibilitychange event, resume when tab is active

**5-Minute Timeout on Async Operations:**
- Issue: All async bridge calls have a hard 5-minute timeout
- Files: `src/gui/web/js/bridge.js` lines 85-121
- Impact: Long operations (large environment clones, model downloads) fail with timeout even if still running; no progress feedback after 5 min
- Improvement path: Make timeout configurable per operation, show warning before timeout, allow user to extend

**Poll Progress Parsing Without Batching:**
- Issue: Each poll interval calls poll_progress() separately, returns all messages; no batching
- Files: `src/gui/web/js/bridge.js` lines 103-114
- Impact: High-frequency progress updates cause UI reflow on every 500ms interval; could be batched into single update
- Improvement path: Batch progress messages, update UI less frequently but with all changes

## Fragile Areas

**Bridge Initialization Race Condition:**
- Issue: App initializes before bridge connection confirmed; navigation to home page might happen before BridgeAPI ready
- Files: `src/gui/web/js/app.js` lines 238-260, `src/gui/web/js/bridge.js` lines 10-23
- Why fragile: If bridge init fails, app navigates to home anyway; subsequent page loads will fail because bridge isn't ready
- Safe modification: Ensure all page modules check BridgeAPI.bridge !== null before calling methods, or wrap all bridge calls in init check
- Test coverage: No tests for initialization order or bridge failure scenarios

**DOM Mutation Without Null Checks:**
- Issue: Code assumes DOM elements exist after render(), but doesn't verify
- Files: `src/gui/web/js/pages/launcher.js` lines 72-73 (assumes launch-env exists), `src/gui/web/js/pages/plugins.js` line 68 (no null check on select)
- Safe modification: Always check return value of querySelector/getElementById before calling methods on result
- Example fragile pattern: `document.getElementById('plug-env').value` without null check at line 79

**Event Handler Accumulation in Polling:**
- Issue: Each page render binds new event handlers; no cleanup on page switch
- Files: `src/gui/web/js/pages/launcher.js` lines 53-56 (buttons bound on every render)
- Impact: Switching between pages and back creates duplicate handlers; old handlers still fire in background
- Safe modification: Add cleanup function to each page module (unregister listeners), call on page switch

**Hardcoded Translation Fallbacks:**
- Issue: Many places use `t('key') || 'fallback string'` instead of ensuring translations exist
- Files: `src/gui/web/js/pages/environments.js` lines 21, 193, 209-215, 239, 298
- Impact: If translation key missing, English fallback appears even if UI language is zh-TW; inconsistent UX
- Safe modification: Ensure all keys exist in both EN and ZH-TW translations, remove fallback chains

## Missing Critical Features

**No Keyboard Shortcuts:**
- Problem: Power users have no way to quickly navigate or trigger common actions
- Impact: Slower workflow, mouse-dependent, poor accessibility
- Blocks: Efficiency for power users, accessibility compliance

**No Undo/Redo:**
- Problem: Destructive operations (delete environment, restore snapshot) can't be undone
- Impact: User mistakes are permanent; not suitable for exploratory operations
- Blocks: Safe experimentation, safe testing

**No Operation Queue or Background Task Management:**
- Problem: User can't queue multiple operations; only one async operation allowed at a time
- Impact: Can't clone env A while cloning env B; no way to know what's running in background
- Blocks: Batch operations, efficient workflows

## Test Coverage Gaps

**No Bridge.js Unit Tests:**
- What's not tested: Promise resolution, error parsing, timeout handling, request ID generation, progress message parsing
- Files: `src/gui/web/js/bridge.js` (171 lines)
- Risk: Timeout edge cases, malformed JSON responses, race conditions in poll logic could fail silently
- Priority: High (critical infrastructure module)

**No App.js Modal/Toast/Progress Tests:**
- What's not tested: Modal lifecycle, button click handlers, progress panel state, toast animations
- Files: `src/gui/web/js/app.js` (310 lines)
- Risk: Modal bugs block all operations; progress panel state loss causes hung UI
- Priority: High

**No Page Module Integration Tests:**
- What's not tested: Environment creation flow, version switching, snapshot restore, plugin analysis workflows
- Files: `src/gui/web/js/pages/*.js` (1000+ lines combined)
- Risk: User workflows could break silently after refactoring
- Priority: Medium (can be caught manually, but should be automated)

**No i18n Tests:**
- What's not tested: Translation key coverage, placeholder replacement, language switching state
- Files: `src/gui/web/js/i18n.js` (353 lines)
- Risk: Missing translations cause key names to display instead of actual text
- Priority: Medium

**No E2E Tests for QWebChannel Integration:**
- What's not tested: Actual Python backend communication, message serialization/deserialization
- Risk: Frontend and backend can drift; breaks only discovered at runtime
- Priority: Medium (requires actual Qt/Python environment)

## Dependencies at Risk

**Hardcoded PyTorch CUDA Index:**
- Issue: `pytorch_index_url` in config.json is hardcoded to CUDA 12.4
- Files: `config.json` line 13
- Impact: Won't work with other CUDA versions; GPU users with cu118, cu121, or CPU-only will fail
- Recommendation: Make configurable in UI, detect or allow user selection of CUDA version

**No Explicit Version Pinning:**
- Issue: No package-lock.json or requirements-lock.txt detected
- Impact: Dependencies could update between environments, causing inconsistencies
- Recommendation: Lock all dependency versions in production configs

## Data Flow and State Issues

**Global State in Page Modules:**
- Issue: Each page module maintains global variables (selectedEnvName, selectedCommitHash, etc.)
- Files: `src/gui/web/js/pages/environments.js` line 67, `src/gui/web/js/pages/launcher.js` line 7, `src/gui/web/js/pages/versions.js` line 6
- Impact: State persists across page switches; selecting env in environments page affects launcher page; no way to reset
- Recommendation: Implement proper state manager (simple object or context), reset on page switch

**Modal State Not Cleared:**
- Issue: Modal overlay hidden with CSS but DOM not cleared; old modal content remains in DOM
- Files: `src/gui/web/js/app.js` lines 92-93 (just adds hidden class)
- Impact: Old event handlers might fire; memory leak if modals opened repeatedly
- Recommendation: Actually remove modal-container innerHTML on hideModal()

**No Request Deduplication:**
- Issue: User can click "Refresh" button multiple times; each click triggers new API call
- Files: All page modules with refresh buttons
- Impact: Multiple in-flight requests overwrite each other's results; flaky UI
- Recommendation: Disable buttons during requests, or implement request deduplication

---

*Concerns audit: 2026-04-06*
