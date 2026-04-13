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
