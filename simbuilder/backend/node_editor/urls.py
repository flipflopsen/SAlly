"""URL routing for node_editor app."""
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from .views import EditorView
from .api import router
from ..config.urls import LandingView


def api_root(request):
    """API root with available endpoints."""
    return JsonResponse({
        'message': 'Node Editor API',
        'endpoints': {
            'editor': '/editor/',
            'editor_with_project': '/editor/<project_id>/',
            'api': '/api/',
            'node_types': '/api/projects/node_types/',
            'connection_types': '/api/projects/connection_types/',
            'projects': '/api/projects/',
            'nodes': '/api/nodes/',
            'connections': '/api/connections/',
            'websocket': 'ws://localhost:8000/ws/graph/<project_id>/',
        }
    })

def list_api_endpoints(request):
    """Debug endpoint to list all registered API endpoints."""
    if not settings.DEBUG:
        return JsonResponse({'error': 'Debug mode not enabled'}, status=403)
    
    endpoints = []
    for prefix, viewset, basename in router.registry:
        # List action
        endpoints.append({
            'name': f'{basename}-list',
            'pattern': f'/api/{prefix}/',
            'methods': ['GET', 'POST']
        })
        # Detail action
        endpoints.append({
            'name': f'{basename}-detail',
            'pattern': f'/api/{prefix}/{{id}}/',
            'methods': ['GET', 'PUT', 'PATCH', 'DELETE']
        })
        # Custom actions
        for action in viewset.get_extra_actions():
            if action.detail:
                pattern = f'/api/{prefix}/{{id}}/{action.url_path}/'
            else:
                pattern = f'/api/{prefix}/{action.url_path}/'
            endpoints.append({
                'name': f'{basename}-{action.url_name or action.__name__}',
                'pattern': pattern,
                'methods': action.methods
            })
    
    return JsonResponse({'endpoints': endpoints})


urlpatterns = [
    # Node Editor Interface - serves the React frontend
    path('', LandingView.as_view(), name='landing'),
    path('editor/', EditorView.as_view(), name='editor'),
    path('editor/<int:project_id>/', EditorView.as_view(), name='editor_project'),

    # REST API endpoints
    path('api/', include('backend.node_editor.api')),

    # Debug endpoint
    path('api/debug/endpoints/', list_api_endpoints, name='api_endpoints'),
]