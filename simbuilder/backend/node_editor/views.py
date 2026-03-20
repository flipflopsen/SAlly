"""REST API views for graph management."""
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from django.db import transaction

from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404, render
from django.views.generic import TemplateView
from django.views import View
from django.http import HttpResponse
from .models import GraphProject, NodeInstance, NodeConnection, ProjectTypeDefinition, NodeTypeDefinition
from .serializers import (
    GraphProjectSerializer,
    GraphProjectListSerializer,
    NodeInstanceSerializer,
    NodeConnectionSerializer,
    TypeDefinitionSerializer,
    FieldDefinitionSerializer,
    ProjectTypeDefinitionSerializer,
    NodeTypeDefinitionSerializer
)
from .services.graph_service import GraphService
from .services.node_registry import registry
from .services.connection_registry import connection_registry

logger = logging.getLogger(__name__)

class EditorView(TemplateView):
    """Serve the React node editor application."""

    def get_template_names(self):
        """Return the Vite-built index.html."""
        return ['node_editor.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Read Vite manifest for asset paths
        manifest_path = Path(settings.BASE_DIR).parent / 'www' / 'manifest.json'
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                context['manifest'] = manifest

        return context


class GraphProjectViewSet(viewsets.ModelViewSet):
    """CRUD operations for graph projects."""

    permission_classes = [AllowAny]  # Change to IsAuthenticated in production
    queryset = GraphProject.objects.all()

    def get_serializer_class(self):
        """Use lightweight serializer for list view."""
        if self.action == 'list':
            return GraphProjectListSerializer
        return GraphProjectSerializer

    def get_queryset(self):
        """Filter projects by authenticated user."""
        # For now, return all projects (remove this in production)
        return GraphProject.objects.all()
        # In production with auth:
        # return GraphProject.objects.filter(owner=self.request.user)

    def get_object(self):
        """Override to create project if it doesn't exist."""
        pk = self.kwargs.get('pk')
        project, created = GraphProject.objects.get_or_create(
            id=pk,
            defaults={'name': f'Project {pk}'}
        )
        if created:
            print(f"Created new project with ID {pk}")
        return project

    def perform_create(self, serializer):
        """Set owner to current user on creation."""
        # For now, create without owner (fix this with authentication)
        serializer.save()
        # In production with auth:
        # serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def add_node(self, request, pk=None):
        """Add node to project."""
        logger.info(f"Adding node to project {pk} with request data: {request.data}")
        project, created = GraphProject.objects.get_or_create(
            id=pk,
            defaults={'name': f'Project {pk}'}
        )
        if created:
            print(f"Created new project with ID {pk}")

        try:
            node = GraphService.add_node(
                project_id=project.id,
                node_id=request.data.get('node_id'),
                node_type=request.data.get('node_type'),
                label=request.data.get('label'),
                position_x=request.data.get('position_x'),
                position_y=request.data.get('position_y'),
                data=request.data.get('data')
            )
            print(f"Added node with ID {node.id}")
            serializer = NodeInstanceSerializer(node)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def add_connection(self, request, pk=None):
        """Add connection between nodes."""
        project, created = GraphProject.objects.get_or_create(
            id=pk,
            defaults={'name': f'Project {pk}'}
        )
        if created:
            print(f"Created new project with ID {pk}")

        print(f"Got project with ID {project.id}")
        print(f"Got request with data: {request.data}")
        data = request.data
        try:
            connection = GraphService.create_connection(
                project_id=project.id,
                connection_id=data['connection_id'],
                connection_type=data['connection_type'],
                source_node_id=data['source_node_id'],
                target_node_id=data['target_node_id'],
                source_handle=data['source_handle'],
                target_handle=data['target_handle']
            )
            print(f"Added connection with ID {connection.id}")
            serializer = NodeConnectionSerializer(connection)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def node_types(self, request):
        """Get all registered node types."""
        node_types = registry.get_all_nodes()
        return Response(node_types)

    @action(detail=False, methods=['get'])
    def connection_types(self, request):
        """Get all registered connection types."""
        connection_types = connection_registry.get_all_connections()
        return Response(connection_types)

    @action(detail=True, methods=['get'])
    def export_graph(self, request, pk=None):
        """Export project graph data as YAML with python_class_path."""
        project, created = GraphProject.objects.get_or_create(
            id=pk,
            defaults={'name': f'Project {pk}'}
        )
        if created:
            print(f"Created new project with ID {pk}")

        try:
            # Serialize the project with full nested data
            serializer = GraphProjectSerializer(project)
            project_data = serializer.data

            # Enhance export data with python_class_path for nodes and connections
            enhanced_nodes = []
            for node in project_data['nodes']:
                node_type = node.get('node_type')
                
                # Look up python_class_path from ProjectTypeDefinition or plugin metadata
                python_class_path = None
                
                # Check if there's a project-specific type definition
                try:
                    type_def = ProjectTypeDefinition.objects.filter(
                        project=project,
                        definition_type='node',
                        type_identifier=node_type
                    ).first()
                    if type_def and type_def.python_class_path:
                        python_class_path = type_def.python_class_path
                except:
                    pass
                
                # If not found in project types, try to get from plugin metadata
                if not python_class_path and node_type in registry._nodes:
                    node_class = registry._nodes[node_type]
                    if hasattr(node_class, 'get_metadata'):
                        try:
                            metadata = node_class.get_metadata()
                            python_class_path = f'backend.plugins.nodes.{node_class.__module__.split(".")[-2]}.{node_class.__name__}'
                        except:
                            pass
                
                enhanced_node = dict(node)
                if python_class_path:
                    enhanced_node['python_class_path'] = python_class_path
                enhanced_nodes.append(enhanced_node)
            
            enhanced_connections = []
            for connection in project_data['connections']:
                connection_type = connection.get('connection_type')
                
                # Look up python_class_path from ProjectTypeDefinition or plugin metadata
                python_class_path = None
                
                # Check if there's a project-specific type definition
                try:
                    type_def = ProjectTypeDefinition.objects.filter(
                        project=project,
                        definition_type='connection',
                        type_identifier=connection_type
                    ).first()
                    if type_def and type_def.python_class_path:
                        python_class_path = type_def.python_class_path
                except:
                    pass
                
                # If not found in project types, try to get from plugin metadata
                if not python_class_path and connection_type in connection_registry._connections:
                    connection_class = connection_registry._connections[connection_type]
                    if hasattr(connection_class, 'get_metadata'):
                        try:
                            metadata = connection_class.get_metadata()
                            python_class_path = f'backend.plugins.connections.{connection_class.__module__.split(".")[-2]}.{connection_class.__name__}'
                        except:
                            pass
                
                enhanced_connection = dict(connection)
                if python_class_path:
                    enhanced_connection['python_class_path'] = python_class_path
                enhanced_connections.append(enhanced_connection)

            # Create export data structure
            export_data = {
                'version': '1.0',
                'project_name': project.name,
                'project_id': project.id,
                'nodes': enhanced_nodes,
                'connections': enhanced_connections,
                'exported_at': datetime.now().isoformat()
            }

            # Serialize to YAML
            yaml_content = yaml.dump(export_data, default_flow_style=False, indent=2)

            # Return response with YAML file download
            response = HttpResponse(
                yaml_content,
                content_type='text/yaml',
                headers={
                    'Content-Disposition': f'attachment; filename="project_{project.id}_graph.yaml"'
                }
            )
            return response

        except Exception as e:
            return Response(
                {'error': f'Export failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='type_definitions')
    def get_project_types(self, request, pk=None):
        """Get type definitions specific to a project."""
        try:
            project = self.get_object()

            # Get project-specific type definitions from database
            project_types = project.get_type_definitions()

            # Load project-specific types into memory if not already registered
            for type_def in project_types:
                definition = type_def.get_definition()
                if type_def.definition_type == 'node':
                    try:
                        registry.register_dynamic_node(definition)
                        registry.register_field_schema(type_def.type_identifier, definition.get('fieldSchema', []))
                        logger.info(f'Loaded project-specific node type: {type_def.type_identifier}')
                    except Exception as e:
                        logger.warning(f'Failed to register project node type {type_def.type_identifier}: {e}')
                else:  # connection
                    try:
                        connection_registry.register_dynamic_connection(definition)
                        connection_registry.register_field_schema(type_def.type_identifier, definition.get('fieldSchema', []))
                        logger.info(f'Loaded project-specific connection type: {type_def.type_identifier}')
                    except Exception as e:
                        logger.warning(f'Failed to register project connection type {type_def.type_identifier}: {e}')

            # Get merged types (global + project-specific)
            node_types = registry.get_all_nodes()
            connection_types = connection_registry.get_all_connections()

            return Response({
                'node_types': list(node_types.values()),
                'connection_types': list(connection_types.values()),
                'project_id': project.id,
                'project_name': project.name
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to get project types: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def import_graph(self, request, pk=None):
        """Import project graph data from JSON."""
        project, created = GraphProject.objects.get_or_create(
            id=pk,
            defaults={'name': f'Project {pk}'}
        )
        if created:
            print(f"Created new project with ID {pk}")

        try:
            import_data = request.data

            # Validate required keys
            if not isinstance(import_data, dict) or 'nodes' not in import_data or 'connections' not in import_data:
                return Response(
                    {'error': 'Invalid import data. Must contain "nodes" and "connections" keys.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            nodes_data = import_data['nodes']
            connections_data = import_data['connections']

            with transaction.atomic():
                # Delete existing nodes and connections
                NodeConnection.objects.filter(project=project).delete()
                NodeInstance.objects.filter(project=project).delete()

                # Import nodes
                imported_nodes = 0
                for node_data in nodes_data:
                    try:
                        GraphService.add_node(
                            project_id=project.id,
                            node_id=node_data['node_id'],
                            node_type=node_data['node_type'],
                            label=node_data['label'],
                            position_x=node_data['position_x'],
                            position_y=node_data['position_y'],
                            data=node_data.get('data')
                        )
                        imported_nodes += 1
                    except Exception as e:
                        raise ValueError(f"Failed to import node {node_data.get('node_id', 'unknown')}: {str(e)}")

                # Import connections
                imported_connections = 0
                for connection_data in connections_data:
                    try:
                        GraphService.create_connection(
                            project_id=project.id,
                            connection_id=connection_data['connection_id'],
                            connection_type=connection_data.get('connection_type', 'default'),
                            source_node_id=connection_data['source_node'],
                            target_node_id=connection_data['target_node'],
                            source_handle=connection_data.get('source_handle'),
                            target_handle=connection_data.get('target_handle')
                        )
                        imported_connections += 1
                    except Exception as e:
                        raise ValueError(f"Failed to import connection {connection_data.get('connection_id', 'unknown')}: {str(e)}")

                return Response({
                    'message': 'Graph imported successfully',
                    'imported_nodes': imported_nodes,
                    'imported_connections': imported_connections
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Import failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def export_type_definitions(self, request):
        """Export all registered node and connection type definitions with updated field schemas."""
        try:
            # Get optional project_id query parameter
            project_id = request.query_params.get('project_id')
            export_data = {
                'version': '1.0',
                'node_types': [],
                'connection_types': []
            }

            # Get global types from registry
            node_types = registry.get_all_nodes()
            connection_types = connection_registry.get_all_connections()

            export_data['node_types'] = list(node_types.values())
            export_data['connection_types'] = list(connection_types.values())

            # If project_id provided, include project-specific types and update field schemas
            if project_id:
                try:
                    project = GraphProject.objects.get(id=project_id)
                    project_types = project.get_type_definitions()

                    # First, check if any node types in the registry have ProjectTypeDefinition
                    # with updated fieldSchema that should override the registry versions
                    for node_type_data in export_data['node_types']:
                        node_type = node_type_data.get('type')
                        if node_type:
                            # Check if there's a ProjectTypeDefinition with updated fieldSchema
                            try:
                                type_def = ProjectTypeDefinition.objects.filter(
                                    project=project,
                                    definition_type='node',
                                    type_identifier=node_type
                                ).first()
                                if type_def:
                                    # Parse the definition_data and check for updated fieldSchema
                                    try:
                                        definition_data = json.loads(type_def.definition_data) if type_def.definition_data else {}
                                        if 'fieldSchema' in definition_data:
                                            # Update the fieldSchema in the export data
                                            node_type_data['fieldSchema'] = definition_data['fieldSchema']
                                            logger.info(f'Updated fieldSchema for exported node type: {node_type}')
                                    except json.JSONDecodeError:
                                        pass
                            except Exception as e:
                                logger.warning(f'Failed to check ProjectTypeDefinition for {node_type}: {e}')

                    # Merge project-specific types (they override global types with same identifier)
                    for type_def in project_types:
                        definition = type_def.get_definition()
                        if type_def.definition_type == 'node':
                            # Remove existing type with same identifier and add project-specific
                            export_data['node_types'] = [
                                t for t in export_data['node_types']
                                if t.get('type') != type_def.type_identifier
                            ]
                            export_data['node_types'].append(definition)
                        else:  # connection
                            # Remove existing type with same identifier and add project-specific
                            export_data['connection_types'] = [
                                t for t in export_data['connection_types']
                                if t.get('type') != type_def.type_identifier
                            ]
                            export_data['connection_types'].append(definition)

                    export_data['project_id'] = project_id
                    export_data['project_name'] = project.name

                except GraphProject.DoesNotExist:
                    return Response(
                        {'error': f'Project with id {project_id} not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )

            response = Response(
                export_data,
                content_type='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename="type_definitions_export{"_project_" + str(project_id) if project_id else ""}.json"'
                }
            )
            return response

        except Exception as e:
            return Response(
                {'error': f'Export failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='global_type_definitions')
    def get_global_type_definitions(self, request):
        """Get global NodeTypeDefinition table for reuse across projects."""
        try:
            # Optional filtering by definition_type query parameter
            definition_type = request.query_params.get('definition_type')
            queryset = NodeTypeDefinition.objects.all()
            
            if definition_type:
                queryset = queryset.filter(definition_type=definition_type)
            
            # Serialize results
            serializer = NodeTypeDefinitionSerializer(queryset, many=True)
            
            # Organize by type for easier frontend consumption
            node_types = []
            connection_types = []
            
            for item in serializer.data:
                if item['definition_type'] == 'node':
                    node_types.append(item)
                else:
                    connection_types.append(item)
            
            return Response({
                'node_types': node_types,
                'connection_types': connection_types,
                'total_count': queryset.count()
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to get global type definitions: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def import_type_definitions(self, request):
        """Import type definitions and register field schemas."""
        try:
            logging.info(f"Incoming request data: {request.data}")
            serializer = TypeDefinitionSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        'error': 'Validation failed',
                        'details': serializer.errors,
                        'hint': 'Each node type must have type and label fields. Each connection type must have type and label fields.',
                        'received_keys': list(request.data.keys()) if isinstance(request.data, dict) else 'Invalid data format'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            data = serializer.validated_data
            logging.info("Validation successful")
            imported_nodes = 0
            imported_connections = 0

            # Get project_id from request data or use default project (1)
            project_id = request.data.get('project_id', 1)
            try:
                project = GraphProject.objects.get(id=project_id)
            except GraphProject.DoesNotExist:
                return Response(
                    {'error': f'Project with id {project_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Import node types
            for node_type_data in data['node_types']:
                node_type = node_type_data['type']
                field_schema = node_type_data.get('fieldSchema', [])
                try:
                    registry.register_dynamic_node(node_type_data)
                    logger.info(f'Registered dynamic node class for type: {node_type}')
                except ValueError as e:
                    logger.warning(f'Failed to register dynamic node {node_type}: {e}')
                except Exception as e:
                    logger.error(f'Unexpected error registering dynamic node {node_type}: {e}')
                registry.register_field_schema(node_type, field_schema)
                logging.info(f"Registered field schema for node type: {node_type}")

                # Save to database for this project
                ProjectTypeDefinition.objects.update_or_create(
                    project=project,
                    definition_type='node',
                    type_identifier=node_type,
                    defaults={'definition_data': json.dumps(node_type_data)}
                )

                imported_nodes += 1

            # Import connection types
            for connection_type_data in data['connection_types']:
                connection_type = connection_type_data['type']
                field_schema = connection_type_data.get('fieldSchema', [])
                try:
                    connection_registry.register_dynamic_connection(connection_type_data)
                    logger.info(f'Registered dynamic connection class for type: {connection_type}')
                except ValueError as e:
                    logger.warning(f'Failed to register dynamic connection {connection_type}: {e}')
                except Exception as e:
                    logger.error(f'Unexpected error registering dynamic connection {connection_type}: {e}')
                connection_registry.register_field_schema(connection_type, field_schema)
                logging.info(f"Registered field schema for connection type: {connection_type}")

                # Save to database for this project
                ProjectTypeDefinition.objects.update_or_create(
                    project=project,
                    definition_type='connection',
                    type_identifier=connection_type,
                    defaults={'definition_data': json.dumps(connection_type_data)}
                )

                imported_connections += 1

            return Response({
                'message': 'Type definitions imported successfully',
                'imported_nodes': imported_nodes,
                'imported_connections': imported_connections,
                'project_id': project_id
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Import failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class NodeInstanceViewSet(viewsets.ModelViewSet):
    """CRUD operations for individual nodes."""

    permission_classes = [AllowAny]
    serializer_class = NodeInstanceSerializer
    queryset = NodeInstance.objects.all()
    lookup_field = 'node_id'

    def get_queryset(self):
        """Filter nodes by user's projects."""
        return NodeInstance.objects.all()
        # In production with auth:
        # return NodeInstance.objects.filter(project__owner=self.request.user)

    def perform_update(self, serializer):
        """Update node with service layer validation."""
        instance = serializer.instance
        GraphService.update_node(
            node_id=instance.node_id,
            label=serializer.validated_data.get('label'),
            position_x=serializer.validated_data.get('position_x'),
            position_y=serializer.validated_data.get('position_y'),
            data=serializer.validated_data.get('data')
        )

    @action(detail=True, methods=['patch'], url_path='update_node_fields')
    def update_node_fields(self, request, node_id=None):
        """Update node field definitions and persist to ProjectTypeDefinition."""
        logger.info(f'update_node_fields called with node_id={node_id}, request.data={request.data}')
        logger.info(f'Attempting to get node with node_id={node_id}')
        try:
            node = self.get_object()
            logger.info(f'Found node: {node.node_id}, type: {node.node_type}')
        except NodeInstance.DoesNotExist:
            logger.error(f'Node with node_id={node_id} not found')
            return Response({'error': f'Node {node_id} not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            field_definitions = request.data.get('field_definitions', [])
            field_serializer = FieldDefinitionSerializer(data=field_definitions, many=True)
            if not field_serializer.is_valid():
                return Response(
                    {'error': field_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Parse current data
            current_data = {}
            if node.data:
                try:
                    current_data = json.loads(node.data)
                except json.JSONDecodeError:
                    current_data = {}

            # Update field definitions in NodeInstance.data
            current_data['field_definitions'] = field_definitions

            # Serialize back to JSON
            node.data = json.dumps(current_data)
            node.save()

            # Enhanced persistence: Update ProjectTypeDefinition and registry
            try:
                # Get the node's project
                project = node.project
                node_type = node.node_type
                
                # Get or create ProjectTypeDefinition record
                type_def, created = ProjectTypeDefinition.objects.get_or_create(
                    project=project,
                    definition_type='node',
                    type_identifier=node_type,
                    defaults={'definition_data': '{}'}
                )
                
                # Parse existing definition_data
                try:
                    definition_data = json.loads(type_def.definition_data) if type_def.definition_data else {}
                except json.JSONDecodeError:
                    definition_data = {}
                
                # Update the fieldSchema in definition_data
                definition_data['fieldSchema'] = field_definitions
                
                # Save back to database
                type_def.definition_data = json.dumps(definition_data)
                type_def.save()
                
                # Update in-memory registry
                registry.register_field_schema(node_type, field_definitions)
                
                logger.info(f'Successfully persisted field definitions to ProjectTypeDefinition and registry for node type: {node_type}')
                
            except Exception as persist_error:
                logger.warning(f'Failed to persist to ProjectTypeDefinition or registry: {persist_error}')
                # Don't fail the entire request if persistence fails

            serializer = NodeInstanceSerializer(node)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Update failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'], url_path='debug_list')
    def debug_list(self, request):
        """Debug endpoint to list all node_ids and their database IDs."""
        nodes = NodeInstance.objects.all().values('id', 'node_id', 'node_type', 'label')
        return Response(list(nodes))


class NodeConnectionViewSet(viewsets.ModelViewSet):
    """CRUD operations for connections."""

    permission_classes = [AllowAny]
    serializer_class = NodeConnectionSerializer
    queryset = NodeConnection.objects.all()
    lookup_field = 'connection_id'

    def get_queryset(self):
        """Filter connections by user's projects."""
        return NodeConnection.objects.all()
        # In production with auth:
        # return NodeConnection.objects.filter(project__owner=self.request.user)