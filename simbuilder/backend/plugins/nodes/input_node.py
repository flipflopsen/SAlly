"""Input node plugin for data entry."""
from typing import Dict, List, Tuple, Optional
from .base import BaseNodePlugin, NodeHandle


class InputNode(BaseNodePlugin):
    """Node for manual data input."""

    @classmethod
    def get_type(cls) -> str:
        return 'input'

    @classmethod
    def get_label(cls) -> str:
        return 'Input'

    @classmethod
    def get_description(cls) -> str:
        return 'Provides input data to the graph'

    @classmethod
    def get_category(cls) -> str:
        return 'Nodes'

    @classmethod
    def get_inputs(cls) -> List[NodeHandle]:
        return []

    @classmethod
    def get_outputs(cls) -> List[NodeHandle]:
        return [
            NodeHandle('output', 'Output', 'output', 'any')
        ]

    @classmethod
    def get_field_schema(cls) -> List[dict]:
        """Return field definitions for input node configuration."""
        return [
            # Output handle - maps to the output connection point
            {
                'name': 'output',
                'field_type': 'output',
                'data_type': 'string',
                'required': True,
                'description': 'Output value that can be connected to other nodes'
            },
            # Value field - user input value
            {
                'name': 'value',
                'field_type': 'monitor',
                'data_type': 'string',
                'required': False,
                'default_value': '',
                'description': 'Input value to be provided'
            },
            # Data type selection - tracks configuration
            {
                'name': 'dataType',
                'field_type': 'monitor',
                'data_type': 'string',
                'required': False,
                'default_value': 'string',
                'description': 'Data type of the input value'
            }
        ]

    @classmethod
    def get_default_data(cls) -> dict:
        return {
            'value': '',
            'dataType': 'string'
        }

    @classmethod
    def validate_data(cls, data: dict, field_schema: Optional[List[dict]] = None) -> Tuple[bool, Optional[str]]:
        if 'value' not in data:
            return False, "Input node must have 'value' field"
        return True, None

    def execute(self, inputs: Dict[str, any]) -> Dict[str, any]:
        """Return configured value."""
        return {
            'output': self.data.get('value')
        }
