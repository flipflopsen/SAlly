"""REST API URL routing for node_editor app."""
from rest_framework.routers import DefaultRouter
from .views import (
    GraphProjectViewSet,
    NodeInstanceViewSet,
    NodeConnectionViewSet
)

# Create a router for REST API endpoints
router = DefaultRouter()
router.register(r'projects', GraphProjectViewSet, basename='project')
router.register(r'nodes', NodeInstanceViewSet, basename='node')
router.register(r'connections', NodeConnectionViewSet, basename='connection')

urlpatterns = router.urls