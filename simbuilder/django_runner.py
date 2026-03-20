"""
Django runner for SAlly simbuilder.

This module provides a clean entry point for running Django management commands
that works correctly with UV and setuptools entry points.
"""
import os
import sys
from pathlib import Path


def run_django():
    """Run Django management commands with proper environment setup."""
    # Get the simbuilder directory
    simbuilder_dir = Path(__file__).resolve().parent

    # Add simbuilder directory to Python path so 'backend' module can be found
    if str(simbuilder_dir) not in sys.path:
        sys.path.insert(0, str(simbuilder_dir))

    # Change working directory to simbuilder
    os.chdir(simbuilder_dir)

    # Set Django settings module
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

    # Fix for Django autoreloader with entry points
    # When running via entry point, __main__.__spec__ is None which breaks autoreloader
    # We need to set it to this module's spec
    import __main__
    if not hasattr(__main__, '__spec__') or __main__.__spec__ is None:
        __main__.__spec__ = __import__(__name__).__spec__

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # Execute Django command
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    run_django()
