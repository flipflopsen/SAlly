"""Plugin-based node type registry with dynamic loading."""
from typing import Dict, Type, Optional, List, Tuple
from ...plugins.nodes.base import BaseNodePlugin, NodeHandle
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class NodeRegistry:
    """Central registry for all node types with plugin support."""

    _instance = None
    _nodes: Dict[str, Type[BaseNodePlugin]] = {}
    _field_schemas: Dict[str, List[dict]] = {}
    _project_types: Dict[int, List[str]] = {}  # Track which types came from which project

    def __new__(cls):
        """Singleton pattern for global registry access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, node_class: Type[BaseNodePlugin]) -> None:
        """Register a new node type plugin.

        Args:
            node_class: Node plugin class implementing BaseNodePlugin
        """
        node_type = node_class.get_type()
        logger.info(f"Registering node type: {node_type} from class {node_class.__name__}")
        if node_type in self._nodes:
            logger.warning(f"Node type '{node_type}' already registered, overwriting")
        self._nodes[node_type] = node_class
        logger.info(f"Registered node type: {node_type}")

    def register_dynamic_node(self, type_data: dict, project_id: Optional[int] = None) -> None:
        """Register a dynamic node plugin class from imported type definitions.

        Args:
            type_data: Dictionary containing type definition data
            project_id: Optional project ID to track which project this type came from
        """
        # Validate required fields
        required_fields = ['type', 'label', 'description', 'category', 'inputs', 'outputs']
        for field in required_fields:
            if field not in type_data:
                raise ValueError(f"Missing required field '{field}' in type_data")

        node_type = type_data['type']
        if node_type in self._nodes:
            logger.warning(f"Node type '{node_type}' already exists, skipping dynamic registration")
            return

        # Convert inputs and outputs to NodeHandle objects
        inputs = [NodeHandle(h['id'], h['label'], h['type'], h.get('dataType', 'any')) for h in type_data['inputs']]
        outputs = [NodeHandle(h['id'], h['label'], h['type'], h.get('dataType', 'any')) for h in type_data['outputs']]

        # Create dynamic class
        class DynamicNode(BaseNodePlugin):
            _imported_metadata = type_data

            @classmethod
            def get_type(cls) -> str:
                return type_data['type']

            @classmethod
            def get_label(cls) -> str:
                return type_data['label']

            @classmethod
            def get_description(cls) -> str:
                return type_data['description']

            @classmethod
            def get_category(cls) -> str:
                return type_data['category']

            @classmethod
            def get_inputs(cls) -> List[NodeHandle]:
                return inputs

            @classmethod
            def get_outputs(cls) -> List[NodeHandle]:
                return outputs

            @classmethod
            def get_field_schema(cls) -> List[dict]:
                return type_data.get('fieldSchema', [])

            @classmethod
            def get_default_data(cls) -> dict:
                return type_data.get('defaultData', {})

            def execute(self, inputs: Dict[str, any]) -> Dict[str, any]:
                return {}

        # Register the dynamic class
        self.register(DynamicNode)

        # Track which project this type came from
        if project_id is not None:
            if project_id not in self._project_types:
                self._project_types[project_id] = []
            if node_type not in self._project_types[project_id]:
                self._project_types[project_id].append(node_type)

        logger.info(f"Successfully registered dynamic node type: {node_type}")

    def unregister(self, node_type: str) -> bool:
        """Remove a node type from registry.

        Args:
            node_type: Type identifier of node to remove

        Returns:
            True if node was removed, False if not found
        """
        if node_type in self._nodes:
            del self._nodes[node_type]
            logger.info(f"Unregistered node type: {node_type}")
            return True
        return False

    def get_node(self, node_type: str) -> Optional[Type[BaseNodePlugin]]:
        """Retrieve node class by type identifier.

        Args:
            node_type: Type identifier string

        Returns:
            Node class or None if not found
        """
        return self._nodes.get(node_type)

    def get_all_nodes(self) -> Dict[str, Dict]:
        """Get metadata for all registered node types.

        Returns:
            Dictionary mapping node types to their metadata
        """
        logger.debug(f"Retrieving all registered nodes. Total count: {len(self._nodes)}")
        return {
            node_type: {
                **node_class.get_metadata(),
                'fieldSchema': self.get_field_schema(node_type)
            }
            for node_type, node_class in self._nodes.items()
        }

    def validate_node_data(self, node_type: str, data: dict) -> Tuple[bool, Optional[str]]:
        """Validate node data against schema.

        Args:
            node_type: Type identifier of node
            data: Data dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        node_class = self.get_node(node_type)
        if not node_class:
            return False, f"Unknown node type: {node_type}"

        field_schema = self.get_field_schema(node_type)
        is_valid, error = node_class.validate_data(data, field_schema)
        return is_valid, error

    def execute_node(self, node_type: str, inputs: dict) -> dict:
        """Execute node processing logic.

        Args:
            node_type: Type identifier of node
            inputs: Input data for node execution

        Returns:
            Dictionary of output data
        """
        node_class = self.get_node(node_type)
        if not node_class:
            raise ValueError(f"Unknown node type: {node_type}")

        instance = node_class()
        return instance.execute(inputs)

    def get_registry_status(self) -> Dict:
        """Get current registry status information.

        Returns:
            Dictionary with registry statistics and metadata
        """
        return {
            'total_nodes': len(self._nodes),
            'node_types': list(self._nodes.keys()),
            'timestamp': datetime.now().isoformat()
        }

    def register_field_schema(self, node_type: str, field_schema: List[dict]) -> None:
        """Register dynamic field schema for a node type.

        Args:
            node_type: Type identifier of node
            field_schema: List of field definition dictionaries
        """
        if not isinstance(field_schema, list):
            raise ValueError("field_schema must be a list")
        for field in field_schema:
            if not isinstance(field, dict):
                raise ValueError("Each field must be a dict")
            required_keys = ['name', 'field_type', 'data_type', 'required']
            for key in required_keys:
                if key not in field:
                    raise ValueError(f"Field missing required key: {key}")
        self._field_schemas[node_type] = field_schema
        logger.info(f"Registered field schema for node type: {node_type}")

    def get_field_schema(self, node_type: str) -> List[dict]:
        """Get field schema for a node type.

        Args:
            node_type: Type identifier of node

        Returns:
            List of field definition dictionaries
        """
        if node_type in self._field_schemas:
            return self._field_schemas[node_type]
        node_class = self.get_node(node_type)
        if node_class:
            return node_class.get_field_schema()
        return []

    def clear_field_schemas(self) -> None:
        """Clear all registered field schemas for testing/reset purposes."""
        self._field_schemas.clear()
        logger.info("Cleared all field schemas")

    def load_project_types(self, project_id: int) -> None:
        """Load project-specific node type definitions from database.

        Args:
            project_id: ID of the project to load types for
        """
        from ..models import ProjectTypeDefinition

        try:
            # Query project-specific node types from database
            project_node_types = ProjectTypeDefinition.objects.filter(
                project_id=project_id,
                definition_type='node'
            )

            loaded_count = 0
            for type_def in project_node_types:
                try:
                    definition = type_def.get_definition()
                    self.register_dynamic_node(definition, project_id)
                    self.register_field_schema(type_def.type_identifier, definition.get('fieldSchema', []))
                    loaded_count += 1
                except Exception as e:
                    logger.warning(f'Failed to load project node type {type_def.type_identifier}: {e}')

            logger.info(f'Loaded {loaded_count} project-specific node types for project {project_id}')

        except Exception as e:
            logger.error(f'Failed to load project types for project {project_id}: {e}')

    def clear_project_types(self, project_id: int) -> None:
        """Remove dynamic types that were loaded from a specific project.

        Args:
            project_id: ID of the project to clear types for
        """
        if project_id not in self._project_types:
            return

        types_to_remove = self._project_types[project_id].copy()
        removed_count = 0

        for node_type in types_to_remove:
            try:
                self.unregister(node_type)
                if node_type in self._field_schemas:
                    del self._field_schemas[node_type]
                removed_count += 1
            except Exception as e:
                logger.warning(f'Failed to remove project type {node_type}: {e}')

        # Clean up tracking
        del self._project_types[project_id]
        logger.info(f'Removed {removed_count} project-specific types for project {project_id}')


# Global registry instance
registry = NodeRegistry()