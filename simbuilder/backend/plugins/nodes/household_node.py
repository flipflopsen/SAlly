"""Household node plugin for residential entities."""
from typing import Dict, List, Tuple, Optional
from .base import BaseNodePlugin, NodeHandle


class HouseholdNode(BaseNodePlugin):
    """Node representing a household with electrical load."""

    @classmethod
    def get_type(cls) -> str:
        return 'household'

    @classmethod
    def get_label(cls) -> str:
        return 'Household'

    @classmethod
    def get_description(cls) -> str:
        return 'Represents a residential household with electrical consumption'

    @classmethod
    def get_category(cls) -> str:
        return 'Nodes'

    @classmethod
    def get_inputs(cls) -> List[NodeHandle]:
        return [
            NodeHandle('electricity', 'Electricity Input', 'input', 'power')
        ]

    @classmethod
    def get_outputs(cls) -> List[NodeHandle]:
        return [
            NodeHandle('load', 'Load Output', 'output', 'power')
        ]

    @classmethod
    def get_field_schema(cls) -> List[dict]:
        """Return field definitions for household node configuration."""
        return [
            # Input handles - maps to the input connection points
            {
                'name': 'electricity',
                'field_type': 'input',
                'data_type': 'number',
                'required': True,
                'units': 'kW',
                'description': 'Electricity input for household consumption'
            },
            # Output handle - maps to the output connection point
            {
                'name': 'load',
                'field_type': 'output',
                'data_type': 'number',
                'required': True,
                'units': 'kW',
                'description': 'Household electrical load demand'
            },
            # Monitor fields - household configuration parameters
            {
                'name': 'household_size',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 4,
                'min_value': 1,
                'max_value': 20,
                'description': 'Number of people in household'
            },
            {
                'name': 'base_load_kw',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 2.5,
                'min_value': 0.1,
                'max_value': 20.0,
                'units': 'kW',
                'description': 'Base electrical load consumption'
            },
            {
                'name': 'peak_load_kw',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 8.0,
                'min_value': 0.1,
                'max_value': 50.0,
                'units': 'kW',
                'description': 'Peak electrical load consumption'
            },
            {
                'name': 'efficiency',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 0.95,
                'min_value': 0.0,
                'max_value': 1.0,
                'description': 'Household electrical efficiency'
            }
        ]

    @classmethod
    def get_default_data(cls) -> dict:
        return {
            'household_size': 4,
            'base_load_kw': 2.5,
            'peak_load_kw': 8.0,
            'efficiency': 0.95
        }

    @classmethod
    def validate_data(cls, data: dict, field_schema: Optional[List[dict]] = None) -> Tuple[bool, Optional[str]]:
        if 'household_size' not in data:
            return False, "Household node must have 'household_size' field"
        if 'base_load_kw' not in data:
            return False, "Household node must have 'base_load_kw' field"
        if data.get('household_size', 0) <= 0:
            return False, "Household size must be positive"
        if data.get('base_load_kw', 0) <= 0:
            return False, "Base load must be positive"
        return True, None

    def execute(self, inputs: Dict[str, any]) -> Dict[str, any]:
        """Calculate household load based on input electricity and household parameters."""
        electricity_input = inputs.get('electricity', 0)

        # Simple load calculation based on household size and time-based factors
        base_load = self.data.get('base_load_kw', 2.5)
        household_size = self.data.get('household_size', 4)
        efficiency = self.data.get('efficiency', 0.95)

        # Basic load model - in reality this would be more sophisticated
        total_load = base_load * household_size * (0.8 + 0.4 * electricity_input)

        return {
            'load': total_load * efficiency
        }