from django.contrib import admin

from notepad.models import Attachment, Note


class AttachmentInline(admin.TabularInline):
    model = Attachment
    fields = ("file", "created_at")
    readonly_fields = ("created_at",)
    extra = 1


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    inlines = (AttachmentInline,)
    fields = ("title", "text", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    list_display = ("__str__", "updated_at")
    ordering = ("-updated_at",)
    search_fields = ("title", "text")
