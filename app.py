from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from waitress import serve

BASE_DIR = Path(__file__).resolve().parent
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


def env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None

    value = value.strip()
    return value or None


def required_env(name: str) -> str:
    value = env(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def resolve_path(raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)

TITLE = required_env("TITLE")
BASE_URL = required_env("BASE_URL").rstrip("/")
REDIRECT_HEADER = required_env("REDIRECT_HEADER")
REDIRECT_HEADER_VALUE = required_env("REDIRECT_HEADER_VALUE")


app = Flask(__name__)
app.secret_key = required_env("SECRET_KEY")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


def database_path() -> Path:
    return resolve_path(required_env("DATABASE_PATH"))


@contextmanager
def connect_db() -> Any:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    ensure_schema(connection)
    try:
        yield connection
    finally:
        connection.close()


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS redirects (
            id TEXT PRIMARY KEY,
            target_url TEXT NOT NULL,
            status_code INTEGER NOT NULL CHECK (status_code IN (301, 302, 307, 308)),
            enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
            preserve_query INTEGER NOT NULL CHECK (preserve_query IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS redirect_paths (
            redirect_id TEXT NOT NULL REFERENCES redirects(id) ON DELETE CASCADE,
            source_path TEXT NOT NULL UNIQUE,
            position INTEGER NOT NULL CHECK (position >= 0),
            PRIMARY KEY (redirect_id, source_path)
        );

        CREATE INDEX IF NOT EXISTS idx_redirect_paths_redirect_position
            ON redirect_paths (redirect_id, position);
        """
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def hydrate_rules(rows: list[sqlite3.Row]) -> list[RedirectRule]:
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        rule_id = str(row["id"])
        rule = grouped.setdefault(
            rule_id,
            {
                "id": rule_id,
                "source_paths": [],
                "target_url": str(row["target_url"]),
                "status_code": int(row["status_code"]),
                "enabled": bool(row["enabled"]),
                "preserve_query": bool(row["preserve_query"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            },
        )
        rule["source_paths"].append(str(row["source_path"]))

    return [RedirectRule(**rule) for rule in grouped.values()]


def fetch_rules(
    connection: sqlite3.Connection,
    where_clause: str = "",
    params: tuple[Any, ...] = (),
) -> list[RedirectRule]:
    where = f" WHERE {where_clause}" if where_clause else ""
    rows = connection.execute(
        f"""
        SELECT
            r.id,
            r.target_url,
            r.status_code,
            r.enabled,
            r.preserve_query,
            r.created_at,
            r.updated_at,
            p.source_path,
            p.position
        FROM redirects r
        JOIN redirect_paths p ON p.redirect_id = r.id
        {where}
        ORDER BY r.id, p.position
        """,
        params,
    ).fetchall()
    return hydrate_rules(rows)


def list_rules() -> list[RedirectRule]:
    with connect_db() as connection:
        return fetch_rules(connection)


def insert_rule(connection: sqlite3.Connection, rule: RedirectRule) -> None:
    connection.execute(
        """
        INSERT INTO redirects (
            id,
            target_url,
            status_code,
            enabled,
            preserve_query,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rule.id,
            rule.target_url,
            rule.status_code,
            int(rule.enabled),
            int(rule.preserve_query),
            rule.created_at,
            rule.updated_at,
        ),
    )
    connection.executemany(
        """
        INSERT INTO redirect_paths (redirect_id, source_path, position)
        VALUES (?, ?, ?)
        """,
        [
            (rule.id, source_path, position)
            for position, source_path in enumerate(rule.source_paths)
        ],
    )


def delete_rule(connection: sqlite3.Connection, rule_id: str) -> bool:
    return (
        connection.execute("DELETE FROM redirects WHERE id = ?", (rule_id,)).rowcount
        > 0
    )


def find_duplicate_path(
    connection: sqlite3.Connection,
    source_paths: list[str],
    exclude_rule_id: str | None = None,
) -> str | None:
    placeholders = ", ".join("?" for _ in source_paths)
    params: list[str] = list(source_paths)
    exclusion = ""
    if exclude_rule_id is not None:
        exclusion = " AND redirect_id != ?"
        params.append(exclude_rule_id)
    row = connection.execute(
        f"""
        SELECT source_path
        FROM redirect_paths
        WHERE source_path IN ({placeholders}){exclusion}
        LIMIT 1
        """,
        tuple(params),
    ).fetchone()
    return str(row["source_path"]) if row else None


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


def parse_status_code(value: str) -> int:
    try:
        status_code = int(value)
    except ValueError as exc:
        raise ValueError("Status code must be one of 301, 302, 307, or 308.") from exc

    if status_code not in STATUS_CODES:
        raise ValueError("Status code must be one of 301, 302, 307, or 308.")

    return status_code


def configured_host() -> str:
    return required_env("HOST")


def configured_port() -> int:
    return int(required_env("PORT"))


def csrf_token() -> str:
    return str(session.setdefault("csrf_token", secrets.token_urlsafe(32)))


@app.context_processor
def inject_csrf() -> dict[str, Any]:
    return {
        "admin_title": TITLE,
        "csrf_token": csrf_token,
    }


def require_csrf() -> None:
    expected = session.get("csrf_token")
    received = request.form.get("csrf_token")
    if expected and received and secrets.compare_digest(str(expected), received):
        return
    abort(400, "Invalid CSRF token.")


def summarize_rules(rules: list[RedirectRule]) -> dict[str, int]:
    return {
        "enabled_count": sum(rule.enabled for rule in rules),
        "path_count": sum(len(rule.source_paths) for rule in rules),
    }

def build_rule(*, rule_id: str, created_at: str, updated_at: str) -> RedirectRule:
    def field(name: str, default: str = "") -> str:
        return request.form.get(name, default)

    return RedirectRule(
        id=rule_id,
        source_paths=normalize_source_paths(field("source_paths")),
        target_url=normalize_target_url(field("target_url")),
        status_code=parse_status_code(field("status_code", "302")),
        enabled=field("enabled") == "on",
        preserve_query=field("preserve_query") == "on",
        created_at=created_at,
        updated_at=updated_at,
    )


def update_rule(connection: sqlite3.Connection, rule: RedirectRule) -> None:
    connection.execute(
        """
        UPDATE redirects
        SET target_url = ?,
            status_code = ?,
            enabled = ?,
            preserve_query = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            rule.target_url,
            rule.status_code,
            int(rule.enabled),
            int(rule.preserve_query),
            rule.updated_at,
            rule.id,
        ),
    )
    connection.execute("DELETE FROM redirect_paths WHERE redirect_id = ?", (rule.id,))
    connection.executemany(
        """
        INSERT INTO redirect_paths (redirect_id, source_path, position)
        VALUES (?, ?, ?)
        """,
        [
            (rule.id, source_path, position)
            for position, source_path in enumerate(rule.source_paths)
        ],
    )


def redirects_redirect(message: str, category: str = "success") -> Any:
    flash(message, category)
    return redirect(url_for("redirects_page"))


@app.get("/")
def dashboard() -> str:
    rules = list_rules()
    return render_template(
        "dashboard.html",
        **summarize_rules(rules),
    )


@app.get("/redirects")
def redirects_page() -> str:
    rules = sorted(list_rules(), key=lambda rule: rule.primary_source_path)
    return render_template(
        "redirects.html",
        rules=rules,
        **summarize_rules(rules),
        status_codes=STATUS_CODES,
        status_labels=STATUS_LABELS,
        base_url=BASE_URL,
    )


@app.post("/redirects")
def create_redirect() -> Any:
    require_csrf()

    try:
        timestamp = now_iso()
        new_rule = build_rule(
            rule_id=secrets.token_urlsafe(12),
            created_at=timestamp,
            updated_at=timestamp,
        )
    except ValueError as exc:
        return redirects_redirect(str(exc), "error")

    with connect_db() as connection:
        with connection:
            duplicate_path = find_duplicate_path(connection, new_rule.source_paths)
            if duplicate_path:
                return redirects_redirect(f"{duplicate_path} already exists.", "error")

            insert_rule(connection, new_rule)

    return redirects_redirect(f"Added {new_rule.primary_source_path}.")


@app.post("/redirects/<rule_id>")
def update_redirect(rule_id: str) -> Any:
    require_csrf()

    action = (request.form.get("action") or "save").strip()
    with connect_db() as connection:
        existing_rules = fetch_rules(connection, "r.id = ?", (rule_id,))
        if not existing_rules:
            return redirects_redirect("Redirect not found.", "error")
        existing_rule = existing_rules[0]

        if action == "delete":
            with connection:
                delete_rule(connection, rule_id)
            return redirects_redirect(f"Deleted {existing_rule.primary_source_path}.")

        if action != "save":
            return redirects_redirect("Unknown redirects action.", "error")

        try:
            updated_rule = build_rule(
                rule_id=rule_id,
                created_at=existing_rule.created_at,
                updated_at=now_iso(),
            )
        except ValueError as exc:
            return redirects_redirect(str(exc), "error")

        duplicate_path = find_duplicate_path(
            connection,
            updated_rule.source_paths,
            exclude_rule_id=rule_id,
        )
        if duplicate_path:
            return redirects_redirect(f"{duplicate_path} already exists.", "error")

        with connection:
            update_rule(connection, updated_rule)

    return redirects_redirect(f"Saved {updated_rule.primary_source_path}.")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.before_request
def resolve_public_proxy_requests() -> Any:
    if request.headers.get(REDIRECT_HEADER) == REDIRECT_HEADER_VALUE:
        return resolve_public_redirect_path(request.path)
    return None


@app.get("/<path:source_path>")
def public_redirect(source_path: str) -> Any:
    if request.headers.get(REDIRECT_HEADER) != REDIRECT_HEADER_VALUE:
        abort(404)

    return resolve_public_redirect_path(f"/{source_path}")


def resolve_public_redirect_path(path: str) -> Any:
    try:
        requested_path = normalize_source_path(path)
    except ValueError:
        abort(404)

    with connect_db() as connection:
        row = connection.execute(
            """
            SELECT target_url, status_code, preserve_query
            FROM redirects
            JOIN redirect_paths ON redirect_paths.redirect_id = redirects.id
            WHERE enabled = 1 AND source_path = ?
            LIMIT 1
            """,
            (requested_path,),
        ).fetchone()

    if row is None:
        abort(404)

    target_url = str(row["target_url"])
    if bool(row["preserve_query"]):
        target_url = append_query(target_url, request.query_string.decode("utf-8"))

    return redirect(target_url, code=int(row["status_code"]))


def append_query(target_url: str, query_string: str) -> str:
    if not query_string:
        return target_url

    separator = "&" if urlsplit(target_url).query else "?"
    return f"{target_url}{separator}{query_string}"


def start() -> None:
    serve(app, host=configured_host(), port=configured_port())


def dev() -> None:
    app.run(
        host=configured_host(),
        port=configured_port(),
        debug=True,
    )


if __name__ == "__main__":
    dev()
