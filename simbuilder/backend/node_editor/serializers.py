"""REST API serializers for graph data transfer."""
import json
from rest_framework import serializers
from .models import GraphProject, NodeInstance, NodeConnection, ProjectTypeDefinition, NodeTypeDefinition


class NodeConnectionSerializer(serializers.ModelSerializer):
    """Serializer for node connections."""

    class Meta:
        model = NodeConnection
        fields = [
            'id', 'connection_id', 'connection_type', 'source_node', 'target_node',
            'source_handle', 'target_handle', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class NodeInstanceSerializer(serializers.ModelSerializer):
    """Serializer for node instances with position data."""

    def to_representation(self, instance):
        """Convert instance to representation, parsing JSON data field."""
        representation = super().to_representation(instance)

        # Parse JSON string data to dict if it's a string
        if isinstance(instance.data, str):
            try:
                representation['data'] = json.loads(instance.data)
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, keep as string
                pass

        # Include field_definitions in representation if present in data
        if isinstance(representation.get('data'), dict) and 'field_definitions' in representation['data']:
            representation['field_definitions'] = representation['data']['field_definitions']

        return representation

    def to_internal_value(self, data):
        """Convert input data to internal value, serializing data field to JSON."""
        internal_value = super().to_internal_value(data)

        # Convert dict data to JSON string if it's a dict
        if 'data' in internal_value and isinstance(internal_value['data'], dict):
            internal_value['data'] = json.dumps(internal_value['data'])

        return internal_value

    class Meta:
        model = NodeInstance
        fields = [
            'id', 'node_id', 'node_type', 'label',
            'position_x', 'position_y', 'data', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ProjectTypeDefinitionSerializer(serializers.ModelSerializer):
    """Serializer for project-specific type definitions."""

    class Meta:
        model = ProjectTypeDefinition
        fields = ['id', 'project', 'definition_type', 'type_identifier', 'definition_data', 'python_class_path', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        """Convert instance to representation, parsing JSON definition_data field."""
        representation = super().to_representation(instance)

        # Parse JSON string definition_data to dict if it's a string
        if isinstance(instance.definition_data, str):
            try:
                representation['definition_data'] = json.loads(instance.definition_data)
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, keep as string
                pass

        return representation

    def to_internal_value(self, data):
        """Convert input data to internal value, serializing definition_data field to JSON."""
        internal_value = super().to_internal_value(data)

        # Convert dict definition_data to JSON string if it's a dict
        if 'definition_data' in internal_value and isinstance(internal_value['definition_data'], dict):
            internal_value['definition_data'] = json.dumps(internal_value['definition_data'])

        return internal_value


class NodeTypeDefinitionSerializer(serializers.ModelSerializer):
    """Serializer for global type definitions."""

    class Meta:
        model = NodeTypeDefinition
        fields = ['id', 'definition_type', 'type_identifier', 'definition_data', 'python_class_path', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        """Convert instance to representation, parsing JSON definition_data field."""
        representation = super().to_representation(instance)

        # Parse JSON string definition_data to dict if it's a string
        if isinstance(instance.definition_data, str):
            try:
                representation['definition_data'] = json.loads(instance.definition_data)
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, keep as string
                pass

        return representation

    def to_internal_value(self, data):
        """Convert input data to internal value, serializing definition_data field to JSON."""
        internal_value = super().to_internal_value(data)

        # Convert dict definition_data to JSON string if it's a dict
        if 'definition_data' in internal_value and isinstance(internal_value['definition_data'], dict):
            internal_value['definition_data'] = json.dumps(internal_value['definition_data'])

        return internal_value


class GraphProjectSerializer(serializers.ModelSerializer):
    """Full graph serializer with nested nodes and connections."""

    nodes = NodeInstanceSerializer(many=True, read_only=True)
    connections = NodeConnectionSerializer(many=True, read_only=True)
    type_definitions = ProjectTypeDefinitionSerializer(many=True, read_only=True)
    owner_name = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = GraphProject
        fields = [
            'id', 'name', 'description', 'owner', 'owner_name',
            'nodes', 'connections', 'type_definitions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'owner']


class GraphProjectListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for project lists."""

    owner_name = serializers.CharField(source='owner.username', read_only=True)
    node_count = serializers.IntegerField(source='nodes.count', read_only=True)

    class Meta:
        model = GraphProject
        fields = [
            'id', 'name', 'description', 'owner_name',
            'node_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FieldDefinitionSerializer(serializers.Serializer):
    """Serializer for individual field definitions."""

    field_name = serializers.CharField()
    field_type = serializers.ChoiceField(choices=['input', 'output', 'monitor'])
    data_type = serializers.CharField()
    units = serializers.CharField(required=False, allow_blank=True)
    min_value = serializers.FloatField(required=False)
    max_value = serializers.FloatField(required=False)
    default_value = serializers.JSONField(required=False)
    required = serializers.BooleanField()
    description = serializers.CharField(required=False, allow_blank=True)


class TypeDefinitionSerializer(serializers.Serializer):
    """Serializer for type definition import/export."""

    version = serializers.CharField()
    node_types = serializers.ListField(child=serializers.DictField())
    connection_types = serializers.ListField(child=serializers.DictField())

    def validate_node_types(self, value):
        """Validate that each node type has required fields."""
        for item in value:
            if not item.get('label'):
                raise serializers.ValidationError("Each node type must have a 'label' field.")
            if not item.get('type'):
                raise serializers.ValidationError("Each node type must have a 'type' field.")
        return value

    def validate_connection_types(self, value):
        """Validate that each connection type has required fields."""
        for item in value:
            if not item.get('label'):
                raise serializers.ValidationError("Each connection type must have a 'label' field.")
            if not item.get('type'):
                raise serializers.ValidationError("Each connection type must have a 'type' field.")
        return value