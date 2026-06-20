from __future__ import annotations

from typing import Any, cast

from django.test import TestCase

from redirects.logic import (
    normalize_source_path,
    normalize_source_paths,
    normalize_target_url,
)
from redirects.models import RedirectPath, RedirectRule


class RedirectLogicTests(TestCase):
    def test_normalize_target_url_adds_https(self) -> None:
        self.assertEqual(normalize_target_url("example.com"), "https://example.com")

    def test_normalize_source_paths_deduplicates(self) -> None:
        self.assertEqual(
            normalize_source_paths("/nico\nnico\n/nico/"),
            ["/nico"],
        )

    def test_normalize_source_path_blocks_admin_namespace(self) -> None:
        with self.assertRaises(ValueError) as exc:
            normalize_source_path("/admin/secret")
        self.assertEqual(str(exc.exception), "Source path cannot start with /admin.")


class RedirectViewTests(TestCase):
    def test_home_page_renders(self) -> None:
        response = cast(Any, self.client.get("/"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pujia")

    def test_admin_without_trailing_slash_redirects_to_admin_root(self) -> None:
        response = cast(Any, self.client.get("/admin", follow=False))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin/")

    def test_public_redirect_works_without_proxy_header(self) -> None:
        rule = cast(Any, RedirectRule).objects.create(
            target_url="https://example.com/about",
            status_code=302,
            enabled=True,
        )
        cast(Any, RedirectPath).objects.create(
            redirect=rule,
            source_path="/about",
            position=0,
        )

        response = cast(
            Any,
            self.client.get("/about"),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "https://example.com/about")

    def test_unknown_public_path_returns_404(self) -> None:
        response = cast(Any, self.client.get("/missing"))

        self.assertEqual(response.status_code, 404)
