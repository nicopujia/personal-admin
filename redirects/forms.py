from __future__ import annotations

from typing import Any, cast

from django import forms

from redirects.logic import normalize_source_paths, normalize_target_url
from redirects.models import RedirectPath, RedirectRule


class RedirectRuleAdminForm(forms.ModelForm):
    source_paths = forms.CharField(
        help_text="Use one path per line or separate paths with commas.",
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    class Meta:
        model = RedirectRule
        fields = [
            "source_paths",
            "target_url",
            "status_code",
            "enabled",
            "preserve_query",
        ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["source_paths"].initial = self.instance.source_paths_text

    def clean_source_paths(self) -> list[str]:
        try:
            source_paths = normalize_source_paths(self.cleaned_data["source_paths"])
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc

        queryset = cast(Any, RedirectPath).objects.filter(source_path__in=source_paths)
        if self.instance.pk:
            queryset = queryset.exclude(redirect=self.instance)

        duplicate = queryset.values_list("source_path", flat=True).first()
        if duplicate is not None:
            raise forms.ValidationError(f"{duplicate} already exists.")

        return source_paths

    def clean_target_url(self) -> str:
        try:
            return normalize_target_url(self.cleaned_data["target_url"])
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
