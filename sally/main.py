#!/usr/bin/env python
"""Unified entry point for SAlly simulations.

Provides a command-line interface to run different simulation modes:
- hdf5: HDF5-based simulation with rule evaluation
- async: Async services-based real-time monitoring
- builder: Interactive simulation builder mode

Examples:
    # Run HDF5 simulation
    python main.py hdf5 --file <path-to-hdf5> --steps 100

    # Run async services
    python main.py async --db-url postgresql://localhost/smartgrid

    # Run with builder (interactive)
    python main.py builder
"""

import argparse
import sys
import asyncio
import time
from pathlib import Path

from sally.core.config import config
from sally.core.logger import get_logger, configure_logging

# Configure logging early
configure_logging()
logger = get_logger(__name__)

# Try to initialize telemetry
_TELEMETRY_AVAILABLE = False
try:
    from sally.core.telemetry import get_telemetry
    from sally.core.service_telemetry import init_service_telemetry, ServiceNames
    _telemetry = get_telemetry()
    _TELEMETRY_AVAILABLE = True
    logger.info("OTEL telemetry initialized")
except ImportError:
    logger.debug("OTEL telemetry not available")
except Exception as e:
    logger.warning("Failed to initialize OTEL telemetry: %s", e)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    default_hdf5 = str(config.get_path("default_hdf5_file"))
    default_rules = str(config.get_path("default_rules_file"))
    default_config = str(config.get_path("config_dir") / "default.yml")
    parser = argparse.ArgumentParser(
        description='SAlly - Smart Grid Ally for Simulation, Monitoring, and Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--version',
        action='version',
        version='SAlly 0.7.3'
    )

    subparsers = parser.add_subparsers(dest='mode', help='Simulation mode')

    # HDF5 simulation mode
    hdf5_parser = subparsers.add_parser(
        'hdf5',
        help='Run HDF5-based simulation'
    )
    hdf5_parser.add_argument(
        '--file',
        type=str,
        default=default_hdf5,
        help='Path to HDF5 data file'
    )
    hdf5_parser.add_argument(
        '--steps',
        type=int,
        default=None,
        help='Number of simulation steps (default: all)'
    )
    hdf5_parser.add_argument(
        '--rules',
        type=str,
        default=default_rules,
        help='Path to rules JSON file'
    )
    hdf5_parser.add_argument(
        '--gui',
        action='store_true',
        help='Launch rule manager GUI'
    )
    hdf5_parser.add_argument(
        '--config',
        type=str,
        default=default_config,
        help='Path to configuration file'
    )

    # Async services mode
    async_parser = subparsers.add_parser(
        'async',
        help='Run async services-based monitoring'
    )
    async_parser.add_argument(
        '--db-url',
        type=str,
        required=True,
        help='TimescaleDB connection URL'
    )
    async_parser.add_argument(
        '--db-pool-size',
        type=int,
        default=10,
        help='Database connection pool size'
    )
    async_parser.add_argument(
        '--event-queue-size',
        type=int,
        default=10000,
        help='Event bus queue size'
    )

    # Builder mode
    builder_parser = subparsers.add_parser(
        'builder',
        help='Interactive simulation builder'
    )
    builder_parser.add_argument(
        '--example',
        type=str,
        choices=['basic', 'database', 'rules', 'full', 'random', 'sinusoidal', 'mosaik'],
        help='Run a specific example scenario'
    )

    return parser


def run_hdf5_mode(args):
    """Run HDF5-based simulation mode."""
    logger.info(
        "Starting HDF5 simulation mode: file=%s steps=%s rules=%s gui=%s",
        args.file, args.steps, args.rules, args.gui
    )
    start_time = time.perf_counter()

    # Import here to avoid loading heavy dependencies unless needed
    from sally.main_dev_and_gui import run_simulation, start_rule_manager_gui
    from sally.containers import ContainerFactory, ContainerType

    # Create container
    logger.debug("Creating container with config: %s", args.config)
    factory = ContainerFactory()
    container = factory.with_config(args.config).create(ContainerType.SIMULATION)
    container.wire(modules=[sys.modules[__name__]])
    logger.debug("Container created and wired")

    # Launch GUI if requested
    if args.gui:
        logger.info("Launching rule manager GUI")
        start_rule_manager_gui()

    # Run simulation
    steps = args.steps if args.steps else config.simulation.default_steps
    logger.info("Starting simulation: steps=%d", steps)

    run_simulation(
        steps=steps,
        hdf5_path=args.file,
        rule_manager=container.rule_manager(),
        database=container.database(),
        data_collector=container.data_collector()
    )

    elapsed = time.perf_counter() - start_time
    logger.info("HDF5 simulation completed: elapsed=%.2fs", elapsed)


async def run_async_mode(args):
    """Run async services-based monitoring mode."""
    logger.info(
        "Starting async services mode: db_url=%s pool_size=%d queue_size=%d",
        args.db_url, args.db_pool_size, args.event_queue_size
    )

    # Import here to avoid loading heavy dependencies unless needed
    from sally.main_async_services import SmartGridMonitoringSystem

    # Create and configure system
    system = SmartGridMonitoringSystem()
    logger.debug("SmartGridMonitoringSystem created")

    # Override settings (TODO: Replace with ConfigManager in Phase 4)
    system.settings = type('Settings', (), {
        'database_url': args.db_url,
        'db_pool_size': args.db_pool_size,
        'db_max_pool_size': args.db_pool_size * 2,
        'event_queue_size': args.event_queue_size
    })

    try:
        logger.info("Initializing monitoring system")
        await system.initialize()
        logger.info("Starting monitoring system")
        await system.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
        await system._shutdown()
    except Exception as e:
        logger.exception("Fatal error in async services mode: %s", e)
        await system._cleanup()
        sys.exit(1)


async def run_builder_mode(args):
    """Run simulation builder mode."""
    logger.info("Starting simulation builder mode: example=%s", args.example)

    if args.example:
        # Run specific example
        logger.info("Running example: %s", args.example)
        # Import and run the specific example from example_simulation_builder.py
        from sally.examples import example_simulation_builder

        example_map = {
            'basic': example_simulation_builder.example_basic_simulation,
            'database': example_simulation_builder.example_custom_database,
            'rules': example_simulation_builder.example_with_custom_rule_manager,
            'full': example_simulation_builder.example_full_integration,
            'random': example_simulation_builder.example_data_provider_simulation,
            'sinusoidal': example_simulation_builder.example_sinusoidal_data_provider,
            'mosaik': example_simulation_builder.example_mosaik_simulation
        }

        start_time = time.perf_counter()
        await example_map[args.example]()
        elapsed = time.perf_counter() - start_time
        logger.info("Example '%s' completed: elapsed=%.2fs", args.example, elapsed)
    else:
        # Interactive mode - show available examples
        print("\nAvailable examples:")
        print("  basic      - Basic HDF5 simulation with default services")
        print("  database   - Simulation with custom TimescaleDB connection")
        print("  rules      - Simulation with custom rule manager")
        print("  full       - Full integration with all services")
        print("  random     - Random data provider simulation")
        print("  sinusoidal - Sinusoidal data provider simulation")
        print("  mosaik     - Mosaik co-simulation integration")
        print("\nRun with --example <name> to execute a specific example.")
        print("Or see examples/ directory for standalone example scripts.")
        logger.debug("Interactive mode - no example specified")


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.mode:
        parser.print_help()
        sys.exit(1)

    # Initialize telemetry with service name based on mode
    if _TELEMETRY_AVAILABLE:
        service_name = ServiceNames.MAIN
        if args.mode == 'hdf5':
            service_name = ServiceNames.ORCHESTRATOR
        elif args.mode == 'async':
            service_name = ServiceNames.SERVICES

        init_service_telemetry(
            service_name,
            extra_attributes={"mode": args.mode}
        )

    logger.info("SAlly starting: mode=%s", args.mode)
    start_time = time.perf_counter()

    try:
        if args.mode == 'hdf5':
            run_hdf5_mode(args)
        elif args.mode == 'async':
            asyncio.run(run_async_mode(args))
        elif args.mode == 'builder':
            asyncio.run(run_builder_mode(args))
    except Exception as e:
        logger.exception("Error in %s mode: %s", args.mode, e)
        sys.exit(1)

    elapsed = time.perf_counter() - start_time
    logger.info("SAlly finished: mode=%s elapsed=%.2fs", args.mode, elapsed)


if __name__ == '__main__':
    main()
