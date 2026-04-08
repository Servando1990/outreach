from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlparse


def normalize_company_name(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.strip().lower()
    lowered = re.sub(r"&", " and ", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def ensure_url(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", stripped):
        stripped = f"https://{stripped}"
    return stripped


def extract_domain(url: str | None) -> str | None:
    parsed_url = ensure_url(url)
    if not parsed_url:
        return None
    parsed = urlparse(parsed_url)
    host = parsed.netloc.lower().split("@")[-1]
    if host.startswith("www."):
        host = host[4:]
    return host or None


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    lowered = email.strip().lower()
    return lowered or None


def split_full_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    parts = full_name.strip().split()
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def unique_strings(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        clean = value.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def stable_hash(*parts: str | None, length: int = 24) -> str:
    payload = "||".join(part or "" for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest[:length]


def company_external_key(company_name: str, website: str | None) -> str:
    domain = extract_domain(website)
    if domain:
        return f"company:{domain}"
    normalized = normalize_company_name(company_name) or stable_hash(company_name)
    return f"company:{normalized}"


def linkedin_handle(url: str | None) -> str | None:
    parsed_url = ensure_url(url)
    if not parsed_url:
        return None
    parsed = urlparse(parsed_url)
    path = parsed.path.strip("/")
    if not path:
        return None
    return path.split("/")[-1] or None


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
