"""Base plugin interface for connection types."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple


class BaseConnectionPlugin(ABC):
    """Abstract base class for all connection plugins."""

    @classmethod
    @abstractmethod
    def get_type(cls) -> str:
        """Return unique type identifier for this connection.

        Returns:
            String type identifier (e.g., 'copper_cable', 'data_cable')
        """
        pass

    @classmethod
    @abstractmethod
    def get_label(cls) -> str:
        """Return human-readable label for this connection type.

        Returns:
            Display label string
        """
        pass

    @classmethod
    @abstractmethod
    def get_description(cls) -> str:
        """Return description of connection functionality.

        Returns:
            Description string
        """
        pass

    @classmethod
    @abstractmethod
    def get_category(cls) -> str:
        """Return category for connection organization.

        Returns:
            Category string (e.g., 'Power', 'Data', 'Communication')
        """
        pass

    @classmethod
    def get_field_schema(cls) -> List[dict]:
        """Return list of field definitions for dynamic fields.

        Returns:
            List of field definition dictionaries
        """
        return []

    @classmethod
    def get_default_data(cls) -> dict:
        """Return default data structure for new connections.

        Returns:
            Dictionary with default values
        """
        defaults = {}
        field_schema = cls.get_field_schema()
        for field in field_schema:
            if 'default_value' in field and field['name'] not in defaults:
                defaults[field['name']] = field['default_value']
        # Merge with any static defaults if subclasses define them
        static_defaults = cls._get_static_defaults()
        defaults.update(static_defaults)
        return defaults

    @classmethod
    def _get_static_defaults(cls) -> dict:
        """Return static default data (for backward compatibility).

        Subclasses can override this to provide static defaults.
        """
        return {}

    @classmethod
    def validate_data(cls, data: dict) -> Tuple[bool, Optional[str]]:
        """Validate connection data structure.

        Args:
            data: Data dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None

    @classmethod
    def validate_field_value(cls, field_def: dict, value) -> Tuple[bool, Optional[str]]:
        """Validate a single field value against its definition.

        Args:
            field_def: Field definition dictionary
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        name = field_def.get('name')
        data_type = field_def.get('data_type')
        required = field_def.get('required', False)

        if required and (value is None or value == ''):
            return False, f"Field '{name}' is required"

        if value is not None and value != '':
            if data_type == 'number':
                try:
                    num_value = float(value)
                except (ValueError, TypeError):
                    return False, f"Field '{name}' must be a number"
                min_val = field_def.get('min_value')
                if min_val is not None and num_value < min_val:
                    return False, f"Field '{name}' must be >= {min_val}"
                max_val = field_def.get('max_value')
                if max_val is not None and num_value > max_val:
                    return False, f"Field '{name}' must be <= {max_val}"
            elif data_type == 'string':
                if not isinstance(value, str):
                    return False, f"Field '{name}' must be a string"
            elif data_type == 'boolean':
                if not isinstance(value, bool) and str(value).lower() not in ['true', 'false']:
                    return False, f"Field '{name}' must be a boolean"
            # Add more data types as needed

        return True, None

    @classmethod
    def get_metadata(cls) -> dict:
        """Get complete metadata for this connection type.

        Returns:
            Dictionary with all connection metadata
        """
        return {
            'type': cls.get_type(),
            'label': cls.get_label(),
            'description': cls.get_description(),
            'category': cls.get_category(),
            'defaultData': cls.get_default_data(),
            'fieldSchema': cls.get_field_schema()
        }

    @abstractmethod
    def execute(self, inputs: Dict[str, any]) -> Dict[str, any]:
        """Execute connection processing logic.

        Args:
            inputs: Dictionary mapping input values

        Returns:
            Dictionary of output data
        """
        pass