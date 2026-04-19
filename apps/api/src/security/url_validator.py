"""URL validation — prevents SSRF attacks by blocking private IP ranges."""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# RFC 1918 and other private ranges
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


class SSRFError(Exception):
    """Raised when a URL resolves to a blocked IP address."""


def validate_url(url: str) -> str:
    """Validate a URL is safe to fetch.

    Checks:
    1. Scheme is http or https.
    2. Hostname is not empty.
    3. Resolved IP is not in a private/internal range.

    Returns the validated URL.
    Raises SSRFError if the URL is unsafe.
    """
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Unsupported scheme: {parsed.scheme}")

    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("Missing hostname")

    # Resolve hostname to IP
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise SSRFError(f"Cannot resolve hostname: {hostname}")

    for _, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        for network in BLOCKED_NETWORKS:
            if ip in network:
                raise SSRFError(
                    f"URL resolves to blocked IP range: {ip} ({network})"
                )

    logger.debug("URL validated: %s", url)
    return url
