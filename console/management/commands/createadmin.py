"""Seed a platform admin. Usage:

    python manage.py createadmin --email you@stampn.net --role SUPER_ADMIN

Password is read interactively (or from ``--password`` for non-interactive use).
Idempotent-ish: refuses to clobber an existing admin unless ``--force``.
"""

from __future__ import annotations

from getpass import getpass
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from console.enums import AdminRole
from console.models import AdminUser


class Command(BaseCommand):
    help = "Create a platform admin (console.AdminUser)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", default="")
        parser.add_argument("--role", default=AdminRole.SUPER_ADMIN, choices=AdminRole.values)
        parser.add_argument("--password", default=None, help="Non-interactive password.")
        parser.add_argument("--force", action="store_true", help="Reset an existing admin.")

    def handle(self, *args: Any, **opts: Any) -> None:
        email = opts["email"].strip().lower()
        existing = AdminUser.objects.filter(email__iexact=email).first()
        if existing and not opts["force"]:
            raise CommandError(f"Admin {email} already exists (use --force to reset).")

        password = opts["password"] or getpass("Password: ")
        if not password or len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")

        admin = existing or AdminUser(email=email)
        admin.name = opts["name"] or admin.name
        admin.role = opts["role"]
        admin.is_active = True
        admin.set_password(password)
        admin.save()
        self.stdout.write(self.style.SUCCESS(f"✓ Admin {email} ({admin.role}) ready."))
