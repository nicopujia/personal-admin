from __future__ import annotations

import json
from pathlib import Path

import pytest

import app as admin_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADMIN_DATA_PATH", str(tmp_path / "redirects.json"))
    admin_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    with admin_app.app.test_client() as test_client:
        yield test_client


def csrf(client) -> str:
    response = client.get("/redirects")
    html = response.get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    end = html.index('"', start)
    return html[start:end]


def test_dashboard_lists_redirects_as_a_feature(client) -> None:
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Admin" in html
    assert "Redirects" in html
    assert 'href="/redirects"' in html


def test_create_and_resolve_redirect_with_multiple_paths(client) -> None:
    response = client.post(
        "/redirects",
        data={
            "csrf_token": csrf(client),
            "source_paths": "/x\n/y",
            "target_url": "https://example.com",
            "status_code": "302",
            "enabled": "on",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    response = client.get("/x", headers={admin_app.PUBLIC_REDIRECT_HEADER: "1"})
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com"

    response = client.get("/y", headers={admin_app.PUBLIC_REDIRECT_HEADER: "1"})
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com"


def test_target_url_defaults_to_https(client) -> None:
    response = client.post(
        "/redirects",
        data={
            "csrf_token": csrf(client),
            "source_paths": "/bare",
            "target_url": "example.com/bare",
            "status_code": "302",
            "enabled": "on",
        },
    )

    assert response.status_code == 302

    response = client.get("/bare", headers={admin_app.PUBLIC_REDIRECT_HEADER: "1"})
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/bare"


def test_target_url_rejects_non_http_scheme(client) -> None:
    response = client.post(
        "/redirects",
        data={
            "csrf_token": csrf(client),
            "source_paths": "/ftp",
            "target_url": "ftp://example.com/file",
            "status_code": "302",
            "enabled": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Target URL must be a valid host or http(s) URL." in response.get_data(as_text=True)


def test_async_create_returns_redirects_partial(client) -> None:
    response = client.post(
        "/redirects",
        data={
            "csrf_token": csrf(client),
            "source_paths": "/async",
            "target_url": "example.com/async",
            "status_code": "302",
            "enabled": "on",
        },
        headers={"X-Pujia-Async": "redirects", "Accept": "application/json"},
    )

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["message"] == "Added /async."
    assert 'id="redirects-content"' in payload["html"]
    assert "/async" in payload["html"]
    assert "https://example.com/async" in payload["html"]


def test_async_create_error_returns_partial_without_redirect(client) -> None:
    response = client.post(
        "/redirects",
        data={
            "csrf_token": csrf(client),
            "source_paths": "",
            "target_url": "example.com/async",
            "status_code": "302",
            "enabled": "on",
        },
        headers={"X-Pujia-Async": "redirects", "Accept": "application/json"},
    )

    payload = response.get_json()

    assert response.status_code == 400
    assert payload["ok"] is False
    assert payload["category"] == "error"
    assert payload["message"] == "At least one source path is required."
    assert 'id="redirects-content"' in payload["html"]


def test_dashboard_labels_redirect_status_codes(client) -> None:
    response = client.get("/redirects")
    html = response.get_data(as_text=True)

    assert "301 - Permanent" in html
    assert "302 - Temporary" in html
    assert "307 - Temporary, same HTTP method" in html
    assert "308 - Permanent, same HTTP method" in html


def test_public_redirect_requires_internal_header(client) -> None:
    response = client.get("/x")

    assert response.status_code == 404


def test_public_proxy_header_cannot_reach_admin_pages(client) -> None:
    response = client.get("/redirects", headers={admin_app.PUBLIC_REDIRECT_HEADER: "1"})

    assert response.status_code == 404


def test_public_proxy_header_can_resolve_path_that_matches_admin_page(client) -> None:
    client.post(
        "/redirects",
        data={
            "csrf_token": csrf(client),
            "source_paths": "/redirects",
            "target_url": "https://example.com/redirects",
            "status_code": "302",
            "enabled": "on",
        },
    )

    response = client.get("/redirects", headers={admin_app.PUBLIC_REDIRECT_HEADER: "1"})

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/redirects"


def test_malformed_public_path_returns_404(client) -> None:
    response = client.get("/bad%20path", headers={admin_app.PUBLIC_REDIRECT_HEADER: "1"})

    assert response.status_code == 404


def test_preserve_query_appends_original_query(client) -> None:
    client.post(
        "/redirects",
        data={
            "csrf_token": csrf(client),
            "source_paths": "/search",
            "target_url": "https://example.com/path?existing=1",
            "status_code": "307",
            "enabled": "on",
            "preserve_query": "on",
        },
    )

    response = client.get(
        "/search?q=test",
        headers={admin_app.PUBLIC_REDIRECT_HEADER: "1"},
    )

    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com/path?existing=1&q=test"


def test_rejects_duplicate_source_path_across_rules(client) -> None:
    token = csrf(client)
    client.post(
        "/redirects",
        data={
            "csrf_token": token,
            "source_paths": "/same",
            "target_url": "https://example.com/one",
            "status_code": "302",
            "enabled": "on",
        },
    )

    response = client.post(
        "/redirects",
        data={
            "csrf_token": token,
            "source_paths": "/same\n/other",
            "target_url": "https://example.com/two",
            "status_code": "302",
            "enabled": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "/same already exists." in response.get_data(as_text=True)


def test_legacy_source_path_records_still_resolve(client, tmp_path: Path) -> None:
    data_path = tmp_path / "redirects.json"
    data_path.write_text(
        json.dumps(
            {
                "redirects": [
                    {
                        "id": "legacy",
                        "source_path": "/legacy",
                        "target_url": "https://example.com/legacy",
                        "status_code": 302,
                        "enabled": True,
                        "preserve_query": False,
                        "created_at": "2026-06-01T00:00:00+00:00",
                        "updated_at": "2026-06-01T00:00:00+00:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    response = client.get("/legacy", headers={admin_app.PUBLIC_REDIRECT_HEADER: "1"})

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/legacy"
