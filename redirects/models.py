from __future__ import annotations

import secrets
from typing import Any, cast

from django.db import models, transaction

from redirects.logic import STATUS_LABELS

STATUS_CODE_CHOICES = [
    (code, f"{code} - {label}") for code, label in STATUS_LABELS.items()
]


class RedirectRule(models.Model):
    id = models.CharField(max_length=255, primary_key=True, editable=False)
    target_url = models.TextField()
    status_code = models.PositiveSmallIntegerField(
        choices=STATUS_CODE_CHOICES,
        default=cast(Any, 302),
    )
    enabled = models.BooleanField(default=cast(Any, True))
    preserve_query = models.BooleanField(default=cast(Any, False))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "redirects"
        ordering = ["-updated_at", "id"]
        verbose_name = "redirect"
        verbose_name_plural = "redirects"

    def __str__(self) -> str:
        return str(self.primary_source_path or self.id)

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.id:
            self.id = secrets.token_urlsafe(12)
        super().save(*args, **kwargs)

    @property
    def source_paths_list(self) -> list[str]:
        path_rows = cast(Any, self).path_rows.all().order_by("position")
        return [str(row.source_path) for row in path_rows]

    @property
    def source_paths_text(self) -> str:
        return "\n".join(self.source_paths_list)

    @property
    def primary_source_path(self) -> str:
        return self.source_paths_list[0] if self.source_paths_list else "/"

    @transaction.atomic
    def sync_paths(self, source_paths: list[str]) -> None:
        cast(Any, self).path_rows.all().delete()
        cast(Any, RedirectPath).objects.bulk_create(
            [
                RedirectPath(
                    redirect=self,
                    source_path=source_path,
                    position=position,
                )
                for position, source_path in enumerate(source_paths)
            ]
        )


class RedirectPath(models.Model):
    pk = models.CompositePrimaryKey("redirect", "source_path")
    redirect = models.ForeignKey(
        RedirectRule,
        db_column="redirect_id",
        on_delete=models.CASCADE,
        related_name="path_rows",
    )
    source_path = models.CharField(max_length=255, unique=True)
    position = models.PositiveIntegerField()

    class Meta:
        db_table = "redirect_paths"
        ordering = ["position", "source_path"]
        verbose_name = "redirect path"
        verbose_name_plural = "redirect paths"

    def __str__(self) -> str:
        return str(self.source_path)
