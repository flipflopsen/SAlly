"""
Parse MIDAS scenario YAML files into a normalized intermediate representation.

MIDAS scenarios (e.g. ``four_bus.yml``, ``midasmv.yml``) use a declarative
YAML schema with top‑level scenario keys that declare:

  - ``modules``: an ordered list of MIDAS upgrade modules to activate
    (e.g. ``[store, powergrid, sndata]``).
  - ``*_params`` blocks: per‑module configuration keyed by scope name.
  - ``parent``: optional parent scenario for inheritance.
  - ``start_date``, ``end``, ``step_size``: timing parameters.

This module reads that schema and produces plain dataclasses that downstream
components can consume.  It does **not** import MIDAS itself — the actual
scenario construction is delegated to the MIDAS ``Configurator`` at
run‑time (see :class:`MidasSimulationAdapter`).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


# ── Intermediate representation ──────────────────────────────────────────────


@dataclass
class MidasModuleDef:
    """One MIDAS upgrade‑module reference from the ``modules`` list."""

    name: str  # e.g. "powergrid", "sndata", "weather"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MidasSimulatorDef:
    """One simulator derived from a module + scope in the YAML."""

    name: str
    module_name: str  # e.g. "powergrid"
    scope: str  # e.g. "four_bus"
    params: Dict[str, Any] = field(default_factory=dict)
    step_size: int = 900


@dataclass
class MidasEntityDef:
    """An entity inferred from a scope's config (e.g. a grid or load profile)."""

    sim_ref: str  # key into simulators
    model: str
    count: int = 1
    params: Dict[str, Any] = field(default_factory=dict)
    entity_id: Optional[str] = None


@dataclass
class MidasConnectionDef:
    """A connection between two entities."""

    src_sim: str
    src_entity: str
    src_attr: str
    dst_sim: str
    dst_entity: str
    dst_attr: str
    async_request: bool = False


@dataclass
class MidasScenario:
    """Complete parsed MIDAS scenario."""

    name: str
    duration: int  # seconds
    step_size: int  # default step size (seconds)
    start_date: Optional[str] = None
    parent: Optional[str] = None
    modules: List[str] = field(default_factory=list)
    simulators: Dict[str, MidasSimulatorDef] = field(default_factory=dict)
    entities: List[MidasEntityDef] = field(default_factory=list)
    connections: List[MidasConnectionDef] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    source_path: Optional[Path] = None


# ── Parser ───────────────────────────────────────────────────────────────────


class MidasScenarioParser:
    """Parse a MIDAS YAML scenario file into :class:`MidasScenario` objects.

    MIDAS YAML files contain one or more top‑level scenario keys
    (e.g. ``four_bus``, ``four_bus_der``).  Each scenario can inherit
    from a *parent* via the ``parent`` key.
    """

    # Known MIDAS module names
    _KNOWN_MODULES = {
        "store", "timesim", "powergrid", "powerseries",
        "sndata", "comdata", "dlpdata", "weather",
        "der", "sbdata", "pwdata",
    }

    def parse_file(self, path: Path | str) -> MidasScenario:
        """Read a YAML file and return a :class:`MidasScenario`.

        If the file contains multiple scenario keys, the *first* key is
        returned.  Use :meth:`parse_all` to get all of them.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"MIDAS scenario not found: {path}")

        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        scenarios = self._parse_all_dict(raw, source_path=path)
        if not scenarios:
            raise ValueError(f"No scenario blocks found in {path}")
        return scenarios[0]

    def parse_all(self, path: Path | str) -> List[MidasScenario]:
        """Return *all* scenario blocks in a YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"MIDAS scenario not found: {path}")

        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        return self._parse_all_dict(raw, source_path=path)

    def parse_string(self, content: str, *, name: str = "inline") -> MidasScenario:
        """Parse a YAML string (first scenario block)."""
        raw = yaml.safe_load(content)
        scenarios = self._parse_all_dict(raw)
        if not scenarios:
            raise ValueError("No scenario blocks found in YAML content")
        return scenarios[0]

    # ── internal ─────────────────────────────────────────────────────────

    def _parse_all_dict(
        self,
        raw: Dict[str, Any],
        *,
        source_path: Optional[Path] = None,
    ) -> List[MidasScenario]:
        """Parse all top‑level scenario keys from a YAML dict."""
        if not isinstance(raw, dict):
            raise ValueError("MIDAS YAML must be a mapping at the top level")

        # Resolve inheritance: build a dict of all raw blocks first
        resolved: Dict[str, Dict[str, Any]] = {}
        for key, block in raw.items():
            if not isinstance(block, dict):
                continue
            resolved[key] = self._resolve_inheritance(key, raw)

        results: List[MidasScenario] = []
        for key, block in resolved.items():
            try:
                scenario = self._parse_single_scenario(key, block, source_path)
                results.append(scenario)
            except Exception as exc:
                logger.warning("Failed to parse scenario '%s': %s", key, exc)

        return results

    def _resolve_inheritance(
        self, key: str, all_blocks: Dict[str, Any], _seen: Optional[set] = None
    ) -> Dict[str, Any]:
        """Walk the ``parent`` chain and merge configs (parent‑first)."""
        if _seen is None:
            _seen = set()
        if key in _seen:
            raise ValueError(f"Circular inheritance detected for '{key}'")
        _seen.add(key)

        block = dict(all_blocks.get(key, {}))
        parent_key = block.pop("parent", None)

        if parent_key and parent_key in all_blocks:
            parent = self._resolve_inheritance(parent_key, all_blocks, _seen)
            merged = self._deep_merge(parent, block)
            return merged

        return block

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge *override* into *base* (override wins)."""
        result = dict(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = MidasScenarioParser._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def _parse_single_scenario(
        self,
        name: str,
        block: Dict[str, Any],
        source_path: Optional[Path] = None,
    ) -> MidasScenario:
        """Parse one resolved scenario block."""

        # Timing
        duration = self._eval_expr(block.get("end", 86400))
        step_size = self._eval_expr(block.get("step_size", 900))
        start_date = block.get("start_date")

        # Modules
        modules = block.get("modules", [])
        if isinstance(modules, str):
            modules = [modules]

        # Build simulator + entity info from *_params blocks
        simulators: Dict[str, MidasSimulatorDef] = {}
        entities: List[MidasEntityDef] = []

        for mod_name in modules:
            params_key = f"{mod_name}_params"
            mod_params = block.get(params_key, {})

            if isinstance(mod_params, dict) and mod_params:
                # Each sub‑key is a "scope" (e.g. grid name)
                for scope, scope_params in mod_params.items():
                    if not isinstance(scope_params, dict):
                        # Single‑value param (e.g. store_params.filename)
                        sim_key = mod_name
                        simulators[sim_key] = MidasSimulatorDef(
                            name=sim_key,
                            module_name=mod_name,
                            scope=mod_name,
                            params=mod_params,
                            step_size=step_size,
                        )
                        break
                    else:
                        sim_key = f"{mod_name}_{scope}"
                        simulators[sim_key] = MidasSimulatorDef(
                            name=sim_key,
                            module_name=mod_name,
                            scope=scope,
                            params=scope_params,
                            step_size=step_size,
                        )
                        # Infer entities from scope params
                        self._extract_entities(mod_name, scope, scope_params, entities)
            else:
                simulators[mod_name] = MidasSimulatorDef(
                    name=mod_name,
                    module_name=mod_name,
                    scope=mod_name,
                    params={},
                    step_size=step_size,
                )

        return MidasScenario(
            name=name,
            duration=duration,
            step_size=step_size,
            start_date=str(start_date) if start_date else None,
            parent=block.get("parent"),
            modules=modules,
            simulators=simulators,
            entities=entities,
            connections=[],  # connections are built by MIDAS Configurator at run‑time
            raw=block,
            source_path=source_path,
        )

    def _extract_entities(
        self,
        mod_name: str,
        scope: str,
        scope_params: Dict[str, Any],
        entities: List[MidasEntityDef],
    ) -> None:
        """Infer entity definitions from scope params for display purposes."""

        if mod_name == "powergrid":
            gridfile = scope_params.get("gridfile", scope)
            entities.append(MidasEntityDef(
                sim_ref=f"powergrid_{scope}",
                model="Grid",
                params={"gridfile": gridfile, **{
                    k: v for k, v in scope_params.items() if k != "gridfile"
                }},
                entity_id=scope,
            ))

        elif mod_name in ("sndata", "comdata", "dlpdata"):
            mapping = scope_params.get("active_mapping", {})
            for bus_id, profiles in mapping.items():
                for profile_entry in (profiles if isinstance(profiles, list) else []):
                    if isinstance(profile_entry, list) and len(profile_entry) >= 2:
                        profile_name, scaling = profile_entry[0], profile_entry[1]
                        entities.append(MidasEntityDef(
                            sim_ref=f"{mod_name}_{scope}",
                            model="Load",
                            params={
                                "bus": bus_id,
                                "profile": profile_name,
                                "scaling": scaling,
                            },
                            entity_id=f"{scope}_bus{bus_id}_{profile_name}",
                        ))

        elif mod_name == "der":
            mapping = scope_params.get("mapping", {})
            for bus_id, ders in mapping.items():
                for der_entry in (ders if isinstance(ders, list) else []):
                    if isinstance(der_entry, list) and len(der_entry) >= 2:
                        der_type, capacity = der_entry[0], der_entry[1]
                        entities.append(MidasEntityDef(
                            sim_ref=f"der_{scope}",
                            model=der_type,
                            params={
                                "bus": bus_id,
                                "capacity": capacity,
                            },
                            entity_id=f"{scope}_bus{bus_id}_{der_type}",
                        ))

        elif mod_name == "weather":
            for provider, weather_cfg in scope_params.items():
                if isinstance(weather_cfg, dict) and "weather_mapping" in weather_cfg:
                    entities.append(MidasEntityDef(
                        sim_ref=f"weather_{scope}",
                        model="Weather",
                        params=weather_cfg,
                        entity_id=provider,
                    ))

    @staticmethod
    def _eval_expr(value: Any) -> int:
        """Evaluate simple arithmetic expressions like ``1*24*60*60`` or ``15*60``."""
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            # Only allow digits, *, +, -, spaces, parentheses
            cleaned = value.strip()
            if re.match(r'^[\d\s\*\+\-\(\)\.]+$', cleaned):
                try:
                    return int(eval(cleaned))  # noqa: S307
                except Exception:
                    pass
        return int(value) if value else 86400
