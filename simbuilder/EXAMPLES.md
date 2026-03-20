# Type Definitions Examples

This document provides practical examples of type definitions for nodes and connections in the SCADA simulation builder. These examples demonstrate how to structure JSON for importing custom node and connection types, including field schemas for dynamic validation.

## Example 1: Basic Node Type

This example shows a simple TemperatureSensor node with minimal fields, demonstrating string and number data types.

```json
{
  "version": "1.0",
  "node_types": [
    {
      "type": "temperature_sensor",
      "label": "Temperature Sensor",
      "description": "A basic temperature sensor that outputs a configurable temperature value",
      "category": "Sensors",
      "inputs": [],
      "outputs": [
        {
          "id": "temperature",
          "label": "Temperature",
          "type": "output",
          "dataType": "number"
        }
      ],
      "defaultData": {
        "unit": "Celsius",
        "value": 25.0
      },
      "fieldSchema": [
        {
          "name": "unit",
          "field_type": "parameter",
          "data_type": "string",
          "default_value": "Celsius",
          "required": true,
          "description": "Temperature measurement unit"
        },
        {
          "name": "value",
          "field_type": "parameter",
          "data_type": "number",
          "default_value": 25.0,
          "required": true,
          "description": "Current temperature value in the specified unit"
        }
      ]
    }
  ],
  "connection_types": []
}
```

## Example 2: Complex Node Type

This example shows a BatteryStorage node with multiple inputs, outputs, and parameter fields, demonstrating all field_type options and min/max validation for numeric fields.

```json
{
  "version": "1.0",
  "node_types": [
    {
      "type": "battery_storage",
      "label": "Battery Storage",
      "description": "Represents a battery energy storage system for grid stabilization",
      "category": "Storage",
      "inputs": [
        {
          "id": "charge",
          "label": "Charge Input",
          "type": "input",
          "dataType": "power"
        },
        {
          "id": "grid_power",
          "label": "Grid Power",
          "type": "input",
          "dataType": "power"
        }
      ],
      "outputs": [
        {
          "id": "discharge",
          "label": "Discharge Output",
          "type": "output",
          "dataType": "power"
        },
        {
          "id": "soc",
          "label": "State of Charge",
          "type": "output",
          "dataType": "percentage"
        }
      ],
      "defaultData": {
        "capacity_kwh": 100.0,
        "max_charge_rate_kw": 50.0,
        "max_discharge_rate_kw": 50.0,
        "current_soc": 0.5,
        "efficiency": 0.92
      },
      "fieldSchema": [
        {
          "name": "capacity_kwh",
          "field_type": "parameter",
          "data_type": "number",
          "units": "kWh",
          "min_value": 0.1,
          "max_value": 10000.0,
          "default_value": 100.0,
          "required": true,
          "description": "Battery storage capacity"
        },
        {
          "name": "max_charge_rate_kw",
          "field_type": "parameter",
          "data_type": "number",
          "units": "kW",
          "min_value": 0.1,
          "max_value": 1000.0,
          "default_value": 50.0,
          "required": true,
          "description": "Maximum charging rate"
        },
        {
          "name": "max_discharge_rate_kw",
          "field_type": "parameter",
          "data_type": "number",
          "units": "kW",
          "min_value": 0.1,
          "max_value": 1000.0,
          "default_value": 50.0,
          "required": true,
          "description": "Maximum discharging rate"
        },
        {
          "name": "current_soc",
          "field_type": "parameter",
          "data_type": "number",
          "min_value": 0.0,
          "max_value": 1.0,
          "default_value": 0.5,
          "required": true,
          "description": "Current state of charge (0.0 to 1.0)"
        },
        {
          "name": "efficiency",
          "field_type": "parameter",
          "data_type": "number",
          "min_value": 0.0,
          "max_value": 1.0,
          "default_value": 0.92,
          "required": true,
          "description": "Round-trip efficiency (0.0 to 1.0)"
        }
      ]
    }
  ],
  "connection_types": []
}
```

## Example 3: Connection Type

This example shows a PowerCable connection type with validation fields, demonstrating how connection fields are validated.

```json
{
  "version": "1.0",
  "node_types": [],
  "connection_types": [
    {
      "type": "power_cable",
      "label": "Power Cable",
      "description": "Electrical cable for power transmission with voltage and current ratings",
      "category": "Power",
      "defaultData": {
        "voltage_rating_v": 400.0,
        "current_rating_a": 100.0,
        "cable_type": "Copper",
        "length_m": 10.0
      },
      "fieldSchema": [
        {
          "name": "voltage_rating_v",
          "field_type": "parameter",
          "data_type": "number",
          "units": "V",
          "min_value": 1.0,
          "max_value": 1000000.0,
          "default_value": 400.0,
          "required": true,
          "description": "Maximum voltage rating"
        },
        {
          "name": "current_rating_a",
          "field_type": "parameter",
          "data_type": "number",
          "units": "A",
          "min_value": 0.1,
          "max_value": 10000.0,
          "default_value": 100.0,
          "required": true,
          "description": "Maximum current rating"
        },
        {
          "name": "cable_type",
          "field_type": "parameter",
          "data_type": "string",
          "default_value": "Copper",
          "required": true,
          "description": "Type of cable material (e.g., Copper, Aluminum)"
        },
        {
          "name": "length_m",
          "field_type": "parameter",
          "data_type": "number",
          "units": "m",
          "min_value": 0.1,
          "max_value": 10000.0,
          "default_value": 10.0,
          "required": true,
          "description": "Cable length in meters"
        }
      ]
    }
  ]
}
```

## Example 4: Import/Export Workflow

This example provides a step-by-step tutorial for exporting, modifying, and importing type definitions.

1. **Export existing types**: In the application UI, navigate to the export functionality and download the current type definitions as a JSON file. This gives you a baseline structure.

1.5. **Verify the exported JSON structure**: Open the downloaded JSON file and ensure it follows the expected format with a top-level structure including "version", "node_types", and "connection_types". Each node type and connection type must have required fields: 'type' (unique identifier) and 'label' (human-readable display name). For example, a valid node type might look like: {"type": "temperature_sensor", "label": "Temperature Sensor", ...}.

2. **Add a new custom node type**: Open the exported JSON file in a text editor. Add a new object to the `node_types` array. For example, add the TemperatureSensor from Example 1. Note: Each node type must include 'type' and 'label' fields; missing either will cause a validation error.

3. **Import the modified JSON**: In the application UI, use the import functionality to upload your modified JSON file. The system will validate and register the new types. If validation fails (e.g., due to a missing 'label' field), you'll receive a 400 Bad Request error with details like: {"error": "Each node type must have a 'label' field."}. To fix, add the missing field to your JSON and re-import.

4. **Verify the new type appears**: Check the node sidebar in the editor. You should see the new "Temperature Sensor" type under the "Sensors" category.

5. **Create an instance**: Drag the new TemperatureSensor node onto the canvas to create an instance.

6. **Configure its fields**: Double-click the node or use the NodeConfigEditor to modify the "unit" and "value" parameters. The fields will validate according to the fieldSchema (e.g., "value" must be a number).

## Example 5: Field Schema Patterns

This example shows common field configurations for reuse in your type definitions.

```json
{
  "version": "1.0",
  "node_types": [
    {
      "type": "example_patterns",
      "label": "Field Schema Patterns",
      "description": "Demonstrates common field configurations",
      "category": "Examples",
      "inputs": [],
      "outputs": [],
      "defaultData": {
        "voltage": 220.0,
        "current": 10.0,
        "temperature": 25.0,
        "enabled": true,
        "identifier": "DEV001"
      },
      "fieldSchema": [
        {
          "name": "voltage",
          "field_type": "parameter",
          "data_type": "number",
          "units": "V",
          "min_value": 0.0,
          "max_value": 1000.0,
          "default_value": 220.0,
          "required": true,
          "description": "Voltage level"
        },
        {
          "name": "current",
          "field_type": "parameter",
          "data_type": "number",
          "units": "A",
          "min_value": 0.0,
          "max_value": 100.0,
          "default_value": 10.0,
          "required": true,
          "description": "Current level"
        },
        {
          "name": "temperature",
          "field_type": "parameter",
          "data_type": "number",
          "units": "°C",
          "min_value": -40.0,
          "max_value": 85.0,
          "default_value": 25.0,
          "required": true,
          "description": "Operating temperature"
        },
        {
          "name": "enabled",
          "field_type": "parameter",
          "data_type": "boolean",
          "default_value": true,
          "required": true,
          "description": "Enable/disable the device"
        },
        {
          "name": "identifier",
          "field_type": "parameter",
          "data_type": "string",
          "default_value": "DEV001",
          "required": true,
          "description": "Unique device identifier"
        }
      ]
    }
  ],
  "connection_types": []
}
```

## Example 6: Real-World Use Case

This example shows a complete smart grid scenario with related node and connection types.

```json
{
  "version": "1.0",
  "node_types": [
    {
      "type": "solar_panel",
      "label": "Solar Panel",
      "description": "Solar photovoltaic panel generating power from sunlight",
      "category": "Generation",
      "inputs": [],
      "outputs": [
        {
          "id": "power",
          "label": "Power Output",
          "type": "output",
          "dataType": "power"
        }
      ],
      "defaultData": {
        "capacity_kw": 5.0,
        "efficiency": 0.2
      },
      "fieldSchema": [
        {
          "name": "capacity_kw",
          "field_type": "parameter",
          "data_type": "number",
          "units": "kW",
          "min_value": 0.1,
          "max_value": 100.0,
          "default_value": 5.0,
          "required": true,
          "description": "Panel capacity"
        },
        {
          "name": "efficiency",
          "field_type": "parameter",
          "data_type": "number",
          "min_value": 0.0,
          "max_value": 1.0,
          "default_value": 0.2,
          "required": true,
          "description": "Conversion efficiency"
        }
      ]
    },
    {
      "type": "wind_turbine",
      "label": "Wind Turbine",
      "description": "Wind turbine generating power from wind",
      "category": "Generation",
      "inputs": [],
      "outputs": [
        {
          "id": "power",
          "label": "Power Output",
          "type": "output",
          "dataType": "power"
        }
      ],
      "defaultData": {
        "capacity_kw": 2.0,
        "cut_in_speed": 3.0,
        "cut_out_speed": 25.0
      },
      "fieldSchema": [
        {
          "name": "capacity_kw",
          "field_type": "parameter",
          "data_type": "number",
          "units": "kW",
          "min_value": 0.1,
          "max_value": 10.0,
          "default_value": 2.0,
          "required": true,
          "description": "Turbine capacity"
        },
        {
          "name": "cut_in_speed",
          "field_type": "parameter",
          "data_type": "number",
          "units": "m/s",
          "min_value": 1.0,
          "max_value": 10.0,
          "default_value": 3.0,
          "required": true,
          "description": "Minimum wind speed for operation"
        },
        {
          "name": "cut_out_speed",
          "field_type": "parameter",
          "data_type": "number",
          "units": "m/s",
          "min_value": 10.0,
          "max_value": 50.0,
          "default_value": 25.0,
          "required": true,
          "description": "Maximum wind speed for safe operation"
        }
      ]
    },
    {
      "type": "grid_connection",
      "label": "Grid Connection",
      "description": "Connection point to the electrical grid",
      "category": "Grid",
      "inputs": [
        {
          "id": "power_in",
          "label": "Power Input",
          "type": "input",
          "dataType": "power"
        }
      ],
      "outputs": [
        {
          "id": "power_out",
          "label": "Power Output",
          "type": "output",
          "dataType": "power"
        }
      ],
      "defaultData": {
        "voltage_v": 400.0,
        "frequency_hz": 50.0
      },
      "fieldSchema": [
        {
          "name": "voltage_v",
          "field_type": "parameter",
          "data_type": "number",
          "units": "V",
          "min_value": 100.0,
          "max_value": 1000.0,
          "default_value": 400.0,
          "required": true,
          "description": "Grid voltage"
        },
        {
          "name": "frequency_hz",
          "field_type": "parameter",
          "data_type": "number",
          "units": "Hz",
          "min_value": 45.0,
          "max_value": 65.0,
          "default_value": 50.0,
          "required": true,
          "description": "Grid frequency"
        }
      ]
    },
    {
      "type": "load_controller",
      "label": "Load Controller",
      "description": "Controls electrical load based on input power",
      "category": "Control",
      "inputs": [
        {
          "id": "power",
          "label": "Power Input",
          "type": "input",
          "dataType": "power"
        }
      ],
      "outputs": [
        {
          "id": "controlled_load",
          "label": "Controlled Load",
          "type": "output",
          "dataType": "power"
        }
      ],
      "defaultData": {
        "max_load_kw": 10.0,
        "efficiency": 0.95
      },
      "fieldSchema": [
        {
          "name": "max_load_kw",
          "field_type": "parameter",
          "data_type": "number",
          "units": "kW",
          "min_value": 0.1,
          "max_value": 1000.0,
          "default_value": 10.0,
          "required": true,
          "description": "Maximum controllable load"
        },
        {
          "name": "efficiency",
          "field_type": "parameter",
          "data_type": "number",
          "min_value": 0.0,
          "max_value": 1.0,
          "default_value": 0.95,
          "required": true,
          "description": "Controller efficiency"
        }
      ]
    }
  ],
  "connection_types": [
    {
      "type": "ac_power_line",
      "label": "AC Power Line",
      "description": "AC power transmission line",
      "category": "Power",
      "defaultData": {
        "voltage_v": 400.0,
        "frequency_hz": 50.0,
        "phase": "3-phase"
      },
      "fieldSchema": [
        {
          "name": "voltage_v",
          "field_type": "parameter",
          "data_type": "number",
          "units": "V",
          "min_value": 100.0,
          "max_value": 1000000.0,
          "default_value": 400.0,
          "required": true,
          "description": "Line voltage"
        },
        {
          "name": "frequency_hz",
          "field_type": "parameter",
          "data_type": "number",
          "units": "Hz",
          "min_value": 45.0,
          "max_value": 65.0,
          "default_value": 50.0,
          "required": true,
          "description": "AC frequency"
        },
        {
          "name": "phase",
          "field_type": "parameter",
          "data_type": "string",
          "default_value": "3-phase",
          "required": true,
          "description": "Number of phases (1-phase, 3-phase)"
        }
      ]
    },
    {
      "type": "dc_power_line",
      "label": "DC Power Line",
      "description": "DC power transmission line",
      "category": "Power",
      "defaultData": {
        "voltage_v": 400.0,
        "current_rating_a": 100.0
      },
      "fieldSchema": [
        {
          "name": "voltage_v",
          "field_type": "parameter",
          "data_type": "number",
          "units": "V",
          "min_value": 1.0,
          "max_value": 1000000.0,
          "default_value": 400.0,
          "required": true,
          "description": "DC voltage"
        },
        {
          "name": "current_rating_a",
          "field_type": "parameter",
          "data_type": "number",
          "units": "A",
          "min_value": 0.1,
          "max_value": 10000.0,
          "default_value": 100.0,
          "required": true,
          "description": "Current rating"
        }
      ]
    }
  ]
}
```

In a graph, you could connect SolarPanel and WindTurbine outputs to GridConnection inputs via AC/DC Power Lines, with LoadController managing consumption.

## Example 7: Validation Scenarios

This example demonstrates what happens with invalid data during import or configuration.

- **Missing required field**: If a node type lacks a required field in fieldSchema (required: true), import fails with "Field 'field_name' is required but missing".
- **Missing 'label' field in node/connection type**: If a node type or connection type lacks the required 'label' field, import fails with the exact error message: "Each node type must have a 'label' field." or "Each connection type must have a 'label' field." To fix, add the 'label' field to your JSON, e.g., change {"type": "temperature_sensor"} to {"type": "temperature_sensor", "label": "Temperature Sensor"} and re-import.
- **Value outside min/max range**: Setting voltage to 1500V when max_value is 1000.0 results in "Field 'voltage' value 1500.0 exceeds maximum 1000.0".
- **Wrong data type**: Providing a string "abc" for a number field returns "Field 'capacity' must be of type number, got string".
- **Duplicate field names**: Having two fields named "power" in fieldSchema causes "Duplicate field name 'power' in fieldSchema".
- Error messages are returned during import validation or when saving node configurations.

## Example 8: Migration Pattern

This example shows how to update existing type definitions while maintaining backward compatibility.

1. **Export current definitions**: Download the existing type definitions JSON.

2. **Add new fields**: For an existing BatteryStorage type, add a new field like "temperature_c" to fieldSchema with default_value and make it optional (required: false).

3. **Handle backward compatibility**: Ensure new fields have sensible defaults so existing nodes can still load without the new field.

4. **Import updated definitions**: Upload the modified JSON. The system updates the type definitions.

5. **Verify existing nodes still work**: Open projects with BatteryStorage nodes; they should load with the new default values for added fields.

## Example 9: Troubleshooting API Errors

This example covers common API errors and how to diagnose and resolve them.

- **400 Bad Request for import_type_definitions**: This occurs when the uploaded JSON fails validation, such as missing required fields ('type' or 'label') in node/connection types. Check the response for details like {"error": "Each node type must have a 'label' field."}. Solution: Edit your JSON to include all required fields and re-upload. Enable DEBUG mode in Django settings to see more detailed logs in the console.

- **404 Not Found for add_node or add_connection**: This happens if the custom action URLs aren't registered properly, often due to missing basenames in router registration. The URLs should be like `/api/projects/{id}/add_node/` or `/api/projects/{id}/add_connection/`. Solution: Ensure `api.py` has explicit basenames (e.g., `basename='project'` for GraphProjectViewSet). To verify, use the debug endpoint at `/api/debug/endpoints/` (if available in DEBUG mode) to list all registered URLs and confirm the actions are present.

- **Using debug endpoints**: If your backend includes a debug endpoint (e.g., `/api/debug/endpoints/`), access it in a browser or via API client to see a JSON list of all registered endpoints, including custom actions and their HTTP methods. This helps confirm URL registration without guessing.

- **Checking Django logs**: For detailed error messages, check your Django server logs (usually in the console or a log file). Look for stack traces related to validation failures or URL resolution. If DEBUG=True in settings, logs will include more context, such as incoming request data for import errors.

- **Common router registration issues**: If basenames are missing from `router.register()` calls, DRF may not generate custom action URLs in some versions. Always include them explicitly (e.g., `router.register(r'projects', GraphProjectViewSet, basename='project')`) to avoid 404 errors. Restart the server after changes to ensure the router reloads.

## Example 9: Importing Custom Types and Verifying Registration

**Step 1: Export baseline types**
- Click "Export Types" button in the node editor
- Save the file as `baseline_types.json`
- Open the file to understand the structure

**Step 2: Create a custom node type**
- Copy the JSON structure and add a new node type:
  - type: "solar_panel"
  - label: "Solar Panel"
  - description: "Photovoltaic solar panel with power output"
  - category: "Energy Sources"
  - inputs: [] (no inputs)
  - outputs: [{id: "power", label: "Power Output", type: "output", dataType: "number"}]
  - defaultData: {capacity: 5000, efficiency: 0.85}
  - fieldSchema: [{name: "capacity", field_type: "parameter", data_type: "number", units: "W", min_value: 0, max_value: 10000, required: true}]

**Step 3: Import the modified file**
- Click "Import Types" button
- Select the modified JSON file
- Verify the success message shows "imported_nodes: 1" (or higher)

**Step 4: Verify the type appears in sidebar**
- Check the sidebar for a new "Energy Sources" category
- Verify "Solar Panel" appears in the list
- The type should be draggable to the canvas

**Step 5: Create an instance**
- Drag the Solar Panel node onto the canvas
- Verify it appears with the correct label
- Double-click to open the configuration editor
- Verify the "capacity" field appears with correct constraints

**Step 6: Test persistence**
- Note: Dynamic types are stored in memory only
- After server restart, you'll need to re-import the JSON
- Consider keeping a library of custom type definitions for re-import

**Common issues and solutions:**
- If type doesn't appear: Check browser console for errors, verify JSON structure
- If import fails: Check Django logs for validation errors
- If sidebar doesn't update: Refresh the page and re-import

**Design rationale:**
- Step-by-step example helps users understand the complete workflow
- Including verification steps ensures users can confirm success
- Noting the in-memory nature of dynamic types sets correct expectations
- Troubleshooting tips address common user issues
