#!/usr/bin/env python
"""Django management script for SAlly simbuilder.

This script can be run in two ways:
1. Directly from sally/simbuilder/: python manage.py runserver
2. Via UV from project root: uv run -- sally-web runserver
"""
import os
import sys
from pathlib import Path


def main():
    """Entry point for Django management commands."""
    # Get the simbuilder directory (where this file is located)
    simbuilder_dir = Path(__file__).resolve().parent

    # Add simbuilder directory to Python path so 'backend' module can be found
    # This allows imports like 'from backend.config import settings' to work
    if str(simbuilder_dir) not in sys.path:
        sys.path.insert(0, str(simbuilder_dir))

    # Change working directory to simbuilder for Django to find templates, static files, etc.
    os.chdir(simbuilder_dir)

    # Set Django settings module
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
