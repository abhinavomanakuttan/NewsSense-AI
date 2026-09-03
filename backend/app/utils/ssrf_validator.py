"""SSRF (Server-Side Request Forgery) protection and URL validation module.

Validates external news source URLs before HTTP requests are initiated, preventing
accidental or malicious requests to private, loopback, link-local, or internal cloud IP ranges.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SSRFValidationError(ValueError):
    """Raised when a target URL fails SSRF security checks."""


# Commonly targeted internal hostnames and cloud metadata endpoints
BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",  # AWS / GCP / Azure Instance Metadata Service
    "169.254.169.253",
    "::1",
    "[::1]",
    "metadata.google.internal",
}


def is_ip_forbidden(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to a private, loopback, link-local, or forbidden range."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url_ssrf(url: str, allow_private: bool = False) -> str:
    """Validate a URL against SSRF vulnerabilities.

    Parameters
    ----------
    url : str
        The URL to validate.
    allow_private : bool
        If True, skip private IP checks (intended only for local unit testing environments).

    Returns
    -------
    str
        The validated URL.

    Raises
    ------
    SSRFValidationError
        If the scheme is non-HTTP/HTTPS or resolves to a restricted IP space.
    """
    if not url or not isinstance(url, str):
        raise SSRFValidationError("URL must be a non-empty string")

    url_str = url.strip()
    try:
        parsed = urlparse(url_str)
    except Exception as exc:
        raise SSRFValidationError(f"Invalid URL structure: {exc}") from exc

    if parsed.scheme not in ("http", "https"):
        raise SSRFValidationError(f"Invalid scheme '{parsed.scheme}': only http and https are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("URL missing hostname")

    hostname_lower = hostname.lower()

    if allow_private:
        return url_str

    if hostname_lower in BLOCKED_HOSTNAMES:
        raise SSRFValidationError(f"Access to blocked internal hostname '{hostname}' is forbidden")

    # Check if the hostname itself is an IP literal
    is_ip = False
    try:
        ip_obj = ipaddress.ip_address(hostname_lower)
        is_ip = True
    except (ValueError, Exception):
        is_ip = False

    if is_ip:
        if is_ip_forbidden(ip_obj):
            raise SSRFValidationError(f"Access to private/internal IP '{ip_obj}' is forbidden")
        return url_str

    # Resolve DNS to check resulting IP addresses
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(hostname_lower, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        # If DNS resolution fails, let higher-level fetcher handle unreachable domain
        logger.debug("DNS resolution for %s failed during SSRF check: %s", hostname, exc)
        return url_str

    for family, socktype, proto, canonname, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if is_ip_forbidden(ip_obj):
                raise SSRFValidationError(
                    f"Domain '{hostname}' resolves to forbidden internal IP address '{ip_str}'"
                )
        except ValueError:
            continue

    return url_str
