"""Business logic layer for graph operations."""
from typing import Dict, List, Optional
from django.db import transaction
from ..models import GraphProject, NodeInstance, NodeConnection
from .node_registry import registry
from .connection_registry import connection_registry
import logging

logger = logging.getLogger(__name__)


class GraphService:
    """Service layer handling graph CRUD operations."""

    @staticmethod
    def create_project(name: str, description: str, owner) -> GraphProject:
        """Create new graph project.

        Args:
            name: Project name
            description: Project description
            owner: User instance owning the project

        Returns:
            Created GraphProject instance
        """
        project = GraphProject.objects.create(
            name=name,
            description=description,
            owner=owner
        )
        logger.info(f"Created project: {project.id}")
        return project

    @staticmethod
    @transaction.atomic
    def add_node(
            project_id: int,
            node_id: str,
            node_type: str,
            label: str,
            position_x: float,
            position_y: float,
            data: Optional[dict] = None
    ) -> NodeInstance:
        """Add node to project with validation.

        Args:
            project_id: ID of parent project
            node_id: Unique node identifier
            node_type: Type from node registry
            label: Display label for node
            position_x: X coordinate
            position_y: Y coordinate
            data: Additional node data

        Returns:
            Created NodeInstance

        Raises:
            ValueError: If node type invalid or data validation fails
        """
        if not registry.get_node(node_type):
            raise ValueError(f"Invalid node type: {node_type}")

        if data:
            is_valid, error = registry.validate_node_data(node_type, data)
            if not is_valid:
                raise ValueError(f"Invalid node data: {error}")

        project, created = GraphProject.objects.get_or_create(id=project_id, defaults={'name': f'Project {project_id}'})
        if created:
            logger.info(f'Created new project {project_id} during node addition')
        node = NodeInstance.objects.create(
            project=project,
            node_id=node_id,
            node_type=node_type,
            label=label,
            position_x=position_x,
            position_y=position_y,
            data=data or {}
        )
        logger.info(f"Added node {node_id} to project {project_id}")
        return node

    @staticmethod
    @transaction.atomic
    def update_node(
            node_id: str,
            label: Optional[str] = None,
            position_x: Optional[float] = None,
            position_y: Optional[float] = None,
            data: Optional[dict] = None
    ) -> NodeInstance:
        """Update node properties.

        Args:
            node_id: Unique node identifier
            label: New label (if provided)
            position_x: New X coordinate (if provided)
            position_y: New Y coordinate (if provided)
            data: Updated data dict (if provided)

        Returns:
            Updated NodeInstance
        """
        node = NodeInstance.objects.get(node_id=node_id)

        if label is not None:
            node.label = label
        if position_x is not None:
            node.position_x = position_x
        if position_y is not None:
            node.position_y = position_y
        if data is not None:
            is_valid, error = registry.validate_node_data(node.node_type, data)
            if not is_valid:
                raise ValueError(f"Invalid node data: {error}")
            node.data = data

        node.save()
        logger.info(f"Updated node {node_id}")
        return node

    @staticmethod
    @transaction.atomic
    def create_connection(
            project_id: int,
            connection_id: str,
            connection_type: str = 'default',
            source_node_id: str = None,
            target_node_id: str = None,
            source_handle: str = None,
            target_handle: str = None
    ) -> NodeConnection:
        """Create connection between nodes.

        Args:
            project_id: ID of parent project
            connection_id: Unique connection identifier
            connection_type: Type of connection (e.g., 'copper_cable', 'data_cable')
            source_node_id: Source node ID
            target_node_id: Target node ID
            source_handle: Output handle on source
            target_handle: Input handle on target

        Returns:
            Created NodeConnection
        """
        project, created = GraphProject.objects.get_or_create(id=project_id, defaults={'name': f'Project {project_id}'})
        if created:
            logger.info(f'Created new project {project_id} during connection creation')
        source = NodeInstance.objects.get(node_id=source_node_id)
        target = NodeInstance.objects.get(node_id=target_node_id)

        # Validate connection type exists
        if not connection_registry.get_connection(connection_type):
            raise ValueError(f"Invalid connection type: {connection_type}")

        # Add field schema validation
        field_schema = connection_registry.get_field_schema(connection_type)

        # Optional: Validate handle compatibility
        if source_handle and target_handle:
            source_metadata = registry.get_node(source.node_type)
            if source_metadata:
                source_metadata = source_metadata.get_metadata()
                source_outputs = source_metadata.get('outputs', [])
                target_metadata = registry.get_node(target.node_type)
                if target_metadata:
                    target_metadata = target_metadata.get_metadata()
                    target_inputs = target_metadata.get('inputs', [])

                    if not any(output.get('id') == source_handle for output in source_outputs):
                        raise ValueError(f"Source handle '{source_handle}' not found in node type '{source.node_type}' outputs")
                    if not any(input.get('id') == target_handle for input in target_inputs):
                        raise ValueError(f"Target handle '{target_handle}' not found in node type '{target.node_type}' inputs")

        connection = NodeConnection.objects.create(
            project=project,
            connection_id=connection_id,
            connection_type=connection_type,
            source_node=source,
            target_node=target,
            source_handle=source_handle,
            target_handle=target_handle
        )
        logger.info(f"Created connection {connection_id} in project {project_id}")
        return connection

    @staticmethod
    def delete_node(node_id: str) -> bool:
        """Delete node and associated connections.

        Args:
            node_id: Unique node identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            node = NodeInstance.objects.get(node_id=node_id)
            node.delete()
            logger.info(f"Deleted node {node_id}")
            return True
        except NodeInstance.DoesNotExist:
            return False

    @staticmethod
    def delete_connection(connection_id: str) -> bool:
        """Delete specific connection.

        Args:
            connection_id: Unique connection identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            connection = NodeConnection.objects.get(connection_id=connection_id)
            connection.delete()
            logger.info(f"Deleted connection {connection_id}")
            return True
        except NodeConnection.DoesNotExist:
            return False