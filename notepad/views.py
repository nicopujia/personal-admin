from pathlib import Path
from typing import Any, cast

from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, HttpRequest
from django.shortcuts import get_object_or_404

from notepad.models import Attachment


@staff_member_required
def download_attachment(request: HttpRequest, name: str) -> FileResponse:
    attachment = get_object_or_404(cast(Any, Attachment), file=name)
    file = cast(Any, attachment.file)
    file.open("rb")
    return FileResponse(file, as_attachment=True, filename=Path(file.name).name)
