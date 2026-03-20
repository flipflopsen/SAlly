# Single Line Diagram (SLD) Generator

## Overview
The SLD Generator provides visualization capabilities for power system single-line diagrams with support for multiple data sources and color schemes.

## Features
- **Multiple Data Sources**: JSON, CSV/Pandas, HDF5
- **Color Schemes**: Default, Dark, High Contrast, Colorblind Friendly, Industrial, Modern
- **Interactive Canvas**: Zoomable, scrollable, moveable nodes, context menus
- **Component Types**: Generator, Transformer, Circuit Breaker, Bus, Transmission Line, Load, Capacitor, Reactor, Switch, Meter
- **Component States**: Normal, Alarm, Fault, Offline, Maintenance
- **Export**: PNG, SVG, PDF formats

## Usage

### Basic Example
```python
from SAlly.gui.sdl import SLDGenerator, JSONDataModel

# Load data from JSON
data_model = JSONDataModel()
components, connections = data_model.load_data('grid_data.json')

# Create and run generator
app = SLDGenerator()
app.load_data_model(data_model)
app.mainloop()
```

### HDF5 Data Source
```python
from SAlly.gui.sdl import SLDGenerator, HDF5DataModel

data_model = HDF5DataModel()
components, connections = data_model.load_data('simulation_data.hdf5')

app = SLDGenerator()
app.load_data_model(data_model)
app.mainloop()
```

## Data Format

### JSON Format
```json
{
  "components": [
    {
      "id": "gen1",
      "name": "Generator 1",
      "type": "generator",
      "x": 100,
      "y": 100,
      "state": "normal",
      "voltage": 230.0,
      "power": 50.0
    }
  ],
  "connections": [
    {
      "id": "conn1",
      "from": "gen1",
      "to": "bus1",
      "type": "line"
    }
  ]
}
```

## Color Schemes
Change color scheme via the View menu or programmatically:
```python
from SAlly.gui.sdl import ColorScheme
app.set_color_scheme(ColorScheme.DARK)
```

## Status
✅ **ACTIVE** - Fully functional and maintained

## Related Modules
- `SAlly.core.hdf5_builder` - For creating HDF5 test data
- `SAlly.simulation` - For generating simulation data to visualize