import mosaik_api_v3
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from sally.core.logger import get_logger
from sally.core.event_bus import EventBus


class BaseMosaikSimulator(mosaik_api_v3.Simulator, ABC):
    """
    Enhanced base class for all Mosaik simulators with dependency injection support.
    """

    def __init__(self, meta: Dict[str, Any], logger=None, event_bus: EventBus = None):
        super().__init__(meta)
        self.eid_prefix = ""
        self.entities: Dict[str, Dict[str, Any]] = {}  # eid -> entity_data
        self.entity_idx = 0
        self.logger = logger or get_logger(self.__class__.__name__)
        self.event_bus = event_bus
        self.sid = None
        self.time_resolution = 1.0
        self.sim_start_time = 0

    def get_entity_id(self, model_name: str) -> str:
        """Generate unique entity ID with prefix"""
        self.entity_idx += 1
        return f"{self.eid_prefix}-{self.entity_idx}"

    def init(self, sid: str, time_resolution: float, eid_prefix: Optional[str] = None,
             sim_start_time: float = 0, **kwargs) -> Dict[str, Any]:
        """
        Initialize the simulator with dependency injection support.

        Args:
            sid: Simulator ID
            time_resolution: Time resolution in seconds
            eid_prefix: Entity ID prefix override
            sim_start_time: Simulation start time
            **kwargs: Additional initialization parameters

        Returns:
            Simulator metadata
        """
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix

        self.sid = sid
        self.time_resolution = time_resolution
        self.sim_start_time = sim_start_time

        self.logger.info(f"Initialized {self.__class__.__name__} with SID: {sid}")
        return self.meta

    @abstractmethod
    def create(self, num: int, model: str, **model_params) -> List[Dict[str, Any]]:
        """Create entities of the specified model type"""
        pass

    @abstractmethod
    def step(self, time: int, inputs: Dict[str, Any], max_advance: int) -> int:
        """Advance simulation by one step"""
        pass

    def get_data(self, outputs: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
        """
        Get data for specified entities and attributes.

        Args:
            outputs: Dict mapping entity IDs to list of attribute names

        Returns:
            Dict mapping entity IDs to attribute data
        """
        data = {}
        for eid, attrs in outputs.items():
            if eid in self.entities:
                data[eid] = {}
                for attr in attrs:
                    if attr in self.entities[eid]:
                        data[eid][attr] = self.entities[eid][attr]
                    else:
                        self.logger.warning(f"Attribute {attr} not found for entity {eid}")
        return data

    def publish_event(self, event_type: str, data: Dict[str, Any]):
        """Publish event to event bus if available"""
        if self.event_bus:
            try:
                # This would need to be implemented based on the event system
                # For now, just log the event
                self.logger.debug(f"Publishing event {event_type}: {data}")
            except Exception as e:
                self.logger.error(f"Failed to publish event: {e}")

    def log_info(self, message: str, **kwargs):
        """Log info message with context"""
        self.logger.info(f"[{self.sid}] {message}", **kwargs)

    def log_warning(self, message: str, **kwargs):
        """Log warning message with context"""
        self.logger.warning(f"[{self.sid}] {message}", **kwargs)

    def log_error(self, message: str, **kwargs):
        """Log error message with context"""
        self.logger.error(f"[{self.sid}] {message}", **kwargs)

    def validate_entity_params(self, model_params: Dict[str, Any], required_params: List[str]) -> bool:
        """
        Validate that required parameters are present in model parameters.

        Args:
            model_params: Model parameters dictionary
            required_params: List of required parameter names

        Returns:
            True if all required parameters are present
        """
        missing_params = [param for param in required_params if param not in model_params]
        if missing_params:
            self.log_error(f"Missing required parameters: {missing_params}")
            return False
        return True

    def get_entity_by_id(self, eid: str) -> Optional[Dict[str, Any]]:
        """Get entity data by entity ID"""
        return self.entities.get(eid)

    def update_entity_attribute(self, eid: str, attr: str, value: Any):
        """Update a specific entity attribute"""
        if eid in self.entities:
            self.entities[eid][attr] = value
        else:
            self.log_warning(f"Entity {eid} not found for attribute update")

    def get_all_entities(self) -> Dict[str, Dict[str, Any]]:
        """Get all entities"""
        return self.entities.copy()

    def get_entity_count(self) -> int:
        """Get number of entities"""
        return len(self.entities)

    def cleanup_entities(self):
        """Clean up entity data"""
        self.entities.clear()
        self.entity_idx = 0
        self.log_info("Entity data cleaned up")
