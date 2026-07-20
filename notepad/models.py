from __future__ import annotations

from django.db import models


class Note(models.Model):
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        text = str(self.text)
        return text.splitlines()[0][:80] if text else "Empty note"
