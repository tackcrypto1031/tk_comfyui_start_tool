"""Tests for Bridge.open_browser: LAN URL selection via running-list lookup.

open_browser is an async QWebChannel slot — it dispatches work to an
AsyncWorker (QThread) and stores the result in ``_result_queue`` keyed by the
request_id the caller supplied.  The helper below invokes the slot
synchronously (bypassing Qt's event loop) by substituting a shim for
``_run_async`` that calls the target function inline on the test thread.
"""
import json


def _make_bridge_with_running(running_entries):
    """Build a Bridge instance with a fake launcher.list_running()."""
    from src.gui.bridge import Bridge

    class FakeLauncher:
        def list_running(self):
            return running_entries

    b = Bridge.__new__(Bridge)  # bypass __init__ (avoids Qt setup)
    b.launcher = FakeLauncher()
    b._result_queue = {}
    b._progress_queue = {}
    b._workers = []

    # Run the worker function inline instead of on a real QThread.
    def _inline_run_async(request_id, fn, *args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            b._result_queue[request_id] = json.dumps(
                {"success": True, "data": result}, default=str, ensure_ascii=False
            )
        except Exception as e:  # pragma: no cover
            b._result_queue[request_id] = json.dumps({"error": str(e)})

    b._run_async = _inline_run_async
    return b


def _call_open_browser(bridge, port, request_id="test-req"):
    bridge.open_browser(request_id, port)
    raw = bridge._result_queue.get(request_id)
    assert raw is not None, "async worker did not produce a result"
    return json.loads(raw)


def test_open_browser_uses_lan_url_when_running_entry_has_it(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    bridge = _make_bridge_with_running([
        {"env_name": "e1", "port": 8188, "lan_url": "http://192.168.1.23:8188"}
    ])
    res = _call_open_browser(bridge, 8188)
    assert res.get("success") is True
    assert res.get("data", {}).get("success") is True
    assert opened == ["http://192.168.1.23:8188"]


def test_open_browser_falls_back_to_localhost_when_no_lan_url(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    bridge = _make_bridge_with_running([
        {"env_name": "e1", "port": 8188}
    ])
    res = _call_open_browser(bridge, 8188)
    assert res.get("success") is True
    assert opened == ["http://localhost:8188"]


def test_open_browser_falls_back_when_port_not_in_running_list(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    bridge = _make_bridge_with_running([])
    res = _call_open_browser(bridge, 8188)
    assert res.get("success") is True
    assert opened == ["http://localhost:8188"]
