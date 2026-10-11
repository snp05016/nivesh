"""The conftest network guard blocks non-loopback connects and DNS (TEST-13)."""
import os
import socket

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ALLOW_NETWORK_TESTS") == "1", reason="network guard disabled by ALLOW_NETWORK_TESTS=1"
)


def test_external_dns_and_connect_blocked():
    with pytest.raises(RuntimeError, match="network blocked"):
        socket.create_connection(("example.com", 80), timeout=1)


def test_external_ip_connect_blocked():
    # TEST-NET-3 address: skips DNS, so this exercises the connect hook itself.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        with pytest.raises(RuntimeError, match="network blocked"):
            s.connect(("203.0.113.1", 80))
        with pytest.raises(RuntimeError, match="network blocked"):
            s.connect_ex(("203.0.113.1", 80))


def test_loopback_allowed_to_attempt():
    # Port 1 is closed: the guard lets the attempt through and the OS refuses it.
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", 1), timeout=1)
