# Error Log Export — Design

## Summary

Add an "Export Log" button below the log output area in the launcher page. Clicking it opens a system file dialog for the user to choose a save path, then exports the full `comfyui.log` for the selected environment.

## Motivation

Users need to share ComfyUI error logs with external debugging tools or AI coding assistants to diagnose environment issues.

## Implementation

### Frontend (`launcher.js`)

- Add a button below `#launch-log` with icon `download` and i18n key `launch_export_log`
- On click: check environment is selected, then call `BridgeAPI.exportLog(envName)`
- Show toast on success, error, or cancellation

### Bridge API (`bridge.js`)

- Add `exportLog(envName)` method calling backend slot `export_log`

### Python Backend (`bridge.py`)

- Add `export_log` slot:
  1. Resolve `comfyui.log` path from environment directory
  2. If file doesn't exist, return error
  3. Open `QFileDialog.getSaveFileName()` with default filename `comfyui_log_{envName}_{timestamp}.log`
  4. Copy file to user-selected path
  5. Return success or failure

### i18n (`i18n.js`)

New keys:

| Key | EN | zh-TW |
|-----|----|-------|
| `launch_export_log` | Export Log | 匯出日誌 |
| `launch_export_success` | Log exported successfully. | 日誌匯出成功 |
| `launch_export_no_log` | No log file found for this environment. | 此環境尚無日誌檔案 |
| `launch_export_cancelled` | Export cancelled. | 已取消匯出 |

## Button Behavior

- Enabled whenever an environment is selected (regardless of running state)
- If no environment selected: toast prompt
- If log file doesn't exist: toast error
- If user cancels dialog: toast info
