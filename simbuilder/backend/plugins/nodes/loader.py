"""Automatic plugin loader for node types."""
import importlib
import pkgutil
from pathlib import Path
from ..nodes.base import BaseNodePlugin
from ...node_editor.services.node_registry import registry
import logging

logger = logging.getLogger(__name__)


def discover_and_register_plugins():
    """Automatically discover and register all node plugins."""
    plugins_dir = Path(__file__).parent

    logger.info(f"Starting node plugin discovery in {plugins_dir}")

    # Import all modules in plugins/nodes directory
    for (_, module_name, _) in pkgutil.iter_modules([str(plugins_dir)]):

        # Skip base and loader modules
        if module_name in ['base', 'loader']:
            continue

        try:
            module = importlib.import_module(f'backend.plugins.nodes.{module_name}')

            # Find all BaseNodePlugin subclasses in module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if (isinstance(attr, type) and
                        issubclass(attr, BaseNodePlugin) and
                        attr is not BaseNodePlugin):
                    registry.register(attr)
                    logger.info(f"Auto-registered plugin: {attr.get_type()}")

        except Exception as e:
            logger.error(f"Failed to load plugin module {module_name}: {e}")

    logger.info(f"Node plugin discovery complete. Registered {len(registry._nodes)} node types")


# Auto-register plugins on module import
discover_and_register_plugins()
