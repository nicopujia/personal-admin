from __future__ import annotations

from urllib.parse import urlsplit

STATUS_CODES = (301, 302, 307, 308)
STATUS_LABELS = {
    301: "Permanent",
    302: "Temporary",
    307: "Temporary, same HTTP method",
    308: "Permanent, same HTTP method",
}


def normalize_source_path(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Source path is required.")

    if not value.startswith("/"):
        value = f"/{value}"

    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("Source path must be a path only, like /twitter.")

    if any(char.isspace() for char in value):
        raise ValueError("Source path cannot contain whitespace.")

    normalized = parsed.path.rstrip("/") or "/"
    if normalized.startswith("/admin"):
        raise ValueError("Source path cannot start with /admin.")

    return normalized


def normalize_source_paths(value: str) -> list[str]:
    paths = [
        normalize_source_path(raw_path)
        for raw_path in value.replace(",", "\n").splitlines()
        if raw_path.strip()
    ]
    paths = list(dict.fromkeys(paths))
    if not paths:
        raise ValueError("At least one source path is required.")
    return paths


def normalize_target_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Target URL is required.")

    parsed = urlsplit(value)
    if not parsed.scheme:
        value = f"https://{value.lstrip('/')}"
        parsed = urlsplit(value)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Target URL must be a valid host or http(s) URL.")

    return value


def append_query(target_url: str, query_string: str) -> str:
    if not query_string:
        return target_url

    separator = "&" if urlsplit(target_url).query else "?"
    return f"{target_url}{separator}{query_string}"
