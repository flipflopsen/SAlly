{
  "version": "1.0",
  "node_types": [
    // Array of node type definitions
  ],
  "connection_types": [
    // Array of connection type definitions
  ]
}
```

- `version` (string, required): Schema version identifier
- `node_types` (array, required): List of node type definitions
- `connection_types` (array, required): List of connection type definitions

## Usage Instructions

- Imported types are registered as dynamic plugin classes in the backend.
- Imported types will appear in the sidebar immediately after import (once the fix is implemented).
- Statically-loaded plugins are loaded from Python files in the plugins directory, while dynamically-imported types are created from JSON definitions at runtime.
- Dynamic types are for visual editing only and may not have execution logic.

## Node Type Definition

Each node type definition is an object containing metadata and configuration for a specific node class. Node types define the structure, behavior, and validation rules for graph nodes.

```json
{
  "type": "solar_panel",
  "label": "Solar Panel",
  "description": "Photovoltaic solar panel with configurable power output",
  "category": "Energy Sources",
  "inputs": [
    {
      "id": "irradiance",
      "label": "Solar Irradiance",
      "type": "input",
      "dataType": "power"
    }
  ],
  "outputs": [
    {
      "id": "power_output",
      "label": "Power Output",
      "type": "output",
      "dataType": "power"
    }
  ],
  "defaultData": {
    "efficiency": 0.18,
    "area_m2": 1.0
  },
  "fieldSchema": [
    // Dynamic field definitions
  ]
}
```

### Field Descriptions

- `type` (string, required): Unique identifier for the node type (used internally)
- `label` (string, required): Human-readable display name shown in the UI
- `description` (string, required): Detailed description of the node's functionality
- `category` (string, required): Organizational category for grouping in the sidebar
- `inputs` (array, optional): List of input handles the node accepts
- `outputs` (array, optional): List of output handles the node provides
- `defaultData` (object, optional): Default values applied when creating new instances
- `fieldSchema` (array, optional): Dynamic field definitions for configurable parameters

**Note:** The `type` field serves as the unique identifier for internal use and matching, while `label` is the human-readable display name shown in the user interface.

### Input/Output Handle Structure

Each handle in the `inputs` and `outputs` arrays has the following structure:

```json
{
  "id": "handle_id",
  "label": "Display Label",
  "type": "input|output",
  "dataType": "power|data|any"
}
```

- `id` (string, required): Unique identifier for the handle
- `label` (string, required): Display label shown in the UI
- `type` (string, required): Either "input" or "output"
- `dataType` (string, optional): Data type constraint for connections (default: "any")

## Connection Type Definition

Connection types define the properties and validation rules for edges between nodes in the graph. They support metadata and dynamic fields similar to node types.

```json
{
  "type": "power_cable",
  "label": "Power Cable",
  "description": "Electrical cable for power transmission",
  "category": "Power Connections",
  "defaultData": {
    "resistance_ohm_per_km": 0.1,
    "max_current_a": 100
  },
  "fieldSchema": [
    // Dynamic field definitions
  ]
}
```

### Field Descriptions

- `type` (string, required): Unique identifier for the connection type
- `label` (string, required): Human-readable display name
- `description` (string, required): Description of the connection's purpose
- `category` (string, required): Organizational category
- `defaultData` (object, optional): Default values for new connections
- `fieldSchema` (array, optional): Dynamic field definitions for connection parameters

**Note:** The `type` field serves as the unique identifier for internal use and matching, while `label` is the human-readable display name shown in the user interface.

## Field Schema Definition

Field schemas define dynamic, configurable parameters for nodes and connections. Each field can have validation rules, data types, and constraints.

```json
{
  "name": "voltage_rating",
  "field_type": "monitor",
  "data_type": "number",
  "units": "V",
  "min_value": 0,
  "max_value": 1000,
  "default_value": 220,
  "required": true,
  "description": "Maximum voltage the cable can handle"
}
```

### Field Descriptions

- `name` (string, required): Unique field identifier (used as object key)
- `field_type` (string, required): Field classification - "input", "output", or "monitor"
- `data_type` (string, required): Data type - "string", "number", "boolean", "array", "object"
- `units` (string, optional): Measurement units (e.g., "V", "A", "°C", "kW")
- `min_value` (number, optional): Minimum allowed value for numeric fields
- `max_value` (number, optional): Maximum allowed value for numeric fields
- `default_value` (any, optional): Default value matching the data_type
- `required` (boolean, required): Whether the field must be provided
- `description` (string, optional): Help text explaining the field's purpose

### Field Type Classifications

- **input**: Fields that accept data from connected nodes
- **output**: Fields that provide data to connected nodes
- **monitor**: Fields that track internal state, configuration parameters, or monitoring values

**Note:** The 'monitor' field type aligns with the monitoring connection type in the system, making it intuitive for users to understand that these fields are used for tracking node/connection state and configuration rather than data flow.

## Complete Example

Below is a complete example showing a custom solar panel node and power cable connection type. This matches the actual export format from the backend, where node and connection types are exported with fields like 'type', 'label', 'description', 'category', etc.

**Note:** The `type` field serves as the unique identifier for internal use and matching, while `label` is the human-readable display name shown in the user interface.

```json
{
  "version": "1.0",
  "node_types": [
    {
      "type": "solar_panel",
      "label": "Solar Panel",
      "description": "Photovoltaic solar panel with configurable efficiency and area",
      "category": "Energy Sources",
      "inputs": [
        {
          "id": "irradiance",
          "label": "Solar Irradiance",
          "type": "input",
          "dataType": "power"
        }
      ],
      "outputs": [
        {
          "id": "power_output",
          "label": "Power Output",
          "type": "output",
          "dataType": "power"
        }
      ],
      "defaultData": {
        "efficiency": 0.18,
        "area_m2": 1.0
      },
      "fieldSchema": [
        {
          "name": "efficiency",
          "field_type": "monitor",
          "data_type": "number",
          "units": "%",
          "min_value": 0.05,
          "max_value": 0.25,
          "default_value": 0.18,
          "required": true,
          "description": "Solar panel efficiency (0.05-0.25)"
        },
        {
          "name": "area_m2",
          "field_type": "monitor",
          "data_type": "number",
          "units": "m²",
          "min_value": 0.1,
          "max_value": 100.0,
          "default_value": 1.0,
          "required": true,
          "description": "Panel surface area in square meters"
        },
        {
          "name": "temperature_coefficient",
          "field_type": "monitor",
          "data_type": "number",
          "units": "%/°C",
          "min_value": -0.5,
          "max_value": 0.0,
          "default_value": -0.004,
          "required": false,
          "description": "Power temperature coefficient"
        }
      ]
    }
  ],
  "connection_types": [
    {
      "type": "power_cable",
      "label": "Power Cable",
      "description": "Electrical cable for power transmission with resistance and current limits",
      "category": "Power Connections",
      "defaultData": {
        "resistance_ohm_per_km": 0.1,
        "max_current_a": 100
      },
      "fieldSchema": [
        {
          "name": "resistance_ohm_per_km",
          "field_type": "monitor",
          "data_type": "number",
          "units": "Ω/km",
          "min_value": 0.01,
          "max_value": 1.0,
          "default_value": 0.1,
          "required": true,
          "description": "Cable resistance per kilometer"
        },
        {
          "name": "max_current_a",
          "field_type": "monitor",
          "data_type": "number",
          "units": "A",
          "min_value": 1,
          "max_value": 1000,
          "default_value": 100,
          "required": true,
          "description": "Maximum current rating"
        },
        {
          "name": "length_km",
          "field_type": "monitor",
          "data_type": "number",
          "units": "km",
          "min_value": 0.001,
          "max_value": 100.0,
          "default_value": 1.0,
          "required": true,
          "description": "Cable length in kilometers"
        },
        {
          "name": "insulation_type",
          "field_type": "monitor",
          "data_type": "string",
          "default_value": "PVC",
          "required": false,
          "description": "Cable insulation material"
        }
      ]
    }
  ]
}

## Troubleshooting

This section covers common issues when importing type definitions and how to resolve them.

### Common Import Errors

#### "Each node type must have a 'label' field"
- **Cause:** The import validation requires both 'type' and 'label' fields for each node type. If 'label' is missing or misspelled, validation fails.
- **Solution:** Ensure every node type object includes a 'label' field with a human-readable string value. Check for typos (e.g., 'name' instead of 'label').

#### "Each connection type must have a 'label' field"
- **Cause:** Similar to node types, connection types must have both 'type' and 'label' fields.
- **Solution:** Add the 'label' field to each connection type object.

#### "Validation failed" with details about missing fields
- **Cause:** The serializer checks for required fields ('type' and 'label') in both node_types and connection_types arrays.
- **Solution:** Review the JSON structure and ensure all required fields are present. The error response includes 'details' with specific validation errors, 'hint' with guidance, and 'received_keys' for debugging.

### Valid vs Invalid Examples

#### Valid Node Type Definition
```json
{
  "type": "solar_panel",
  "label": "Solar Panel",
  "description": "Photovoltaic solar panel",
  "category": "Energy Sources"
}
```

#### Invalid Node Type Definition (Missing 'label')
```json
{
  "type": "solar_panel",
  "name": "Solar Panel",  // Incorrect: Should be 'label', not 'name'
  "description": "Photovoltaic solar panel",
  "category": "Energy Sources"
}
```
**Fix:** Change `"name"` to `"label"`.

#### Invalid Connection Type Definition (Missing 'type')
```json
{
  "label": "Power Cable",
  "description": "Electrical cable",
  "category": "Power Connections"
}
```
**Fix:** Add `"type": "power_cable"` (or another unique identifier).

### General Guidance
- **Field Name Consistency:** Always use 'label' for display names and 'type' for unique identifiers. The backend export uses 'label', so imports must match.
- **JSON Structure:** Ensure the top-level object has 'version', 'node_types', and 'connection_types'. Each array element must be an object with required fields.
- **Validation Feedback:** Check the API response for 'details' and 'hint' fields to identify specific issues. If problems persist, verify the JSON against the Complete Example above.
- **Testing Imports:** Use the export_type_definitions endpoint to see the exact format, then modify and re-import to test changes.

### Additional Troubleshooting

- **Issue: Imported types don't appear in sidebar**
  - Solution: Ensure the JSON structure matches the schema exactly
  - Check browser console for error messages
  - Verify the import success message shows correct counts
- **Issue: Import succeeds but types are missing**
  - Solution: Check that type names don't conflict with existing static plugins
  - Review Django logs for registration errors
  - Try exporting current types to see the expected format
- **Issue: Sidebar doesn't update after import**
  - Solution: This was a known issue, now fixed by registering dynamic plugin classes
  - If still occurring, check browser console for API errors

## Technical Details

- The backend creates dynamic Python classes from imported JSON using the `type()` function, which extend `BaseNodePlugin` or `BaseConnectionPlugin`.
- These dynamic classes implement all required abstract methods as class methods, including `get_type()`, `get_label()`, `get_description()`, `get_category()`, and type-specific methods like `get_inputs()` and `get_outputs()` for nodes.
- Dynamic types are stored in memory within the singleton registries and are lost on server restart (unless persisted to a database in a future enhancement).
- Field schemas can be updated for both static and dynamic types, allowing runtime configuration of parameters.
