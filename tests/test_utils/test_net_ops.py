import socket
from unittest.mock import patch, MagicMock
from src.utils.net_ops import get_local_lan_ip


def test_get_local_lan_ip_uses_udp_probe():
    fake_sock = MagicMock()
    fake_sock.getsockname.return_value = ("192.168.1.42", 12345)
    with patch("socket.socket", return_value=fake_sock):
        assert get_local_lan_ip() == "192.168.1.42"
    fake_sock.connect.assert_called_once_with(("8.8.8.8", 80))
    fake_sock.close.assert_called_once()


def test_get_local_lan_ip_falls_back_on_oserror():
    fake_sock = MagicMock()
    fake_sock.connect.side_effect = OSError("no route")
    with patch("socket.socket", return_value=fake_sock):
        assert get_local_lan_ip() == "127.0.0.1"
    fake_sock.close.assert_called_once()
