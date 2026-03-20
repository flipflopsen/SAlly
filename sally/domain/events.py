# domain/events.py
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from sally.core.event_bus import Event
from sally.domain.grid_entities import GridMeasurement, EntityType
import time


@dataclass
class GridDataEvent(Event):
    """High-frequency grid measurement event"""
    event_type: str = field(init=False, default="grid_data_update")
    measurement: GridMeasurement = None

    def __post_init__(self):
        if self.timestamp is None and self.measurement is not None:
            self.timestamp = self.measurement.timestamp


@dataclass
class GridAlarmEvent(Event):
    """Grid alarm and fault detection event"""
    event_type: str = field(init=False, default="grid_alarm")
    entity: str = ""
    entity_type: str = ""
    alarm_type: str = ""
    severity: str = "INFO"  # 'INFO', 'WARNING', 'CRITICAL', 'EMERGENCY'
    message: str = ""
    threshold_value: Optional[float] = None
    measured_value: Optional[float] = None

    def __post_init__(self):
        pass


@dataclass
class LoadForecastEvent(Event):
    """Load forecasting result event"""
    event_type: str = field(init=False, default="load_forecast")
    entity: str = ""
    horizon_minutes: int = 0
    predicted_load: float = 0.0
    confidence_interval: Optional[tuple] = None  # (lower, upper)
    model_accuracy: Optional[float] = None

    def __post_init__(self):
        pass


@dataclass
class StabilityEvent(Event):
    """Grid stability monitoring event"""
    event_type: str = field(init=False, default="stability_alert")
    affected_entities: List[str] = field(default_factory=list)
    stability_metric: str = ""  # 'frequency', 'voltage', 'phase_angle'
    deviation_magnitude: float = 0.0
    risk_level: str = "LOW"  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    recommended_action: Optional[str] = None

    def __post_init__(self):
        pass


@dataclass
class ControlActionEvent(Event):
    """Automated control action event"""
    event_type: str = field(init=False, default="control_action")
    target_entity: str = ""
    action_type: str = ""  # 'voltage_regulation', 'load_shedding', 'generation_dispatch'
    control_value: float = 0.0
    reason: str = ""
    expected_result: str = ""

    def __post_init__(self):
        pass


@dataclass
class RuleTriggeredEvent(Event):
    event_type: str = field(init=False, default="rule_triggered")
    entity_name: str = ""
    variable_name: str = ""
    threshold: float = 0.0
    actual_value: float = 0.0
    action: str = ""
    rule_id: str = ""

    def __post_init__(self):
        pass


@dataclass
class SimulationStepEvent(Event):
    event_type: str = field(init=False, default="simulation_step")
    timestep: int = 0
    simulation_time: float = 0.0

    def __post_init__(self):
        pass


@dataclass
class SimulationStateEvent(Event):
    event_type: str = field(init=False, default="simulation_state")
    timestep: int = 0
    simulation_time: float = 0.0
    snapshot: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        pass


@dataclass
class SetpointChangeEvent(Event):
    event_type: str = field(init=False, default="setpoint_change")
    entity: str = ""
    variable: str = ""
    old_value: float = 0.0
    new_value: float = 0.0
    source: str  = "" # "scada_gui" or "external"

    def __post_init__(self):
        pass


@dataclass
class GridEntityData:
    """Grid entity metadata for relational database"""
    entity_id: int
    entity_name: str
    entity_type: str  # EntityType.value
    rated_power: Optional[float] = None
    rated_voltage: Optional[float] = None
    location: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    installation_date: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class GridConnectionData:
    """Grid entity connection/topology data"""
    from_entity_id: int
    to_entity_id: int
    connection_type: str  # 'line', 'transformer', 'switch', etc.
    line_length: Optional[float] = None
    resistance: Optional[float] = None
    reactance: Optional[float] = None
    capacity: Optional[float] = None
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class EntityRelationalDataEvent(Event):
    """Event for updating grid entity and connection topology data"""
    event_type: str = field(init=False, default="entity_relational_data")
    entities: List[GridEntityData] = field(default_factory=list)
    connections: List[GridConnectionData] = field(default_factory=list)
    operation: str = "upsert"  # 'insert', 'update', 'upsert', 'delete'

    def __post_init__(self):
        pass
