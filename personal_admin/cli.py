from __future__ import annotations

import os
from typing import Any, cast

from django import setup
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command, execute_from_command_line
from dotenv import load_dotenv
from waitress import serve

from personal_admin.settings import BASE_DIR


def configured_host() -> str:
    return os.environ.get("HOST", "127.0.0.1")


def configured_port() -> int:
    return int(os.environ.get("PORT", "8043"))


def ensure_admin_user() -> None:
    username = settings.BOOTSTRAP_ADMIN_USERNAME
    password = settings.BOOTSTRAP_ADMIN_PASSWORD
    if not username or not password:
        return

    user_model = get_user_model()
    user, _ = user_model.objects.get_or_create(
        username=username,
        defaults={
            "email": settings.BOOTSTRAP_ADMIN_EMAIL,
            "is_active": True,
            "is_staff": True,
            "is_superuser": True,
        },
    )

    changed = False
    if settings.BOOTSTRAP_ADMIN_EMAIL and user.email != settings.BOOTSTRAP_ADMIN_EMAIL:
        user.email = settings.BOOTSTRAP_ADMIN_EMAIL
        changed = True

    for field in ("is_active", "is_staff", "is_superuser"):
        if not getattr(user, field):
            setattr(user, field, True)
            changed = True

    if not user.check_password(password):
        user.set_password(password)
        changed = True

    if changed:
        user.save()


def prepare_runtime() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "personal_admin.settings")
    load_dotenv(BASE_DIR / ".env", override=False)
    setup()
    call_command("migrate", interactive=False, verbosity=0, fake_initial=True)
    call_command("collectstatic", interactive=False, verbosity=0)
    ensure_admin_user()


def start() -> None:
    prepare_runtime()
    from django.core.wsgi import get_wsgi_application

    serve(
        cast(Any, get_wsgi_application()),
        host=configured_host(),
        port=configured_port(),
    )


def dev() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "personal_admin.settings")
    os.environ["DJANGO_DEBUG"] = "1"

    if os.environ.get("RUN_MAIN") != "true":
        prepare_runtime()

    execute_from_command_line(
        ["manage.py", "runserver", f"{configured_host()}:{configured_port()}"]
    )
