# SSRF Prevention — URL Validation RAG Reference Document

<!-- RAG_METADATA
topic: security, ssrf, url-validation
library: python-stdlib (ipaddress, socket, urllib.parse)
version: Python 3.9+
python_min: 3.9
tags: ssrf, url-validation, security, private-ip, ipaddress, socket, fastapi
use_case: phase-7-subtask-3-auth-and-security
-->

## Overview

**Server-Side Request Forgery (SSRF)** is an attack where an attacker tricks the server into making HTTP requests to internal/private resources (e.g., `http://192.168.1.1/admin`, `http://169.254.169.254/` AWS metadata). The URL validator uses Python's standard library (`ipaddress`, `socket`, `urllib.parse`) — no external dependencies needed.

---

## Complete Implementation

```python
"""URL validation — prevents SSRF attacks by blocking private IP ranges."""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# RFC 1918 private ranges + special-use addresses
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918 private
    ipaddress.ip_network("172.16.0.0/12"),      # RFC 1918 private
    ipaddress.ip_network("192.168.0.0/16"),     # RFC 1918 private
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local (AWS metadata: 169.254.169.254)
    ipaddress.ip_network("0.0.0.0/8"),          # "This" network
    ipaddress.ip_network("100.64.0.0/10"),      # Shared address space (RFC 6598)
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1 (documentation)
    ipaddress.ip_network("198.18.0.0/15"),      # Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2 (documentation)
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3 (documentation)
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique local (private)
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("::/128"),             # IPv6 unspecified
]


class SSRFError(Exception):
    """Raised when a URL resolves to a blocked IP address."""


def validate_url(url: str) -> str:
    """Validate a URL is safe to fetch (SSRF prevention).

    Checks:
    1. Scheme is http or https.
    2. Hostname is present.
    3. Resolved IP is not in a private/internal range.

    Returns the validated URL string.
    Raises SSRFError if the URL is unsafe.
    """
    parsed = urlparse(url)

    # 1. Check scheme
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Unsupported scheme: {parsed.scheme!r}. Only http/https allowed.")

    # 2. Check hostname
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("Missing hostname in URL")

    # 3. Resolve hostname to IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise SSRFError(f"Cannot resolve hostname {hostname!r}: {e}")

    # 4. Check each resolved IP against blocked networks
    for _, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        for network in BLOCKED_NETWORKS:
            if ip in network:
                raise SSRFError(
                    f"URL resolves to blocked IP range: {ip} is in {network}"
                )

    logger.debug("URL validated safe: %s", url)
    return url
```

---

## Blocked IP Ranges Reference

| Network | Description | Example |
|---|---|---|
| `10.0.0.0/8` | RFC 1918 private | `10.0.0.1` |
| `172.16.0.0/12` | RFC 1918 private | `172.16.0.1` |
| `192.168.0.0/16` | RFC 1918 private | `192.168.1.1` |
| `127.0.0.0/8` | Loopback | `127.0.0.1`, `localhost` |
| `169.254.0.0/16` | Link-local / AWS metadata | `169.254.169.254` |
| `::1/128` | IPv6 loopback | `::1` |
| `fc00::/7` | IPv6 unique local | `fd00::1` |
| `fe80::/10` | IPv6 link-local | `fe80::1` |

---

## Usage in FastAPI

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.security.url_validator import SSRFError, validate_url

router = APIRouter()


class IngestRequest(BaseModel):
    url: str


@router.post("/api/v1/ingest")
async def ingest_url(request: IngestRequest):
    try:
        safe_url = validate_url(request.url)
    except SSRFError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Proceed with fetching safe_url
    ...
```

---

## DNS Rebinding Attack Prevention

DNS rebinding is an advanced SSRF variant where a hostname initially resolves to a public IP (passing validation) but later resolves to a private IP. To mitigate:

```python
import httpx

async def safe_fetch(url: str) -> str:
    """Fetch URL with SSRF protection — validates before AND after DNS resolution."""
    # Validate before fetching
    validate_url(url)
    
    # Use a custom transport that re-validates the resolved IP
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=False)
        # Don't follow redirects — they could redirect to internal IPs
        return response.text
```

---

## Testing the Validator

```python
import pytest
from src.security.url_validator import SSRFError, validate_url


def test_valid_public_url():
    url = validate_url("https://docs.python.org/3/")
    assert url == "https://docs.python.org/3/"


def test_blocks_private_ip():
    with pytest.raises(SSRFError, match="blocked IP range"):
        validate_url("http://192.168.1.1/secret")


def test_blocks_localhost():
    with pytest.raises(SSRFError, match="blocked IP range"):
        validate_url("http://127.0.0.1/admin")


def test_blocks_aws_metadata():
    with pytest.raises(SSRFError, match="blocked IP range"):
        validate_url("http://169.254.169.254/latest/meta-data/")


def test_blocks_ipv6_loopback():
    with pytest.raises(SSRFError, match="blocked IP range"):
        validate_url("http://[::1]/admin")


def test_blocks_ftp_scheme():
    with pytest.raises(SSRFError, match="Unsupported scheme"):
        validate_url("ftp://example.com/file")


def test_blocks_file_scheme():
    with pytest.raises(SSRFError, match="Unsupported scheme"):
        validate_url("file:///etc/passwd")


def test_blocks_missing_hostname():
    with pytest.raises(SSRFError):
        validate_url("http:///path")
```

---

## `urlparse` Reference

```python
from urllib.parse import urlparse

parsed = urlparse("https://example.com:8080/path?q=1#frag")
# parsed.scheme   = "https"
# parsed.netloc   = "example.com:8080"
# parsed.hostname = "example.com"   ← lowercase, no port
# parsed.port     = 8080
# parsed.path     = "/path"
# parsed.query    = "q=1"
# parsed.fragment = "frag"
```

---

## `socket.getaddrinfo` Reference

```python
import socket

results = socket.getaddrinfo("example.com", None)
# Returns list of tuples: (family, type, proto, canonname, sockaddr)
# sockaddr for IPv4: ("93.184.216.34", 0)
# sockaddr for IPv6: ("2606:2800:220:1:248:1893:25c8:1946", 0, 0, 0)

for family, type_, proto, canonname, sockaddr in results:
    ip = sockaddr[0]   # IP address string
```

---

## `ipaddress` Module Reference

```python
import ipaddress

# Create IP address object
ip = ipaddress.ip_address("192.168.1.1")

# Create network object
network = ipaddress.ip_network("192.168.0.0/16")

# Check membership
ip in network   # True

# Works with both IPv4 and IPv6
ipv6 = ipaddress.ip_address("::1")
loopback = ipaddress.ip_network("::1/128")
ipv6 in loopback   # True
```

---

## Common Pitfalls

1. **`localhost` resolves to `127.0.0.1`** — `socket.getaddrinfo("localhost", None)` returns `127.0.0.1`. The validator catches this via the `127.0.0.0/8` block.
2. **IPv6 in URLs** — IPv6 addresses in URLs use bracket notation: `http://[::1]/`. `urlparse` handles this correctly — `parsed.hostname` returns `::1` (without brackets).
3. **DNS resolution required** — The validator makes a DNS lookup for every URL. This adds latency. Cache results if needed.
4. **Redirect following** — Even after validating the initial URL, HTTP redirects could lead to internal IPs. Don't follow redirects, or re-validate after each redirect.
5. **`socket.gaierror`** — Raised when DNS resolution fails (hostname doesn't exist). Treat as invalid URL.
6. **`0.0.0.0`** — Maps to all interfaces on the local machine. Block it via `0.0.0.0/8`.

---

## Sources
- https://docs.python.org/3/library/ipaddress.html (Python ipaddress module)
- https://docs.python.org/3/library/socket.html#socket.getaddrinfo
- https://docs.python.org/3/library/urllib.parse.html#urllib.parse.urlparse
- https://owasp.org/www-community/attacks/Server_Side_Request_Forgery (OWASP SSRF)
- https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
