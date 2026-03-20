"""Core data models for node graph persistence."""
from django.db import models
from django.contrib.auth.models import User
import json


class GraphProject(models.Model):
    """Container for node graphs with metadata."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='graph_projects',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        owner_name = self.owner.username if self.owner else 'No Owner'
        return f"{self.name} ({owner_name})"

    def get_type_definitions(self, definition_type=None):
        """Return queryset of ProjectTypeDefinition filtered by project and optionally by definition_type."""
        queryset = self.type_definitions.all()
        if definition_type:
            queryset = queryset.filter(definition_type=definition_type)
        return queryset


class NodeInstance(models.Model):
    """Individual node instances in the graph."""

    project = models.ForeignKey(
        GraphProject,
        on_delete=models.CASCADE,
        related_name='nodes'
    )
    node_id = models.CharField(max_length=255, unique=True)
    node_type = models.CharField(max_length=100)
    label = models.CharField(max_length=255, default='Untitled Node')
    position_x = models.FloatField(default=0.0)
    position_y = models.FloatField(default=0.0)
    data = models.TextField(default='{}')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['project', 'node_type']),
        ]

    def __str__(self):
        return f"{self.label} ({self.node_type})"

    def get_field_definitions(self):
        """Parse the data JSON field and extract 'field_definitions' key if present.

        Returns:
            List of field definition dictionaries, or empty list if not found.
        """
        data = json.loads(self.data)
        return data.get('field_definitions', [])

    def set_field_definitions(self, field_defs):
        """Parse current data JSON, update 'field_definitions' key with field_defs, serialize back to JSON and save.

        Args:
            field_defs: List of field definition dictionaries.
        """
        data = json.loads(self.data)
        data['field_definitions'] = field_defs
        self.data = json.dumps(data)
        self.save()

    def get_field_values(self):
        """Return all field values from data excluding 'field_definitions' metadata.

        Returns:
            Dictionary of field values.
        """
        data = json.loads(self.data)
        data.pop('field_definitions', None)
        return data

    def validate_against_schema(self):
        """Get field definitions, validate current field values against schema.

        Returns:
            Tuple of (is_valid, errors) where errors is a list of error messages.
        """
        field_defs = self.get_field_definitions()
        field_values = self.get_field_values()
        errors = []
        for field_def in field_defs:
            name = field_def['name']
            if field_def.get('required', False) and name not in field_values:
                errors.append(f"Required field '{name}' is missing")
                continue
            if name in field_values:
                value = field_values[name]
                data_type = field_def.get('data_type')
                if data_type == 'number':
                    if not isinstance(value, (int, float)):
                        errors.append(f"Field '{name}' must be a number")
                    else:
                        min_val = field_def.get('min_value')
                        if min_val is not None and value < min_val:
                            errors.append(f"Field '{name}' must be >= {min_val}")
                        max_val = field_def.get('max_value')
                        if max_val is not None and value > max_val:
                            errors.append(f"Field '{name}' must be <= {max_val}")
                elif data_type == 'string':
                    if not isinstance(value, str):
                        errors.append(f"Field '{name}' must be a string")
                elif data_type == 'boolean':
                    if not isinstance(value, bool):
                        errors.append(f"Field '{name}' must be a boolean")
                # Add more data types as needed
        is_valid = len(errors) == 0
        return is_valid, errors


class NodeConnection(models.Model):
    """Edges connecting nodes in the graph."""

    project = models.ForeignKey(
        GraphProject,
        on_delete=models.CASCADE,
        related_name='connections'
    )
    connection_id = models.CharField(max_length=255, unique=True)
    connection_type = models.CharField(max_length=100, default='default')
    source_node = models.ForeignKey(
        NodeInstance,
        on_delete=models.CASCADE,
        related_name='outgoing_connections'
    )
    target_node = models.ForeignKey(
        NodeInstance,
        on_delete=models.CASCADE,
        related_name='incoming_connections'
    )
    source_handle = models.CharField(max_length=100)
    target_handle = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ['source_node', 'source_handle', 'target_node', 'target_handle']
        ]

    def __str__(self):
        return f"{self.source_node.label} → {self.target_node.label}"


class ProjectTypeDefinition(models.Model):
    """Storage for project-specific node and connection type definitions."""

    DEFINITION_TYPE_CHOICES = [
        ('node', 'Node Type'),
        ('connection', 'Connection Type'),
    ]

    project = models.ForeignKey(
        GraphProject,
        on_delete=models.CASCADE,
        related_name='type_definitions'
    )
    definition_type = models.CharField(
        max_length=20,
        choices=DEFINITION_TYPE_CHOICES
    )
    type_identifier = models.CharField(max_length=100)
    definition_data = models.TextField()
    python_class_path = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='Python import path to the plugin class'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['project', 'definition_type', 'type_identifier']]
        ordering = ['definition_type', 'type_identifier']
        indexes = [
            models.Index(fields=['project', 'definition_type']),
        ]

    def __str__(self):
        return f"{self.type_identifier} ({self.definition_type}) - {self.project.name}"

    def get_definition(self):
        """Parse and return definition_data as dict."""
        return json.loads(self.definition_data)

    def set_definition(self, data):
        """Serialize data to JSON and store in definition_data."""
        self.definition_data = json.dumps(data)


class NodeTypeDefinition(models.Model):
    """Global storage for reusable node and connection type definitions."""

    DEFINITION_TYPE_CHOICES = [
        ('node', 'Node Type'),
        ('connection', 'Connection Type'),
    ]

    definition_type = models.CharField(
        max_length=20,
        choices=DEFINITION_TYPE_CHOICES
    )
    type_identifier = models.CharField(max_length=100)
    definition_data = models.TextField()
    python_class_path = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['definition_type', 'type_identifier']
        unique_together = [['definition_type', 'type_identifier']]
        indexes = [
            models.Index(fields=['definition_type']),
        ]

    def __str__(self):
        return f"{self.type_identifier} ({self.definition_type}) - Global"

    def get_definition(self):
        """Parse and return definition_data as dict."""
        return json.loads(self.definition_data)

    def set_definition(self, data):
        """Serialize data to JSON and store in definition_data."""
        self.definition_data = json.dumps(data)