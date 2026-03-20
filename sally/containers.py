from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
import warnings

from dependency_injector import containers, providers

# Import from new layered architecture
from sally.core import get_logger, EventBus
from sally.core.config import get_config
from sally.infrastructure import SmartGridDatabase, SGDataCollector, TimescaleDBConnection
from sally.infrastructure.services.grid_data_service import GridDataService
from sally.infrastructure.services.load_forecasting_service import LoadForecastingService
from sally.infrastructure.services.stability_monitoring_service import StabilityMonitoringService
from sally.application import RandomDataProvider, SinusoidalDataProvider
from sally.application.simulation.mosaik_simulators.simulation_config_manager import SimulationConfigurationManager
from sally.application.rule_management.sg_rule_manager import SmartGridRuleManager

# Mosaik simulators (if enabled)
try:
    from sally.application.simulation.mosaik_simulators.base import BaseMosaikSimulator
    from sally.application.simulation.mosaik_simulators.battery import BatterySim
    from sally.application.simulation.mosaik_simulators.load import LoadSim
    from sally.application.simulation.mosaik_simulators.pv import PVSim
    from sally.application.simulation.mosaik_simulators.monitor import MonitorSim
    from sally.application.simulation.mosaik_simulators.generator import GeneratorSim
    from sally.application.simulation.mosaik_simulators.line import LineSim
    from sally.application.simulation.mosaik_simulators.node import NodeSim
    from sally.application.simulation.mosaik_simulators.protection_relay import ProtectionRelaySim
    from sally.application.simulation.mosaik_simulators.remediation import RemediationSim
    from sally.application.simulation.mosaik_simulators.connector import GridConnector
    MOSAIK_AVAILABLE = True
except ImportError:
    MOSAIK_AVAILABLE = False


class BaseContainer(containers.DeclarativeContainer):
    """Base container with common dependencies"""
    logger = providers.Singleton(get_logger, __name__)
    config = providers.Configuration()
    event_bus = providers.Singleton(EventBus, max_queue_size=get_config().event_bus.max_queue_size)
    rule_manager = providers.Singleton(SmartGridRuleManager)
    mosaik_config_manager = providers.Singleton(
        SimulationConfigurationManager
    )
    database = providers.Singleton(SmartGridDatabase)
    data_collector = providers.Singleton(
        SGDataCollector,
        db=database
    )
    grid_data_service = providers.Singleton(
        GridDataService,
        database=database,
        event_bus=event_bus
    )
    load_forecasting_service = providers.Singleton(
        LoadForecastingService,
        database=database,
        event_bus=event_bus
    )
    stability_monitoring_service = providers.Singleton(
        StabilityMonitoringService,
        database=database,
        event_bus=event_bus
    )

class ApplicationContainer(BaseContainer):
    """Unified application container with feature flags

    This container replaces the separate SimulationContainer, MosaikContainer,
    and DataProviderContainer with a single container that conditionally
    registers providers based on feature flags.

    Args:
        enable_simulation: Enable simulation components and services (default: True)
        enable_mosaik: Enable Mosaik simulator components (default: False)
        enable_data_providers: Enable data provider factories (default: False)
        enable_services: Enable monitoring and forecasting services (default: True)
        enable_database: Enable database components (default: True)
        enable_rules: Enable rule management components (default: True)
    """

    def __init__(
        self,
        enable_simulation: bool = True,
        enable_mosaik: bool = False,
        enable_data_providers: bool = False,
        enable_services: bool = True,
        enable_database: bool = True,
        enable_rules: bool = True,
        **kwargs
    ):
        #super().__init__(**kwargs)

        self.enable_simulation = enable_simulation
        self.enable_mosaik = enable_mosaik
        self.enable_data_providers = enable_data_providers
        self.enable_services = enable_services
        self.enable_database = enable_database
        self.enable_rules = enable_rules

        self._setup_providers()
        super().__init__(**kwargs)

    def _setup_providers(self):
        """Setup providers based on feature flags"""

        # Database components
        if self.enable_database:
            self.database = providers.Singleton(SmartGridDatabase)
            self.data_collector = providers.Singleton(
                SGDataCollector,
                db=self.database
            )
            self.timescale_db = providers.Singleton(TimescaleDBConnection)

        # Rule management
        if self.enable_rules:
            self.rule_manager = providers.Singleton(SmartGridRuleManager)

        # Services
        if self.enable_services:
            self.grid_data_service = providers.Singleton(
                GridDataService,
                database=self.database if self.enable_database else None,
                event_bus=self.event_bus
            )
            self.load_forecasting_service = providers.Singleton(
                LoadForecastingService,
                database=self.database if self.enable_database else None,
                event_bus=self.event_bus
            )
            self.stability_monitoring_service = providers.Singleton(
                StabilityMonitoringService,
                database=self.database if self.enable_database else None,
                event_bus=self.event_bus
            )

        # Simulation components
        if self.enable_simulation:
            self.mosaik_config_manager = providers.Singleton(
                SimulationConfigurationManager
            )

        # Data providers
        if self.enable_data_providers:
            self.random_data_provider = providers.Factory(RandomDataProvider)
            self.sinusoidal_data_provider = providers.Factory(SinusoidalDataProvider)

        # Mosaik components
        if self.enable_mosaik and MOSAIK_AVAILABLE:
            self._setup_mosaik_providers()

    def _setup_mosaik_providers(self):
        """Setup Mosaik-specific providers"""
        if not MOSAIK_AVAILABLE:
            return

        # Mosaik Simulators
        self.base_simulator = providers.Singleton(BaseMosaikSimulator)
        self.generator_sim = providers.Singleton(GeneratorSim)
        self.pv_sim = providers.Singleton(PVSim)
        self.load_sim = providers.Singleton(LoadSim)
        self.line_sim = providers.Singleton(LineSim)
        self.node_sim = providers.Singleton(NodeSim)
        self.battery_sim = providers.Singleton(BatterySim)
        self.protection_relay_sim = providers.Singleton(ProtectionRelaySim)
        self.monitor_sim = providers.Singleton(MonitorSim)
        self.remediation_sim = providers.Singleton(RemediationSim)

        # Connection Management
        self.grid_connector = providers.Singleton(GridConnector)

    def get_services(self) -> List:
        """Get all enabled service instances"""
        services = []

        if self.enable_services:
            services.extend([
                self.grid_data_service() if hasattr(self, 'grid_data_service') else None,
                self.load_forecasting_service() if hasattr(self, 'load_forecasting_service') else None,
                self.stability_monitoring_service() if hasattr(self, 'stability_monitoring_service') else None,
            ])

        return [service for service in services if service is not None]


class ContainerType(Enum):
    """
    Container types for backward compatibility (DEPRECATED).

    These container types will be removed in a future version.
    Use ApplicationContainer with feature flags instead.

    Available container types:

    SIMULATION: For HDF5-based simulations with services
                Maps to: ApplicationContainer(enable_simulation=True, enable_services=True)

    MOSAIK: For Mosaik-specific simulator components
            Maps to: ApplicationContainer(enable_mosaik=True)

    DATA_PROVIDER: For simulations using data providers
                   Maps to: ApplicationContainer(enable_data_providers=True)

    TEST: Lightweight container for unit testing
          Maps to: ApplicationContainer(enable_database=True, enable_rules=True)

    FULL: Combined container with all components
          Maps to: ApplicationContainer(enable_simulation=True, enable_mosaik=True,
                                        enable_data_providers=True, enable_services=True)

    NOTE: SG_WITH_DUMMIES has been removed. Use SIMULATION instead.
    """
    SIMULATION = "simulation"
    MOSAIK = "mosaik"
    DATA_PROVIDER = "data_provider"
    TEST = "test"
    FULL = "full"

    def __str__(self):
        warnings.warn(
            f"ContainerType.{self.name} is deprecated. "
            "Use ApplicationContainer with feature flags instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return super().__str__()


class ContainerFactory:
    """Factory for creating configured Application containers"""

    def __init__(self):
        self._config_path: Optional[str] = None
        self._custom_providers: Dict[str, Any] = {}

    def with_config(self, config_path: str) -> 'ContainerFactory':
        """Set the config path and return self for method chaining"""
        self._config_path = config_path
        return self

    def with_custom_provider(self, name: str, provider: Any) -> 'ContainerFactory':
        """Add a custom provider override"""
        self._custom_providers[name] = provider
        return self

    def create(
        self,
        container_type: Optional[ContainerType] = None,
        features: Optional[Dict[str, bool]] = None
    ) -> ApplicationContainer:
        """Create a container using either container type (deprecated) or feature flags

        Args:
            container_type: Deprecated container type for backward compatibility
            features: Dictionary of feature flags for the new API

        Returns:
            ApplicationContainer instance
        """
        # Handle legacy container type (deprecated)
        if container_type is not None:
            warnings.warn(
                "Using ContainerType is deprecated. Use ApplicationContainer with feature flags instead.",
                DeprecationWarning,
                stacklevel=2
            )

            # Map legacy container types to feature flags
            feature_mapping = {
                ContainerType.SIMULATION: {
                    'enable_simulation': True,
                    'enable_services': True,
                    'enable_database': True,
                    'enable_rules': True,
                },
                ContainerType.MOSAIK: {
                    'enable_mosaik': True,
                },
                ContainerType.DATA_PROVIDER: {
                    'enable_data_providers': True,
                },
                ContainerType.TEST: {
                    'enable_database': True,
                    'enable_rules': True,
                },
                ContainerType.FULL: {
                    'enable_simulation': True,
                    'enable_mosaik': True,
                    'enable_data_providers': True,
                    'enable_services': True,
                    'enable_database': True,
                    'enable_rules': True,
                },
            }

            features = feature_mapping.get(container_type, {})

        # Use default features if none provided
        if features is None:
            features = {
                'enable_simulation': True,
                'enable_services': True,
                'enable_database': True,
                'enable_rules': True,
            }

        # Create container with feature flags
        container = ApplicationContainer()

        # Load configuration using ConfigManager
        self._load_config(container)

        # Apply custom providers
        for name, provider in self._custom_providers.items():
            if hasattr(container, name):
                getattr(container, name).override(provider)

        return container

    def _load_config(self, container: ApplicationContainer):
        """Load configuration using ConfigManager"""
        try:
            # Try to load from provided config path
            if self._config_path:
                config = get_config()
                config_file = Path(self._config_path)
                if config_file.exists():
                    # Update container config from ConfigManager
                    container.config.from_dict(config.to_dict())
                else:
                    # Try default config location
                    default_config = config.get_path("config_dir") / "default.yml"
                    if default_config.exists():
                        container.config.from_yaml(str(default_config))
            else:
                # Use ConfigManager defaults
                config = get_config()
                container.config.from_dict(config.to_dict())

        except Exception as e:
            # Fall back to basic configuration if ConfigManager fails
            container.logger().warning(f"Failed to load configuration: {e}")
            if self._config_path:
                try:
                    container.config.from_yaml(self._config_path)
                except:
                    pass  # Continue with defaults


# Backward compatibility - keep old imports working
__all__ = [
    'ApplicationContainer',
    'ContainerFactory',
    'ContainerType',
    # Keep legacy names for compatibility
    'BaseContainer'
]

# Legacy container classes are now deprecated
# Users should use ApplicationContainer with feature flags instead
