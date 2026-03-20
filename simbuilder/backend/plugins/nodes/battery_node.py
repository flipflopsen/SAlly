"""Battery node plugin for energy storage entities."""
from typing import Dict, List, Tuple, Optional
from .base import BaseNodePlugin, NodeHandle


class BatteryNode(BaseNodePlugin):
    """Node representing a battery energy storage system."""

    @classmethod
    def get_type(cls) -> str:
        return 'battery'

    @classmethod
    def get_label(cls) -> str:
        return 'Battery'

    @classmethod
    def get_description(cls) -> str:
        return 'Represents a battery energy storage system for grid stabilization'

    @classmethod
    def get_category(cls) -> str:
        return 'Nodes'

    @classmethod
    def get_inputs(cls) -> List[NodeHandle]:
        return [
            NodeHandle('charge', 'Charge Input', 'input', 'power'),
            NodeHandle('grid_power', 'Grid Power', 'input', 'power')
        ]

    @classmethod
    def get_outputs(cls) -> List[NodeHandle]:
        return [
            NodeHandle('discharge', 'Discharge Output', 'output', 'power'),
            NodeHandle('soc', 'State of Charge', 'output', 'percentage')
        ]

    @classmethod
    def get_field_schema(cls) -> List[dict]:
        """Return field definitions for battery node configuration."""
        return [
            # Input handles - maps to the input connection points
            {
                'name': 'charge',
                'field_type': 'input',
                'data_type': 'number',
                'required': True,
                'units': 'kW',
                'description': 'Power input for charging the battery'
            },
            {
                'name': 'grid_power',
                'field_type': 'input',
                'data_type': 'number',
                'required': True,
                'units': 'kW',
                'description': 'Grid power availability'
            },
            # Output handles - maps to the output connection points
            {
                'name': 'discharge',
                'field_type': 'output',
                'data_type': 'number',
                'required': True,
                'units': 'kW',
                'description': 'Power output from battery discharge'
            },
            {
                'name': 'soc',
                'field_type': 'output',
                'data_type': 'number',
                'required': True,
                'units': '%',
                'description': 'State of charge as percentage'
            },
            # Monitor fields - battery configuration parameters
            {
                'name': 'capacity_kwh',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 100.0,
                'min_value': 0.1,
                'units': 'kWh',
                'description': 'Total battery capacity'
            },
            {
                'name': 'max_charge_rate_kw',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 50.0,
                'min_value': 0.1,
                'units': 'kW',
                'description': 'Maximum charging power rate'
            },
            {
                'name': 'max_discharge_rate_kw',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 50.0,
                'min_value': 0.1,
                'units': 'kW',
                'description': 'Maximum discharging power rate'
            },
            {
                'name': 'current_soc',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 0.5,
                'min_value': 0.0,
                'max_value': 1.0,
                'description': 'Current state of charge (0-1)'
            },
            {
                'name': 'efficiency',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 0.92,
                'min_value': 0.0,
                'max_value': 1.0,
                'description': 'Battery round-trip efficiency'
            }
        ]

    @classmethod
    def get_default_data(cls) -> dict:
        return {
            'capacity_kwh': 100.0,
            'max_charge_rate_kw': 50.0,
            'max_discharge_rate_kw': 50.0,
            'current_soc': 0.5,  # 50% state of charge
            'efficiency': 0.92
        }

    @classmethod
    def validate_data(cls, data: dict, field_schema: Optional[List[dict]] = None) -> Tuple[bool, Optional[str]]:
        if 'capacity_kwh' not in data:
            return False, "Battery node must have 'capacity_kwh' field"
        if 'max_charge_rate_kw' not in data:
            return False, "Battery node must have 'max_charge_rate_kw' field"
        if 'max_discharge_rate_kw' not in data:
            return False, "Battery node must have 'max_discharge_rate_kw' field"
        if data.get('capacity_kwh', 0) <= 0:
            return False, "Battery capacity must be positive"
        if data.get('current_soc', 0) < 0 or data.get('current_soc', 1) > 1:
            return False, "State of charge must be between 0 and 1"
        return True, None

    def execute(self, inputs: Dict[str, any]) -> Dict[str, any]:
        """Calculate battery behavior based on inputs and current state."""
        charge_input = inputs.get('charge', 0)
        grid_power = inputs.get('grid_power', 0)

        capacity = self.data.get('capacity_kwh', 100.0)
        max_charge_rate = self.data.get('max_charge_rate_kw', 50.0)
        max_discharge_rate = self.data.get('max_discharge_rate_kw', 50.0)
        current_soc = self.data.get('current_soc', 0.5)
        efficiency = self.data.get('efficiency', 0.92)

        # Simple battery model
        # If grid power is high, charge the battery
        # If grid power is low, discharge to support grid

        net_power = grid_power - charge_input

        if net_power > 0:
            # Excess power available, charge battery
            charge_amount = min(net_power, max_charge_rate)
            energy_charged = charge_amount * efficiency
            new_soc = min(1.0, current_soc + (energy_charged / capacity))
            discharge_amount = 0
        else:
            # Need power, discharge battery
            discharge_amount = min(abs(net_power), max_discharge_rate)
            energy_discharged = discharge_amount / efficiency
            new_soc = max(0.0, current_soc - (energy_discharged / capacity))
            charge_amount = 0

        # Update the battery's state of charge for next execution
        self.data['current_soc'] = new_soc

        return {
            'discharge': discharge_amount,
            'soc': new_soc * 100  # Return as percentage
        }