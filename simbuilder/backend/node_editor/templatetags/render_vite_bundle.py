import json
from pathlib import Path

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


def load_json_from_dist(json_filename="manifest.json"):
    manifest_file_path = Path(settings.BASE_DIR, "static", ".vite", json_filename)
    if not manifest_file_path.exists():
        raise Exception(
            f"Vite manifest file not found on path: {str(manifest_file_path)}"
        )
    else:
        with open(manifest_file_path, "r") as manifest_file:
            try:
                manifest = json.load(manifest_file)
            except Exception:
                raise Exception(
                    f"Vite manifest file invalid. Maybe your {str(manifest_file_path)} file is empty?"
                )
            else:
                return manifest


@register.simple_tag
def render_vite_bundle():
    """
    Template tag to render a vite bundle.
    Supposed to only be used in production.
    For development, see other files.
    """

    manifest = load_json_from_dist()

    entry = manifest.get("index.html")
    if not entry:
        return ""

    file_path = entry.get("file", "")
    css_files = entry.get("css", [])

    css_links = "".join(
        f'<link rel="stylesheet" type="text/css" href="/static/{css}" />' for css in css_files
    )

    return mark_safe(
        f"""<script type="module" src="/static/{file_path}"></script>
        {css_links}"""
    )