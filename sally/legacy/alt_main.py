"""
[LEGACY] Alternative async services-based architecture for smart grid monitoring system.

!!! WARNING: This module is DEPRECATED !!!
Use sally.main_async_services.SmartGridMonitoringSystem instead.

This module was an early prototype that was superseded by main_async_services.py.
It is preserved here for reference only.

Original description:
This module provides an event-driven architecture using async services and TimescaleDB
persistence, compared to the HDF5-based approach in main.py. Currently incomplete and
requires Settings implementation before it can run successfully.

Key differences from main.py:
- Event-driven architecture with EventBus
- Real-time monitoring simulation
- TimescaleDB for data persistence
- Service-based modular design

Migration notes:
- SmartGridMonitoringSystem functionality is now in main_async_services.py
- Settings implementation is available in sally.core.settings
- This file contains duplicate code and incomplete implementations
"""
from sally.core.event_bus import EventHandler, Event, EventBus
from sally.infrastructure.data_management.timescale.timescaledb_connection import TimescaleDBConnection
from sally.domain.events import GridDataEvent
from sally.domain.grid_entities import GridMeasurement, EntityType

import asyncio
import signal
import sys
import warnings
from typing import Optional

from sally.infrastructure.services.grid_data_service import GridDataService
from sally.infrastructure.services.load_forecasting_service import LoadForecastingService
from sally.infrastructure.services.stability_monitoring_service import StabilityMonitoringService
from sally.core.event_bus import EventHandler, Event, EventBus
from sally.infrastructure.data_management.timescale.timescaledb_connection import TimescaleDBConnection

from sally.core.logger import get_logger

logger = get_logger(__name__)


class SmartGridMonitoringSystem:
    """
    [DEPRECATED] Main application class for smart grid monitoring and control system.

    Use sally.main_async_services.SmartGridMonitoringSystem instead.
    """

    def __init__(self):
        warnings.warn(
            "alt_main.SmartGridMonitoringSystem is deprecated. "
            "Use sally.main_async_services.SmartGridMonitoringSystem instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.event_bus: Optional[EventBus] = None
        self.database: Optional[TimescaleDBConnection] = None
        self.services = []
        self.running = False

    async def initialize(self) -> None:
        """Initialize all smart grid monitoring components"""
        logger.warning("Using deprecated SmartGridMonitoringSystem from alt_main")
        logger.info("Initializing smart grid monitoring system")

        # NOTE: This implementation is incomplete - settings not available
        self.database = TimescaleDBConnection(
            dsn=self.settings.database_url,
            pool_size=self.settings.db_pool_size,
            max_size=self.settings.db_max_pool_size
        )
        await self.database.initialize()

        self.event_bus = EventBus(
            max_queue_size=self.settings.event_queue_size
        )

        self.database = TimescaleDBConnection(
            dsn='self.settings.database_url',
            pool_size=self.settings.db_pool_size,
            max_size=self.settings.db_max_pool_size
        )
        await self.database.initialize()

        self.event_bus = EventBus(
            max_queue_size=self.settings.event_queue_size
        )

        grid_data_service = GridDataService(self.database, self.event_bus)
        load_forecasting_service = LoadForecastingService(self.database, self.event_bus)
        stability_monitoring_service = StabilityMonitoringService(self.database, self.event_bus)

        self.services = [grid_data_service, load_forecasting_service, stability_monitoring_service]

        for service in self.services:
            self.event_bus.subscribe(service)

        logger.info("Smart grid system initialization complete")

    async def start(self) -> None:
        """Start the smart grid monitoring system"""
        logger.info("Starting smart grid monitoring system")
        self.running = True

        await self.event_bus.start()

        tasks = []

        grid_data_service = self.services[0]
        tasks.append(
            asyncio.create_task(grid_data_service.start_data_acquisition())
        )

        load_forecasting_service = self.services[1]
        tasks.append(
            asyncio.create_task(load_forecasting_service.start_forecasting())
        )

        stability_monitoring_service = self.services[2]
        tasks.append(
            asyncio.create_task(stability_monitoring_service.start_monitoring())
        )

        if sys.platform != 'win32':
            for sig in (signal.SIGTERM, signal.SIGINT):
                asyncio.get_event_loop().add_signal_handler(
                    sig, lambda s=sig: asyncio.create_task(self._shutdown(s))
                )

        try:
            logger.info("Smart grid monitoring system operational",
                        services=len(self.services),
                        grid_entities=len(grid_data_service.grid_entities))

            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error("Error in main loop", error=str(e))
        finally:
            await self._cleanup()

    async def _shutdown(self, signal_received=None) -> None:
        """Graceful shutdown handler"""
        if signal_received:
            logger.info("Shutdown signal received", signal=signal_received.name)
        else:
            logger.info("Shutdown requested")

        self.running = False

        for service in self.services:
            if hasattr(service, 'stop'):
                await service.stop()

        if self.event_bus:
            await self.event_bus.stop()

    async def _cleanup(self) -> None:
        """Cleanup resources"""
        logger.info("Cleaning up smart grid system resources")

        if self.database:
            await self.database.close()

        logger.info("Smart grid system shutdown complete")


async def main():
    """Main entry point for smart grid monitoring system"""
    warnings.warn(
        "alt_main.main() is deprecated. Use sally.main_async_services instead.",
        DeprecationWarning,
        stacklevel=2
    )
    system = SmartGridMonitoringSystem()

    try:
        await system.initialize()
        await system.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await system._shutdown()
    except Exception as e:
        logger.error("Fatal error in smart grid system", error=str(e))
        await system._cleanup()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
