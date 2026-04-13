# LAN URL Browser Open Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 當使用者啟用監聽 (listen_enabled) 且綁定非 loopback IP 時,「開啟瀏覽器」動作(自動與手動)改開 `http://<區網IP>:<port>`,而非 `http://localhost:<port>`。

**Architecture:** 在 `start()` 計算 `lan_url` 後順手落盤至 `.comfyui.pid` JSON;`_open_browser` thread 與 `bridge.open_browser()` 都從該來源取 URL,有則開 LAN,無則 fallback localhost。前端與 i18n 零改動,toast 行為不變。

**Tech Stack:** Python 3.10+, PySide6, pytest, `src/core/comfyui_launcher.py`, `src/gui/bridge.py`, `.comfyui.pid` JSON file state。

---

## File Structure

- Modify: `src/core/comfyui_launcher.py` — pid file 寫入 `lan_url`;`_open_browser` thread 改開 `lan_url`;抽出 loopback 判定成 module 級函式供 bridge 重用
- Modify: `src/gui/bridge.py` — `open_browser(port)` 從 `list_running()` 查 `lan_url`
- Modify: `VERSION.json` — bump 0.2.2 → 0.2.3
- Test: `tests/test_core/test_comfyui_launcher.py` — 新增 lan_url 落盤測試
- Test: `tests/test_gui/test_bridge_open_browser.py` — 新增(或附加至現有)open_browser 路由測試

---

### Task 1: 抽出 loopback IP 判定函式

**Files:**
- Modify: `src/core/comfyui_launcher.py:245`

- [ ] **Step 1: 在 `comfyui_launcher.py` 模組頂層(imports 之後、class 之前)新增 helper**

```python
def _is_loopback_ip(ip: str) -> bool:
    """Return True if ip is a loopback address (no LAN reachability)."""
    if not ip:
        return False
    return ip in ("127.0.0.1", "localhost", "::1") or ip.startswith("127.")
```

- [ ] **Step 2: 重構 `start()` 內原本的字串比對(約 L245)**

把:
```python
if listen_ip and listen_ip not in ("127.0.0.1", "localhost", "::1"):
```
改成:
```python
if listen_ip and not _is_loopback_ip(listen_ip):
```

- [ ] **Step 3: 跑既有測試確認沒打破東西**

Run: `pytest tests/test_core/test_comfyui_launcher.py -v`
Expected: 全過(行為未變)。

- [ ] **Step 4: Commit**

```bash
git add src/core/comfyui_launcher.py
git commit -m "refactor(launcher): extract _is_loopback_ip helper"
```

---

### Task 2: 把 lan_url 落盤到 .comfyui.pid(先寫失敗測試)

**Files:**
- Test: `tests/test_core/test_comfyui_launcher.py`

- [ ] **Step 1: 新增失敗測試 — listen 0.0.0.0 時 pid file 應含 lan_url**

在 `tests/test_core/test_comfyui_launcher.py` 末尾追加:

```python
def test_start_writes_lan_url_to_pid_file_when_listen_non_loopback(tmp_path, monkeypatch):
    """When --listen is non-loopback, .comfyui.pid must include lan_url."""
    from src.core.comfyui_launcher import ComfyUILauncher
    import json

    # Arrange: fake env dir with minimal ComfyUI skeleton
    envs_dir = tmp_path / "environments"
    env_dir = envs_dir / "e1"
    (env_dir / "ComfyUI").mkdir(parents=True)
    (env_dir / "venv" / "Scripts").mkdir(parents=True)
    (env_dir / "ComfyUI" / "main.py").write_text("# stub")

    launcher = ComfyUILauncher(environments_dir=str(envs_dir), config={"auto_open_browser": False})
    launcher._post_spawn_sanity_delay = 0

    # Stub out heavy ops
    monkeypatch.setattr("src.core.comfyui_launcher.pip_ops.get_venv_python", lambda p: "python")
    monkeypatch.setattr("src.core.comfyui_launcher.get_local_lan_ip", lambda: "192.168.1.23")

    class FakeProc:
        pid = 4242
        def poll(self): return None
    monkeypatch.setattr(
        "src.core.comfyui_launcher.process_manager.start_process",
        lambda *a, **kw: FakeProc()
    )
    monkeypatch.setattr(
        "src.core.comfyui_launcher.process_manager.is_port_in_use",
        lambda p: False
    )
    monkeypatch.setattr(
        "src.core.comfyui_launcher.process_manager.find_available_port",
        lambda p, exclude=None: p
    )
    monkeypatch.setattr(launcher, "_ensure_manager_ready", lambda env_dir: None)

    # Act
    result = launcher.start("e1", port=8188, extra_args=["--listen", "0.0.0.0"], auto_open=False)

    # Assert return value
    assert result["lan_url"] == "http://192.168.1.23:8188"

    # Assert pid file on disk
    pid_data = json.loads((env_dir / ".comfyui.pid").read_text())
    assert pid_data["lan_url"] == "http://192.168.1.23:8188"


def test_start_omits_lan_url_when_listen_loopback(tmp_path, monkeypatch):
    """When --listen is loopback (or absent), pid file must not contain lan_url."""
    from src.core.comfyui_launcher import ComfyUILauncher
    import json

    envs_dir = tmp_path / "environments"
    env_dir = envs_dir / "e1"
    (env_dir / "ComfyUI").mkdir(parents=True)
    (env_dir / "venv" / "Scripts").mkdir(parents=True)
    (env_dir / "ComfyUI" / "main.py").write_text("# stub")

    launcher = ComfyUILauncher(environments_dir=str(envs_dir), config={"auto_open_browser": False})
    launcher._post_spawn_sanity_delay = 0

    monkeypatch.setattr("src.core.comfyui_launcher.pip_ops.get_venv_python", lambda p: "python")

    class FakeProc:
        pid = 4242
        def poll(self): return None
    monkeypatch.setattr("src.core.comfyui_launcher.process_manager.start_process", lambda *a, **kw: FakeProc())
    monkeypatch.setattr("src.core.comfyui_launcher.process_manager.is_port_in_use", lambda p: False)
    monkeypatch.setattr("src.core.comfyui_launcher.process_manager.find_available_port", lambda p, exclude=None: p)
    monkeypatch.setattr(launcher, "_ensure_manager_ready", lambda env_dir: None)

    result = launcher.start("e1", port=8188, extra_args=["--listen", "127.0.0.1"], auto_open=False)
    assert "lan_url" not in result
    pid_data = json.loads((env_dir / ".comfyui.pid").read_text())
    assert "lan_url" not in pid_data
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_core/test_comfyui_launcher.py::test_start_writes_lan_url_to_pid_file_when_listen_non_loopback -v`
Expected: FAIL — pid file 尚無 `lan_url` 欄位(第一個測試 AssertionError on `pid_data["lan_url"]`)。第二個測試可能先過,不代表實作完成。

> 注意:若既有測試因 monkeypatch 目標不同而需調整,保留測試核心斷言,把 stub 對齊實際模組行為。

---

### Task 3: 把 lan_url 寫入 pid file,並讓 _open_browser 使用

**Files:**
- Modify: `src/core/comfyui_launcher.py:214-247`

- [ ] **Step 1: 在 `start()` 裡把 lan_url 計算提前到 pid file 寫入之前**

把現行 L212-247 區段(從 `# Save PID` 到 `return result`)替換為:

```python
        # Compute lan_url up front so we can embed it in the pid file and
        # pass it to the auto-open-browser thread. Only set when listening on
        # a non-loopback IP; loopback mode keeps localhost.
        listen_ip = None
        if extra_args:
            try:
                idx = extra_args.index("--listen")
                listen_ip = extra_args[idx + 1]
            except (ValueError, IndexError):
                listen_ip = None
        lan_url = None
        if listen_ip and not _is_loopback_ip(listen_ip):
            lan_url = f"http://{get_local_lan_ip()}:{port}"

        # Save PID (still in "starting" state — get_status() promotes it to
        # "running" once the process has actually bound the socket).
        pid_payload = {
            "pid": proc.pid,
            "port": port,
            "status": "starting",
            "started_at": time.time(),
        }
        if lan_url:
            pid_payload["lan_url"] = lan_url
        pid_file.write_text(json.dumps(pid_payload))

        # Auto-open browser after a short delay
        if auto_open and self.config.get("auto_open_browser", True):
            import threading
            open_target = lan_url or f"http://localhost:{port}"
            def _open_browser():
                import time
                import webbrowser
                for _ in range(30):
                    time.sleep(2)
                    if not process_manager.is_process_running(proc.pid):
                        return
                    if self.health_check(port, timeout=2):
                        webbrowser.open(open_target)
                        return
            threading.Thread(target=_open_browser, daemon=True).start()

        result = {"pid": proc.pid, "port": port, "env_name": env_name}
        if lan_url:
            result["lan_url"] = lan_url
        return result
```

- [ ] **Step 2: 跑 Task 2 新測試確認通過**

Run: `pytest tests/test_core/test_comfyui_launcher.py -k "lan_url" -v`
Expected: 兩個測試皆 PASS。

- [ ] **Step 3: 跑整個 launcher 測試確認無回歸**

Run: `pytest tests/test_core/test_comfyui_launcher.py -v`
Expected: 全過。

- [ ] **Step 4: Commit**

```bash
git add src/core/comfyui_launcher.py tests/test_core/test_comfyui_launcher.py
git commit -m "feat(launcher): persist lan_url in pid file and use for auto-open"
```

---

### Task 4: 讓 bridge.open_browser 在 LAN 模式下開 LAN URL(失敗測試)

**Files:**
- Test: `tests/test_gui/test_bridge_open_browser.py` (新建)

- [ ] **Step 1: 確認 tests/test_gui/ 是否存在**

Run: `ls tests/test_gui 2>/dev/null || echo MISSING`

若 MISSING,建立:
```bash
mkdir -p tests/test_gui && touch tests/test_gui/__init__.py
```

- [ ] **Step 2: 新建 `tests/test_gui/test_bridge_open_browser.py`**

```python
"""Tests for Bridge.open_browser: LAN URL selection via running-list lookup."""
import json


def _make_bridge_with_running(running_entries):
    """Build a Bridge instance with a fake launcher.list_running()."""
    from src.gui.bridge import Bridge

    class FakeLauncher:
        def list_running(self):
            return running_entries

    b = Bridge.__new__(Bridge)  # bypass __init__ (avoids Qt setup)
    b.launcher = FakeLauncher()
    return b


def test_open_browser_uses_lan_url_when_running_entry_has_it(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    bridge = _make_bridge_with_running([
        {"env_name": "e1", "port": 8188, "lan_url": "http://192.168.1.23:8188"}
    ])
    res = json.loads(bridge.open_browser(8188))
    assert res == {"success": True}
    assert opened == ["http://192.168.1.23:8188"]


def test_open_browser_falls_back_to_localhost_when_no_lan_url(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    bridge = _make_bridge_with_running([
        {"env_name": "e1", "port": 8188}
    ])
    res = json.loads(bridge.open_browser(8188))
    assert res == {"success": True}
    assert opened == ["http://localhost:8188"]


def test_open_browser_falls_back_when_port_not_in_running_list(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    bridge = _make_bridge_with_running([])
    res = json.loads(bridge.open_browser(8188))
    assert res == {"success": True}
    assert opened == ["http://localhost:8188"]
```

- [ ] **Step 3: 跑測試確認失敗(localhost fallback 可能通過,lan_url 測試必失敗)**

Run: `pytest tests/test_gui/test_bridge_open_browser.py -v`
Expected: `test_open_browser_uses_lan_url_when_running_entry_has_it` FAIL — 目前實作寫死 localhost。

---

### Task 5: 實作 bridge.open_browser 改走 list_running lookup

**Files:**
- Modify: `src/gui/bridge.py:416-424`

- [ ] **Step 1: 替換 `open_browser` 方法**

把 L416-424:
```python
    @Slot(int, result=str)
    def open_browser(self, port):
        """Open browser to localhost:<port>."""
        import webbrowser
        try:
            webbrowser.open(f"http://localhost:{port}")
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"error": str(e)})
```

改成:
```python
    @Slot(int, result=str)
    def open_browser(self, port):
        """Open browser to the running env's URL.

        If the running env was started with --listen on a non-loopback IP,
        list_running() reports a lan_url — we open that so the address bar
        shows an IP another machine can reach. Otherwise fall back to
        localhost.
        """
        import webbrowser
        try:
            target = f"http://localhost:{port}"
            try:
                for entry in self.launcher.list_running() or []:
                    if entry.get("port") == port and entry.get("lan_url"):
                        target = entry["lan_url"]
                        break
            except Exception:
                pass  # any lookup error → keep localhost fallback
            webbrowser.open(target)
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"error": str(e)})
```

- [ ] **Step 2: 跑 Task 4 測試確認通過**

Run: `pytest tests/test_gui/test_bridge_open_browser.py -v`
Expected: 三個測試全 PASS。

- [ ] **Step 3: 跑完整測試套件確認無回歸**

Run: `pytest`
Expected: 全過。

- [ ] **Step 4: Commit**

```bash
git add src/gui/bridge.py tests/test_gui/test_bridge_open_browser.py tests/test_gui/__init__.py
git commit -m "feat(bridge): open LAN URL when env is listening on non-loopback"
```

---

### Task 6: Bump VERSION.json

**Files:**
- Modify: `VERSION.json`

- [ ] **Step 1: 讀取當前 VERSION.json**

Run: `cat VERSION.json`

- [ ] **Step 2: 更新版本至 0.2.3,加入中英文說明**

把 version 欄位改為 `"0.2.3"`,`release_notes` 改為 `"修正監聽模式下開啟瀏覽器仍使用 localhost 的問題"`,並在 `changes` 陣列最前面插入該條目,`changes_i18n["zh-TW"]` 同;`changes_i18n["en"]` 加入英文版 `"Fixed: browser now opens LAN URL (not localhost) when listen mode is enabled, so the address bar shows an IP other machines can reach."`。

保留 `min_python` 及其他既有欄位。

- [ ] **Step 3: 跑 pytest 確認沒壞**

Run: `pytest`
Expected: 全過。

- [ ] **Step 4: Commit**

```bash
git add VERSION.json
git commit -m "chore: bump version to 0.2.3 for LAN URL browser open fix"
```

---

### Task 7: 手測驗收(GUI 必測)

**Files:** 無 — 僅操作驗證

- [ ] **Step 1: 啟動 launcher**

Run: `pythonw launcher.py`

- [ ] **Step 2: Loopback 模式迴歸**

確保「開啟監聽」**未勾選**,啟動任一環境。驗證:
- Toast 顯示啟動成功,**不顯示** LAN URL toast
- 自動開啟的瀏覽器網址為 `http://localhost:<port>/`
- 關閉瀏覽器後,點主畫面「開啟瀏覽器」,網址仍為 `http://localhost:<port>/`
- 運行列表的「開啟瀏覽器」亦為 `http://localhost:<port>/`
停止環境。

- [ ] **Step 3: LAN 模式**

勾選「開啟監聽」(IP 欄留白),通過確認 modal 後啟動。驗證:
- Toast 顯示 LAN URL(`http://<區網IP>:<port>`)
- 自動開啟的瀏覽器網址為 `http://<區網IP>:<port>/`
- 手動「開啟瀏覽器」與運行列表的按鈕皆開同一個區網 URL

- [ ] **Step 4: 另一台電腦連線驗證**

同網段另一台電腦打開剛才的 LAN URL。應看到 ComfyUI 介面。若失敗:
- 檢查 Windows 防火牆:允許 Python 或 port 8188
- 檢查路由器是否有 AP 隔離 / 訪客網路隔離
- 這不是程式 bug,記入 README 補充(本 plan 不處理)

- [ ] **Step 5: 若以上皆通過,合併 / push**

報告結果給使用者,交由他決定是否 merge + push。

---

## Self-Review

**Spec coverage:**
- 落盤 lan_url 至 pid file → Task 3 ✓
- `_open_browser` thread 改用 lan_url → Task 3 ✓
- `bridge.open_browser` 查 list_running → Task 5 ✓
- Loopback 判定 helper → Task 1 ✓
- 單元測試覆蓋 launcher 與 bridge → Task 2, 4 ✓
- 手測步驟(含防火牆提醒)→ Task 7 ✓
- VERSION.json bump → Task 6 ✓

**Placeholder scan:** 每個 step 都有具體檔案路徑、程式碼區塊或指令,無 TBD/TODO。

**Type consistency:** `lan_url` 欄位 key 全程一致;pid file schema 只新增欄位;`_is_loopback_ip` 在 Task 1 定義後於 Task 3 被引用。
