from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from django.db import models
from django.db.models.signals import post_delete


class Note(models.Model):
    title = models.CharField(max_length=200, blank=True, default="")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        text = str(self.text)
        return str(self.title) or (text.splitlines()[0][:80] if text else "Empty note")


class Attachment(models.Model):
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="notepad/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return Path(str(self.file)).name


def delete_attachment_file(
    sender: type[Attachment],
    instance: Attachment,
    **kwargs: object,
) -> None:
    if instance.file:
        cast(Any, instance.file).delete(save=False)


post_delete.connect(delete_attachment_file, sender=Attachment)
