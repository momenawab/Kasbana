"""Keep the committed OpenAPI contract in sync with the live code.

drf-spectacular generates the schema from the actual views/serializers, so the
committed ``contracts/openapi.yaml`` is a snapshot of that. This command either
rewrites the snapshot (``--write``) or fails when it has drifted (default, run in
CI) — so a route or field added without updating the contract is caught.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.renderers import OpenApiYamlRenderer
from drf_spectacular.validation import validate_schema

# backend/ -> repo root -> contracts/openapi.yaml
CONTRACT_PATH = Path(settings.BASE_DIR).parent / "contracts" / "openapi.yaml"


def _generate() -> bytes:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    validate_schema(schema)
    return OpenApiYamlRenderer().render(schema, renderer_context={})


class Command(BaseCommand):
    help = "Check (or --write) that contracts/openapi.yaml matches the live schema."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--write",
            action="store_true",
            help="Rewrite contracts/openapi.yaml from the live schema instead of checking.",
        )

    def handle(self, *args, **options) -> None:
        generated = _generate()

        if options["write"]:
            CONTRACT_PATH.write_bytes(generated)
            self.stdout.write(self.style.SUCCESS(f"Wrote {CONTRACT_PATH}"))
            return

        if not CONTRACT_PATH.exists():
            raise CommandError(
                f"{CONTRACT_PATH} is missing. Run `manage.py check_openapi --write`."
            )

        # Normalize line endings before comparing: git ``autocrlf=true`` (common on
        # Windows) checks the LF-committed file out as CRLF, which would otherwise
        # read back as a spurious "drift" against the LF the renderer emits. Real
        # content changes still differ; a pure EOL difference does not.
        committed = CONTRACT_PATH.read_bytes().replace(b"\r\n", b"\n")
        generated = generated.replace(b"\r\n", b"\n")
        if committed == generated:
            self.stdout.write(self.style.SUCCESS("OpenAPI contract is in sync."))
            return

        diff = difflib.unified_diff(
            committed.decode("utf-8").splitlines(),
            generated.decode("utf-8").splitlines(),
            fromfile="contracts/openapi.yaml (committed)",
            tofile="live schema",
            lineterm="",
            n=2,
        )
        self.stdout.write("\n".join(list(diff)[:200]))
        raise CommandError(
            "contracts/openapi.yaml has drifted from the code. "
            "Run `python manage.py check_openapi --write` and commit the result."
        )
