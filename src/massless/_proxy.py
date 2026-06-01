"""Trusted-proxy header handling, matching uvicorn's default ProxyHeadersMiddleware.

uvicorn runs with ``proxy_headers=True`` and ``forwarded_allow_ips="127.0.0.1"`` by
default, so a request arriving from a trusted local proxy has its ``scheme`` taken from
a single ``X-Forwarded-Proto`` and its client address taken from a single
``X-Forwarded-For``. massless mirrors that here so ``request.scheme`` / ``is_secure()``
and ``REMOTE_ADDR`` match uvicorn+Django behind the same proxy. The trusted set comes
from ``settings.MASSLESS_FORWARDED_ALLOW_IPS`` (falling back to the ``FORWARDED_ALLOW_IPS``
env var, then ``"127.0.0.1"``); ``"*"`` trusts every peer.
"""

from __future__ import annotations

import ipaddress
import os
from functools import lru_cache

from django.conf import settings


def _parse_raw_hosts(value: str) -> list[str]:
    return [item.strip() for item in value.split(",")]


def _parse_host_port(value: str) -> tuple[str, int]:  # noqa: PLR0911
    """Split a forwarded host token into (host, port). Bare IPs, ``host:port``, and
    bracketed IPv6 ``[host]:port`` are understood; anything malformed keeps its port at 0."""
    if value.startswith("["):
        bracket_end = value.find("]")
        if bracket_end == -1:
            return value, 0
        host = value[1:bracket_end]
        remainder = value[bracket_end + 1 :]
        if not remainder:
            return host, 0
        if not remainder.startswith(":"):
            return value, 0
        try:
            return host, int(remainder[1:])
        except ValueError:
            return host, 0
    if value.count(":") == 1:
        host, port = value.rsplit(":", 1)
        try:
            return host, int(port)
        except ValueError:
            return value, 0
    return value, 0


class TrustedHosts:
    """Set membership for trusted proxies: bare IPs, CIDR networks, literals, or ``*``."""

    def __init__(self, trusted: str) -> None:
        self.always_trust = trusted in ("*", ["*"])
        self.literals: set[str] = set()
        self.addresses: set = set()
        self.networks: set = set()
        if self.always_trust:
            return
        for host in _parse_raw_hosts(trusted):
            if "/" in host:
                try:
                    self.networks.add(ipaddress.ip_network(host))
                except ValueError:
                    self.literals.add(host)
            else:
                try:
                    self.addresses.add(ipaddress.ip_address(host))
                except ValueError:
                    self.literals.add(host)

    def __contains__(self, host: str | None) -> bool:
        if self.always_trust:
            return True
        if not host:
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return host in self.literals
        if ip in self.addresses:
            return True
        return any(ip in net for net in self.networks)

    def get_trusted_client_address(self, x_forwarded_for: str) -> tuple[str, int]:
        """The first untrusted host from the right of the X-Forwarded-For chain."""
        hosts = _parse_raw_hosts(x_forwarded_for)
        if self.always_trust:
            return _parse_host_port(hosts[0])
        for host_port in reversed(hosts):
            host, port = _parse_host_port(host_port)
            if host not in self:
                return host, port
        return _parse_host_port(hosts[0])


@lru_cache(maxsize=8)
def _trusted_for(value: str) -> TrustedHosts:
    return TrustedHosts(value)


def _trusted_hosts() -> TrustedHosts:
    value = getattr(settings, "MASSLESS_FORWARDED_ALLOW_IPS", None)
    if value is None:
        value = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")
    if not isinstance(value, str):
        value = ",".join(value)
    return _trusted_for(value)


def forwarded_overrides(
    peer_host: str | None,
    headers: list[tuple[bytes, bytes]],
) -> tuple[str | None, tuple[str, int] | None]:
    """Return ``(scheme, client)`` overrides for a request, or ``(None, None)``.

    ``peer_host`` is the direct TCP peer's host (or ``None``); ``headers`` is the
    lower-cased ``list[(bytes, bytes)]``. Mirrors uvicorn: only honor the forwarded
    headers when the peer is trusted, and only when exactly one copy is present
    (so a spoofed second copy is ignored). ``scheme`` is ``"http"``/``"https"`` or
    ``None``; ``client`` is ``(host, port)`` or ``None``.
    """
    if peer_host is None:
        return None, None
    trusted = _trusted_hosts()
    if peer_host not in trusted:
        return None, None
    proto_values = []
    for_values = []
    for name, value in headers:
        if name == b"x-forwarded-proto":
            proto_values.append(value)
        elif name == b"x-forwarded-for":
            for_values.append(value)
    scheme = None
    if len(proto_values) == 1:
        candidate = proto_values[0].decode("latin1").strip()
        if candidate in ("http", "https"):
            scheme = candidate
    client = None
    if len(for_values) == 1:
        host, port = trusted.get_trusted_client_address(for_values[0].decode("latin1"))
        if host:
            client = (host, port)
    return scheme, client
