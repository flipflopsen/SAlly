"""Monitor connection plugin for monitoring and observation flows."""
from typing import Dict, Tuple, Optional, List
from .base import BaseConnectionPlugin


class MonitorConnection(BaseConnectionPlugin):
    """Connection representing monitoring and observation data flow."""

    @classmethod
    def get_type(cls) -> str:
        return 'monitor'

    @classmethod
    def get_label(cls) -> str:
        return 'Monitor'

    @classmethod
    def get_description(cls) -> str:
        return 'Monitor connection for observation and monitoring data'

    @classmethod
    def get_category(cls) -> str:
        return 'Connections'

    @classmethod
    def get_field_schema(cls) -> List[dict]:
        """Return field definitions for monitor connection configuration."""
        return [
            {
                'name': 'monitoring_type',
                'field_type': 'monitor',
                'data_type': 'string',
                'required': False,
                'default_value': 'status',
                'description': 'Type of monitoring being performed'
            },
            {
                'name': 'sample_rate',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'default_value': 1.0,
                'min_value': 0.1,
                'max_value': 60.0,
                'description': 'Rate of monitoring data sampling'
            },
            {
                'name': 'alert_threshold',
                'field_type': 'monitor',
                'data_type': 'number',
                'required': False,
                'description': 'Threshold value for triggering alerts'
            }
        ]

    @classmethod
    def get_default_data(cls) -> dict:
        return {
            'monitoring_type': 'status',
            'sample_rate': 1.0,
            'alert_threshold': None
        }

    @classmethod
    def validate_data(cls, data: dict) -> Tuple[bool, Optional[str]]:
        if 'monitoring_type' not in data:
            return False, "Monitor connection must have 'monitoring_type' field"
        if 'sample_rate' not in data:
            return False, "Monitor connection must have 'sample_rate' field"
        if data.get('sample_rate', 0) <= 0:
            return False, "Sample rate must be positive"
        return True, None

    def execute(self, inputs: Dict[str, any]) -> Dict[str, any]:
        """Process monitoring data flow."""
        data_input = inputs.get('data', {})
        sample_rate = self.data.get('sample_rate', 1.0)
        monitoring_type = self.data.get('monitoring_type', 'status')

        return {
            'data': data_input,
            'monitoring_type': monitoring_type,
            'sample_rate': sample_rate,
            'success': True
        }