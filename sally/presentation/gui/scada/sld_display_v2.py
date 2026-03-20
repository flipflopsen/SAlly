"""
Single Line Diagram Display V2 - Ultra High Performance

Clean engineering-style SLD visualization matching industrial standards.
Optimized for 60+ FPS with hundreds of components.

Key optimizations:
1. Static topology cached on first render - only values update
2. Minimal canvas items - no unnecessary decorations
3. Direct canvas.itemconfigure() for value updates only
4. No position recalculations after initial layout
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, font as tkfont
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional, Set, Any
import math
import os
import json
from pathlib import Path
from PIL import Image, ImageTk

from sally.core.logger import get_logger

logger = get_logger(__name__)


class ComponentType(Enum):
    """Component types for SLD visualization - Guardian compatible."""
    # Primary equipment types (Guardian-compatible)
    GENERATOR = "generator"  # Sgen in PandaPower
    TRANSFORMER = "transformer"  # Trafo
    LOAD = "load"  # Load element
    BUS = "bus"  # Bus bar
    BRANCH = "branch"  # Line/Cable
    LINE = "line"  # Alias for branch
    CABLE = "cable"  # Alias for branch

    # Source types
    PV = "pv"  # Solar PV (sgen subtype)
    SGEN = "sgen"  # Static generator
    EXT_GRID = "ext_grid"  # External grid connection
    WIND = "wind"  # Wind turbine
    BATTERY = "battery"  # Battery storage

    # Load types
    HOUSEHOLD = "household"  # Residential load

    # Switching equipment
    SWITCH = "switch"  # Circuit breaker/switch
    BREAKER = "breaker"  # Circuit breaker

    # Measurement
    NODE = "node"  # Measurement node

    # Shunt devices
    SHUNT = "shunt"  # Shunt capacitor/reactor


@dataclass
class SLDComponent:
    """Lightweight component data for SLD rendering."""
    id: str
    name: str
    comp_type: ComponentType
    attributes: Dict[str, Any] = field(default_factory=dict)
    is_anomaly: bool = False


class SLDCanvasV2(ttk.Frame):
    """
    Ultra-optimized Single Line Diagram canvas.

    Design principles:
    - White/light background with black lines (engineering style)
    - Minimal visual elements
    - Static topology, dynamic values only
    - Bus bars as horizontal lines
    - Standard electrical symbols
    """

    # Color scheme - for dark theme (white lines on dark background)
    COLORS = {
        "bg": "#2b3e50",  # Match darkly theme background
        "line": "#ffffff",  # White lines
        "line_light": "#aaaaaa",
        "bus": "#ffffff",  # White bus bars
        "text": "#ffffff",  # White text
        "text_dim": "#aaaaaa",  # Dimmed text
        "value_normal": "#5cb85c",  # Bright green for normal values
        "value_warning": "#f0ad4e",  # Orange for warning
        "value_critical": "#d9534f",  # Red for critical
        "generator": "#5bc0de",  # Cyan/blue
        "transformer": "#ffffff",
        "load": "#ffffff",
        "highlight": "#5bc0de",
    }

    def __init__(self, parent, width: int = 1200, height: int = 800):
        super().__init__(parent)

        self._width = width
        self._height = height

        # Topology cache - built once
        self._topology_built = False
        self._component_items: Dict[str, Dict[str, int]] = {}  # id -> {symbol, label, value}
        self._bus_items: List[int] = []
        self._connection_items: List[int] = []

        # Layout cache
        self._component_positions: Dict[str, Tuple[int, int]] = {}
        self._bus_positions: List[Tuple[int, int, int, int]] = []  # (x1, y1, x2, y2)

        # Value cache for change detection
        self._value_cache: Dict[str, Tuple[Optional[float], Optional[float], bool]] = {}

        # Asset management
        self._assets: Dict[str, ImageTk.PhotoImage] = {}
        self._load_assets()

        # Render stats
        self._render_count = 0
        self._last_component_count = 0

        # Create canvas with light background
        self._canvas = tk.Canvas(
            self,
            width=width,
            height=height,
            bg=self.COLORS["bg"],
            highlightthickness=1,
            highlightbackground="#e0e0e0",
        )

        # Scrollbars
        self._h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._v_scroll = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(
            xscrollcommand=self._h_scroll.set,
            yscrollcommand=self._v_scroll.set,
            scrollregion=(0, 0, width * 2, height * 2)
        )

        # Grid layout
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._h_scroll.grid(row=1, column=0, sticky="ew")
        self._v_scroll.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Pan and zoom
        self._canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self._canvas.bind("<B1-Motion>", self._on_pan_move)
        self._canvas.bind("<MouseWheel>", self._on_zoom)

        # Fonts
        self._font_title = ("Consolas", 10, "bold")
        self._font_label = ("Consolas", 9)
        self._font_value = ("Consolas", 8, "bold")



        # Load assets
    def _load_assets(self):
        try:
            # Determine paths
            base_dir = Path(__file__).parent
            assets_dir = base_dir / "assets"
            config_dir = base_dir.parent.parent.parent / "config"
            mapping_file = config_dir / "EntityMapping.json"

            # Load mapping
            mapping: List[Dict[str, str]] = []
            if mapping_file.exists():
                with open(mapping_file, "r") as f:
                    mapping = json.load(f)

            # Map EntityName -> Asset filename
            # We can use this to lookup assets by entity type/name if we have that info available
            # For now, we'll just load all PNGs found in the assets folder as generic assets
            # keyed by their stem (filename without extension)

            if not assets_dir.exists():
                logger.warning(f"Assets directory not found: {assets_dir}")
                return

            for item in assets_dir.glob("*.png"):
                try:
                    # Load and resize image to standard icon size (e.g. 32x32 or 40x40)
                    # We might need different sizes for different components
                    pil_image = Image.open(item)
                    # Resize if too large? Let's check size.
                    # Assuming assets are reasonably sized or we resize them.
                    # Standard grid size is ~60-80px?
                    pil_image.thumbnail((48, 48), Image.Resampling.LANCZOS)

                    tk_image = ImageTk.PhotoImage(pil_image)
                    self._assets[item.stem] = tk_image
                    # Also map 'photovoltaik' to 'pv', etc if needed, or rely on strict naming

                except Exception as e:
                    logger.error(f"Failed to load asset {item.name}: {e}")

            logger.info(f"Loaded {len(self._assets)} assets from {assets_dir}")

        except Exception as e:
            logger.error(f"Error initializing assets: {e}")



    logger.info("SLDCanvasV2 initialized")

    def update_components(self, components: List[SLDComponent]) -> None:
        """
        Update the SLD with component data.

        On first call: builds entire topology
        On subsequent calls: only updates value text (ultra-fast)
        """
        self._render_count += 1

        # Check if topology needs rebuild
        if not self._topology_built or len(components) != self._last_component_count:
            self._build_topology(components)
            self._topology_built = True
            self._last_component_count = len(components)
            if self._render_count % 100 == 0:
                logger.debug(f"SLD Render {self._render_count}: Topology rebuilt")
            return

        # Fast path: only update values that changed
        updates = 0
        for comp in components:
            cached = self._value_cache.get(comp.id)
            current = (tuple(sorted(comp.attributes.items())), comp.is_anomaly)

            if cached != current:
                self._update_component_value(comp)
                self._value_cache[comp.id] = current
                updates += 1

        if self._render_count % 100 == 0:
            # Log some sample values for debugging
            sample = [c.name for c in components[:3]]
            logger.debug(f"SLD Render {self._render_count}: Fast update ({updates} values changed), sample={sample}")

    def _build_topology(self, components: List[SLDComponent]) -> None:
        """Build the static SLD topology matching industrial SLD style."""
        self._canvas.delete("all")
        self._component_items.clear()
        self._component_positions.clear()
        self._value_cache.clear()
        self._bus_items.clear()
        self._connection_items.clear()

        if not components:
            return

        # Categorize components
        generators = [c for c in components if c.comp_type == ComponentType.GENERATOR]
        transformers = [c for c in components if c.comp_type == ComponentType.TRANSFORMER]
        loads = [c for c in components if c.comp_type in (ComponentType.LOAD, ComponentType.HOUSEHOLD)]
        pvs = [c for c in components if c.comp_type == ComponentType.PV]
        nodes = [c for c in components if c.comp_type == ComponentType.NODE]
        branches = [c for c in components if c.comp_type == ComponentType.BRANCH]
        buses = [c for c in components if c.comp_type == ComponentType.BUS]

        # Layout parameters - comfortable spacing
        margin = 50
        bus_y_start = 90
        bus_spacing = 160  # More vertical space between buses
        component_spacing = 90  # More horizontal space between components

        # Calculate actual content widths (compact buses)
        num_gens = min(len(generators), 4)
        num_trans = min(len(transformers), 4)
        num_pvs = min(len(pvs), 8)
        num_loads = min(len(loads), 10)

        # Bus widths based on content
        hv_bus_width = max(200, num_gens * component_spacing + 60)
        mv_bus_width = max(300, max(num_trans * component_spacing * 1.5, num_pvs * component_spacing) + 60)
        lv_bus_width = max(400, num_loads * component_spacing + 60)

        canvas_width = max(hv_bus_width, mv_bus_width, lv_bus_width) + margin * 2
        self._canvas.configure(scrollregion=(0, 0, canvas_width + 100, 700))

        # Center buses horizontally
        center_x = canvas_width // 2

        # ═══════════════════════════════════════════════════════════════
        # HV BUS (220kV) - Top
        # ═══════════════════════════════════════════════════════════════
        bus1_y = bus_y_start
        bus1_x1 = center_x - hv_bus_width // 2
        bus1_x2 = center_x + hv_bus_width // 2

        # Draw double bus bar (like in reference image)
        bus1 = self._canvas.create_line(
            bus1_x1, bus1_y, bus1_x2, bus1_y,
            fill=self.COLORS["bus"], width=3,
        )
        self._bus_items.append(bus1)

        # Bus label on the right
        self._canvas.create_text(
            bus1_x2 + 8, bus1_y, text="220kV - HV Bus",
            anchor="w", font=self._font_label, fill=self.COLORS["text_dim"]
        )

        # Draw generators on top bus (with circuit breakers)
        gen_x_start = bus1_x1 + 40
        for i, gen in enumerate(generators[:num_gens]):
            x = gen_x_start + i * component_spacing
            y = bus_y_start - 55
            self._draw_generator(gen, x, y, bus1_y)

        # ═══════════════════════════════════════════════════════════════
        # MV BUS (132kV) - Middle
        # ═══════════════════════════════════════════════════════════════
        bus2_y = bus_y_start + bus_spacing
        bus2_x1 = center_x - mv_bus_width // 2
        bus2_x2 = center_x + mv_bus_width // 2

        bus2 = self._canvas.create_line(
            bus2_x1, bus2_y, bus2_x2, bus2_y,
            fill=self.COLORS["bus"], width=2
        )
        self._bus_items.append(bus2)

        self._canvas.create_text(
            bus2_x2 + 8, bus2_y, text="132kV - MV Bus",
            anchor="w", font=self._font_label, fill=self.COLORS["text_dim"]
        )

        # Draw transformers between HV and MV buses (with circuit breakers)
        trans_x_start = center_x - (num_trans - 1) * component_spacing // 2
        for i, trans in enumerate(transformers[:num_trans]):
            x = trans_x_start + i * component_spacing
            self._draw_transformer(trans, x, bus1_y, bus2_y)

        # ═══════════════════════════════════════════════════════════════
        # LV BUS (11kV) - Bottom
        # ═══════════════════════════════════════════════════════════════
        bus3_y = bus2_y + bus_spacing
        bus3_x1 = center_x - lv_bus_width // 2
        bus3_x2 = center_x + lv_bus_width // 2

        bus3 = self._canvas.create_line(
            bus3_x1, bus3_y, bus3_x2, bus3_y,
            fill=self.COLORS["bus"], width=2
        )
        self._bus_items.append(bus3)

        self._canvas.create_text(
            bus3_x2 + 8, bus3_y, text="11kV - LV Bus",
            anchor="w", font=self._font_label, fill=self.COLORS["text_dim"]
        )

        # Draw PV sources on MV bus (above)
        pv_x_start = bus2_x1 + 40
        for i, pv in enumerate(pvs[:num_pvs]):
            x = pv_x_start + i * (component_spacing - 10)
            self._draw_pv(pv, x, bus2_y)

        # Draw loads on LV bus (below)
        load_x_start = bus3_x1 + 30
        for i, load in enumerate(loads[:num_loads]):
            x = load_x_start + i * (component_spacing - 5)
            self._draw_load(load, x, bus3_y)

        # Draw nodes as small markers BELOW the LV bus (not overlapping)
        # Position them after the loads, spaced out
        node_start_x = load_x_start + num_loads * (component_spacing - 5) + 40
        for i, node in enumerate(nodes[:6]):
            row = i // 4
            col = i % 4
            x = node_start_x + col * 50
            y = bus3_y + 60 + row * 30  # Below the LV bus
            self._draw_node(node, x, y)

        # Summary text (top left)
        summary = f"Gen: {len(generators)} | Trans: {len(transformers)} | Load: {len(loads)} | PV: {len(pvs)}"
        self._canvas.create_text(
            10, 12, text=summary, anchor="w",
            font=("Consolas", 8), fill=self.COLORS["text_dim"]
        )

    def _draw_generator(self, comp: SLDComponent, x: int, y: int, bus_y: int) -> None:
        """Draw generator symbol - using asset if available."""
        # Vertical connection line to bus
        self._canvas.create_line(
            x, y + 16, x, bus_y - 8,  # Using standard radius 16 for connection point
            fill=self.COLORS["line"], width=1
        )

        # Circuit breaker symbol
        cb_y = bus_y - 15
        cb_size = 5
        self._canvas.create_rectangle(
            x - cb_size, cb_y - cb_size, x + cb_size, cb_y + cb_size,
            outline=self.COLORS["line"], width=1, fill=self.COLORS["bg"]
        )

        # Short connection from CB to bus
        self._canvas.create_line(x, cb_y + cb_size, x, bus_y, fill=self.COLORS["line"], width=1)

        # Determine asset
        asset_key = "generator"
        if comp.comp_type == ComponentType.WIND:
            asset_key = "wind_turbine"
        elif comp.comp_type == ComponentType.BATTERY:
            asset_key = "industry"  # Or specific battery asset if added

        image = self._assets.get(asset_key)
        r = 16

        if image:
            # Draw image
            symbol = self._canvas.create_image(x, y, image=image)
        else:
            # Fallback: Draw standard symbol
            symbol = self._canvas.create_oval(
                x - r, y - r, x + r, y + r,
                outline=self.COLORS["line"], width=2, fill=self.COLORS["bg"]
            )
            # Cross pattern inside
            self._canvas.create_line(x - r + 4, y, x + r - 4, y, fill=self.COLORS["line"], width=1)
            self._canvas.create_line(x, y - r + 4, x, y + r - 4, fill=self.COLORS["line"], width=1)
            offset = r - 5
            self._canvas.create_line(x - offset, y - offset, x + offset, y + offset, fill=self.COLORS["line"], width=1)
            self._canvas.create_line(x + offset, y - offset, x - offset, y + offset, fill=self.COLORS["line"], width=1)

        # Name label above
        label = self._canvas.create_text(
            x, y - r - 10, text=self._short_name(comp.name, max_len=6),
            font=self._font_label, fill=self.COLORS["text"]
        )

        # Value label (power) below
        value_text = self._format_attributes(comp.attributes)
        value = self._canvas.create_text(
            x, y + r + 12, text=value_text,
            font=self._font_value, fill=self._get_value_color(comp)
        )

        self._component_items[comp.id] = {"symbol": symbol, "label": label, "value": value}
        self._component_positions[comp.id] = (x, y)
        self._value_cache[comp.id] = (tuple(sorted(comp.attributes.items())), comp.is_anomaly)

    def _draw_transformer(self, comp: SLDComponent, x: int, y1: int, y2: int) -> None:
        """Draw transformer symbol - using asset if available."""
        mid_y = (y1 + y2) // 2
        r = 12

        # Connections and breakers
        # Top CB
        cb_y_top = y1 + 15
        cb_size = 4
        self._canvas.create_line(x, y1, x, cb_y_top - cb_size, fill=self.COLORS["line"], width=1)
        self._canvas.create_rectangle(
            x - cb_size, cb_y_top - cb_size, x + cb_size, cb_y_top + cb_size,
            outline=self.COLORS["line"], width=1, fill=self.COLORS["bg"]
        )

        # Bottom CB
        cb_y_bottom = y2 - 15
        self._canvas.create_line(x, cb_y_bottom + cb_size, x, y2, fill=self.COLORS["line"], width=1)
        self._canvas.create_rectangle(
            x - cb_size, cb_y_bottom - cb_size, x + cb_size, cb_y_bottom + cb_size,
            outline=self.COLORS["line"], width=1, fill=self.COLORS["bg"]
        )

        image = self._assets.get("trafo")

        if image:
            # Connections to image
            self._canvas.create_line(x, cb_y_top + cb_size, x, mid_y - 16, fill=self.COLORS["line"], width=1) # Approx top
            self._canvas.create_line(x, mid_y + 16, x, cb_y_bottom - cb_size, fill=self.COLORS["line"], width=1) # Approx bottom
            symbol = self._canvas.create_image(x, mid_y, image=image)
        else:
            # Fallback drawing
            overlap = 4
            top_circle_y = mid_y - r + overlap // 2
            self._canvas.create_line(x, cb_y_top + cb_size, x, top_circle_y - r, fill=self.COLORS["line"], width=1)

            # Primary winding
            self._canvas.create_oval(
                x - r, top_circle_y - r, x + r, top_circle_y + r,
                outline=self.COLORS["line"], width=2, fill=self.COLORS["bg"]
            )

            # Secondary winding
            bottom_circle_y = mid_y + r - overlap // 2
            symbol = self._canvas.create_oval(
                x - r, bottom_circle_y - r, x + r, bottom_circle_y + r,
                outline=self.COLORS["line"], width=2, fill=self.COLORS["bg"]
            )

            self._canvas.create_line(x, bottom_circle_y + r, x, cb_y_bottom - cb_size, fill=self.COLORS["line"], width=1)

        # Name label
        label = self._canvas.create_text(
            x + r + 6, mid_y, text=self._short_name(comp.name, max_len=6),
            font=("Consolas", 8), fill=self.COLORS["text"], anchor="w"
        )

        # Value label
        value = self._canvas.create_text(
            x - r - 6, mid_y, text=self._format_attributes(comp.attributes),
            font=("Consolas", 7), fill=self._get_value_color(comp), anchor="e"
        )

        self._component_items[comp.id] = {"symbol": symbol, "label": label, "value": value}
        self._component_positions[comp.id] = (x, mid_y)
        self._value_cache[comp.id] = (tuple(sorted(comp.attributes.items())), comp.is_anomaly)

    def _draw_load(self, comp: SLDComponent, x: int, bus_y: int) -> None:
        """Draw load symbol - using asset if available."""
        y = bus_y + 35
        size = 12

        # Circuit breaker
        cb_y = bus_y + 10
        cb_size = 4
        self._canvas.create_line(x, bus_y, x, cb_y - cb_size, fill=self.COLORS["line"], width=1)
        self._canvas.create_rectangle(
            x - cb_size, cb_y - cb_size, x + cb_size, cb_y + cb_size,
            outline=self.COLORS["line"], width=1, fill=self.COLORS["bg"]
        )

        asset_key = "load"
        if comp.comp_type == ComponentType.HOUSEHOLD:
            asset_key = "house"

        image = self._assets.get(asset_key)

        if image:
            self._canvas.create_line(x, cb_y + cb_size, x, y - 16, fill=self.COLORS["line"], width=1)
            symbol = self._canvas.create_image(x, y, image=image)
        else:
            self._canvas.create_line(x, cb_y + cb_size, x, y - size, fill=self.COLORS["line"], width=1)
            points = [x, y + size, x - size, y - size, x + size, y - size]
            symbol = self._canvas.create_polygon(
                points, outline=self.COLORS["line"], width=1, fill=self.COLORS["bg"]
            )

        # Name label
        label = self._canvas.create_text(
            x, y + size + 8, text=self._short_name(comp.name, max_len=8),
            font=("Consolas", 7), fill=self.COLORS["text"]
        )

        # Value label
        value_text = self._format_attributes(comp.attributes)
        value = self._canvas.create_text(
            x, y + size + 18, text=value_text,
            font=("Consolas", 7), fill=self._get_value_color(comp)
        )

        self._component_items[comp.id] = {"symbol": symbol, "label": label, "value": value}
        self._component_positions[comp.id] = (x, y)
        self._value_cache[comp.id] = (tuple(sorted(comp.attributes.items())), comp.is_anomaly)

    def _draw_pv(self, comp: SLDComponent, x: int, bus_y: int) -> None:
        """Draw PV symbol - using asset if available."""
        y = bus_y - 32
        r = 10

        # Circuit breaker
        cb_y = bus_y - 12
        cb_size = 4
        self._canvas.create_line(x, bus_y, x, cb_y + cb_size, fill=self.COLORS["line"], width=1)
        self._canvas.create_rectangle(
            x - cb_size, cb_y - cb_size, x + cb_size, cb_y + cb_size,
            outline=self.COLORS["line"], width=1, fill=self.COLORS["bg"]
        )

        asset_key = "photovoltaik" # Based on asset naming
        image = self._assets.get(asset_key)

        if image:
            self._canvas.create_line(x, cb_y - cb_size, x, y + 16, fill=self.COLORS["line"], width=1)
            symbol = self._canvas.create_image(x, y, image=image)
        else:
            self._canvas.create_line(x, cb_y - cb_size, x, y + r, fill=self.COLORS["line"], width=1)
            symbol = self._canvas.create_oval(
                x - r, y - r, x + r, y + r,
                outline=self.COLORS["line"], width=1, fill=self.COLORS["bg"]
            )
            # Arrow inside
            self._canvas.create_line(x, y + 5, x, y - 5, fill=self.COLORS["line"], width=1, arrow="first")

        # Name label
        label = self._canvas.create_text(
            x, y - r - 8, text=self._short_name(comp.name, max_len=6),
            font=("Consolas", 7), fill=self.COLORS["text"]
        )

        # Value label
        value = self._canvas.create_text(
            x + r + 5, y, text=self._format_attributes(comp.attributes),
            font=self._font_value, fill=self._get_value_color(comp), anchor="w"
        )

        self._component_items[comp.id] = {"symbol": symbol, "label": label, "value": value}
        self._component_positions[comp.id] = (x, y)
        self._value_cache[comp.id] = (tuple(sorted(comp.attributes.items())), comp.is_anomaly)

    def _draw_node(self, comp: SLDComponent, x: int, y: int) -> None:
        """Draw simple node marker (small filled circle)."""
        r = 4

        symbol = self._canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=self.COLORS["line"], outline=""
        )

        # Minimal label
        label = self._canvas.create_text(
            x + r + 4, y, text=self._short_name(comp.name, max_len=8),
            font=("Consolas", 7), fill=self.COLORS["text_dim"], anchor="w"
        )

        # Value (power flow)
        value = self._canvas.create_text(
            x, y + 12, text=self._format_attributes(comp.attributes, short=True),
            font=("Consolas", 7), fill=self._get_value_color(comp)
        )

        self._component_items[comp.id] = {"symbol": symbol, "label": label, "value": value}
        self._component_positions[comp.id] = (x, y)
        self._value_cache[comp.id] = (tuple(sorted(comp.attributes.items())), comp.is_anomaly)

    def _update_component_value(self, comp: SLDComponent) -> None:
        """Update only the value text for a component (fast operation)."""
        items = self._component_items.get(comp.id)
        if not items or "value" not in items:
            return

        # Update value text
        new_text = self._format_attributes(comp.attributes)
        new_color = self._get_value_color(comp)

        self._canvas.itemconfigure(items["value"], text=new_text, fill=new_color)

    def _short_name(self, name: str, max_len: int = 12) -> str:
        """Shorten component name for display."""
        # Remove common prefixes
        for prefix in ["HouseholdSim-0.", "CSV-0.", "PyPower-0.0-"]:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break

        if len(name) > max_len:
            return name[:max_len-2] + ".."
        return name

    def _format_attributes(self, attrs: Dict[str, Any], short: bool = False) -> str:
        """Format attributes for display."""
        lines = []

        # Power (P)
        if 'p_mw' in attrs:
            val = attrs['p_mw']
            lines.append(f"{val:.2f} MW")
        elif 'p' in attrs:
            lines.append(f"P: {attrs['p']:.2f}")

        # Reactive Power (Q)
        if 'q_mvar' in attrs:
            val = attrs['q_mvar']
            lines.append(f"{val:.2f} MVar")
        elif 'q' in attrs:
            lines.append(f"Q: {attrs['q']:.2f}")

        # Voltage
        if 'vm_pu' in attrs:
            lines.append(f"{attrs['vm_pu']:.3f} pu")
        elif 'vm' in attrs:
            lines.append(f"{attrs['vm']:.3f} pu")

        # Loading
        if 'loading_percent' in attrs:
            lines.append(f"{attrs['loading_percent']:.1f}% Load")

        # Switch State
        if 'closed' in attrs:
            state = "Closed" if attrs['closed'] else "Open"
            lines.append(state)

        if not lines:
            return ""

        return "\n".join(lines)

    def _get_value_color(self, comp: SLDComponent) -> str:
        """Get color for value based on state."""
        if comp.is_anomaly:
            return self.COLORS["value_critical"]

        attrs = comp.attributes

        # Check limits
        if 'loading_percent' in attrs and attrs['loading_percent'] > 90:
            return self.COLORS["value_warning"]

        if 'vm_pu' in attrs:
            v = attrs['vm_pu']
            if v < 0.9 or v > 1.1:
                return self.COLORS["value_warning"]

        return self.COLORS["value_normal"]

    def _on_pan_start(self, event):
        self._canvas.scan_mark(event.x, event.y)

    def _on_pan_move(self, event):
        self._canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_zoom(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self._canvas.scale("all", event.x, event.y, factor, factor)

    def clear(self) -> None:
        """Clear the canvas."""
        self._canvas.delete("all")
        self._component_items.clear()
        self._component_positions.clear()
        self._value_cache.clear()
        self._topology_built = False
