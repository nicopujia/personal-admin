from __future__ import annotations

import fcntl
import json
import os
import secrets
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = BASE_DIR / "data" / "redirects.json"
PUBLIC_REDIRECT_HEADER = "X-Pujia-Redirect-Request"
PUBLIC_REDIRECT_HEADER_VALUE = "1"
STATUS_CODES = (301, 302, 307, 308)
STATUS_LABELS = {
    301: "Permanent",
    302: "Temporary",
    307: "Temporary, same HTTP method",
    308: "Permanent, same HTTP method",
}


@dataclass(frozen=True)
class RedirectRule:
    id: str
    source_paths: list[str]
    target_url: str
    status_code: int
    enabled: bool
    preserve_query: bool
    created_at: str
    updated_at: str

    @property
    def primary_source_path(self) -> str:
        return self.source_paths[0] if self.source_paths else "/"

    @property
    def source_paths_text(self) -> str:
        return "\n".join(self.source_paths)


app = Flask(__name__)
app.secret_key = os.environ.get("ADMIN_SECRET_KEY", secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


def data_path() -> Path:
    path = Path(os.environ.get("ADMIN_DATA_PATH", DEFAULT_DATA_PATH)).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def lock_path() -> Path:
    path = data_path()
    return path.with_suffix(path.suffix + ".lock")


@contextmanager
def data_lock() -> Any:
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_store() -> dict[str, Any]:
    return {"redirects": []}


def read_store() -> dict[str, Any]:
    path = data_path()
    if not path.exists():
        return empty_store()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty_store()

    if not isinstance(raw, dict) or not isinstance(raw.get("redirects"), list):
        return empty_store()

    return raw


def write_store(store: dict[str, Any]) -> None:
    path = data_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as temp_file:
        json.dump(store, temp_file, indent=2, sort_keys=True)
        temp_file.write("\n")
        temp_name = temp_file.name

    Path(temp_name).replace(path)


def load_rules() -> list[RedirectRule]:
    return [coerce_rule(item) for item in read_store()["redirects"]]


def coerce_rule(item: Any) -> RedirectRule:
    if not isinstance(item, dict):
        item = {}

    created_at = str(item.get("created_at") or now_iso())
    updated_at = str(item.get("updated_at") or created_at)

    return RedirectRule(
        id=str(item.get("id") or secrets.token_urlsafe(12)),
        source_paths=coerce_stored_source_paths(item),
        target_url=str(item.get("target_url") or ""),
        status_code=int(item.get("status_code") or 302),
        enabled=bool(item.get("enabled", True)),
        preserve_query=bool(item.get("preserve_query", False)),
        created_at=created_at,
        updated_at=updated_at,
    )


def serialize_rule(rule: RedirectRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "source_paths": rule.source_paths,
        "target_url": rule.target_url,
        "status_code": rule.status_code,
        "enabled": rule.enabled,
        "preserve_query": rule.preserve_query,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def coerce_stored_source_paths(item: dict[str, Any]) -> list[str]:
    raw_paths = item.get("source_paths")
    candidates: list[str] = []

    if isinstance(raw_paths, list):
        candidates.extend(str(path) for path in raw_paths)
    elif isinstance(raw_paths, str):
        candidates.append(raw_paths)

    legacy_path = item.get("source_path")
    if legacy_path:
        candidates.append(str(legacy_path))

    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            path = normalize_source_path(candidate)
        except ValueError:
            continue
        if path in seen:
            continue
        normalized.append(path)
        seen.add(path)

    return normalized or ["/"]


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
    paths: list[str] = []
    seen: set[str] = set()

    for raw_path in value.replace(",", "\n").splitlines():
        raw_path = raw_path.strip()
        if not raw_path:
            continue

        path = normalize_source_path(raw_path)
        if path in seen:
            continue

        paths.append(path)
        seen.add(path)

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


def parse_status_code(value: str) -> int:
    try:
        status_code = int(value)
    except ValueError as exc:
        raise ValueError("Status code must be one of 301, 302, 307, or 308.") from exc

    if status_code not in STATUS_CODES:
        raise ValueError("Status code must be one of 301, 302, 307, or 308.")

    return status_code


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return str(token)


@app.context_processor
def inject_csrf() -> dict[str, Any]:
    return {"csrf_token": csrf_token}


def require_csrf() -> None:
    expected = session.get("csrf_token")
    received = request.form.get("csrf_token")
    if not expected or not received or not secrets.compare_digest(str(expected), received):
        abort(400, "Invalid CSRF token.")


def redirects_context() -> dict[str, Any]:
    rules = sorted(load_rules(), key=lambda rule: rule.primary_source_path)
    enabled_count = sum(1 for rule in rules if rule.enabled)
    path_count = sum(len(rule.source_paths) for rule in rules)

    return {
        "rules": rules,
        "enabled_count": enabled_count,
        "path_count": path_count,
        "status_codes": STATUS_CODES,
        "status_labels": STATUS_LABELS,
        "public_base_url": "https://pujia.ar",
    }


def is_async_redirects_request() -> bool:
    return request.headers.get("X-Pujia-Async") == "redirects"


def redirects_result(message: str, category: str = "success", status: int = 200) -> Any:
    if is_async_redirects_request():
        return (
            jsonify(
                {
                    "ok": category != "error",
                    "category": category,
                    "message": message,
                    "html": render_template("_redirects_content.html", **redirects_context()),
                }
            ),
            status,
        )

    flash(message, category)
    return redirect(url_for("redirects_page"))


@app.get("/")
def dashboard() -> str:
    rules = load_rules()
    enabled_count = sum(1 for rule in rules if rule.enabled)
    path_count = sum(len(rule.source_paths) for rule in rules)

    return render_template(
        "dashboard.html",
        enabled_count=enabled_count,
        path_count=path_count,
        redirect_count=len(rules),
    )


@app.get("/redirects")
def redirects_page() -> str:
    return render_template("redirects.html", **redirects_context())


@app.post("/redirects")
def create_redirect() -> Any:
    require_csrf()
    try:
        source_paths_raw = request.form.get("source_paths") or request.form.get("source_path", "")
        new_rule = RedirectRule(
            id=secrets.token_urlsafe(12),
            source_paths=normalize_source_paths(source_paths_raw),
            target_url=normalize_target_url(request.form.get("target_url", "")),
            status_code=parse_status_code(request.form.get("status_code", "302")),
            enabled=request.form.get("enabled") == "on",
            preserve_query=request.form.get("preserve_query") == "on",
            created_at=now_iso(),
            updated_at=now_iso(),
        )
    except ValueError as exc:
        return redirects_result(str(exc), "error", 400)

    with data_lock():
        rules = load_rules()
        duplicate_path = find_duplicate_path(rules, new_rule.source_paths)
        if duplicate_path:
            return redirects_result(f"{duplicate_path} already exists.", "error", 400)

        write_store({"redirects": [serialize_rule(rule) for rule in [*rules, new_rule]]})

    return redirects_result(f"Added {new_rule.primary_source_path}.")


@app.post("/redirects/<rule_id>")
def update_redirect(rule_id: str) -> Any:
    require_csrf()
    try:
        source_paths_raw = request.form.get("source_paths") or request.form.get("source_path", "")
        source_paths = normalize_source_paths(source_paths_raw)
        target_url = normalize_target_url(request.form.get("target_url", ""))
        status_code = parse_status_code(request.form.get("status_code", "302"))
        enabled = request.form.get("enabled") == "on"
        preserve_query = request.form.get("preserve_query") == "on"
    except ValueError as exc:
        return redirects_result(str(exc), "error", 400)

    with data_lock():
        rules = load_rules()
        duplicate_path = find_duplicate_path(rules, source_paths, exclude_rule_id=rule_id)
        if duplicate_path:
            return redirects_result(f"{duplicate_path} already exists.", "error", 400)

        updated_rules: list[RedirectRule] = []
        changed = False
        for rule in rules:
            if rule.id != rule_id:
                updated_rules.append(rule)
                continue

            updated_rules.append(
                RedirectRule(
                    id=rule.id,
                    source_paths=source_paths,
                    target_url=target_url,
                    status_code=status_code,
                    enabled=enabled,
                    preserve_query=preserve_query,
                    created_at=rule.created_at,
                    updated_at=now_iso(),
                )
            )
            changed = True

        if not changed:
            return redirects_result("Redirect not found.", "error", 404)

        write_store({"redirects": [serialize_rule(rule) for rule in updated_rules]})

    return redirects_result(f"Saved {source_paths[0]}.")


@app.post("/redirects/<rule_id>/delete")
def delete_redirect(rule_id: str) -> Any:
    require_csrf()
    with data_lock():
        rules = load_rules()
        kept_rules = [rule for rule in rules if rule.id != rule_id]
        if len(kept_rules) == len(rules):
            return redirects_result("Redirect not found.", "error", 404)

        write_store({"redirects": [serialize_rule(rule) for rule in kept_rules]})

    return redirects_result("Deleted redirect.")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.before_request
def resolve_public_proxy_requests() -> Any:
    if request.headers.get(PUBLIC_REDIRECT_HEADER) == PUBLIC_REDIRECT_HEADER_VALUE:
        return resolve_public_redirect_path(request.path)
    return None


@app.get("/<path:source_path>")
def public_redirect(source_path: str) -> Any:
    if request.headers.get(PUBLIC_REDIRECT_HEADER) != PUBLIC_REDIRECT_HEADER_VALUE:
        abort(404)

    return resolve_public_redirect_path(f"/{source_path}")


def resolve_public_redirect_path(path: str) -> Any:
    try:
        requested_path = normalize_source_path(path)
    except ValueError:
        abort(404)

    for rule in load_rules():
        if rule.enabled and requested_path in rule.source_paths:
            target_url = append_query(rule.target_url, request.query_string.decode("utf-8")) if rule.preserve_query else rule.target_url
            return redirect(target_url, code=rule.status_code)

    abort(404)


def append_query(target_url: str, query_string: str) -> str:
    if not query_string:
        return target_url

    separator = "&" if urlsplit(target_url).query else "?"
    return f"{target_url}{separator}{query_string}"


def find_duplicate_path(
    rules: list[RedirectRule],
    source_paths: list[str],
    exclude_rule_id: str | None = None,
) -> str | None:
    for rule in rules:
        if rule.id == exclude_rule_id:
            continue
        for source_path in source_paths:
            if source_path in rule.source_paths:
                return source_path
    return None


def main() -> None:
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8043")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )


if __name__ == "__main__":
    main()
