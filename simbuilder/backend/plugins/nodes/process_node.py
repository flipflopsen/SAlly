"""Processing node plugin for data transformation."""
from typing import Dict, List, Tuple, Optional
from .base import BaseNodePlugin, NodeHandle


class ProcessNode(BaseNodePlugin):
    """Node for data processing and transformation."""

    @classmethod
    def get_type(cls) -> str:
        return 'process'

    @classmethod
    def get_label(cls) -> str:
        return 'Process'

    @classmethod
    def get_description(cls) -> str:
        return 'Processes input data and produces output'

    @classmethod
    def get_category(cls) -> str:
        return 'Nodes'

    @classmethod
    def get_inputs(cls) -> List[NodeHandle]:
        return [
            NodeHandle('input1', 'Input 1', 'input', 'any'),
            NodeHandle('input2', 'Input 2', 'input', 'any')
        ]

    @classmethod
    def get_outputs(cls) -> List[NodeHandle]:
        return [
            NodeHandle('output', 'Result', 'output', 'any')
        ]

    @classmethod
    def get_field_schema(cls) -> List[dict]:
        """Return field definitions for process node configuration."""
        return [
            # Input handles - maps to the input connection points
            {
                'name': 'input1',
                'field_type': 'input',
                'data_type': 'any',
                'required': True,
                'description': 'First input value for processing'
            },
            {
                'name': 'input2',
                'field_type': 'input',
                'data_type': 'any',
                'required': True,
                'description': 'Second input value for processing'
            },
            # Output handle - maps to the output connection point
            {
                'name': 'output',
                'field_type': 'output',
                'data_type': 'any',
                'required': True,
                'description': 'Processed output result'
            },
            # Operation field - processing configuration
            {
                'name': 'operation',
                'field_type': 'monitor',
                'data_type': 'string',
                'required': False,
                'default_value': 'concat',
                'description': 'Processing operation to perform'
            },
            # Parameters field - operation parameters
            {
                'name': 'parameters',
                'field_type': 'monitor',
                'data_type': 'object',
                'required': False,
                'default_value': {},
                'description': 'Additional parameters for the operation'
            }
        ]

    @classmethod
    def get_default_data(cls) -> dict:
        return {
            'operation': 'concat',
            'parameters': {}
        }

    @classmethod
    def validate_data(cls, data: dict, field_schema: Optional[List[dict]] = None) -> Tuple[bool, Optional[str]]:
        if 'operation' not in data:
            return False, "Process node must specify 'operation'"

        valid_operations = ['concat', 'add', 'multiply', 'transform']
        if data['operation'] not in valid_operations:
            return False, f"Invalid operation. Must be one of: {valid_operations}"

        return True, None

    def execute(self, inputs: Dict[str, any]) -> Dict[str, any]:
        """Execute configured operation on inputs."""
        operation = self.data.get('operation', 'concat')
        input1 = inputs.get('input1')
        input2 = inputs.get('input2')

        if operation == 'concat':
            result = str(input1) + str(input2)
        elif operation == 'add':
            result = float(input1) + float(input2)
        elif operation == 'multiply':
            result = float(input1) * float(input2)
        else:
            result = None

        return {'output': result}
