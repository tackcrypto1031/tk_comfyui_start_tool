# LAN URL 正確開啟 — 設計文件

**Date:** 2026-04-13
**Status:** Draft → Approved pending review

## Problem

使用者開啟「監聽其他電腦」(listen_enabled) 後,預期「開啟瀏覽器」按鈕與自動開啟瀏覽器會帶到一個**別台電腦也能貼上的網址**。目前兩處都寫死 `http://localhost:{port}`:

1. `src/core/comfyui_launcher.py:233` — 啟動後自動開瀏覽器
2. `src/gui/bridge.py:421` — 手動「開啟瀏覽器」按鈕(運行列表、主畫面共用)

Toast 已正確顯示 LAN URL (`comfyui_launcher.py:246`),但使用者點按鈕後瀏覽器網址仍是 `localhost`,無法直接複製分享。

**誤解澄清**:`localhost` 與 `127.0.0.1` 皆為 loopback,兩者對 LAN 外連接性相同(都連不到)。真正讓其他電腦連進來的關鍵是 `--listen 0.0.0.0`(已正確實作)。此設計只解決「應開哪個網址」。

## Scope

**IN:**
- 當 `listen_enabled=true` 且綁定 IP 非 loopback(含空白→0.0.0.0)時,兩處開瀏覽器動作改開 `http://<LAN_IP>:<port>`
- 不影響 loopback 模式(預設)下的行為

**OUT:**
- 防火牆 / Windows Defender 設定(僅於驗收步驟文字提醒)
- 新的 UI 設定、Toast 樣式變更、i18n 新增

## Design

### 資料儲存

啟動 ComfyUI 時,在 `.comfyui.pid` JSON 多寫一個 `lan_url` 欄位(當且僅當監聽非 loopback 時):

```json
{ "pid": 1234, "port": 8188, "lan_url": "http://192.168.1.23:8188", ... }
```

此欄已於啟動回傳結果中計算 (`comfyui_launcher.py:246`),只是目前沒落盤。落盤後 `list_running()` 自然會帶回前端。

### 改動點

**1. `src/core/comfyui_launcher.py`**
- `start()`:寫入 pid file 時,若啟動參數含 `--listen` 且 IP 非 loopback,加入 `lan_url` 鍵。
- `_open_browser` 執行緒 (L224-235):若有 `lan_url` 用它,否則 `localhost`。

**2. `src/gui/bridge.py`**
- `open_browser(port)` (L417):查 `self.launcher.list_running()`,找到 `port` 匹配的 entry,有 `lan_url` 用它,否則 fallback `localhost`。簽名不動,前端零改動。

### 資料流

```
start(listen_enabled, ip)
   └─ build_launch_args → extra_args 含 --listen <ip>
   └─ 啟動 process
   └─ 計算 lan_url(非 loopback 時)
   └─ 寫入 .comfyui.pid(含 lan_url)   ← 新
   └─ _open_browser thread 用 lan_url ← 修
   └─ 回傳 {pid, port, lan_url?}

使用者點「開啟瀏覽器」
   └─ BridgeAPI.openBrowser(port)
   └─ bridge.open_browser(port)
       └─ launcher.list_running() 查 port → entry.lan_url   ← 新
       └─ webbrowser.open(lan_url or f"http://localhost:{port}")
```

### Loopback 判定

沿用 `launcher.js:813` 的定義:`127.0.0.1`、`localhost`、`::1`、開頭 `127.`。後端需同等判斷(`comfyui_launcher.py:245` 已有同規則,重用)。

## Tests

- `tests/test_core/test_comfyui_launcher.py`:start 帶 `--listen 0.0.0.0` → pid file 含 `lan_url`;帶 `--listen 127.0.0.1` 或無 `--listen` → 無 `lan_url`。
- `tests/test_gui/test_bridge.py`(若有):`open_browser(port)` 有 lan_url 時走 lan_url 分支;沒 lan_url 時 fallback localhost。可用 `monkeypatch` 替 `webbrowser.open` 捕獲參數。

## 手測驗收

1. 預設模式啟動 → 瀏覽器開 `localhost:8188`,運行列表按鈕亦同。
2. 開啟 listen(IP 空白)→ 啟動 → toast、auto-open、手動按鈕三者皆開 `http://<區網IP>:8188`。
3. **另一台電腦**於同網段打開該 URL,確認連得到 ComfyUI 介面。若連不到,檢查:
   - Windows 防火牆是否允許 Python / port 8188
   - 路由器是否有 AP 隔離
4. 關掉 listen 回到 loopback → 行為恢復為 localhost。

## Risks

- `list_running()` 在 `open_browser` 路徑被額外呼叫一次(掃 environments 目錄)。環境數 < 數十時成本可忽略。
- pid file schema 新增欄位,舊 pid file 讀起來 `lan_url` 為 None,`.get` 自然 fallback,相容。

## Version Bump

`VERSION.json` → 0.2.3,中英文說明:「修正監聽模式下開啟瀏覽器仍使用 localhost 的問題,改為開啟區網 IP 以便分享」。
