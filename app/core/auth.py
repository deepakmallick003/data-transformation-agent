from __future__ import annotations

import hashlib
import hmac

from flask import Response as FlaskResponse

from app.core.config import Settings


AUTH_COOKIE_NAME = "data_transform_agent_auth"


def expected_auth_cookie_value(settings: Settings) -> str:
    payload = f"{settings.auth_username}\n{settings.auth_password}".encode("utf-8")
    secret = settings.resolved_auth_secret.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def is_authenticated_cookie(cookie_value: str | None, settings: Settings) -> bool:
    if not cookie_value:
        return False
    return hmac.compare_digest(cookie_value, expected_auth_cookie_value(settings))


def set_auth_cookie(response: FlaskResponse, settings: Settings) -> FlaskResponse:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        expected_auth_cookie_value(settings),
        httponly=True,
        samesite="Lax",
        secure=False,
        path="/",
    )
    return response


def clear_auth_cookie(response: FlaskResponse) -> FlaskResponse:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response
