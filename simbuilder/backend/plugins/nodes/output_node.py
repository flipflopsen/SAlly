"""Output node plugin for data visualization."""
from typing import Dict, List
from .base import BaseNodePlugin, NodeHandle


class OutputNode(BaseNodePlugin):
    """Node for displaying or exporting results."""

    @classmethod
    def get_type(cls) -> str:
        return 'output'

    @classmethod
    def get_label(cls) -> str:
        return 'Output'

    @classmethod
    def get_description(cls) -> str:
        return 'Displays or exports final results'

    @classmethod
    def get_category(cls) -> str:
        return 'Nodes'

    @classmethod
    def get_inputs(cls) -> List[NodeHandle]:
        return [
            NodeHandle('input', 'Input', 'input', 'any')
        ]

    @classmethod
    def get_outputs(cls) -> List[NodeHandle]:
        return []

    @classmethod
    def get_field_schema(cls) -> List[dict]:
        """Return field definitions for output node configuration."""
        return [
            # Input handle - maps to the input connection point
            {
                'name': 'input',
                'field_type': 'input',
                'data_type': 'any',
                'required': True,
                'description': 'Input value to be displayed or exported'
            },
            # Format field - output formatting configuration
            {
                'name': 'format',
                'field_type': 'monitor',
                'data_type': 'string',
                'required': False,
                'default_value': 'text',
                'description': 'Output format type'
            },
            # Destination field - output destination configuration
            {
                'name': 'destination',
                'field_type': 'monitor',
                'data_type': 'string',
                'required': False,
                'default_value': 'console',
                'description': 'Output destination'
            }
        ]

    @classmethod
    def get_default_data(cls) -> dict:
        return {
            'format': 'text',
            'destination': 'console'
        }

    def execute(self, inputs: Dict[str, any]) -> Dict[str, any]:
        """Log or store output value."""
        input_value = inputs.get('input')
        print(f"Output Node: {input_value}")
        return {}
