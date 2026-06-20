from __future__ import annotations

from django.conf import settings
from django.contrib import admin

from redirects.forms import RedirectRuleAdminForm
from redirects.models import RedirectRule


@admin.register(RedirectRule)
class RedirectRuleAdmin(admin.ModelAdmin):
    form = RedirectRuleAdminForm
    fields = (
        "id",
        "source_paths",
        "target_url",
        "status_code",
        "enabled",
        "preserve_query",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    list_display = (
        "primary_source_path",
        "target_url",
        "status_code",
        "enabled",
        "preserve_query",
        "updated_at",
    )
    list_filter = ("enabled", "preserve_query", "status_code")
    search_fields = ("id", "target_url", "path_rows__source_path")
    ordering = ("-updated_at", "id")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("path_rows")

    @admin.display(description="Primary path")
    def primary_source_path(self, obj: RedirectRule) -> str:
        return obj.primary_source_path

    def save_model(
        self,
        request,
        obj: RedirectRule,
        form: RedirectRuleAdminForm,
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)
        obj.sync_paths(form.cleaned_data["source_paths"])

    def view_on_site(self, obj: RedirectRule) -> str | None:
        if not settings.BASE_URL:
            return None
        return f"{settings.BASE_URL}{obj.primary_source_path}"


admin.site.site_header = settings.ADMIN_TITLE
admin.site.site_title = settings.ADMIN_TITLE
admin.site.index_title = settings.ADMIN_TITLE
