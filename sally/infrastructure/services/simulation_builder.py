from typing import Optional, List, Union
from sally.application.simulation.sg_hdf5_sim import SmartGridSimulation
from sally.application.simulation.mosaik_sim import MosaikSimulation
from sally.core.event_bus import EventBus
from sally.infrastructure.data_management.timescale.timescaledb_connection import TimescaleDBConnection
from sally.infrastructure.services.grid_data_service import GridDataService
from sally.infrastructure.services.load_forecasting_service import LoadForecastingService
from sally.infrastructure.services.stability_monitoring_service import StabilityMonitoringService
from sally.application.rule_management.sg_dummies import DummySmartGridRuleManager
from sally.containers import ContainerFactory, ContainerType
from sally.core.config import config
from sally.core.logger import get_logger

logger = get_logger(__name__)


class SimulationBuilder:
    """
    Builder for creating SmartGridSimulation instances with dependency injection
    and service integration.
    """

    def __init__(self):
        self._hdf5_filepath: Optional[str] = None
        self._data_provider: Optional[object] = None
        self._mosaik_config: Optional[dict] = None
        self._rule_manager: Optional[DummySmartGridRuleManager] = None
        self._event_bus: Optional[EventBus] = None
        self._database: Optional[TimescaleDBConnection] = None
        self._services: List = []
        self._container_type: ContainerType = ContainerType.SIMULATION
        self._config_path: Optional[str] = None
        self._simulation_type: str = "hdf5"  # "hdf5", "mosaik", or "data_provider"

    def with_hdf5_file(self, filepath: str) -> 'SimulationBuilder':
        """Set the HDF5 file path for simulation data"""
        self._hdf5_filepath = filepath
        return self

    def with_rule_manager(self, rule_manager: DummySmartGridRuleManager) -> 'SimulationBuilder':
        """Set the rule manager for the simulation"""
        self._rule_manager = rule_manager
        return self

    def with_event_bus(self, event_bus: EventBus) -> 'SimulationBuilder':
        """Set the event bus for service communication"""
        self._event_bus = event_bus
        return self

    def with_database(self, database: TimescaleDBConnection) -> 'SimulationBuilder':
        """Set the TimescaleDB connection"""
        self._database = database
        return self

    def with_services(self, services: List) -> 'SimulationBuilder':
        """Set the services to connect with the simulation"""
        self._services = services
        return self

    def with_container_type(self, container_type: ContainerType) -> 'SimulationBuilder':
        """Set the dependency injection container type"""
        self._container_type = container_type
        return self

    def with_config(self, config_path: str) -> 'SimulationBuilder':
        """Set the configuration file path"""
        self._config_path = config_path
        return self

    def with_data_provider(self, data_provider) -> 'SimulationBuilder':
        """Set a data provider for generating random data instead of HDF5"""
        self._data_provider = data_provider
        self._simulation_type = "data_provider"
        return self

    def with_mosaik_config(self, mosaik_config: dict) -> 'SimulationBuilder':
        """Set Mosaik simulation configuration"""
        self._mosaik_config = mosaik_config
        self._simulation_type = "mosaik"
        return self

    def as_hdf5_simulation(self) -> 'SimulationBuilder':
        """Set simulation type to HDF5"""
        self._simulation_type = "hdf5"
        return self

    def _initialize_dependencies(self):
        """Initialize dependencies using dependency injection container"""
        if not self._config_path:
            self._config_path = str(config.get_path("config_dir") / "default.yml")

        factory = ContainerFactory()
        container = factory.create(self._container_type)

        if self._config_path:
            container.config.from_yaml(self._config_path)

        # Override with provided dependencies
        if self._database:
            container.database.override(self._database)
        if self._rule_manager:
            container.rule_manager.override(self._rule_manager)

        return container

    def _setup_event_bus(self) -> EventBus:
        """Setup event bus and subscribe services"""
        if not self._event_bus:
            self._event_bus = EventBus(max_queue_size=config.event_bus.max_queue_size)

        # Subscribe services to event bus
        for service in self._services:
            self._event_bus.subscribe(service)

        return self._event_bus

    def _create_services(self, database: TimescaleDBConnection, event_bus: EventBus):
        """Create default services if not provided"""
        if not self._services:
            self._services = [
                GridDataService(database, event_bus),
                LoadForecastingService(database, event_bus),
                StabilityMonitoringService(database, event_bus)
            ]
        return self._services

    def build(self) -> Union[SmartGridSimulation, MosaikSimulation]:
        """Build the simulation with all configured dependencies"""
        # Initialize dependencies
        container = self._initialize_dependencies()

        # Get or create database
        database = self._database or container.database()

        # Setup event bus
        event_bus = self._setup_event_bus()

        # Create services
        services = self._create_services(database, event_bus)

        # Get rule manager
        rule_manager = self._rule_manager or container.rule_manager()

        # Create simulation based on type
        if self._simulation_type == "hdf5":
            if not self._hdf5_filepath:
                raise ValueError("HDF5 file path must be set for HDF5 simulations")
            simulation = SmartGridSimulation(
                hdf5_filepath=self._hdf5_filepath,
                rule_manager=rule_manager,
                event_bus=event_bus
            )
            logger.info("HDF5 simulation built successfully")

        elif self._simulation_type == "data_provider":
            if not self._data_provider:
                raise ValueError("Data provider must be set for data provider simulations")
            simulation = SmartGridSimulation(
                hdf5_filepath="",
                rule_manager=rule_manager,
                event_bus=event_bus
            )
            # Set data provider data
            simulation.set_data(self._data_provider.generate_timeseries_data(),
                              self._data_provider.generate_relational_data())
            logger.info("Data provider simulation built successfully")

        elif self._simulation_type == "mosaik":
            if not self._mosaik_config:
                raise ValueError("Mosaik configuration must be set for Mosaik simulations")
            simulation = MosaikSimulation(
                mosaik_config=self._mosaik_config,
                rule_manager=rule_manager,
                event_bus=event_bus
            )
            logger.info("Mosaik simulation built successfully")

        else:
            raise ValueError(f"Unknown simulation type: {self._simulation_type}")

        return simulation

    async def build_and_start_services(self) -> tuple[SmartGridSimulation, List]:
        """Build simulation and start all services"""
        simulation = self.build()

        # Start services
        startup_tasks = []
        for service in self._services:
            if hasattr(service, 'start_data_acquisition'):
                startup_tasks.append(service.start_data_acquisition())
            elif hasattr(service, 'start_forecasting'):
                startup_tasks.append(service.start_forecasting())
            elif hasattr(service, 'start_monitoring'):
                startup_tasks.append(service.start_monitoring())

        if startup_tasks:
            import asyncio
            await asyncio.gather(*startup_tasks, return_exceptions=True)
            logger.info("Services started successfully")

        return simulation, self._services
