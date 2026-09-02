"""Minimal, provider-neutral delivery for one-time account login codes."""

from __future__ import annotations

import os
import smtplib
import json
from email.message import EmailMessage
from urllib.request import Request, urlopen


def email_delivery_status() -> dict[str, object]:
    """Return a browser-safe readiness summary without exposing credentials."""
    mode = os.getenv("AUTH_EMAIL_MODE", "disabled").strip().lower()
    if mode == "development":
        return {"mode": mode, "configured": True}
    if mode == "smtp":
        configured = bool(
            os.getenv("AUTH_SMTP_HOST", "").strip()
            and os.getenv("AUTH_SMTP_FROM", "").strip()
        )
        return {"mode": mode, "configured": configured}
    if mode == "resend":
        configured = bool(
            os.getenv("AUTH_RESEND_API_KEY", "").strip()
            and os.getenv("AUTH_EMAIL_FROM", "").strip()
        )
        return {"mode": mode, "configured": configured}
    return {"mode": "disabled", "configured": False}


def deliver_login_code(email: str, code: str, locale: str = "en") -> bool:
    """Deliver a code and return whether development UI may reveal it.

    Development mode performs no network I/O and reveals the code only when
    AUTH_DEV_EXPOSE_CODE is explicitly enabled. SMTP mode never returns it.
    """

    mode = os.getenv("AUTH_EMAIL_MODE", "disabled").strip().lower()
    if mode == "development":
        return os.getenv("AUTH_DEV_EXPOSE_CODE", "false").lower() in {
            "1",
            "true",
            "yes",
        }
    if mode == "resend":
        api_key = os.getenv("AUTH_RESEND_API_KEY", "").strip()
        sender = os.getenv("AUTH_EMAIL_FROM", "").strip()
        if not api_key or not sender:
            raise RuntimeError("Resend API key and sender are required")
        chinese = locale == "zh-CN"
        payload = json.dumps(
            {
                "from": sender,
                "to": [email],
                "subject": "EverStory 登录验证码" if chinese else "EverStory sign-in code",
                "text": (
                    f"你的 EverStory 验证码是：{code}\n验证码 10 分钟内有效。\n"
                    if chinese
                    else f"Your EverStory verification code is: {code}\nIt expires in 10 minutes.\n"
                ),
            }
        ).encode()
        request = Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "EverStory/1.4",
            },
            method="POST",
        )
        with urlopen(request, timeout=10) as response:  # nosec B310: fixed HTTPS host
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Resend rejected the email: HTTP {response.status}")
        return False
    if mode != "smtp":
        raise RuntimeError("email login is not configured")

    host = os.getenv("AUTH_SMTP_HOST", "").strip()
    sender = os.getenv("AUTH_SMTP_FROM", "").strip()
    if not host or not sender:
        raise RuntimeError("SMTP host and sender are required")
    port = int(os.getenv("AUTH_SMTP_PORT", "587"))
    username = os.getenv("AUTH_SMTP_USERNAME", "").strip()
    password = os.getenv("AUTH_SMTP_PASSWORD", "")
    use_ssl = os.getenv("AUTH_SMTP_SSL", "false").lower() in {"1", "true", "yes"}
    use_tls = os.getenv("AUTH_SMTP_TLS", "true").lower() in {"1", "true", "yes"}

    chinese = locale == "zh-CN"
    message = EmailMessage()
    message["From"] = sender
    message["To"] = email
    message["Subject"] = "EverStory 登录验证码" if chinese else "EverStory sign-in code"
    message.set_content(
        (
            f"你的 EverStory 验证码是：{code}\n验证码 10 分钟内有效。\n"
            if chinese
            else f"Your EverStory verification code is: {code}\nIt expires in 10 minutes.\n"
        )
    )

    smtp_type = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_type(host, port, timeout=10) as client:
        if use_tls and not use_ssl:
            client.starttls()
        if username:
            client.login(username, password)
        client.send_message(message)
    return False
