"""
Resolve the real client IP behind reverse proxies (Cloudflare, Traefik, nginx).

When the app sits behind Cloudflare orange-cloud, ``request.remote_addr`` is often a
Cloudflare edge address (e.g. 172.70.x.x). The visitor IP is in ``CF-Connecting-IP``.
"""

from __future__ import annotations

import ipaddress
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Request

# Published Cloudflare IPv4 ranges (https://www.cloudflare.com/ips-v4)
_CLOUDFLARE_IPV4_NETS: tuple[ipaddress.IPv4Network, ...] = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "108.162.192.0/18",
        "131.0.72.0/22",
        "141.101.64.0/18",
        "162.158.0.0/15",
        "172.64.0.0/13",
        "173.245.48.0/20",
        "188.114.96.0/20",
        "190.93.240.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
    )
)


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _normalize_ip(ip_raw: str | None) -> str | None:
    raw = (ip_raw or "").strip()
    if not raw:
        return None
    if raw in ("::1", "0:0:0:0:0:0:0:1"):
        return "127.0.0.1"
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def _is_cloudflare_edge(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv4Address):
        return any(ip in net for net in _CLOUDFLARE_IPV4_NETS)
    return False


def _trust_proxy_headers(remote_ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if remote_ip.is_private or remote_ip.is_loopback or remote_ip.is_link_local:
        return True
    if _truthy_env("TRUST_PROXY"):
        return True
    if _is_cloudflare_edge(remote_ip):
        return True
    return False


def resolve_client_ip(req: Request) -> str:
    """
    Return the best-effort visitor IP for logging, quotas, and audit rows.

    Order when behind a trusted proxy hop: ``CF-Connecting-IP``, first ``X-Forwarded-For``,
    ``X-Real-IP``, else ``remote_addr``.
    """
    remote = _normalize_ip(req.remote_addr)
    if remote is None:
        return "unknown"

    try:
        remote_ip = ipaddress.ip_address(remote)
    except ValueError:
        return remote

    if not _trust_proxy_headers(remote_ip):
        return remote

    cf_ip = _normalize_ip(req.headers.get("CF-Connecting-IP"))
    if cf_ip:
        return cf_ip

    xff = (req.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        xff_ip = _normalize_ip(first)
        if xff_ip:
            return xff_ip

    real_ip = _normalize_ip(req.headers.get("X-Real-IP"))
    if real_ip:
        return real_ip

    return remote
