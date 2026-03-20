"""
Map MIDAS scenario data to SAlly display types.

This mapper translates the parsed MIDAS scenario (module names, scopes,
and ``*_params`` blocks) into SAlly‑friendly dataclasses for use in the
GUI and metadata pipeline.  It does **not** build a mosaik ``World`` —
that is delegated to the MIDAS ``Configurator`` at run‑time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from sally.infrastructure.midas.midas_parser import (
    MidasConnectionDef,
    MidasEntityDef,
    MidasScenario,
    MidasSimulatorDef,
)

logger = logging.getLogger(__name__)


@dataclass
class SallySimDef:
    """A simulator definition ready for :class:`SimulationBuilder`."""

    sim_key: str
    sally_module: str
    sally_class: str
    step_size: int = 900
    params: Dict[str, Any] = field(default_factory=dict)
    sim_type: str = "time-based"


@dataclass
class SallyEntityDef:
    """An entity definition ready for :class:`SimulationBuilder`."""

    sim_key: str
    model: str
    count: int = 1
    params: Dict[str, Any] = field(default_factory=dict)
    entity_id: Optional[str] = None


@dataclass
class SallyConnectionDef:
    """A connection definition ready for :class:`SimulationBuilder`."""

    src: str  # "SimKey.EntityId"
    dst: str  # "SimKey.EntityId"
    attrs: List[Tuple[str, str]] = field(default_factory=list)
    async_request: bool = False


@dataclass
class SallyScenarioDef:
    """Complete SAlly-compatible scenario definition."""

    name: str
    duration: int
    step_size: int
    start_date: Optional[str]
    simulators: Dict[str, SallySimDef] = field(default_factory=dict)
    entities: List[SallyEntityDef] = field(default_factory=list)
    connections: List[SallyConnectionDef] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Type mapping registry ────────────────────────────────────────────────────

# Maps MIDAS module name → (SAlly display module, SAlly display class, default model)
# These are used for GUI representation only — the actual mosaik simulators
# are created by the MIDAS Configurator.
_DEFAULT_TYPE_MAP: Dict[str, Tuple[str, str, str]] = {
    "powergrid": (
        "midas_powergrid",
        "PowergridSimulator",
        "Grid",
    ),
    "sndata": (
        "midas_smartnord",
        "SmartNordDataSimulator",
        "Load",
    ),
    "comdata": (
        "midas_commercials",
        "CommercialDataSimulator",
        "Load",
    ),
    "dlpdata": (
        "midas_dlp",
        "DLPDataSimulator",
        "Load",
    ),
    "weather": (
        "midas_weather",
        "WeatherDataSimulator",
        "Weather",
    ),
    "der": (
        "pysimmods",
        "PysimmodsSimulator",
        "DER",
    ),
    "store": (
        "midas_store",
        "MidasHdf5Simulator",
        "Monitor",
    ),
    "timesim": (
        "midas_timesim",
        "TimeSimSimulator",
        "Time",
    ),
    "sbdata": (
        "midas_simbench",
        "SimbenchDataSimulator",
        "Node",
    ),
    "pwdata": (
        "midas_pwdata",
        "PVWindDataSimulator",
        "Generation",
    ),
    "powerseries": (
        "midas_powerseries",
        "PowerSeriesSimulator",
        "PowerSeries",
    ),
}

# Attribute name translations:  MIDAS attr → SAlly attr
_DEFAULT_ATTR_MAP: Dict[str, str] = {
    "p_mw": "active_power_mw",
    "q_mvar": "reactive_power_mvar",
    "vm_pu": "voltage_pu",
    "va_degree": "voltage_angle_deg",
    "loading_percent": "loading_pct",
    "p_gen_mw": "active_power_mw",
    "q_gen_mvar": "reactive_power_mvar",
    "soc_percent": "soc_pct",
    "p_kw": "active_power_kw",
    "q_kvar": "reactive_power_kvar",
    "cos_phi": "power_factor",
    "i_ka": "current_ka",
    "sn_mva": "rated_power_mva",
}


class MidasToSallyMapper:
    """
    Translate a :class:`MidasScenario` into a :class:`SallyScenarioDef`.

    The mapper can be extended at runtime by registering additional type
    mappings or attribute translations via :meth:`register_type` and
    :meth:`register_attr`.
    """

    def __init__(self) -> None:
        self._type_map: Dict[str, Tuple[str, str, str]] = dict(_DEFAULT_TYPE_MAP)
        self._attr_map: Dict[str, str] = dict(_DEFAULT_ATTR_MAP)
        self._custom_transformers: Dict[str, Callable[[MidasSimulatorDef], SallySimDef]] = {}

    # ── Public registration API ──────────────────────────────────────────

    def register_type(
        self,
        midas_prefix: str,
        sally_module: str,
        sally_class: str,
        default_model: str = "Model",
    ) -> None:
        """Register a custom MIDAS→SAlly simulator type mapping."""
        self._type_map[midas_prefix] = (sally_module, sally_class, default_model)

    def register_attr(self, midas_attr: str, sally_attr: str) -> None:
        """Register a custom attribute name translation."""
        self._attr_map[midas_attr] = sally_attr

    def register_transformer(
        self,
        midas_prefix: str,
        transformer: Callable[[MidasSimulatorDef], SallySimDef],
    ) -> None:
        """Register a fully custom transformer for a MIDAS module prefix."""
        self._custom_transformers[midas_prefix] = transformer

    # ── Main mapping entry point ─────────────────────────────────────────

    def map(self, scenario: MidasScenario) -> SallyScenarioDef:
        """Convert a parsed MIDAS scenario to a SAlly scenario definition."""

        sally_sims: Dict[str, SallySimDef] = {}
        sim_key_remap: Dict[str, str] = {}  # midas key → sally key

        # 1. Map simulators
        for mkey, msim in scenario.simulators.items():
            sally_sim, sally_key = self._map_simulator(mkey, msim)
            sally_sims[sally_key] = sally_sim
            sim_key_remap[mkey] = sally_key

        # 2. Map entities
        sally_entities: List[SallyEntityDef] = []
        for ment in scenario.entities:
            sally_ent = self._map_entity(ment, sim_key_remap)
            sally_entities.append(sally_ent)

        # 3. Map connections
        sally_conns: List[SallyConnectionDef] = []
        for mconn in scenario.connections:
            sally_conn = self._map_connection(mconn, sim_key_remap)
            sally_conns.append(sally_conn)

        return SallyScenarioDef(
            name=scenario.name,
            duration=scenario.duration,
            step_size=scenario.step_size,
            start_date=scenario.start_date,
            simulators=sally_sims,
            entities=sally_entities,
            connections=sally_conns,
            metadata={
                "source": str(scenario.source_path) if scenario.source_path else "inline",
                "midas_raw_keys": list(scenario.raw.keys()),
            },
        )

    # ── Internal mapping helpers ─────────────────────────────────────────

    def _map_simulator(
        self, midas_key: str, msim: MidasSimulatorDef
    ) -> Tuple[SallySimDef, str]:
        """Map a single MIDAS simulator to a SAlly simulator."""

        # Check custom transformers first
        for prefix, transformer in self._custom_transformers.items():
            if msim.module_name.startswith(prefix):
                sally_sim = transformer(msim)
                return sally_sim, sally_sim.sim_key

        # Look up in type map by module name
        sally_module, sally_class, _ = self._resolve_type(msim.module_name)

        # Build a clean SAlly key
        sally_key = self._clean_key(midas_key)

        # Translate params
        translated_params = self._translate_params(msim.params)

        return (
            SallySimDef(
                sim_key=sally_key,
                sally_module=sally_module,
                sally_class=sally_class,
                step_size=msim.step_size,
                params=translated_params,
                sim_type="time-based",
            ),
            sally_key,
        )

    def _map_entity(
        self, ment: MidasEntityDef, remap: Dict[str, str]
    ) -> SallyEntityDef:
        sim_key = remap.get(ment.sim_ref, ment.sim_ref)
        translated_params = self._translate_params(ment.params)
        return SallyEntityDef(
            sim_key=sim_key,
            model=ment.model,
            count=ment.count,
            params=translated_params,
            entity_id=ment.entity_id,
        )

    def _map_connection(
        self, mconn: MidasConnectionDef, remap: Dict[str, str]
    ) -> SallyConnectionDef:
        src_sim = remap.get(mconn.src_sim, mconn.src_sim)
        dst_sim = remap.get(mconn.dst_sim, mconn.dst_sim)
        src_attr = self._attr_map.get(mconn.src_attr, mconn.src_attr)
        dst_attr = self._attr_map.get(mconn.dst_attr, mconn.dst_attr)

        attrs: List[Tuple[str, str]] = []
        if src_attr and dst_attr:
            attrs.append((src_attr, dst_attr))
        elif src_attr:
            attrs.append((src_attr, src_attr))

        return SallyConnectionDef(
            src=f"{src_sim}.{mconn.src_entity}",
            dst=f"{dst_sim}.{mconn.dst_entity}",
            attrs=attrs,
            async_request=mconn.async_request,
        )

    def _resolve_type(self, module_name: str) -> Tuple[str, str, str]:
        """Find the best matching SAlly type for a MIDAS module name."""
        # Direct lookup
        if module_name in self._type_map:
            return self._type_map[module_name]

        # Prefix match for extended module names (e.g. "powergrid_ext")
        best_match = ""
        for prefix in self._type_map:
            if module_name.startswith(prefix) and len(prefix) > len(best_match):
                best_match = prefix

        if best_match:
            return self._type_map[best_match]

        logger.warning(
            "No SAlly mapping for MIDAS module '%s'; using generic display.",
            module_name,
        )
        return (module_name, "Unknown", "Unknown")

    def _translate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Translate parameter keys using the attribute map."""
        result: Dict[str, Any] = {}
        for k, v in params.items():
            new_key = self._attr_map.get(k, k)
            result[new_key] = v
        return result

    @staticmethod
    def _clean_key(key: str) -> str:
        """Normalize a MIDAS simulator key to a SAlly-friendly identifier."""
        return key.replace("-", "_").replace(" ", "_")
