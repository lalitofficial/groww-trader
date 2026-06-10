from __future__ import annotations

import json
from typing import Any

import requests

from .spec import StrategySpec, validate_spec


_RAW_HOST = "raw.githubusercontent.com"


class GitHubImportError(ValueError):
    pass


def import_spec_from_url(url: str) -> StrategySpec:
    raw_url = _normalize(url)
    if not raw_url:
        raise GitHubImportError("URL must point to a GitHub-hosted strategy spec (raw URL or blob URL).")
    try:
        response = requests.get(raw_url, headers={"User-Agent": "groww-trader-strategy-import"}, timeout=12)
    except requests.RequestException as exc:
        raise GitHubImportError(f"Could not fetch spec: {exc}") from exc
    if response.status_code != 200:
        raise GitHubImportError(f"Fetch returned {response.status_code} for {raw_url}.")
    body = response.text.strip()
    if not body:
        raise GitHubImportError("Spec body is empty.")
    payload = _parse(body)
    spec = validate_spec(payload)
    if not spec.source_url:
        spec = StrategySpec.from_dict({**spec.to_dict(), "source_url": raw_url})
    return spec


def _normalize(url: str) -> str | None:
    if not url or not url.startswith("http"):
        return None
    if _RAW_HOST in url:
        return url
    # Convert github.com/<user>/<repo>/blob/<branch>/<path> -> raw.githubusercontent.com/<user>/<repo>/<branch>/<path>
    if "github.com" in url and "/blob/" in url:
        cleaned = url.split("github.com/", 1)[1]
        return f"https://{_RAW_HOST}/{cleaned.replace('/blob/', '/')}"
    return None


def _parse(body: str) -> dict[str, Any]:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        pass
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(body)
        if isinstance(loaded, dict):
            return loaded
        raise GitHubImportError("YAML did not parse to an object.")
    except ImportError:
        raise GitHubImportError("Body is not valid JSON and PyYAML is not installed for YAML parsing.")
    except Exception as exc:
        raise GitHubImportError(f"Could not parse spec: {exc}") from exc
