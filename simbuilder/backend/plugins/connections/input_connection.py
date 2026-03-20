"""Input connection plugin for data input flows."""
from typing import Dict, Tuple, Optional, List
from .base import BaseConnectionPlugin


class InputConnection(BaseConnectionPlugin):
    """Connection representing input data flow between nodes."""

    @classmethod
    def get_type(cls) -> str:
        return 'input'

    @classmethod
    def get_label(cls) -> str:
        return 'Input'

    @classmethod
    def get_description(cls) -> str:
        return 'Input connection for data flow into nodes'

    @classmethod
    def get_category(cls) -> str:
        return 'Connections'

    @classmethod
    def get_field_schema(cls) -> List[dict]:
        """Return field definitions for input connection configuration."""
        return [
            {
                'name': 'data_type',
                'field_type': 'monitor',
                'data_type': 'string',
                'required': False,
                'default_value': 'generic',
                'description': 'Type of data being input'
            },
            {
                'name': 'flow_rate',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 1.0,
                'min_value': 0.1,
                'max_value': 100.0,
                'description': 'Rate of data flow'
            },
            {
                'name': 'priority',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 1,
                'min_value': 1,
                'max_value': 10,
                'description': 'Priority level for this input connection'
            }
        ]

    @classmethod
    def get_default_data(cls) -> dict:
        return {
            'data_type': 'generic',
            'flow_rate': 1.0,
            'priority': 1
        }

    @classmethod
    def validate_data(cls, data: dict) -> Tuple[bool, Optional[str]]:
        if 'data_type' not in data:
            return False, "Input connection must have 'data_type' field"
        if 'flow_rate' not in data:
            return False, "Input connection must have 'flow_rate' field"
        if data.get('flow_rate', 0) <= 0:
            return False, "Flow rate must be positive"
        return True, None

    def execute(self, inputs: Dict[str, any]) -> Dict[str, any]:
        """Process input data flow."""
        data_input = inputs.get('data', {})
        flow_rate = self.data.get('flow_rate', 1.0)

        return {
            'data': data_input,
            'flow_rate': flow_rate,
            'success': True
        }