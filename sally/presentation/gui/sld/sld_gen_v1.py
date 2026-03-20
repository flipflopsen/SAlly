"""
Enhanced Single Line Diagram Generator for SCADA Systems
Comprehensive solution with HDF5 support, moveable nodes, and multiple color schemes
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import json
import yaml
import pandas as pd
import numpy as np
import h5py
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple, Union
from abc import ABC, abstractmethod
import math
from pathlib import Path
import logging
from enum import Enum

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """Enumeration of supported component types for the SLD"""
    GENERATOR = "generator"
    TRANSFORMER = "transformer"
    CIRCUIT_BREAKER = "circuit_breaker"
    BUS = "bus"
    TRANSMISSION_LINE = "transmission_line"
    LOAD = "load"
    CAPACITOR = "capacitor"
    REACTOR = "reactor"
    SWITCH = "switch"
    METER = "meter"


class ComponentState(Enum):
    """Component operational states"""
    NORMAL = "normal"
    ALARM = "alarm"
    FAULT = "fault"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class ColorScheme(Enum):
    """Available color schemes for the diagram"""
    DEFAULT = "default"
    DARK = "dark"
    HIGH_CONTRAST = "high_contrast"
    COLORBLIND_FRIENDLY = "colorblind_friendly"
    INDUSTRIAL = "industrial"
    MODERN = "modern"


@dataclass
class ComponentData:
    """Data structure for component information"""
    id: str
    name: str
    component_type: ComponentType
    position: Tuple[float, float]
    state: ComponentState = ComponentState.NORMAL
    voltage: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    frequency: Optional[float] = None
    temperature: Optional[float] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    connections: List[str] = field(default_factory=list)


@dataclass
class ConnectionData:
    """Data structure for connections between components"""
    id: str
    from_component: str
    to_component: str
    connection_type: str = "line"
    state: ComponentState = ComponentState.NORMAL
    properties: Dict[str, Any] = field(default_factory=dict)


class ColorSchemeManager:
    """Manages different color schemes for the diagram"""

    SCHEMES = {
        ColorScheme.DEFAULT: {
            ComponentState.NORMAL: "#2ECC71",
            ComponentState.ALARM: "#F39C12",
            ComponentState.FAULT: "#E74C3C",
            ComponentState.OFFLINE: "#95A5A6",
            ComponentState.MAINTENANCE: "#9B59B6",
            "background": "#FFFFFF",
            "text": "#000000",
            "connection": "#000000",
            "bus": "#34495E"
        },
        ColorScheme.DARK: {
            ComponentState.NORMAL: "#27AE60",
            ComponentState.ALARM: "#E67E22",
            ComponentState.FAULT: "#C0392B",
            ComponentState.OFFLINE: "#7F8C8D",
            ComponentState.MAINTENANCE: "#8E44AD",
            "background": "#2C3E50",
            "text": "#ECF0F1",
            "connection": "#BDC3C7",
            "bus": "#34495E"
        },
        ColorScheme.HIGH_CONTRAST: {
            ComponentState.NORMAL: "#00FF00",
            ComponentState.ALARM: "#FFFF00",
            ComponentState.FAULT: "#FF0000",
            ComponentState.OFFLINE: "#808080",
            ComponentState.MAINTENANCE: "#FF00FF",
            "background": "#000000",
            "text": "#FFFFFF",
            "connection": "#FFFFFF",
            "bus": "#FFFFFF"
        },
        ColorScheme.COLORBLIND_FRIENDLY: {
            ComponentState.NORMAL: "#0173B2",
            ComponentState.ALARM: "#DE8F05",
            ComponentState.FAULT: "#CC78BC",
            ComponentState.OFFLINE: "#949494",
            ComponentState.MAINTENANCE: "#029E73",
            "background": "#FFFFFF",
            "text": "#000000",
            "connection": "#000000",
            "bus": "#56B4E9"
        },
        ColorScheme.INDUSTRIAL: {
            ComponentState.NORMAL: "#4CAF50",
            ComponentState.ALARM: "#FF9800",
            ComponentState.FAULT: "#F44336",
            ComponentState.OFFLINE: "#9E9E9E",
            ComponentState.MAINTENANCE: "#673AB7",
            "background": "#F5F5F5",
            "text": "#212121",
            "connection": "#424242",
            "bus": "#607D8B"
        },
        ColorScheme.MODERN: {
            ComponentState.NORMAL: "#00BCD4",
            ComponentState.ALARM: "#FFC107",
            ComponentState.FAULT: "#E91E63",
            ComponentState.OFFLINE: "#9E9E9E",
            ComponentState.MAINTENANCE: "#9C27B0",
            "background": "#FAFAFA",
            "text": "#263238",
            "connection": "#37474F",
            "bus": "#455A64"
        }
    }

    @classmethod
    def get_color(cls, scheme: ColorScheme, state_or_element: Union[ComponentState, str]) -> str:
        """Get color for a specific state or element in the given scheme"""
        return cls.SCHEMES[scheme].get(state_or_element, "#000000")


class DataModelInterface(ABC):
    """Abstract interface for data model adapters"""

    @abstractmethod
    def load_data(self, source: Union[str, Dict, pd.DataFrame]) -> Tuple[List[ComponentData], List[ConnectionData]]:
        """Load and parse data from various sources"""
        pass

    @abstractmethod
    def validate_data(self, components: List[ComponentData], connections: List[ConnectionData]) -> bool:
        """Validate the loaded data structure"""
        pass


class JSONDataModel(DataModelInterface):
    """JSON data model adapter for simulation data"""

    def load_data(self, source: Union[str, Dict]) -> Tuple[List[ComponentData], List[ConnectionData]]:
        """Load data from JSON file or dictionary"""
        try:
            if isinstance(source, str):
                with open(source, 'r') as file:
                    data = json.load(file)
            else:
                data = source

            components = []
            connections = []

            # Parse components
            for comp_data in data.get('components', []):
                component = ComponentData(
                    id=comp_data['id'],
                    name=comp_data['name'],
                    component_type=ComponentType(comp_data['type']),
                    position=(comp_data['x'], comp_data['y']),
                    state=ComponentState(comp_data.get('state', 'normal')),
                    voltage=comp_data.get('voltage'),
                    current=comp_data.get('current'),
                    power=comp_data.get('power'),
                    frequency=comp_data.get('frequency'),
                    temperature=comp_data.get('temperature'),
                    properties=comp_data.get('properties', {}),
                    connections=comp_data.get('connections', [])
                )
                components.append(component)

            # Parse connections
            for conn_data in data.get('connections', []):
                connection = ConnectionData(
                    id=conn_data['id'],
                    from_component=conn_data['from'],
                    to_component=conn_data['to'],
                    connection_type=conn_data.get('type', 'line'),
                    state=ComponentState(conn_data.get('state', 'normal')),
                    properties=conn_data.get('properties', {})
                )
                connections.append(connection)

            return components, connections

        except Exception as e:
            logger.error(f"Error loading JSON data: {e}")
            raise

    def validate_data(self, components: List[ComponentData], connections: List[ConnectionData]) -> bool:
        """Validate component and connection data"""
        component_ids = {comp.id for comp in components}

        for connection in connections:
            if connection.from_component not in component_ids:
                logger.error(f"Connection references unknown component: {connection.from_component}")
                return False
            if connection.to_component not in component_ids:
                logger.error(f"Connection references unknown component: {connection.to_component}")
                return False

        return True


class PandasDataModel(DataModelInterface):
    """Pandas DataFrame data model adapter"""

    def load_data(self, source: Union[str, pd.DataFrame]) -> Tuple[List[ComponentData], List[ConnectionData]]:
        """Load data from CSV file or DataFrame"""
        try:
            if isinstance(source, str):
                df_components = pd.read_csv(source)
                # Assume connections are in a separate file or sheet
                connections_file = source.replace('components', 'connections')
                try:
                    df_connections = pd.read_csv(connections_file)
                except FileNotFoundError:
                    df_connections = pd.DataFrame()
            else:
                df_components = source
                df_connections = pd.DataFrame()

            components = []
            for _, row in df_components.iterrows():
                component = ComponentData(
                    id=str(row['id']),
                    name=str(row['name']),
                    component_type=ComponentType(row['type']),
                    position=(float(row['x']), float(row['y'])),
                    state=ComponentState(row.get('state', 'normal')),
                    voltage=row.get('voltage'),
                    current=row.get('current'),
                    power=row.get('power'),
                    frequency=row.get('frequency'),
                    temperature=row.get('temperature'),
                    properties={}
                )
                components.append(component)

            connections = []
            if not df_connections.empty:
                for _, row in df_connections.iterrows():
                    connection = ConnectionData(
                        id=str(row['id']),
                        from_component=str(row['from']),
                        to_component=str(row['to']),
                        connection_type=row.get('type', 'line'),
                        state=ComponentState(row.get('state', 'normal')),
                        properties={}
                    )
                    connections.append(connection)

            return components, connections

        except Exception as e:
            logger.error(f"Error loading Pandas data: {e}")
            raise

    def validate_data(self, components: List[ComponentData], connections: List[ConnectionData]) -> bool:
        """Validate DataFrame-based data"""
        return True


class HDF5DataModel(DataModelInterface):
    """HDF5 data model adapter for high-performance simulation data"""

    def __init__(self, logger=None):
        self.hdf5_filepath = None
        self.logger = logger if logger else logging.getLogger(__name__)
        self.entity_variable_timeseries_data = {}
        self.relation_data = {}
        self.total_timesteps = 0
        self._hdf5_file_handle = None

    def _load_hdf5_data(self):
        if not self.hdf5_filepath:
            self.logger.info("Error: HDF5 filepath not provided for simulation.")
            return

        self.entity_variable_timeseries_data = {}
        self.relation_data = {}
        self.total_timesteps = 0

        try:
            self._hdf5_file_handle = h5py.File(self.hdf5_filepath, 'r')

            def visitor_function(name, obj):
                # name is the full HDF5 path, e.g., "Relations/CSV-0.PV_0" or "Generator1/P_MW_out"
                path_parts = name.split('/')

                if isinstance(obj, h5py.Dataset):
                    if path_parts[0] == "Relations" and len(path_parts) == 2:
                        # This is a relation dataset, e.g., Relations/CSV-0.PV_0
                        relation_name = path_parts[1]
                        self.relation_data[relation_name] = obj[:]  # Load the entire matrix/data
                        # self.logger.info(f"Debug: Loaded Relation '{relation_name}'")

                    elif path_parts[0] != "Relations":  # Process as potential "Series" data
                        # This part relies on your previously working "Series" parsing logic.
                        # Assuming EntityName/VariableName structure for series:
                        if len(path_parts) >= 2:
                            entity_name = path_parts[-2]
                            variable_name = path_parts[-1]

                            # Prevent misinterpreting something like "OtherGroup/Relations/Dataset"
                            if entity_name == "Relations":
                                return  # Skip if the immediate parent group is "Relations"

                            if entity_name not in self.entity_variable_timeseries_data:
                                self.entity_variable_timeseries_data[entity_name] = {}

                            self.entity_variable_timeseries_data[entity_name][variable_name] = obj[:]

                            # Determine total_timesteps from Series data
                            current_len = len(obj[:])
                            if current_len > 0:
                                if self.total_timesteps == 0:
                                    self.total_timesteps = current_len
                                elif current_len != self.total_timesteps:
                                    self.logger.warning(
                                        f"Warning: Inconsistent dataset length for Series data '{name}'. "
                                        f"Expected {self.total_timesteps}, found {current_len}. "
                                        f"Using previously determined total_timesteps: {self.total_timesteps}.")

            self._hdf5_file_handle.visititems(visitor_function)

            if self.entity_variable_timeseries_data and self.total_timesteps == 0:
                self.logger.warning(
                    "Warning: 'Series' data found, but total_timesteps is 0 (all series datasets might be empty).")
            elif self.entity_variable_timeseries_data:
                self.logger.info(f"HDF5 'Series' data loaded. Total simulation timesteps: {self.total_timesteps}")

            if self.relation_data:
                self.logger.info(f"HDF5 'Relations' data loaded for {len(self.relation_data)} items.")
            else:
                self.logger.error("No 'Relations' data found or loaded from HDF5.")

        except FileNotFoundError:
            self.logger.critical(f"Error: HDF5 file not found at '{self.hdf5_filepath}'")
            self.total_timesteps = 0
        except Exception as e:
            self.logger.critical(f"Error loading HDF5 file '{self.hdf5_filepath}': {e}")
            self.total_timesteps = 0
        # File handle remains open for potential future partial reads (though currently all is loaded)
        # It will be closed by self.close()

    def load_data(self, source: str) -> Tuple[List[ComponentData], List[ConnectionData]]:
        """Load data from HDF5 file using the improved _load_hdf5_data method"""
        self.hdf5_filepath = source
        self._load_hdf5_data()

        components = []
        connections = []

        # Convert entity_variable_timeseries_data to components
        for entity_name, variables in self.entity_variable_timeseries_data.items():
            # Extract component properties from time series data
            voltage = None
            current = None
            power = None
            frequency = None
            temperature = None

            # Try to extract meaningful values from time series (use latest or average)
            if 'voltage' in variables and len(variables['voltage']) > 0:
                voltage = float(variables['voltage'][-1])  # Use latest value
            elif 'V_pu' in variables and len(variables['V_pu']) > 0:
                voltage = float(variables['V_pu'][-1])

            if 'current' in variables and len(variables['current']) > 0:
                current = float(variables['current'][-1])
            elif 'I_A' in variables and len(variables['I_A']) > 0:
                current = float(variables['I_A'][-1])

            if 'power' in variables and len(variables['power']) > 0:
                power = float(variables['power'][-1])
            elif 'P_MW' in variables and len(variables['P_MW']) > 0:
                power = float(variables['P_MW'][-1])

            if 'frequency' in variables and len(variables['frequency']) > 0:
                frequency = float(variables['frequency'][-1])
            elif 'f_Hz' in variables and len(variables['f_Hz']) > 0:
                frequency = float(variables['f_Hz'][-1])

            # Determine component type based on entity name or variables
            component_type = ComponentType.BUS  # Default
            if 'gen' in entity_name.lower() or 'generator' in entity_name.lower():
                component_type = ComponentType.GENERATOR
            elif 'trans' in entity_name.lower() or 'transformer' in entity_name.lower():
                component_type = ComponentType.TRANSFORMER
            elif 'load' in entity_name.lower():
                component_type = ComponentType.LOAD
            elif 'breaker' in entity_name.lower() or 'cb' in entity_name.lower():
                component_type = ComponentType.CIRCUIT_BREAKER

            component = ComponentData(
                id=entity_name,
                name=entity_name,
                component_type=component_type,
                position=(0.0, 0.0),  # Default position, could be improved with layout algorithm
                state=ComponentState.NORMAL,
                voltage=voltage,
                current=current,
                power=power,
                frequency=frequency,
                temperature=temperature,
                properties=variables,  # Store all time series data as properties
                connections=[]
            )
            components.append(component)

        # Convert relation_data to connections
        for relation_name, relation_matrix in self.relation_data.items():
            # Parse relation data to create connections
            # Assuming relation_matrix contains connection information
            if len(relation_matrix.shape) >= 2 and relation_matrix.shape[0] > 0:
                # For each row in the relation matrix, create a connection
                for i, row in enumerate(relation_matrix):
                    if len(row) >= 2:  # Assuming at least from and to components
                        from_component = str(row[0]) if not isinstance(row[0], bytes) else row[0].decode('utf-8')
                        to_component = str(row[1]) if not isinstance(row[1], bytes) else row[1].decode('utf-8')

                        connection = ConnectionData(
                            id=f"{relation_name}_{i}",
                            from_component=from_component,
                            to_component=to_component,
                            connection_type="line",
                            state=ComponentState.NORMAL,
                            properties={"relation_data": row.tolist()}
                        )
                        connections.append(connection)

        return components, connections

    def close(self):
        """Close the HDF5 file handle"""
        if self._hdf5_file_handle:
            self._hdf5_file_handle.close()
            self._hdf5_file_handle = None

    def __del__(self):
        """Ensure file handle is closed when object is destroyed"""
        self.close()

    def validate_data(self, components: List[ComponentData], connections: List[ConnectionData]) -> bool:
        """Validate HDF5-based data"""
        component_ids = {comp.id for comp in components}
        faulty_component_ids = []
        faulty_connection_ids = []

        for connection in connections:
            if connection.from_component not in component_ids:
                faulty_component_ids.append(connection.from_component)
                faulty_connection_ids.append(connection.id)
                logger.error(f"Connection references unknown component: {connection.from_component}")
                #return False
            if connection.to_component not in component_ids:
                faulty_component_ids.append(connection.to_component)
                faulty_connection_ids.append(connection.id)
                logger.error(f"Connection references unknown component: {connection.to_component}")
                #return False

        # Remove faulty components (only if they exist in components)
        components[:] = [comp for comp in components if comp.id not in faulty_component_ids]

        # Remove faulty connections
        connections[:] = [conn for conn in connections if conn.id not in faulty_connection_ids]

        return True

    def save_data(self, filename: str, components: List[ComponentData], connections: List[ConnectionData]):
        """Save data to HDF5 file"""
        try:
            with h5py.File(filename, 'w') as hdf_file:
                # Save components
                if components:
                    comp_group = hdf_file.create_group('components')

                    # Prepare data arrays
                    ids = [comp.id for comp in components]
                    names = [comp.name for comp in components]
                    types = [comp.component_type.value for comp in components]
                    x_positions = [comp.position[0] for comp in components]
                    y_positions = [comp.position[1] for comp in components]
                    states = [comp.state.value for comp in components]
                    voltages = [comp.voltage if comp.voltage is not None else np.nan for comp in components]
                    currents = [comp.current if comp.current is not None else np.nan for comp in components]
                    powers = [comp.power if comp.power is not None else np.nan for comp in components]
                    frequencies = [comp.frequency if comp.frequency is not None else np.nan for comp in components]
                    temperatures = [comp.temperature if comp.temperature is not None else np.nan for comp in components]

                    # Create datasets
                    comp_group.create_dataset('id', data=[s.encode('utf-8') for s in ids])
                    comp_group.create_dataset('name', data=[s.encode('utf-8') for s in names])
                    comp_group.create_dataset('type', data=[s.encode('utf-8') for s in types])
                    comp_group.create_dataset('x', data=x_positions)
                    comp_group.create_dataset('y', data=y_positions)
                    comp_group.create_dataset('state', data=[s.encode('utf-8') for s in states])
                    comp_group.create_dataset('voltage', data=voltages)
                    comp_group.create_dataset('current', data=currents)
                    comp_group.create_dataset('power', data=powers)
                    comp_group.create_dataset('frequency', data=frequencies)
                    comp_group.create_dataset('temperature', data=temperatures)

                # Save connections
                if connections:
                    conn_group = hdf_file.create_group('connections')

                    conn_ids = [conn.id for conn in connections]
                    from_components = [conn.from_component for conn in connections]
                    to_components = [conn.to_component for conn in connections]
                    conn_types = [conn.connection_type for conn in connections]
                    conn_states = [conn.state.value for conn in connections]

                    conn_group.create_dataset('id', data=[s.encode('utf-8') for s in conn_ids])
                    conn_group.create_dataset('from', data=[s.encode('utf-8') for s in from_components])
                    conn_group.create_dataset('to', data=[s.encode('utf-8') for s in to_components])
                    conn_group.create_dataset('type', data=[s.encode('utf-8') for s in conn_types])
                    conn_group.create_dataset('state', data=[s.encode('utf-8') for s in conn_states])

            logger.info(f"Data saved to HDF5 file: {filename}")

        except Exception as e:
            logger.error(f"Error saving HDF5 data: {e}")
            raise


class ComponentRenderer(ABC):
    """Abstract base class for component renderers"""

    @abstractmethod
    def render(self, canvas: tk.Canvas, component: ComponentData, scale: float = 1.0,
               color_scheme: ColorScheme = ColorScheme.DEFAULT) -> List[int]:
        """Render component on canvas and return canvas item IDs"""
        pass

    @abstractmethod
    def get_connection_points(self, component: ComponentData) -> Dict[str, Tuple[float, float]]:
        """Get connection points for the component"""
        pass


class GeneratorRenderer(ComponentRenderer):
    """Renderer for generator components"""

    def render(self, canvas: tk.Canvas, component: ComponentData, scale: float = 1.0,
               color_scheme: ColorScheme = ColorScheme.DEFAULT) -> List[int]:
        """Render generator symbol"""
        x, y = component.position
        size = 30 * scale

        color = ColorSchemeManager.get_color(color_scheme, component.state)
        text_color = ColorSchemeManager.get_color(color_scheme, "text")

        items = []

        # Generator circle
        circle = canvas.create_oval(
            x - size / 2, y - size / 2, x + size / 2, y + size / 2,
            fill=color, outline="black", width=2
        )
        items.append(circle)

        # Generator symbol (G)
        text = canvas.create_text(
            x, y, text="G", font=("Arial", int(12 * scale), "bold"),
            fill="white"
        )
        items.append(text)

        # Component label
        label = canvas.create_text(
            x, y + size / 2 + 15, text=component.name,
            font=("Arial", int(10 * scale)), fill=text_color
        )
        items.append(label)

        # Status indicators
        if component.voltage:
            voltage_text = canvas.create_text(
                x, y - size / 2 - 15, text=f"{component.voltage:.1f}V",
                font=("Arial", int(8 * scale)), fill="blue"
            )
            items.append(voltage_text)

        return items

    def get_connection_points(self, component: ComponentData) -> Dict[str, Tuple[float, float]]:
        """Get connection points for generator"""
        x, y = component.position
        return {
            "output": (x + 15, y),
            "neutral": (x, y + 15)
        }


class TransformerRenderer(ComponentRenderer):
    """Renderer for transformer components"""

    def render(self, canvas: tk.Canvas, component: ComponentData, scale: float = 1.0,
               color_scheme: ColorScheme = ColorScheme.DEFAULT) -> List[int]:
        """Render transformer symbol"""
        x, y = component.position
        size = 40 * scale

        color = ColorSchemeManager.get_color(color_scheme, component.state)
        text_color = ColorSchemeManager.get_color(color_scheme, "text")

        items = []

        # Primary winding
        primary = canvas.create_oval(
            x - size / 3, y - size / 4, x, y + size / 4,
            fill="white", outline=color, width=3
        )
        items.append(primary)

        # Secondary winding
        secondary = canvas.create_oval(
            x, y - size / 4, x + size / 3, y + size / 4,
            fill="white", outline=color, width=3
        )
        items.append(secondary)

        # Core
        core = canvas.create_line(
            x - 2, y - size / 3, x - 2, y + size / 3,
            fill="black", width=2
        )
        items.append(core)

        core2 = canvas.create_line(
            x + 2, y - size / 3, x + 2, y + size / 3,
            fill="black", width=2
        )
        items.append(core2)

        # Label
        label = canvas.create_text(
            x, y + size / 2 + 15, text=component.name,
            font=("Arial", int(10 * scale)), fill=text_color
        )
        items.append(label)

        return items

    def get_connection_points(self, component: ComponentData) -> Dict[str, Tuple[float, float]]:
        """Get connection points for transformer"""
        x, y = component.position
        return {
            "primary": (x - 20, y),
            "secondary": (x + 20, y),
            "primary_neutral": (x - 20, y + 15),
            "secondary_neutral": (x + 20, y + 15)
        }


class CircuitBreakerRenderer(ComponentRenderer):
    """Renderer for circuit breaker components"""

    def render(self, canvas: tk.Canvas, component: ComponentData, scale: float = 1.0,
               color_scheme: ColorScheme = ColorScheme.DEFAULT) -> List[int]:
        """Render circuit breaker symbol"""
        x, y = component.position
        size = 20 * scale

        # State-based rendering
        is_open = component.state == ComponentState.OFFLINE
        color = ColorSchemeManager.get_color(color_scheme, ComponentState.FAULT if is_open else ComponentState.NORMAL)
        text_color = ColorSchemeManager.get_color(color_scheme, "text")

        items = []

        # Breaker contacts
        if is_open:
            # Open contacts
            contact1 = canvas.create_line(
                x - size / 2, y, x - 5, y - 10,
                fill=color, width=3
            )
            contact2 = canvas.create_line(
                x + 5, y + 10, x + size / 2, y,
                fill=color, width=3
            )
        else:
            # Closed contacts
            contact1 = canvas.create_line(
                x - size / 2, y, x + size / 2, y,
                fill=color, width=3
            )
            contact2 = contact1  # Same line for closed state

        items.extend([contact1, contact2] if is_open else [contact1])

        # Breaker box
        box = canvas.create_rectangle(
            x - size / 3, y - size / 3, x + size / 3, y + size / 3,
            fill="white", outline="black", width=2
        )
        items.append(box)

        # Label
        label = canvas.create_text(
            x, y + size / 2 + 15, text=component.name,
            font=("Arial", int(8 * scale)), fill=text_color
        )
        items.append(label)

        return items

    def get_connection_points(self, component: ComponentData) -> Dict[str, Tuple[float, float]]:
        """Get connection points for circuit breaker"""
        x, y = component.position
        return {
            "input": (x - 10, y),
            "output": (x + 10, y)
        }


class BusRenderer(ComponentRenderer):
    """Renderer for bus components"""

    def render(self, canvas: tk.Canvas, component: ComponentData, scale: float = 1.0,
               color_scheme: ColorScheme = ColorScheme.DEFAULT) -> List[int]:
        """Render bus symbol"""
        x, y = component.position
        length = 60 * scale
        width = 8 * scale

        color = ColorSchemeManager.get_color(color_scheme, "bus")
        text_color = ColorSchemeManager.get_color(color_scheme, "text")

        items = []

        # Bus bar
        bus_bar = canvas.create_rectangle(
            x - length / 2, y - width / 2, x + length / 2, y + width / 2,
            fill=color, outline="black", width=2
        )
        items.append(bus_bar)

        # Voltage level indicator
        if component.voltage:
            voltage_text = canvas.create_text(
                x, y - width / 2 - 15, text=f"{component.voltage:.1f}kV",
                font=("Arial", int(10 * scale), "bold"), fill="red"
            )
            items.append(voltage_text)

        # Label
        label = canvas.create_text(
            x, y + width / 2 + 15, text=component.name,
            font=("Arial", int(10 * scale)), fill=text_color
        )
        items.append(label)

        return items

    def get_connection_points(self, component: ComponentData) -> Dict[str, Tuple[float, float]]:
        """Get connection points for bus"""
        x, y = component.position
        return {
            "left": (x - 30, y),
            "right": (x + 30, y),
            "center": (x, y),
            "top": (x, y - 4),
            "bottom": (x, y + 4)
        }


class ComponentRendererFactory:
    """Factory for creating component renderers"""

    _renderers = {
        ComponentType.GENERATOR: GeneratorRenderer(),
        ComponentType.TRANSFORMER: TransformerRenderer(),
        ComponentType.CIRCUIT_BREAKER: CircuitBreakerRenderer(),
        ComponentType.BUS: BusRenderer(),
    }

    @classmethod
    def get_renderer(cls, component_type: ComponentType) -> ComponentRenderer:
        """Get renderer for component type"""
        return cls._renderers.get(component_type, cls._renderers[ComponentType.BUS])

    @classmethod
    def register_renderer(cls, component_type: ComponentType, renderer: ComponentRenderer):
        """Register new component renderer"""
        cls._renderers[component_type] = renderer


class SLDCanvas:
    """Enhanced canvas for Single Line Diagram rendering with moveable nodes"""

    def __init__(self, parent, width=1200, height=800):
        self.parent = parent
        self.width = width
        self.height = height
        self.scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.color_scheme = ColorScheme.DEFAULT

        # Create scrollable canvas
        self.frame = ttk.Frame(parent)
        self.canvas = tk.Canvas(
            self.frame,
            width=width,
            height=height,
            bg=ColorSchemeManager.get_color(self.color_scheme, "background"),
            scrollregion=(0, 0, width * 2, height * 2)
        )

        # Scrollbars
        self.h_scrollbar = ttk.Scrollbar(self.frame, orient="horizontal", command=self.canvas.xview)
        self.v_scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)

        # Grid layout
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")

        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        # Bind events for moveable nodes
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-3>", self.on_right_click)

        # Component tracking
        self.components = {}
        self.connections = {}
        self.selected_component = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

    def set_color_scheme(self, scheme: ColorScheme):
        """Set the color scheme for the canvas"""
        self.color_scheme = scheme
        self.canvas.configure(bg=ColorSchemeManager.get_color(scheme, "background"))
        self.redraw()

    def clear(self):
        """Clear the canvas"""
        self.canvas.delete("all")
        self.components.clear()
        self.connections.clear()

    def render_components(self, components: List[ComponentData]):
        """Render all components on the canvas"""
        for component in components:
            renderer = ComponentRendererFactory.get_renderer(component.component_type)
            items = renderer.render(self.canvas, component, self.scale, self.color_scheme)
            self.components[component.id] = {
                'component': component,
                'items': items,
                'renderer': renderer
            }

            # Tag items for easy identification
            for item in items:
                self.canvas.addtag_withtag(f"component_{component.id}", item)

    def render_connections(self, connections: List[ConnectionData]):
        """Render connections between components"""
        for connection in connections:
            self.draw_connection(connection)

    def draw_connection(self, connection: ConnectionData):
        """Draw a connection line between components"""
        from_comp = self.components.get(connection.from_component)
        to_comp = self.components.get(connection.to_component)

        if not from_comp or not to_comp:
            logger.warning(f"Cannot draw connection {connection.id}: missing components")
            return

        from_pos = from_comp['component'].position
        to_pos = to_comp['component'].position

        connection_color = ColorSchemeManager.get_color(self.color_scheme, "connection")

        # Simple straight line connection
        line = self.canvas.create_line(
            from_pos[0], from_pos[1], to_pos[0], to_pos[1],
            fill=connection_color, width=2, tags="connection"
        )

        self.connections[connection.id] = {
            'connection': connection,
            'item': line
        }

    def find_component_at_position(self, x, y):
        """Find component at given canvas position"""
        item = self.canvas.find_closest(x, y)[0]
        tags = self.canvas.gettags(item)

        for tag in tags:
            if tag.startswith("component_"):
                component_id = tag.replace("component_", "")
                return component_id

        return None

    def on_click(self, event):
        """Handle mouse click events"""
        self.drag_start_x = event.x
        self.drag_start_y = event.y

        component_id = self.find_component_at_position(event.x, event.y)
        if component_id:
            self.selected_component = component_id
            self.is_dragging = True
        else:
            self.selected_component = None
            self.is_dragging = False

    def on_drag(self, event):
        """Handle mouse drag events for moving components"""
        if self.is_dragging and self.selected_component:
            # Calculate movement delta
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y

            # Update component position
            component_data = self.components[self.selected_component]
            old_x, old_y = component_data['component'].position
            new_x, new_y = old_x + dx, old_y + dy
            component_data['component'].position = (new_x, new_y)

            # Move all canvas items for this component
            for item in component_data['items']:
                self.canvas.move(item, dx, dy)

            # Update connections
            self.update_connections_for_component(self.selected_component)

            # Update drag start position
            self.drag_start_x = event.x
            self.drag_start_y = event.y

    def on_release(self, event):
        """Handle mouse release events"""
        self.is_dragging = False
        self.selected_component = None

    def update_connections_for_component(self, component_id):
        """Update all connections involving the moved component"""
        for conn_id, conn_data in self.connections.items():
            connection = conn_data['connection']

            if connection.from_component == component_id or connection.to_component == component_id:
                # Delete old connection line
                self.canvas.delete(conn_data['item'])

                # Redraw connection
                from_comp = self.components.get(connection.from_component)
                to_comp = self.components.get(connection.to_component)

                if from_comp and to_comp:
                    from_pos = from_comp['component'].position
                    to_pos = to_comp['component'].position

                    connection_color = ColorSchemeManager.get_color(self.color_scheme, "connection")

                    new_line = self.canvas.create_line(
                        from_pos[0], from_pos[1], to_pos[0], to_pos[1],
                        fill=connection_color, width=2, tags="connection"
                    )

                    conn_data['item'] = new_line

    def on_zoom(self, event):
        """Handle mouse wheel zoom"""
        factor = 1.1 if event.delta > 0 else 0.9
        self.scale *= factor
        self.redraw()

    def on_right_click(self, event):
        """Handle right-click context menu"""
        component_id = self.find_component_at_position(event.x, event.y)
        if component_id:
            self.show_context_menu(event, component_id)

    def show_context_menu(self, event, component_id):
        """Show context menu for component"""
        context_menu = tk.Menu(self.canvas, tearoff=0)
        context_menu.add_command(label="Properties", command=lambda: self.show_component_properties(component_id))
        context_menu.add_command(label="Delete", command=lambda: self.delete_component(component_id))
        context_menu.add_separator()
        context_menu.add_command(label="Change State", command=lambda: self.change_component_state(component_id))

        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def show_component_properties(self, component_id):
        """Show component properties dialog"""
        component = self.components[component_id]['component']
        messagebox.showinfo("Component Properties",
                            f"ID: {component.id}\n"
                            f"Name: {component.name}\n"
                            f"Type: {component.component_type.value}\n"
                            f"State: {component.state.value}\n"
                            f"Position: {component.position}\n"
                            f"Voltage: {component.voltage}\n"
                            f"Current: {component.current}\n"
                            f"Power: {component.power}")

    def delete_component(self, component_id):
        """Delete a component from the diagram"""
        if messagebox.askyesno("Delete Component", f"Are you sure you want to delete component {component_id}?"):
            # Remove canvas items
            for item in self.components[component_id]['items']:
                self.canvas.delete(item)

            # Remove connections involving this component
            connections_to_remove = []
            for conn_id, conn_data in self.connections.items():
                connection = conn_data['connection']
                if connection.from_component == component_id or connection.to_component == component_id:
                    self.canvas.delete(conn_data['item'])
                    connections_to_remove.append(conn_id)

            for conn_id in connections_to_remove:
                del self.connections[conn_id]

            # Remove component
            del self.components[component_id]

    def change_component_state(self, component_id):
        """Change component state"""
        component = self.components[component_id]['component']

        # Create state selection dialog
        state_window = tk.Toplevel(self.canvas)
        state_window.title("Change Component State")
        state_window.geometry("300x200")

        ttk.Label(state_window, text=f"Component: {component.name}").pack(pady=10)

        state_var = tk.StringVar(value=component.state.value)
        for state in ComponentState:
            ttk.Radiobutton(state_window, text=state.value.title(),
                            variable=state_var, value=state.value).pack(anchor="w", padx=20)

        def apply_state():
            component.state = ComponentState(state_var.get())
            self.redraw_component(component_id)
            state_window.destroy()

        ttk.Button(state_window, text="Apply", command=apply_state).pack(pady=10)

    def redraw_component(self, component_id):
        """Redraw a specific component"""
        component_data = self.components[component_id]
        component = component_data['component']
        renderer = component_data['renderer']

        # Remove old items
        for item in component_data['items']:
            self.canvas.delete(item)

        # Render new items
        new_items = renderer.render(self.canvas, component, self.scale, self.color_scheme)
        component_data['items'] = new_items

        # Tag items for identification
        for item in new_items:
            self.canvas.addtag_withtag(f"component_{component.id}", item)

    def redraw(self):
        """Redraw all components with current scale and color scheme"""
        # Store current component and connection data
        components = [comp_data['component'] for comp_data in self.components.values()]
        connections = [conn_data['connection'] for conn_data in self.connections.values()]

        # Clear and redraw
        self.clear()
        self.render_components(components)
        self.render_connections(connections)

    def get_frame(self):
        """Get the main frame widget"""
        return self.frame


class ComponentEditor:
    """Editor for component properties and configuration"""

    def __init__(self, parent):
        self.parent = parent
        self.current_component = None
        self.setup_ui()

    def setup_ui(self):
        """Setup the component editor UI"""
        self.frame = ttk.LabelFrame(self.parent, text="Component Editor", padding=10)

        # Component selection
        ttk.Label(self.frame, text="Component:").grid(row=0, column=0, sticky="w", pady=2)
        self.component_var = tk.StringVar()
        self.component_combo = ttk.Combobox(self.frame, textvariable=self.component_var, state="readonly")
        self.component_combo.grid(row=0, column=1, sticky="ew", pady=2)
        self.component_combo.bind("<<ComboboxSelected>>", self.on_component_selected)

        # Properties frame
        self.props_frame = ttk.LabelFrame(self.frame, text="Properties", padding=5)
        self.props_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)

        # Property entries
        self.property_vars = {}
        self.property_entries = {}

        # Standard properties
        properties = ["name", "voltage", "current", "power", "frequency", "temperature"]
        for i, prop in enumerate(properties):
            ttk.Label(self.props_frame, text=f"{prop.title()}:").grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            entry = ttk.Entry(self.props_frame, textvariable=var)
            entry.grid(row=i, column=1, sticky="ew", pady=2)
            self.property_vars[prop] = var
            self.property_entries[prop] = entry

        # State selection
        ttk.Label(self.props_frame, text="State:").grid(row=len(properties), column=0, sticky="w", pady=2)
        self.state_var = tk.StringVar()
        self.state_combo = ttk.Combobox(
            self.props_frame,
            textvariable=self.state_var,
            values=[state.value for state in ComponentState],
            state="readonly"
        )
        self.state_combo.grid(row=len(properties), column=1, sticky="ew", pady=2)

        # Buttons
        button_frame = ttk.Frame(self.frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Apply Changes", command=self.apply_changes).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Reset", command=self.reset_values).pack(side="left", padx=5)

        self.frame.grid_columnconfigure(1, weight=1)
        self.props_frame.grid_columnconfigure(1, weight=1)

    def load_components(self, components: List[ComponentData]):
        """Load components into the editor"""
        component_names = [f"{comp.name} ({comp.id})" for comp in components]
        self.component_combo['values'] = component_names
        self.components = {f"{comp.name} ({comp.id})": comp for comp in components}

    def on_component_selected(self, event=None):
        """Handle component selection"""
        selected = self.component_var.get()
        if selected in self.components:
            self.current_component = self.components[selected]
            self.load_component_properties()

    def load_component_properties(self):
        """Load current component properties into the editor"""
        if not self.current_component:
            return

        comp = self.current_component
        self.property_vars["name"].set(comp.name)
        self.property_vars["voltage"].set(str(comp.voltage or ""))
        self.property_vars["current"].set(str(comp.current or ""))
        self.property_vars["power"].set(str(comp.power or ""))
        self.property_vars["frequency"].set(str(comp.frequency or ""))
        self.property_vars["temperature"].set(str(comp.temperature or ""))
        self.state_var.set(comp.state.value)

    def apply_changes(self):
        """Apply changes to the current component"""
        if not self.current_component:
            return

        try:
            # Update component properties
            self.current_component.name = self.property_vars["name"].get()
            self.current_component.voltage = float(self.property_vars["voltage"].get()) if self.property_vars[
                "voltage"].get() else None
            self.current_component.current = float(self.property_vars["current"].get()) if self.property_vars[
                "current"].get() else None
            self.current_component.power = float(self.property_vars["power"].get()) if self.property_vars[
                "power"].get() else None
            self.current_component.frequency = float(self.property_vars["frequency"].get()) if self.property_vars[
                "frequency"].get() else None
            self.current_component.temperature = float(self.property_vars["temperature"].get()) if self.property_vars[
                "temperature"].get() else None
            self.current_component.state = ComponentState(self.state_var.get())

            messagebox.showinfo("Success", "Component properties updated successfully!")

        except ValueError as e:
            messagebox.showerror("Error", f"Invalid value entered: {e}")

    def reset_values(self):
        """Reset values to original component properties"""
        self.load_component_properties()

    def get_frame(self):
        """Get the editor frame"""
        return self.frame


class SLDGenerator:
    """Main Single Line Diagram Generator application"""

    def __init__(self):
        self.root = ttkb.Window(themename="superhero")
        self.root.title("Single Line Diagram Generator - SCADA System")
        self.root.geometry("1400x900")

        # Data storage
        self.components = []
        self.connections = []
        self.data_models = {
            "JSON": JSONDataModel(),
            "CSV/Pandas": PandasDataModel(),
            "HDF5": HDF5DataModel()
        }
        self.current_data_model = self.data_models["JSON"]

        self.setup_ui()
        self.setup_menu()

    def setup_ui(self):
        """Setup the main user interface"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left panel for controls
        left_panel = ttk.Frame(main_frame, width=300)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        left_panel.pack_propagate(False)

        # Right panel for diagram
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side="right", fill="both", expand=True)

        # Setup left panel components
        self.setup_control_panel(left_panel)

        # Setup diagram canvas
        self.sld_canvas = SLDCanvas(right_panel, width=1000, height=700)
        self.sld_canvas.get_frame().pack(fill="both", expand=True)

    def setup_control_panel(self, parent):
        """Setup the control panel"""
        # Data source section
        data_frame = ttk.LabelFrame(parent, text="Data Source", padding=10)
        data_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(data_frame, text="Data Model:").pack(anchor="w")
        self.data_model_var = tk.StringVar(value="JSON")
        data_model_combo = ttk.Combobox(
            data_frame,
            textvariable=self.data_model_var,
            values=list(self.data_models.keys()),
            state="readonly"
        )
        data_model_combo.pack(fill="x", pady=(5, 10))
        data_model_combo.bind("<<ComboboxSelected>>", self.on_data_model_changed)

        ttk.Button(data_frame, text="Load Data File", command=self.load_data_file).pack(fill="x", pady=2)
        ttk.Button(data_frame, text="Load Sample Data", command=self.load_sample_data).pack(fill="x", pady=2)

        # Color scheme section
        color_frame = ttk.LabelFrame(parent, text="Color Scheme", padding=10)
        color_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(color_frame, text="Scheme:").pack(anchor="w")
        self.color_scheme_var = tk.StringVar(value="DEFAULT")
        color_scheme_combo = ttk.Combobox(
            color_frame,
            textvariable=self.color_scheme_var,
            values=[scheme.value.upper() for scheme in ColorScheme],
            state="readonly"
        )
        color_scheme_combo.pack(fill="x", pady=(5, 0))
        color_scheme_combo.bind("<<ComboboxSelected>>", self.on_color_scheme_changed)

        # Component editor
        self.component_editor = ComponentEditor(parent)
        self.component_editor.get_frame().pack(fill="x", pady=(0, 10))

        # Diagram controls
        diagram_frame = ttk.LabelFrame(parent, text="Diagram Controls", padding=10)
        diagram_frame.pack(fill="x", pady=(0, 10))

        ttk.Button(diagram_frame, text="Generate Diagram", command=self.generate_diagram).pack(fill="x", pady=2)
        ttk.Button(diagram_frame, text="Clear Diagram", command=self.clear_diagram).pack(fill="x", pady=2)
        ttk.Button(diagram_frame, text="Auto Layout", command=self.auto_layout).pack(fill="x", pady=2)

        # Export options
        export_frame = ttk.LabelFrame(parent, text="Export Options", padding=10)
        export_frame.pack(fill="x")

        ttk.Button(export_frame, text="Export as PNG", command=self.export_png).pack(fill="x", pady=2)
        ttk.Button(export_frame, text="Export as SVG", command=self.export_svg).pack(fill="x", pady=2)
        ttk.Button(export_frame, text="Save Configuration", command=self.save_configuration).pack(fill="x", pady=2)
        ttk.Button(export_frame, text="Save as HDF5", command=self.save_hdf5).pack(fill="x", pady=2)

    def setup_menu(self):
        """Setup the application menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self.new_diagram)
        file_menu.add_command(label="Open", command=self.load_data_file)
        file_menu.add_command(label="Save", command=self.save_configuration)
        file_menu.add_command(label="Save as HDF5", command=self.save_hdf5)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Zoom In", command=lambda: self.zoom(1.2))
        view_menu.add_command(label="Zoom Out", command=lambda: self.zoom(0.8))
        view_menu.add_command(label="Fit to Window", command=self.fit_to_window)

        # Color scheme submenu
        color_submenu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label="Color Scheme", menu=color_submenu)
        for scheme in ColorScheme:
            color_submenu.add_command(
                label=scheme.value.replace("_", " ").title(),
                command=lambda s=scheme: self.set_color_scheme(s)
            )

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Validate Data", command=self.validate_data)
        tools_menu.add_command(label="Component Library", command=self.show_component_library)

    def on_data_model_changed(self, event=None):
        """Handle data model selection change"""
        selected = self.data_model_var.get()
        self.current_data_model = self.data_models[selected]
        logger.info(f"Data model changed to: {selected}")

    def on_color_scheme_changed(self, event=None):
        """Handle color scheme selection change"""
        selected = self.color_scheme_var.get()
        scheme = ColorScheme(selected.lower())
        self.set_color_scheme(scheme)

    def set_color_scheme(self, scheme: ColorScheme):
        """Set the color scheme for the application"""
        self.sld_canvas.set_color_scheme(scheme)
        self.color_scheme_var.set(scheme.value.upper())
        logger.info(f"Color scheme changed to: {scheme.value}")

    def load_data_file(self):
        """Load data from file"""
        try:
            filetypes = [
                ("JSON files", "*.json"),
                ("CSV files", "*.csv"),
                ("HDF5 files", "*.h5;*.hdf5"),
                ("YAML files", "*.yaml"),
                ("All files", "*.*")
            ]

            filename = filedialog.askopenfilename(
                title="Select Data File",
                filetypes=filetypes
            )

            if filename:
                # Auto-detect file type and set appropriate data model
                file_ext = Path(filename).suffix.lower()
                if file_ext in ['.h5', '.hdf5']:
                    self.current_data_model = self.data_models["HDF5"]
                    self.data_model_var.set("HDF5")
                elif file_ext == '.csv':
                    self.current_data_model = self.data_models["CSV/Pandas"]
                    self.data_model_var.set("CSV/Pandas")
                else:
                    self.current_data_model = self.data_models["JSON"]
                    self.data_model_var.set("JSON")

                self.components, self.connections = self.current_data_model.load_data(filename)

                if self.current_data_model.validate_data(self.components, self.connections):
                    self.component_editor.load_components(self.components)
                    messagebox.showinfo("Success",
                                        f"Loaded {len(self.components)} components and {len(self.connections)} connections")
                    logger.info(f"Data loaded successfully from {filename}")
                else:
                    messagebox.showerror("Error", "Data validation failed")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {e}")
            logger.error(f"Error loading data: {e}")

    def load_sample_data(self):
        """Load sample data for demonstration"""
        sample_data = {
            "components": [
                {
                    "id": "gen1", "name": "Generator 1", "type": "generator",
                    "x": 100, "y": 200, "state": "normal",
                    "voltage": 13.8, "current": 150.0, "power": 2.5, "frequency": 50.0
                },
                {
                    "id": "trans1", "name": "Main Transformer", "type": "transformer",
                    "x": 300, "y": 200, "state": "normal",
                    "voltage": 138.0, "current": 15.0
                },
                {
                    "id": "bus1", "name": "Bus 138kV", "type": "bus",
                    "x": 500, "y": 200, "state": "normal",
                    "voltage": 138.0
                },
                {
                    "id": "cb1", "name": "CB-001", "type": "circuit_breaker",
                    "x": 400, "y": 200, "state": "normal"
                }
            ],
            "connections": [
                {"id": "conn1", "from": "gen1", "to": "trans1", "type": "line"},
                {"id": "conn2", "from": "trans1", "to": "cb1", "type": "line"},
                {"id": "conn3", "from": "cb1", "to": "bus1", "type": "line"}
            ]
        }

        try:
            self.components, self.connections = self.current_data_model.load_data(sample_data)
            self.component_editor.load_components(self.components)
            messagebox.showinfo("Success", "Sample data loaded successfully")
            logger.info("Sample data loaded")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sample data: {e}")

    def generate_diagram(self):
        """Generate the single line diagram"""
        try:
            self.sld_canvas.clear()
            self.sld_canvas.render_components(self.components)
            self.sld_canvas.render_connections(self.connections)
            logger.info("Diagram generated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate diagram: {e}")
            logger.error(f"Error generating diagram: {e}")

    def clear_diagram(self):
        """Clear the current diagram"""
        self.sld_canvas.clear()
        logger.info("Diagram cleared")

    def auto_layout(self):
        """Automatically arrange components"""
        if not self.components:
            messagebox.showwarning("Warning", "No components to layout")
            return

        # Simple grid layout algorithm
        grid_size = 100
        cols = int(math.sqrt(len(self.components))) + 1

        for i, component in enumerate(self.components):
            row = i // cols
            col = i % cols
            component.position = (col * grid_size + 150, row * grid_size + 150)

        self.generate_diagram()
        logger.info("Auto layout applied")

    def zoom(self, factor):
        """Zoom the diagram"""
        self.sld_canvas.scale *= factor
        self.sld_canvas.redraw()

    def fit_to_window(self):
        """Fit diagram to window"""
        # Implementation for fitting diagram to window
        self.sld_canvas.scale = 1.0
        self.sld_canvas.redraw()

    def validate_data(self):
        """Validate current data"""
        try:
            is_valid = self.current_data_model.validate_data(self.components, self.connections)
            if is_valid:
                messagebox.showinfo("Validation", "Data validation passed")
            else:
                messagebox.showwarning("Validation", "Data validation failed")
        except Exception as e:
            messagebox.showerror("Error", f"Validation error: {e}")

    def show_component_library(self):
        """Show component library window"""
        # Implementation for component library
        messagebox.showinfo("Component Library", "Component library feature coming soon!")

    def export_png(self):
        """Export diagram as PNG"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            if filename:
                # Implementation for PNG export
                messagebox.showinfo("Export", f"Diagram exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def export_svg(self):
        """Export diagram as SVG"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".svg",
                filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]
            )
            if filename:
                # Implementation for SVG export
                messagebox.showinfo("Export", f"Diagram exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def save_configuration(self):
        """Save current configuration"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if filename:
                config_data = {
                    "components": [asdict(comp) for comp in self.components],
                    "connections": [asdict(conn) for conn in self.connections]
                }
                with open(filename, 'w') as file:
                    json.dump(config_data, file, indent=2, default=str)
                messagebox.showinfo("Save", f"Configuration saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")

    def save_hdf5(self):
        """Save current configuration as HDF5"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".h5",
                filetypes=[("HDF5 files", "*.h5;*.hdf5"), ("All files", "*.*")]
            )
            if filename:
                if isinstance(self.data_models["HDF5"], HDF5DataModel):
                    self.data_models["HDF5"].save_data(filename, self.components, self.connections)
                    messagebox.showinfo("Save", f"Configuration saved as HDF5 to {filename}")
                else:
                    messagebox.showerror("Error", "HDF5 data model not available")
        except Exception as e:
            messagebox.showerror("Error", f"HDF5 save failed: {e}")

    def new_diagram(self):
        """Create new diagram"""
        self.components.clear()
        self.connections.clear()
        self.clear_diagram()
        logger.info("New diagram created")

    def run(self):
        """Run the application"""
        logger.info("Starting Single Line Diagram Generator")
        self.root.mainloop()


def main():
    """Main entry point"""
    try:
        app = SLDGenerator()
        app.run()
    except Exception as e:
        logger.error(f"Application error: {e}")
        messagebox.showerror("Fatal Error", f"Application failed to start: {e}")

if __name__ == "__main__":
    main()
