"""Automatic plugin loader for connection types."""
import importlib
import pkgutil
from pathlib import Path
from .base import BaseConnectionPlugin
from ...node_editor.services.connection_registry import connection_registry
import logging

logger = logging.getLogger(__name__)


def discover_and_register_connection_plugins():
    """Automatically discover and register all connection plugins."""
    connections_dir = Path(__file__).parent

    logger.info(f"Starting connection plugin discovery in {connections_dir}")

    # Import all modules in plugins/connections directory
    for (_, module_name, _) in pkgutil.iter_modules([str(connections_dir)]):
        # Skip the base and loader modules
        if module_name in ['base', 'loader']:
            continue

        try:
            module = importlib.import_module(f'backend.plugins.connections.{module_name}')

            # Find all BaseConnectionPlugin subclasses in module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if (isinstance(attr, type) and
                        issubclass(attr, BaseConnectionPlugin) and
                        attr is not BaseConnectionPlugin):
                    connection_registry.register(attr)
                    logger.info(f"Auto-registered connection plugin: {attr.get_type()}")

        except Exception as e:
            logger.error(f"Failed to load connection plugin module {module_name}: {e}")

    logger.info(f"Connection plugin discovery complete. Registered {len(connection_registry._connections)} connection types")


# Auto-register plugins on module import
discover_and_register_connection_plugins()