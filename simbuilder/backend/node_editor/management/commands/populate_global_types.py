"""Management command to populate NodeTypeDefinition table from existing plugins."""
import json
from django.core.management.base import BaseCommand
from backend.node_editor.models import NodeTypeDefinition
from backend.node_editor.services.node_registry import registry
from backend.node_editor.services.connection_registry import connection_registry


class Command(BaseCommand):
    """Populate global NodeTypeDefinition table from plugin registries."""

    help = 'Populate NodeTypeDefinition table with existing node and connection plugins'

    def handle(self, *args, **kwargs):
        """Execute the command to populate global type definitions."""
        self.stdout.write(self.style.SUCCESS('Starting global type definition population...'))
        
        # Process node plugins
        self.stdout.write('Processing node plugins...')
        node_count = 0
        for node_type, node_class in registry._nodes.items():
            try:
                # Get metadata from the plugin
                metadata = node_class.get_metadata() if hasattr(node_class, 'get_metadata') else {}
                
                # Construct python_class_path from module and class info
                module_path = node_class.__module__
                class_name = node_class.__name__
                
                # Extract module name from full path (backend.plugins.nodes.input_node)
                module_parts = module_path.split('.')
                if len(module_parts) >= 4:
                    module_name = module_parts[3]  # input_node, battery_node, etc.
                    python_class_path = f'backend.plugins.nodes.{module_name}.{class_name}'
                else:
                    # Fallback: use full module path
                    python_class_path = f'{module_path}.{class_name}'
                
                # Create or update the NodeTypeDefinition
                obj, created = NodeTypeDefinition.objects.update_or_create(
                    definition_type='node',
                    type_identifier=node_type,
                    defaults={
                        'definition_data': json.dumps(metadata),
                        'python_class_path': python_class_path
                    }
                )
                
                status = 'Created' if created else 'Updated'
                self.stdout.write(self.style.SUCCESS(f'{status} node type: {node_type} ({python_class_path})'))
                node_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Failed to process node type {node_type}: {e}'))
        
        # Process connection plugins
        self.stdout.write('Processing connection plugins...')
        connection_count = 0
        for connection_type, connection_class in connection_registry._connections.items():
            try:
                # Get metadata from the plugin
                metadata = connection_class.get_metadata() if hasattr(connection_class, 'get_metadata') else {}
                
                # Construct python_class_path from module and class info
                module_path = connection_class.__module__
                class_name = connection_class.__name__
                
                # Extract module name from full path (backend.plugins.connections.input)
                module_parts = module_path.split('.')
                if len(module_parts) >= 4:
                    module_name = module_parts[3]  # input, output, monitor, etc.
                    python_class_path = f'backend.plugins.connections.{module_name}.{class_name}'
                else:
                    # Fallback: use full module path
                    python_class_path = f'{module_path}.{class_name}'
                
                # Create or update the NodeTypeDefinition
                obj, created = NodeTypeDefinition.objects.update_or_create(
                    definition_type='connection',
                    type_identifier=connection_type,
                    defaults={
                        'definition_data': json.dumps(metadata),
                        'python_class_path': python_class_path
                    }
                )
                
                status = 'Created' if created else 'Updated'
                self.stdout.write(self.style.SUCCESS(f'{status} connection type: {connection_type} ({python_class_path})'))
                connection_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Failed to process connection type {connection_type}: {e}'))
        
        # Display summary
        self.stdout.write(self.style.SUCCESS(f'Global type definition population complete!'))
        self.stdout.write(f'Processed {node_count} node types and {connection_count} connection types.')
        self.stdout.write(f'Total global type definitions: {node_count + connection_count}')