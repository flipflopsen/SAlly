from django.apps import AppConfig


class PluginsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backend.plugins'  # Must match the directory name exactly
    verbose_name = 'Node Plugins'

    def ready(self):
        """Import plugin loaders to register plugins when Django starts."""
        try:
            # Import node plugin loader
            from .nodes import loader as node_loader  # noqa

            # Import connection plugin loader
            from .connections import loader as connection_loader  # noqa

        except ImportError as e:
            # Log warning but don't fail if plugins can't be loaded
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not load plugin loaders: {e}")
