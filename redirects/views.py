from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from redirects.logic import append_query, normalize_source_path
from redirects.models import RedirectPath


def home_page(request: HttpRequest) -> HttpResponse:
    return render(request, "redirects/home.html", {"site_name": settings.SITE_NAME})


def admin_root(request: HttpRequest) -> HttpResponse:
    return redirect("/admin/")


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def public_redirect(request: HttpRequest, source_path: str) -> HttpResponse:
    try:
        requested_path = normalize_source_path(f"/{source_path}")
    except ValueError as exc:
        raise Http404 from exc

    path_row = (
        cast(Any, RedirectPath)
        .objects.select_related("redirect")
        .filter(source_path=requested_path, redirect__enabled=True)
        .first()
    )
    if path_row is None:
        raise Http404

    target_url = path_row.redirect.target_url
    if path_row.redirect.preserve_query:
        target_url = append_query(target_url, request.META.get("QUERY_STRING", ""))

    return HttpResponse(
        status=path_row.redirect.status_code,
        headers={"Location": target_url},
    )
