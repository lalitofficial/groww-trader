from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class GrowwSettings:
    access_token: str | None
    api_key: str | None
    api_secret: str | None
    totp_token: str | None
    totp_secret: str | None
    default_exchange: str
    default_segment: str

    @property
    def has_api_secret_flow(self) -> bool:
        return bool(self.api_key and self.api_secret)

    @property
    def has_totp_flow(self) -> bool:
        return bool(self.totp_token and self.totp_secret)


def load_settings() -> GrowwSettings:
    load_dotenv()
    return GrowwSettings(
        access_token=_clean(os.getenv("GROWW_ACCESS_TOKEN")),
        api_key=_clean(os.getenv("GROWW_API_KEY")),
        api_secret=_clean(os.getenv("GROWW_API_SECRET")),
        totp_token=_clean(os.getenv("GROWW_TOTP_TOKEN")),
        totp_secret=_clean(os.getenv("GROWW_TOTP_SECRET")),
        default_exchange=os.getenv("GROWW_DEFAULT_EXCHANGE", "NSE").strip().upper(),
        default_segment=os.getenv("GROWW_DEFAULT_SEGMENT", "CASH").strip().upper(),
    )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
