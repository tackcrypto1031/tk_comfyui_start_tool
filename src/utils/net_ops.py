"""Network helpers."""
import socket


def get_local_lan_ip() -> str:
    """Return the IPv4 of the interface that would reach the public internet.

    Uses a UDP connect (no packet actually sent) to pick the OS's default-route
    interface. Falls back to 127.0.0.1 if the probe fails.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
