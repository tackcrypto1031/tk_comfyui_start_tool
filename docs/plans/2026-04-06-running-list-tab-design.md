# Launcher Running List Tab Design

## Overview

Add tab switching to the Launcher page: "Launcher" (existing) + "Running List" (new).
Shows all running ComfyUI instances with port, PID, version, and quick actions.

## Default Tab Logic

1. On page enter, call `BridgeAPI.listRunning()`
2. If running instances exist → show "Running List" tab
3. If none → show "Launcher" tab

## Running List UI

Table with columns:
- Environment name
- Port (clickable, opens browser via Python `webbrowser.open`)
- PID
- Version (branch/commit from env_meta.json)
- Actions: "Open Browser" + "Stop"

Empty state: "No running environments"

## Data

`list_running` expanded to include `branch` and `commit` from env_meta.json.

## Files to Change

1. `comfyui_launcher.py` — expand `list_running` return with branch/commit
2. `bridge.py` — add `open_browser(port)` slot
3. `bridge.js` — add `openBrowser` API
4. `launcher.js` — refactor to tab architecture, add running list tab
5. i18n files — add translation keys
