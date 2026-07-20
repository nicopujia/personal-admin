from typing import Any, cast

from django.contrib.auth import get_user_model
from django.test import TestCase

from notepad.models import Note


class NoteAdminTests(TestCase):
    def test_admin_can_save_text(self) -> None:
        user = get_user_model().objects.create_superuser(username="admin")
        self.client.force_login(user)

        response = cast(
            Any,
            self.client.post("/admin/notepad/note/add/", {"text": "Buy milk"}),
        )

        self.assertEqual(response.status_code, 302)
        note = cast(Any, Note).objects.get()
        self.assertEqual(note.title, "")
        self.assertEqual(note.text, "Buy milk")

    def test_title_labels_note(self) -> None:
        note = Note(title="Shopping", text="Buy milk")

        self.assertEqual(str(note), "Shopping")
