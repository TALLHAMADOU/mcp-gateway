"""Shared SSRF guard.

Rejects URLs whose host resolves to a private, loopback, link-local, reserved
or unspecified address. Used by the REST proxy (``main.py``) and the MCP
``call_connector`` tool (``mcp_server.py``) so the policy lives in one place.
"""
import ipaddress
import socket
import urllib.parse


def is_upstream_url_allowed(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        for _fam, _type, _proto, _canon, sockaddr in socket.getaddrinfo(host, None):
            ip = sockaddr[0]
            try:
                addr = ipaddress.ip_address(ip)
            except Exception:
                return False
            if (addr.is_private or addr.is_loopback or addr.is_link_local
                    or addr.is_reserved or addr.is_unspecified):
                return False
        return True
    except Exception:
        return False
