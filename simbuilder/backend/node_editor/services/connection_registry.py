"""Plugin-based connection type registry with dynamic loading."""
from typing import Dict, Type, List, Optional, Tuple
from ...plugins.connections.base import BaseConnectionPlugin
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class ConnectionRegistry:
    """Central registry for all connection types with plugin support."""

    _instance = None
    _connections: Dict[str, Type[BaseConnectionPlugin]] = {}
    _field_schemas: Dict[str, List[dict]] = {}
    _project_types: Dict[int, List[str]] = {}  # Track which types came from which project

    def __new__(cls):
        """Singleton pattern for global registry access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, connection_class: Type[BaseConnectionPlugin]) -> None:
        """Register a new connection type plugin.

        Args:
            connection_class: Connection plugin class implementing BaseConnectionPlugin
        """
        connection_type = connection_class.get_type()
        logger.info(f"Registering connection type: {connection_type} from class {connection_class.__name__}")
        if connection_type in self._connections:
            logger.warning(f"Connection type '{connection_type}' already registered, overwriting")
        self._connections[connection_type] = connection_class
        logger.info(f"Registered connection type: {connection_type}")

    def register_dynamic_connection(self, type_data: dict, project_id: Optional[int] = None) -> None:
        """Register a dynamic connection plugin class from imported type definitions.

        Args:
            type_data: Dictionary containing type, label, description, category, defaultData, fieldSchema
            project_id: Optional project ID to track which project this type came from
        """
        # Validate required fields
        required_fields = ['type', 'label', 'description', 'category']
        for field in required_fields:
            if field not in type_data:
                raise ValueError(f"Missing required field '{field}' in type_data")

        connection_type = type_data['type']
        if connection_type in self._connections:
            logger.warning(f"Connection type '{connection_type}' already exists, skipping dynamic registration")
            return

        # Create dynamic class using type()
        class_name = f"DynamicConnection_{connection_type.replace('-', '_').replace(' ', '_')}"

        def get_type(cls):
            return type_data['type']

        def get_label(cls):
            return type_data['label']

        def get_description(cls):
            return type_data['description']

        def get_category(cls):
            return type_data['category']

        def get_field_schema(cls):
            return type_data.get('fieldSchema', [])

        def get_default_data(cls):
            return type_data.get('defaultData', {})

        def execute(self, inputs):
            return {}

        DynamicConnection = type(class_name, (BaseConnectionPlugin,), {
            'get_type': classmethod(get_type),
            'get_label': classmethod(get_label),
            'get_description': classmethod(get_description),
            'get_category': classmethod(get_category),
            'get_field_schema': classmethod(get_field_schema),
            'get_default_data': classmethod(get_default_data),
            'execute': execute,
            '_imported_metadata': type_data
        })

        self.register(DynamicConnection)

        # Track which project this type came from
        if project_id is not None:
            if project_id not in self._project_types:
                self._project_types[project_id] = []
            if connection_type not in self._project_types[project_id]:
                self._project_types[project_id].append(connection_type)

        logger.info(f"Successfully registered dynamic connection type: {connection_type}")

    def unregister(self, connection_type: str) -> bool:
        """Remove a connection type from registry.

        Args:
            connection_type: Type identifier of connection to remove

        Returns:
            True if connection was removed, False if not found
        """
        if connection_type in self._connections:
            del self._connections[connection_type]
            logger.info(f"Unregistered connection type: {connection_type}")
            return True
        return False

    def get_connection(self, connection_type: str) -> Optional[Type[BaseConnectionPlugin]]:
        """Retrieve connection class by type identifier.

        Args:
            connection_type: Type identifier string

        Returns:
            Connection class or None if not found
        """
        return self._connections.get(connection_type)

    def get_all_connections(self) -> Dict[str, Dict]:
        """Get metadata for all registered connection types.

        Returns:
            Dictionary mapping connection types to their metadata
        """
        logger.debug(f"Retrieving all registered connections. Total count: {len(self._connections)}")
        return {
            connection_type: {
                **connection_class.get_metadata(),
                'fieldSchema': self.get_field_schema(connection_type)
            }
            for connection_type, connection_class in self._connections.items()
        }

    def validate_connection_data(self, connection_type: str, data: dict) -> Tuple[bool, Optional[str]]:
        """Validate connection data against schema.

        Args:
            connection_type: Type identifier of connection
            data: Data dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        connection_class = self.get_connection(connection_type)
        if not connection_class:
            return False, f"Unknown connection type: {connection_type}"

        is_valid, error = connection_class.validate_data(data)
        field_schema = self.get_field_schema(connection_type)
        if field_schema:
            for field in field_schema:
                name = field['name']
                if name in data:
                    valid, err = connection_class.validate_field_value(field, data[name])
                    if not valid:
                        if error:
                            error += f"; {err}"
                        else:
                            error = err
                        is_valid = False
        return is_valid, error

    def execute_connection(self, connection_type: str, inputs: dict) -> dict:
        """Execute connection processing logic.

        Args:
            connection_type: Type identifier of connection
            inputs: Input data for connection execution

        Returns:
            Dictionary of output data
        """
        connection_class = self.get_connection(connection_type)
        if not connection_class:
            raise ValueError(f"Unknown connection type: {connection_type}")

        instance = connection_class()
        return instance.execute(inputs)

    def get_registry_status(self) -> Dict:
        """Get current registry status information.

        Returns:
            Dictionary with registry statistics and metadata
        """
        return {
            'total_connections': len(self._connections),
            'connection_types': list(self._connections.keys()),
            'timestamp': datetime.now().isoformat()
        }

    def register_field_schema(self, connection_type: str, field_schema: List[dict]) -> None:
        """Register dynamic field schema for a connection type.

        Args:
            connection_type: Type identifier of connection
            field_schema: List of field definition dictionaries
        """
        # Validate field_schema structure
        if not isinstance(field_schema, list):
            raise ValueError("Field schema must be a list")
        for field in field_schema:
            if not isinstance(field, dict):
                raise ValueError("Field schema must be list of dicts")
            required_keys = ['name', 'field_type', 'data_type']
            for key in required_keys:
                if key not in field:
                    raise ValueError(f"Field missing required key: {key}")
        self._field_schemas[connection_type] = field_schema
        logger.info(f"Registered field schema for connection type: {connection_type}")

    def get_field_schema(self, connection_type: str) -> List[dict]:
        """Get field schema for a connection type.

        Args:
            connection_type: Type identifier of connection

        Returns:
            List of field definition dictionaries
        """
        if connection_type in self._field_schemas:
            return self._field_schemas[connection_type]
        connection_class = self.get_connection(connection_type)
        if connection_class:
            return connection_class.get_field_schema()
        return []

    def clear_field_schemas(self) -> None:
        """Clear all registered field schemas (for testing/reset purposes)."""
        self._field_schemas.clear()
        logger.info("Cleared all field schemas")

    def load_project_types(self, project_id: int) -> None:
        """Load project-specific connection type definitions from database.

        Args:
            project_id: ID of the project to load types for
        """
        from ..models import ProjectTypeDefinition

        try:
            # Query project-specific connection types from database
            project_connection_types = ProjectTypeDefinition.objects.filter(
                project_id=project_id,
                definition_type='connection'
            )

            loaded_count = 0
            for type_def in project_connection_types:
                try:
                    definition = type_def.get_definition()
                    self.register_dynamic_connection(definition, project_id)
                    self.register_field_schema(type_def.type_identifier, definition.get('fieldSchema', []))
                    loaded_count += 1
                except Exception as e:
                    logger.warning(f'Failed to load project connection type {type_def.type_identifier}: {e}')

            logger.info(f'Loaded {loaded_count} project-specific connection types for project {project_id}')

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

        for connection_type in types_to_remove:
            try:
                self.unregister(connection_type)
                if connection_type in self._field_schemas:
                    del self._field_schemas[connection_type]
                removed_count += 1
            except Exception as e:
                logger.warning(f'Failed to remove project type {connection_type}: {e}')

        # Clean up tracking
        del self._project_types[project_id]
        logger.info(f'Removed {removed_count} project-specific connection types for project {project_id}')


# Global registry instance
connection_registry = ConnectionRegistry()