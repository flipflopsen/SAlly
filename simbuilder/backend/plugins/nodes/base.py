"""Base plugin interface for node types."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple


class NodeHandle:
    """Defines input/output handle on a node."""

    def __init__(
            self,
            handle_id: str,
            label: str,
            handle_type: str,
            data_type: str = 'any'
    ):
        """Initialize node handle.

        Args:
            handle_id: Unique identifier for handle
            label: Display label
            handle_type: 'input' or 'output'
            data_type: Data type constraint
        """
        self.handle_id = handle_id
        self.label = label
        self.handle_type = handle_type
        self.data_type = data_type

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            'id': self.handle_id,
            'label': self.label,
            'type': self.handle_type,
            'dataType': self.data_type
        }


class BaseNodePlugin(ABC):
    """Abstract base class for all node plugins."""

    @classmethod
    @abstractmethod
    def get_type(cls) -> str:
        """Return unique type identifier for this node.

        Returns:
            String type identifier (e.g., 'input', 'process')
        """
        pass

    @classmethod
    @abstractmethod
    def get_label(cls) -> str:
        """Return human-readable label for this node type.

        Returns:
            Display label string
        """
        pass

    @classmethod
    @abstractmethod
    def get_description(cls) -> str:
        """Return description of node functionality.

        Returns:
            Description string
        """
        pass

    @classmethod
    @abstractmethod
    def get_category(cls) -> str:
        """Return category for node organization.

        Returns:
            Category string (e.g., 'Input', 'Processing', 'Output')
        """
        pass

    @classmethod
    @abstractmethod
    def get_inputs(cls) -> List[NodeHandle]:
        """Define input handles for this node type.

        Returns:
            List of NodeHandle objects for inputs
        """
        pass

    @classmethod
    @abstractmethod
    def get_outputs(cls) -> List[NodeHandle]:
        """Define output handles for this node type.

        Returns:
            List of NodeHandle objects for outputs
        """
        pass

    @classmethod
    def get_field_schema(cls) -> List[dict]:
        """Return list of field definition dicts for dynamic fields.

        Each field definition dict should contain:
        - name: str
        - field_type: str ('input', 'output', 'parameter')
        - data_type: str ('string', 'number', 'boolean', etc.)
        - units: str (optional)
        - min_value: float (optional)
        - max_value: float (optional)
        - default_value: any (optional)
        - required: bool
        - description: str (optional)

        Returns:
            List of field definition dictionaries
        """
        return []

    @classmethod
    def get_default_data(cls) -> dict:
        """Return default data structure for new nodes, merged with field schema defaults.

        Returns:
            Dictionary with default values
        """
        defaults = {}
        field_schema = cls.get_field_schema()
        for field in field_schema:
            if 'default_value' in field:
                defaults[field['name']] = field['default_value']
        return defaults

    @classmethod
    def validate_data(cls, data: dict, field_schema: Optional[List[dict]] = None) -> Tuple[bool, Optional[str]]:
        """Validate node data structure, including dynamic field validation.

        Args:
            data: Data dictionary to validate
            field_schema: Optional list of field definitions for runtime validation

        Returns:
            Tuple of (is_valid, error_message)
        """
        if field_schema is None:
            field_schema = cls.get_field_schema()
        if field_schema:
            for field_def in field_schema:
                name = field_def['name']
                if field_def.get('required', False) and name not in data:
                    return False, f"Required field '{name}' is missing"
                if name in data:
                    is_valid, error = cls.validate_field_value(field_def, data[name])
                    if not is_valid:
                        return False, error
        return True, None

    @classmethod
    def validate_field_value(cls, field_def: dict, value) -> Tuple[bool, str]:
        """Validate a single field value against its definition.

        Args:
            field_def: Field definition dictionary
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        data_type = field_def.get('data_type', 'any')
        if data_type == 'number':
            if not isinstance(value, (int, float)):
                return False, f"Field '{field_def['name']}' must be a number"
            min_val = field_def.get('min_value')
            if min_val is not None and value < min_val:
                return False, f"Field '{field_def['name']}' must be >= {min_val}"
            max_val = field_def.get('max_value')
            if max_val is not None and value > max_val:
                return False, f"Field '{field_def['name']}' must be <= {max_val}"
        elif data_type == 'string':
            if not isinstance(value, str):
                return False, f"Field '{field_def['name']}' must be a string"
        elif data_type == 'boolean':
            if not isinstance(value, bool):
                return False, f"Field '{field_def['name']}' must be a boolean"
        # Add more data types as needed
        return True, ""

    @classmethod
    def get_metadata(cls) -> dict:
        """Get complete metadata for this node type.

        Returns:
            Dictionary with all node metadata
        """
        return {
            'type': cls.get_type(),
            'label': cls.get_label(),
            'description': cls.get_description(),
            'category': cls.get_category(),
            'inputs': [h.to_dict() for h in cls.get_inputs()],
            'outputs': [h.to_dict() for h in cls.get_outputs()],
            'defaultData': cls.get_default_data(),
            'fieldSchema': cls.get_field_schema()
        }

    @abstractmethod
    def execute(self, inputs: Dict[str, any]) -> Dict[str, any]:
        """Execute node processing logic.

        Args:
            inputs: Dictionary mapping input handle IDs to values

        Returns:
            Dictionary mapping output handle IDs to computed values
        """
        pass