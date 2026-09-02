"""Minimal, provider-neutral delivery for one-time account login codes."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


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
