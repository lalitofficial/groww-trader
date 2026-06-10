from __future__ import annotations

from contextlib import redirect_stdout
import io
from typing import Any

from .config import GrowwSettings

try:
    from growwapi import GrowwAPI
except ImportError:  # pragma: no cover - only used by live Groww calls
    GrowwAPI = None

try:
    import pyotp
except ImportError:  # pragma: no cover - only used when optional TOTP flow is configured
    pyotp = None


class GrowwConfigError(RuntimeError):
    """Raised when Groww credentials are missing or contradictory."""


_ACCESS_TOKEN_CACHE: dict[str, str] = {}
_CLIENT_CACHE: dict[str, GrowwAPI] = {}


def create_groww_client(settings: GrowwSettings) -> GrowwAPI:
    if GrowwAPI is None:
        raise GrowwConfigError("Install growwapi to use live Groww API calls.")
    token = get_access_token(settings)
    if token in _CLIENT_CACHE:
        return _CLIENT_CACHE[token]
    with redirect_stdout(io.StringIO()):
        client = GrowwAPI(token)
    _CLIENT_CACHE[token] = client
    return client


def get_access_token(settings: GrowwSettings) -> str:
    if settings.access_token:
        return settings.access_token

    cache_key = "|".join(
        value or ""
        for value in (
            settings.api_key,
            settings.api_secret,
            settings.totp_token,
            settings.totp_secret,
        )
    )
    if cache_key in _ACCESS_TOKEN_CACHE:
        return _ACCESS_TOKEN_CACHE[cache_key]

    if settings.has_api_secret_flow and settings.has_totp_flow:
        raise GrowwConfigError(
            "Set either GROWW_API_KEY/GROWW_API_SECRET or "
            "GROWW_TOTP_TOKEN/GROWW_TOTP_SECRET, not both."
        )

    if settings.has_api_secret_flow:
        if GrowwAPI is None:
            raise GrowwConfigError("Install growwapi to generate a Groww access token.")
        token = GrowwAPI.get_access_token(
            api_key=settings.api_key,
            secret=settings.api_secret,
        )
        _ACCESS_TOKEN_CACHE[cache_key] = token
        return token

    if settings.has_totp_flow:
        if GrowwAPI is None:
            raise GrowwConfigError("Install growwapi to generate a Groww access token.")
        if pyotp is None:
            raise GrowwConfigError("Install pyotp to use GROWW_TOTP_TOKEN/GROWW_TOTP_SECRET.")
        totp = pyotp.TOTP(settings.totp_secret).now()
        token = GrowwAPI.get_access_token(api_key=settings.totp_token, totp=totp)
        _ACCESS_TOKEN_CACHE[cache_key] = token
        return token

    raise GrowwConfigError(
        "Missing Groww credentials. Fill .env with GROWW_ACCESS_TOKEN, "
        "GROWW_API_KEY/GROWW_API_SECRET, or GROWW_TOTP_TOKEN/GROWW_TOTP_SECRET."
    )


def groww_constant(client: GrowwAPI, prefix: str, value: str) -> Any:
    name = f"{prefix}_{value.strip().upper()}"
    if not hasattr(client, name):
        raise GrowwConfigError(f"Groww SDK does not expose constant {name}.")
    return getattr(client, name)
