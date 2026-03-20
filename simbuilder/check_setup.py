import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings')
django.setup()

from django.conf import settings
from django.apps import apps

print("=" * 60)
print("INSTALLED_APPS Check")
print("=" * 60)

for app in settings.INSTALLED_APPS:
    try:
        app_config = apps.get_app_config(app.split('.')[-1])
        print(f"✓ {app}")
        print(f"  - Name: {app_config.name}")
        print(f"  - Label: {app_config.label}")
    except Exception as e:
        print(f"✗ {app}: {e}")

print("=" * 60)
print("Models Check")
print("=" * 60)

try:
    from backend.node_editor.models import GraphProject, NodeInstance, NodeConnection
    print("✓ GraphProject model loaded")
    print("✓ NodeInstance model loaded")
    print("✓ NodeConnection model loaded")
except Exception as e:
    print(f"✗ Error loading models: {e}")

print("=" * 60)
