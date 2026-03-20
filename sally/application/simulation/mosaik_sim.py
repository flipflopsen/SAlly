import mosaik
import mosaik_api_v3
import random
import time
import asyncio
from typing import Dict, Any, Optional, List
from sally.application.simulation.base_sim import BaseSimulation
from sally.core.event_bus import EventBus, EventHandler
from sally.domain.events import GridDataEvent, ControlActionEvent, EntityRelationalDataEvent, GridEntityData, GridConnectionData
from sally.domain.grid_entities import GridMeasurement, EntityType
from sally.core.logger import get_logger

logger = get_logger(__name__)


class MosaikSimulation(BaseSimulation, EventHandler):
    """
    Mosaik-based simulation that integrates with the event bus and services.
    """

    def __init__(self, mosaik_config: Dict[str, Any], rule_manager, event_bus: EventBus = None):
        super().__init__(rule_manager)
        self.mosaik_config = mosaik_config
        self.event_bus = event_bus
        self.world = None
        self.simulators = {}
        self.entities = {}
        self.current_timestep = 0
        self.total_timesteps = mosaik_config.get('total_timesteps', 1000)
        self.step_size = mosaik_config.get('step_size', 1)
        self.current_timestep_data = None

        # Grid topology tracking
        self._entity_map = {}  # Map entity_name -> entity_id
        self._connection_map = {}  # Track connections
        self._topology_published = False

        # Performance tracking
        self._measurements_received = 0
        self._last_measurement_time = time.time()

        # Subscribe to event bus if provided
        if self.event_bus:
            self.event_bus.subscribe(self)

        self._setup_mosaik_simulation()

    @property
    def event_types(self) -> List[str]:
        return ["control_action", "grid_data_update"]

    async def handle(self, event):
        """Handle events efficiently with minimal processing overhead."""
        if isinstance(event, ControlActionEvent):
            logger.debug(f"Control action: {event.action_type} for {event.target_entity}")
            await self._apply_control_action(event)
        elif isinstance(event, GridDataEvent):
            # Track measurements for monitoring
            self._measurements_received += 1
            # Optionally update internal state
            self._update_entity_state(event.measurement)

    def _update_entity_state(self, measurement: GridMeasurement) -> None:
        """Update internal entity state from measurement (lightweight)."""
        # Store only essential state information
        if measurement.entity not in self._entity_map:
            # Assign entity_id
            self._entity_map[measurement.entity] = len(self._entity_map) + 1

    async def _apply_control_action(self, event: ControlActionEvent):
        """Apply control actions to Mosaik simulators."""
        # This would interface with actual Mosaik simulator controls
        logger.debug(f"Applying control: {event.action_type} to {event.target_entity}")
        # TODO: Implement actual Mosaik control interface

    def _setup_mosaik_simulation(self):
        """Setup the Mosaik simulation based on configuration"""
        try:
            # Create Mosaik world
            self.world = mosaik.World(self.mosaik_config.get('sim_config', {}))

            # Start simulators based on config
            sim_configs = self.mosaik_config.get('simulators', {})

            for sim_name, sim_config in sim_configs.items():
                sim_class = sim_config.get('class')
                if sim_class:
                    self.simulators[sim_name] = self.world.start(sim_name, **sim_config.get('params', {}))

            # Create entities
            entity_configs = self.mosaik_config.get('entities', {})
            for entity_group, config in entity_configs.items():
                sim_name = config.get('simulator')
                if sim_name and sim_name in self.simulators:
                    entities = getattr(self.simulators[sim_name], config.get('method', 'create'))(
                        **config.get('params', {})
                    )
                    self.entities[entity_group] = entities

            # Connect entities
            connections = self.mosaik_config.get('connections', [])
            for connection in connections:
                self._make_connection(connection)

            # Build topology mappings
            self._build_topology_map()

            logger.info("Mosaik simulation setup completed")

        except Exception as e:
            logger.error("Failed to setup Mosaik simulation")
            raise

    def _make_connection(self, connection_config):
        """Make connections between Mosaik entities"""
        source = connection_config.get('source')
        dest = connection_config.get('dest')
        attrs = connection_config.get('attrs', [])

        if source and dest and self.world:
            try:
                self.world.connect(source, dest, *attrs)
                # Track connection
                if source not in self._connection_map:
                    self._connection_map[source] = []
                self._connection_map[source].append(dest)
            except Exception as e:
                logger.warning(f"Failed to connect {source} to {dest}: {e}")

    def _build_topology_map(self) -> None:
        """Build entity ID mapping and extract topology from Mosaik world."""
        entity_id = 1

        # Map all entities to IDs
        for entity_group, entities in self.entities.items():
            for entity in entities:
                entity_name = entity.eid
                if entity_name not in self._entity_map:
                    self._entity_map[entity_name] = entity_id
                    entity_id += 1

        logger.info(f"Built topology map with {len(self._entity_map)} entities and {sum(len(v) for v in self._connection_map.values())} connections")

    async def _publish_topology(self) -> None:
        """Publish grid topology as EntityRelationalDataEvent."""
        if self._topology_published:
            return

        logger.info("Publishing grid topology to event bus")

        # Create entity data
        entities = []
        for entity_name, entity_id in self._entity_map.items():
            # Infer entity type from name
            entity_type = self._infer_entity_type(entity_name)

            # Create entity data with basic information
            entity_data = GridEntityData(
                entity_id=entity_id,
                entity_name=entity_name,
                entity_type=entity_type.value,
                rated_power=self._estimate_rated_power(entity_name, entity_type),
                rated_voltage=self._estimate_rated_voltage(entity_name, entity_type),
                location=f"Grid_Zone_{entity_id % 10}",
                metadata={"source": "mosaik_sim", "timestep": self.current_timestep}
            )
            entities.append(entity_data)

        # Create connection data
        connections = []
        connection_id = 1
        for from_entity, to_entities in self._connection_map.items():
            from_id = self._entity_map.get(from_entity)
            if from_id is None:
                continue

            for to_entity in to_entities:
                to_id = self._entity_map.get(to_entity)
                if to_id is None:
                    continue

                # Infer connection type
                connection_type = self._infer_connection_type(from_entity, to_entity)

                connection_data = GridConnectionData(
                    from_entity_id=from_id,
                    to_entity_id=to_id,
                    connection_type=connection_type,
                    line_length=random.uniform(0.5, 50.0) if connection_type == 'line' else None,
                    resistance=random.uniform(0.01, 1.0) if connection_type == 'line' else None,
                    reactance=random.uniform(0.05, 2.0) if connection_type == 'line' else None,
                    capacity=random.uniform(50, 500) if connection_type in ['line', 'transformer'] else None,
                    is_active=True,
                    metadata={"source": "mosaik_sim"}
                )
                connections.append(connection_data)
                connection_id += 1

        # Publish event
        topology_event = EntityRelationalDataEvent(
            entities=entities,
            connections=connections,
            operation="upsert",
            timestamp=time.time(),
            correlation_id=f"mosaik_topology_{self.current_timestep}"
        )

        await self.event_bus.publish(topology_event)
        self._topology_published = True
        logger.info(f"Published topology: {len(entities)} entities, {len(connections)} connections")

    def _estimate_rated_power(self, entity_name: str, entity_type: EntityType) -> Optional[float]:
        """Estimate rated power based on entity type."""
        name_lower = entity_name.lower()
        if entity_type == EntityType.CSV_PV:
            return random.uniform(5, 30)  # 5-30 kW for PV
        elif entity_type == EntityType.WIND_TURBINE:
            return random.uniform(10, 20)  # 10-20 MW for wind
        elif 'gen' in name_lower:
            return random.uniform(50, 500)  # 50-500 MW for generators
        elif 'load' in name_lower or 'house' in name_lower:
            return random.uniform(1, 10)  # 1-10 MW for loads
        return None

    def _estimate_rated_voltage(self, entity_name: str, entity_type: EntityType) -> Optional[float]:
        """Estimate rated voltage based on entity type."""
        name_lower = entity_name.lower()
        if 'gen' in name_lower:
            return 230.0  # kV transmission
        elif 'trans' in name_lower:
            return 69.0  # kV sub-transmission
        elif 'pv' in name_lower or 'house' in name_lower:
            return 0.4  # kV distribution
        return 138.0  # Default transmission voltage

    def _infer_connection_type(self, from_entity: str, to_entity: str) -> str:
        """Infer connection type from entity names."""
        if 'trans' in from_entity.lower() or 'trans' in to_entity.lower():
            return 'transformer'
        elif 'switch' in from_entity.lower() or 'switch' in to_entity.lower():
            return 'switch'
        elif 'break' in from_entity.lower() or 'break' in to_entity.lower():
            return 'breaker'
        return 'line'

    async def step(self) -> bool:
        """
        Advance the Mosaik simulation by one step.
        """
        if self.current_timestep >= self.total_timesteps:
            logger.info(f"Mosaik simulation has finished at timestep {self.total_timesteps}")
            return False

        try:
            # Publish topology on first step
            if not self._topology_published and self.event_bus:
                await self._publish_topology()

            logger.info(f"Mosaik simulation step: {self.current_timestep + 1} / {self.total_timesteps}")

            # Run Mosaik step
            if self.world:
                self.world.step()

            # Collect data from simulators
            current_data = self._collect_current_data()
            self.current_timestep_data = current_data

            # Publish data events to services
            if self.event_bus:
                await self._publish_data_events(current_data)

            # Evaluate rules
            triggered_actions = self.evaluate_rules_at_timestep(current_data)

            if triggered_actions:
                for action_info in triggered_actions:
                    self.on_rule_triggered(action_info)

            self.current_timestep += 1

            return True

        except Exception as e:
            logger.error("Error in Mosaik simulation step")
            return False

    def _collect_current_data(self) -> Dict[str, Any]:
        """Collect current data from all Mosaik simulators"""
        current_data = {}

        try:
            # Get data from each simulator
            for sim_name, simulator in self.simulators.items():
                if hasattr(simulator, 'get_data'):
                    # This is a simplified approach - in practice, you'd need to know
                    # which entities belong to which simulator
                    pass

            # For now, generate some sample data based on entity types
            for entity_group, entities in self.entities.items():
                for entity in entities:
                    entity_name = entity.eid
                    current_data[entity_name] = self._generate_entity_data(entity)

        except Exception as e:
            logger.error("Error collecting Mosaik data")

        return current_data

    def _generate_entity_data(self, entity) -> Dict[str, float]:
        """Generate sample data for an entity based on its type"""
        # This is a placeholder - in a real implementation, you'd get actual data from Mosaik
        entity_type = getattr(entity, 'type', 'Unknown')

        if 'Generator' in entity_type:
            return {
                'P_MW_out': random.uniform(20, 100),
                'Q_MVAR_out': random.uniform(-10, 20),
                'VM': random.uniform(0.95, 1.05),
                'VA': random.uniform(-0.1, 0.1)
            }
        elif 'PV' in entity_type:
            return {
                'P_MW_out': random.uniform(0, 30),
                'Q_MVAR_out': random.uniform(-5, 5)
            }
        elif 'Load' in entity_type:
            return {
                'P_MW': random.uniform(10, 50),
                'Q_MVAR': random.uniform(2, 15)
            }
        else:
            return {
                'P_MW': random.uniform(-20, 20),
                'Q_MVAR': random.uniform(-10, 10),
                'VM': random.uniform(0.9, 1.1)
            }

    async def _publish_data_events(self, current_data: Dict[str, Any]):
        """Publish grid data events to connected services"""
        current_time = time.time()

        for entity_name, variables in current_data.items():
            if isinstance(variables, dict):
                measurement = self._create_measurement_from_data(entity_name, variables, current_time)
                if measurement:
                    event = GridDataEvent(
                        measurement=measurement,
                        timestamp=current_time,
                        correlation_id=f"mosaik_{entity_name}_{self.current_timestep}"
                    )
                    await self.event_bus.publish(event)

    def _create_measurement_from_data(self, entity_name: str, variables: Dict[str, float], timestamp: float) -> Optional[GridMeasurement]:
        """Create GridMeasurement from Mosaik data"""
        # Infer entity type from entity name
        entity_type = self._infer_entity_type(entity_name)

        measurement_kwargs = {
            'entity': entity_name,
            'entity_type': entity_type,
            'timestamp': timestamp
        }

        # Map variables to measurement fields
        var_mapping = {
            'P_MW_out': 'p_out',
            'P_MW': 'p',
            'Q_MVAR_out': 'q',
            'Q_MVAR': 'q',
            'VM': 'vm',
            'VA': 'va'
        }

        for var_name, value in variables.items():
            field_name = var_mapping.get(var_name, var_name.lower())
            if field_name in ['p', 'p_out', 'q', 'va', 'vl', 'vm', 'humidity']:
                measurement_kwargs[field_name] = float(value)

        try:
            return GridMeasurement(**measurement_kwargs)
        except Exception as e:
            logger.warning(f"Failed to create measurement for {entity_name}: {e}")
            return None

    def _infer_entity_type(self, entity_name: str) -> EntityType:
        """Infer EntityType from entity name"""
        name_lower = entity_name.lower()
        if 'gen' in name_lower:
            return EntityType.PYPOWER_NODE
        elif 'pv' in name_lower:
            return EntityType.CSV_PV
        elif 'wind' in name_lower:
            return EntityType.WIND_TURBINE
        elif 'house' in name_lower or 'load' in name_lower:
            return EntityType.HOUSEHOLD_SIM
        elif 'batt' in name_lower:
            return EntityType.BATTERY_ESS
        else:
            return EntityType.PYPOWER_NODE

    def get_current_data_snapshot(self) -> Dict[str, Any]:
        """Get current simulation data snapshot"""
        return self._collect_current_data()

    def close(self):
        """Clean up Mosaik simulation resources"""
        try:
            if self.world:
                self.world.shutdown()
            logger.info("Mosaik simulation closed")
        except Exception as e:
            logger.error("Error closing Mosaik simulation")

    def reset(self):
        """Reset simulation to beginning"""
        self.current_timestep = 0
        logger.info("Mosaik simulation reset to timestep 0")

    async def run_steps(self, num_steps: int):
        """Run specified number of steps"""
        logger.info(f"Running Mosaik simulation for {num_steps} steps")
        for _ in range(num_steps):
            if not await self.step():
                break
        logger.info("Finished requested number of Mosaik steps")

    async def run_all(self):
        """Run entire simulation"""
        logger.info("Running entire Mosaik simulation")
        while self.current_timestep < self.total_timesteps:
            if not await self.step():
                break
        logger.info("Entire Mosaik simulation completed")

    def on_rule_triggered(self, action_info: dict):
        """Handle rule triggers"""
        entity_name = action_info.get('triggering_entity', 'N/A')
        variable_name = action_info.get('triggering_variable', 'N/A')

        logger.info("Rule triggered in Mosaik simulation")
        #logger.info("Rule triggered in Mosaik simulation",
        #           entity=entity_name,
        #           variable=variable_name,
        #           action=action_info.get('action_command', 'N/A'))
