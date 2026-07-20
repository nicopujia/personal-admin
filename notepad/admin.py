from django.contrib import admin

from notepad.models import Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    fields = ("title", "text", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    list_display = ("__str__", "updated_at")
    ordering = ("-updated_at",)
    search_fields = ("title", "text")
