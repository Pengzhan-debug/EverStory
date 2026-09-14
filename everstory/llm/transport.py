"""Public-network-only transport for user-configurable model endpoints.

DNS answers are checked once and the connection is pinned to that IP, while
TLS SNI and certificate validation retain the original hostname. Redirects and
ambient proxy settings cannot bypass the endpoint policy.
"""

import ipaddress
import os
import socket
from urllib.parse import urlsplit, urlunsplit


def private_endpoints_allowed() -> bool:
    return os.getenv("LLM_ALLOW_PRIVATE_ENDPOINTS", "false").lower() in {"1", "true", "yes"}


def validate_endpoint(url: str):
    parsed = urlsplit(url)
    if (not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.scheme not in {"http", "https"}):
        raise ValueError("Invalid model endpoint URL.")
    port = parsed.port  # Also rejects invalid ports.
    if private_endpoints_allowed():
        return parsed
    if parsed.scheme != "https":
        raise ValueError("Public model endpoints must use HTTPS.")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Private model endpoints are disabled on this server.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and (not address.is_global or address.is_multicast):
        raise ValueError("Private model endpoints are disabled on this server.")
    return parsed


def post_completion(url: str, **kwargs):
    import requests
    from requests.adapters import HTTPAdapter

    parsed = validate_endpoint(url)
    session = requests.Session()
    session.trust_env = False
    kwargs["allow_redirects"] = False
    try:
        if private_endpoints_allowed():
            response = session.post(url, **kwargs)
        else:
            hostname = parsed.hostname.encode("idna").decode("ascii")
            addresses = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
            ips = [ipaddress.ip_address(entry[4][0]) for entry in addresses]
            if not ips or any(not ip.is_global or ip.is_multicast for ip in ips):
                raise ValueError("Model endpoint resolves to a non-public address.")
            ip = ips[0]
            host = f"[{ip}]" if ip.version == 6 else str(ip)
            netloc = f"{host}:{parsed.port or 443}"
            pinned_url = urlunsplit(("https", netloc, parsed.path, "", ""))
            adapter = HTTPAdapter()
            adapter.poolmanager.connection_pool_kw.update(server_hostname=hostname, assert_hostname=hostname)
            session.mount("https://", adapter)
            kwargs["headers"] = {**kwargs.get("headers", {}), "Host": parsed.netloc}
            response = session.post(pinned_url, **kwargs)
        if kwargs.get("stream"):
            close_response = response.close

            def close():
                try:
                    close_response()
                finally:
                    session.close()
            response.close = close
        else:
            session.close()
        return response
    except Exception:
        session.close()
        raise
