"""
SLD Data Adapter V2 - Optimized for performance

Converts SCADA state to lightweight SLD components.
Key optimization: Caches component categorization to avoid re-parsing names.

Compatible with Guardian's SLD visualization types.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from sally.domain.scada_state import SCADAState
from sally.domain.grid_entities import EntityType
from sally.presentation.gui.scada.sld_display_v2 import SLDComponent, ComponentType


@dataclass
class AdapterConfig:
    """Configuration for the SLD adapter."""
    max_generators: int = 4
    max_transformers: int = 4
    max_loads: int = 12
    max_pvs: int = 6
    max_nodes: int = 20


# Mapping from EntityType to ComponentType (Guardian-compatible)
ENTITY_TYPE_TO_COMPONENT: Dict[EntityType, ComponentType] = {
    # PandaPower types (Guardian)
    EntityType.PANDAPOWER_BUS: ComponentType.BUS,
    EntityType.PANDAPOWER_LOAD: ComponentType.LOAD,
    EntityType.PANDAPOWER_SGEN: ComponentType.SGEN,
    EntityType.PANDAPOWER_TRAFO: ComponentType.TRANSFORMER,
    EntityType.PANDAPOWER_LINE: ComponentType.LINE,
    EntityType.PANDAPOWER_SWITCH: ComponentType.SWITCH,
    EntityType.PANDAPOWER_EXT_GRID: ComponentType.EXT_GRID,

    # PyPower types
    EntityType.PYPOWER_NODE: ComponentType.BUS,
    EntityType.PYPOWER_BRANCH: ComponentType.BRANCH,
    EntityType.PYPOWER_TRANSFORMER: ComponentType.TRANSFORMER,
    EntityType.PYPOWER_TR_PRI: ComponentType.TRANSFORMER,
    EntityType.PYPOWER_TR_SEC: ComponentType.TRANSFORMER,

    # Simulation types
    EntityType.HOUSEHOLD_SIM: ComponentType.HOUSEHOLD,
    EntityType.CSV_PV: ComponentType.PV,
    EntityType.WIND_TURBINE: ComponentType.WIND,
    EntityType.BATTERY_ESS: ComponentType.BATTERY,
    EntityType.LOAD_BUS: ComponentType.LOAD,
}


class SLDDataAdapterV2:
    """
    High-performance adapter that converts SCADA state to SLD components.

    Optimizations:
    - Caches entity type inference (done once per entity)
    - Pre-filters entities to avoid processing irrelevant data
    - Minimal object creation

    Compatible with Guardian's visualization format.
    """

    def __init__(self, config: Optional[AdapterConfig] = None):
        self._config = config or AdapterConfig()
        self._type_cache: Dict[str, ComponentType] = {}
        self._anomaly_entities: Set[str] = set()

    def convert(self, state: SCADAState) -> List[SLDComponent]:
        """
        Convert SCADA state to SLD components.

        This is designed to be called every frame, so it must be fast.
        """
        # Update anomaly set (fast set operations)
        self._anomaly_entities = {
            a.entity for a in state.anomalies
            if a.severity.upper() in ("CRITICAL", "WARNING")
        }

        components: List[SLDComponent] = []

        for entity_name, measurement in state.grid_measurements.items():
            # Try to get type from entity_type field first
            comp_type = None
            if hasattr(measurement, 'entity_type') and measurement.entity_type:
                comp_type = ENTITY_TYPE_TO_COMPONENT.get(measurement.entity_type)

            # Fall back to cached/inferred type
            if comp_type is None:
                comp_type = self._get_type(entity_name)

            # Extract attributes based on comp_type and measurements
            attributes = {}

            # Power
            for attr in ("p_mw", "p", "p_out", "p_from"):
                val = getattr(measurement, attr, None)
                if val is not None:
                    if attr == "p_mw":
                        attributes["p_mw"] = val
                    else:
                        attributes["p"] = val
                    break

            # Reactive Power
            for attr in ("q_mvar", "q", "q_from"):
                val = getattr(measurement, attr, None)
                if val is not None:
                    if attr == "q_mvar":
                        attributes["q_mvar"] = val
                    else:
                        attributes["q"] = val
                    break

            # Voltage
            for attr in ("vm_pu", "vm", "vl"):
                val = getattr(measurement, attr, None)
                if val is not None:
                    if attr == "vm_pu":
                        attributes["vm_pu"] = val
                    else:
                        attributes["vm"] = val
                    break

            # Loading
            if measurement.loading_percent is not None:
                attributes["loading_percent"] = measurement.loading_percent

            # Switch state
            if measurement.closed is not None:
                attributes["closed"] = measurement.closed

            # Check anomaly status
            is_anomaly = entity_name in self._anomaly_entities

            components.append(SLDComponent(
                id=entity_name,
                name=entity_name,
                comp_type=comp_type,
                attributes=attributes,
                is_anomaly=is_anomaly,
            ))

        return components

    def _get_type(self, entity_name: str) -> ComponentType:
        """Get component type, using cache for performance."""
        if entity_name in self._type_cache:
            return self._type_cache[entity_name]

        comp_type = self._infer_type(entity_name)
        self._type_cache[entity_name] = comp_type
        return comp_type

    def _infer_type(self, entity_name: str) -> ComponentType:
        """Infer component type from entity name (Guardian-compatible patterns)."""
        name_lower = entity_name.lower()

        # Check for specific patterns (ordered by specificity)
        if "ext_grid" in name_lower or "extgrid" in name_lower or "slack" in name_lower:
            return ComponentType.EXT_GRID
        if "sgen" in name_lower:
            return ComponentType.SGEN
        if "gen" in name_lower and "load" not in name_lower:
            return ComponentType.GENERATOR
        if "trafo" in name_lower or "transform" in name_lower or "tr_" in name_lower:
            return ComponentType.TRANSFORMER
        if "pv" in name_lower or "solar" in name_lower:
            return ComponentType.PV
        if "wind" in name_lower:
            return ComponentType.WIND
        if "battery" in name_lower or "bess" in name_lower or "ess" in name_lower:
            return ComponentType.BATTERY
        if "switch" in name_lower or "breaker" in name_lower or "cb_" in name_lower:
            return ComponentType.SWITCH
        if "house" in name_lower or "household" in name_lower:
            return ComponentType.HOUSEHOLD
        if "load" in name_lower or "lump" in name_lower:
            return ComponentType.LOAD
        if "line" in name_lower or "cable" in name_lower:
            return ComponentType.LINE
        if "branch" in name_lower:
            return ComponentType.BRANCH
        if "node" in name_lower or "bus" in name_lower:
            return ComponentType.BUS

        # Default to node for unknown types
        return ComponentType.NODE

    def clear_cache(self) -> None:
        """Clear the type cache (call if entity set changes significantly)."""
        self._type_cache.clear()
