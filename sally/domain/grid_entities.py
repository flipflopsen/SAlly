from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class EntityType(Enum):
    """Grid entity types with their measurement characteristics"""
    # PyPower entity types
    PYPOWER_NODE = "pypower node"  # p, q, va, vl, vm
    PYPOWER_BRANCH = "pypower branch"  # p_from, p_to, q_from
    PYPOWER_TR_PRI = "pypower tr_pri"  # p, q, va, vl, vm
    PYPOWER_TR_SEC = "pypower tr_sec"  # p, q, va, vl, vm
    PYPOWER_TRANSFORMER = "pypower transformer"  # p_from, p_to, q_from

    # PandaPower entity types (Guardian-compatible)
    PANDAPOWER_BUS = "pandapower bus"  # vm_pu, va_degree, p_mw, q_mvar
    PANDAPOWER_LOAD = "pandapower load"  # p_mw, q_mvar, sn_mva
    PANDAPOWER_SGEN = "pandapower sgen"  # p_mw, q_mvar, min_p_mw, max_p_mw
    PANDAPOWER_TRAFO = "pandapower trafo"  # loading_percent
    PANDAPOWER_LINE = "pandapower line"  # loading_percent, max_i_ka
    PANDAPOWER_SWITCH = "pandapower switch"  # in_service, closed
    PANDAPOWER_EXT_GRID = "pandapower ext_grid"  # reference bus

    # Simulation entity types
    HOUSEHOLD_SIM = "household-sim house"  # p_out
    CSV_PV = "csv PV"  # p
    WIND_TURBINE = "wind turbine"  # p, q
    BATTERY_ESS = "battery ess"  # p, q (can be negative for charging)
    LOAD_BUS = "load bus"  # p, q


@dataclass
class GridMeasurement:
    """Represents a single grid measurement for any entity type"""
    entity: str
    entity_type: EntityType
    timestamp: float

    # Power measurements (PyPower format)
    p: Optional[float] = None  # Active power
    p_out: Optional[float] = None  # Power output (generation)
    p_from: Optional[float] = None  # Power flow from
    p_to: Optional[float] = None  # Power flow to

    # Reactive power measurements (PyPower format)
    q: Optional[float] = None  # Reactive power
    q_from: Optional[float] = None  # Reactive power flow

    # Voltage measurements (PyPower format)
    va: Optional[float] = None  # Voltage angle (radians)
    vl: Optional[float] = None  # Voltage level
    vm: Optional[float] = None  # Voltage magnitude (p.u.)

    # PandaPower / Guardian-compatible measurements
    p_mw: Optional[float] = None  # Active power in MW
    q_mvar: Optional[float] = None  # Reactive power in Mvar
    vm_pu: Optional[float] = None  # Voltage magnitude per-unit
    va_degree: Optional[float] = None  # Voltage angle in degrees
    loading_percent: Optional[float] = None  # Line/Trafo loading percentage
    max_i_ka: Optional[float] = None  # Maximum current in kA
    sn_mva: Optional[float] = None  # Apparent power rating in MVA
    min_p_mw: Optional[float] = None  # Minimum active power in MW
    max_p_mw: Optional[float] = None  # Maximum active power in MW
    vn_kv: Optional[float] = None  # Nominal voltage in kV

    # Switch states
    in_service: Optional[bool] = None  # Whether element is in service
    closed: Optional[bool] = None  # Whether switch is closed

    # Environmental
    humidity: Optional[float] = None  # Relative humidity %

    # Metadata
    metadata: Optional[Dict[str, Any]] = None

    def validate_measurements(self) -> bool:
        """Validate that measurements align with entity type"""
        expected_fields = {
            # PyPower types
            EntityType.PYPOWER_NODE: ['p', 'q', 'va', 'vl', 'vm'],
            EntityType.PYPOWER_BRANCH: ['p_from', 'p_to', 'q_from'],
            EntityType.PYPOWER_TR_PRI: ['p', 'q', 'va', 'vl', 'vm'],
            EntityType.PYPOWER_TR_SEC: ['p', 'q', 'va', 'vl', 'vm'],
            EntityType.PYPOWER_TRANSFORMER: ['p_from', 'p_to', 'q_from'],
            # PandaPower types
            EntityType.PANDAPOWER_BUS: ['vm_pu', 'va_degree'],
            EntityType.PANDAPOWER_LOAD: ['p_mw', 'q_mvar'],
            EntityType.PANDAPOWER_SGEN: ['p_mw', 'q_mvar'],
            EntityType.PANDAPOWER_TRAFO: ['loading_percent'],
            EntityType.PANDAPOWER_LINE: ['loading_percent'],
            EntityType.PANDAPOWER_SWITCH: [],  # No required measurements
            EntityType.PANDAPOWER_EXT_GRID: [],  # Reference bus
            # Simulation types
            EntityType.HOUSEHOLD_SIM: ['p_out'],
            EntityType.CSV_PV: ['p'],
            EntityType.WIND_TURBINE: ['p', 'q'],
            EntityType.BATTERY_ESS: ['p', 'q'],
            EntityType.LOAD_BUS: ['p', 'q']
        }

        required_fields = expected_fields.get(self.entity_type, [])
        for field in required_fields:
            if getattr(self, field) is None:
                return False
        return True

    def to_guardian_format(self, category: str) -> Dict[str, Any]:
        """Convert measurement to Guardian-compatible sensor data format."""
        import math

        payload: Dict[str, Any] = {}

        if category == "bus":
            # Bus: vm_pu, va_degree, p_mw, q_mvar
            payload["vm_pu"] = self.vm_pu if self.vm_pu is not None else self.vm
            if self.va_degree is not None:
                payload["va_degree"] = self.va_degree
            elif self.va is not None:
                payload["va_degree"] = math.degrees(self.va)
            payload["p_mw"] = self.p_mw if self.p_mw is not None else self.p
            payload["q_mvar"] = self.q_mvar if self.q_mvar is not None else self.q

        elif category in ("load", "sgen"):
            # Load/Sgen: p_mw, q_mvar
            if self.p_mw is not None:
                payload["p_mw"] = self.p_mw
            elif self.p is not None:
                payload["p_mw"] = self.p
            elif self.p_out is not None:
                payload["p_mw"] = self.p_out
            payload["q_mvar"] = self.q_mvar if self.q_mvar is not None else self.q

        elif category in ("trafo", "line"):
            # Trafo/Line: loading_percent
            payload["loading_percent"] = self.loading_percent or 0.0

        # Remove None values
        return {k: v for k, v in payload.items() if v is not None}
