"""Main URL configuration for the node editor project."""
import json
from pathlib import Path

from django.contrib import admin
from django.shortcuts import render
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView


def health_check(request):
    """Simple health check endpoint."""
    return JsonResponse({
        'status': 'ok',
        'message': 'Node Editor API is running'
    })

def api_root(request):
    """API root with available endpoints."""
    return JsonResponse({
        'message': 'Node Editor API',
        'endpoints': {
            'editor': '/editor/',
            'editor_with_project': '/editor/<project_id>/',
            'admin': '/admin/',
            'api': '/api/',
            'health': '/health/',
            'websocket': 'ws://localhost:8000/ws/graph/<project_id>/',
        }
    })

class LandingView(TemplateView):
    """Serve the React node editor application."""

    def get_template_names(self):
        """Return the Vite-built index.html."""
        return ['index.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Read Vite manifest for asset paths
        manifest_path = settings.BASE_DIR / 'static' / 'manifest.json'
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                context['manifest'] = manifest

        return context

urlpatterns = [
    # Root endpoint
    path('', LandingView.as_view(), name='landing'),

    # Admin interface
    path('admin/', admin.site.urls),

    # Health check
    path('health/', health_check, name='health_check'),

    # Node Editor Interface and API
    path('', include('backend.node_editor.urls')),

    path('', include('pwa.urls')),
]

def index(request):
    return render(request, "index.html")

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)