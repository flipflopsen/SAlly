from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sally.domain.scada_state import SCADAState
from sally.presentation.gui.scada.sld_display import (
    ComponentData,
    ComponentState,
    ComponentType,
    ConnectionData,
)


@dataclass
class SLDLayoutConfig:
    component_spacing: int = 120
    auto_layout: bool = True


class SLDDataAdapter:
    def __init__(self, relation_data: Optional[Dict[str, List[List[float]]]] = None, config: Optional[SLDLayoutConfig] = None):
        self._relation_data = relation_data or {}
        self._config = config or SLDLayoutConfig()

    def build_diagram(self, state: SCADAState) -> Tuple[List[ComponentData], List[ConnectionData]]:
        components = self._build_components(state)
        connections = self._build_connections(components)
        if self._config.auto_layout:
            self._auto_layout(components)
        return components, connections

    def _build_components(self, state: SCADAState) -> List[ComponentData]:
        components: List[ComponentData] = []
        for entity_name, measurement in state.grid_measurements.items():
            comp_type = self._infer_component_type(entity_name)
            comp_state = self._infer_component_state(entity_name, state)
            power_value = getattr(measurement, "p", None)
            if power_value is None:
                power_value = getattr(measurement, "p_out", None)
            if power_value is None:
                power_value = getattr(measurement, "p_from", None)

            components.append(
                ComponentData(
                    id=entity_name,
                    name=entity_name,
                    component_type=comp_type,
                    position=(0, 0),
                    state=comp_state,
                    voltage=getattr(measurement, "vm", None),
                    power=power_value,
                    current=getattr(measurement, "q", None),
                )
            )

        return components

    def _build_connections(self, components: List[ComponentData]) -> List[ConnectionData]:
        connections: List[ConnectionData] = []
        component_map = {comp.id: comp for comp in components}
        if self._relation_data:
            idx = 0
            for rel_name, matrix in self._relation_data.items():
                if not components:
                    continue
                if matrix is None:
                    continue
                if hasattr(matrix, "size") and matrix.size == 0:
                    continue
                if hasattr(matrix, "__len__") and len(matrix) == 0:
                    continue
                for i in range(len(components) - 1):
                    from_comp = components[i]
                    to_comp = components[i + 1]
                    value_text = None
                    if from_comp.power is not None:
                        value_text = f"P:{from_comp.power:.2f}"
                    connections.append(
                        ConnectionData(
                            id=f"rel-{rel_name}-{idx}",
                            from_component=from_comp.id,
                            to_component=to_comp.id,
                            state=ComponentState.NORMAL,
                            value_text=value_text,
                        )
                    )
                    idx += 1
            return connections

        for i in range(len(components) - 1):
            from_comp = components[i]
            to_comp = components[i + 1]
            value_text = None
            if from_comp.power is not None:
                value_text = f"P:{from_comp.power:.2f}"
            connections.append(
                ConnectionData(
                    id=f"conn-{i}",
                    from_component=from_comp.id,
                    to_component=to_comp.id,
                    state=ComponentState.NORMAL,
                    value_text=value_text,
                )
            )
        return connections

    def _auto_layout(self, components: List[ComponentData]) -> None:
        spacing = self._config.component_spacing
        row = 0
        col = 0
        for index, component in enumerate(components):
            component.position = (col * spacing + 150, row * spacing + 150)
            col += 1
            if col >= 6:
                col = 0
                row += 1

    def _infer_component_type(self, entity_name: str) -> ComponentType:
        name = entity_name.lower()
        if "gen" in name or "generator" in name:
            return ComponentType.GENERATOR
        if "trafo" in name or "transform" in name:
            return ComponentType.TRANSFORMER
        if "breaker" in name or "switch" in name:
            return ComponentType.CIRCUIT_BREAKER
        return ComponentType.BUS

    def _infer_component_state(self, entity_name: str, state: SCADAState) -> ComponentState:
        for anomaly in state.anomalies:
            if anomaly.entity == entity_name and anomaly.severity.upper() == "CRITICAL":
                return ComponentState.CRITICAL
            if anomaly.entity == entity_name and anomaly.severity.upper() == "WARNING":
                return ComponentState.WARNING
        return ComponentState.NORMAL
