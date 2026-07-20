from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from notepad.models import Attachment, Note


@override_settings(
    STORAGES={
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    }
)
class NoteAdminTests(TestCase):
    def test_admin_can_save_text(self) -> None:
        user = get_user_model().objects.create_superuser(username="admin")
        self.client.force_login(user)

        response = cast(
            Any,
            self.client.post(
                "/admin/notepad/note/add/",
                {
                    "text": "Buy milk",
                    "attachments-TOTAL_FORMS": "0",
                    "attachments-INITIAL_FORMS": "0",
                    "attachments-MIN_NUM_FORMS": "0",
                    "attachments-MAX_NUM_FORMS": "1000",
                },
            ),
        )

        self.assertEqual(response.status_code, 302)
        note = cast(Any, Note).objects.get()
        self.assertEqual(note.title, "")
        self.assertEqual(note.text, "Buy milk")

    def test_title_labels_note(self) -> None:
        note = Note(title="Shopping", text="Buy milk")

        self.assertEqual(str(note), "Shopping")

    def test_admin_can_upload_and_download_attachment(self) -> None:
        user = get_user_model().objects.create_superuser(username="admin")
        self.client.force_login(user)

        response = cast(
            Any,
            self.client.post(
                "/admin/notepad/note/add/",
                {
                    "title": "Receipt",
                    "text": "Groceries",
                    "attachments-TOTAL_FORMS": "1",
                    "attachments-INITIAL_FORMS": "0",
                    "attachments-MIN_NUM_FORMS": "0",
                    "attachments-MAX_NUM_FORMS": "1000",
                    "attachments-0-file": SimpleUploadedFile(
                        "receipt.txt",
                        b"paid",
                    ),
                },
            ),
        )

        self.assertEqual(response.status_code, 302)
        attachment = cast(Any, Attachment).objects.get()
        name = attachment.file.name
        storage = attachment.file.storage

        self.client.logout()
        anonymous_download = cast(Any, self.client.get(attachment.file.url))
        self.assertEqual(anonymous_download.status_code, 302)

        self.client.force_login(user)
        download = cast(Any, self.client.get(attachment.file.url))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b"".join(download.streaming_content), b"paid")

        attachment.delete()
        self.assertFalse(storage.exists(name))
