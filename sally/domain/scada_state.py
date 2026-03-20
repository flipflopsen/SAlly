from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sally.domain.grid_entities import GridMeasurement


@dataclass
class RuleStatus:
    rule_id: str
    entity_name: str
    variable_name: str
    action: str
    timestamp: float
    severity: str = "WARNING"


@dataclass
class AnomalyInfo:
    entity: str
    anomaly_type: str
    severity: str
    timestamp: float
    details: Optional[str] = None


@dataclass
class SCADAState:
    grid_measurements: Dict[str, GridMeasurement] = field(default_factory=dict)
    triggered_rules: List[RuleStatus] = field(default_factory=list)
    anomalies: List[AnomalyInfo] = field(default_factory=list)
    setpoints: Dict[str, float] = field(default_factory=dict)
    simulation_time: float = 0.0
    last_update: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def update_measurement(self, measurement: GridMeasurement) -> None:
        with self._lock:
            self.grid_measurements[measurement.entity] = measurement
            self.last_update = time.time()

    def add_triggered_rule(self, rule_status: RuleStatus, max_history: int = 50) -> None:
        with self._lock:
            self.triggered_rules.append(rule_status)
            if len(self.triggered_rules) > max_history:
                self.triggered_rules = self.triggered_rules[-max_history:]
            self.last_update = time.time()

    def add_anomaly(self, anomaly: AnomalyInfo, max_history: int = 50) -> None:
        with self._lock:
            self.anomalies.append(anomaly)
            if len(self.anomalies) > max_history:
                self.anomalies = self.anomalies[-max_history:]
            self.last_update = time.time()

    def update_setpoint(self, key: str, value: float) -> None:
        with self._lock:
            self.setpoints[key] = value
            self.last_update = time.time()

    def clear_setpoints(self) -> None:
        with self._lock:
            self.setpoints.clear()
            self.last_update = time.time()

    def remove_setpoint(self, key: str) -> bool:
        """Remove a single setpoint. Returns True if removed, False if not found."""
        with self._lock:
            if key in self.setpoints:
                del self.setpoints[key]
                self.last_update = time.time()
                return True
            return False

    def update_simulation_time(self, sim_time: float) -> None:
        with self._lock:
            self.simulation_time = sim_time
            self.last_update = time.time()

    def snapshot(self) -> "SCADAState":
        with self._lock:
            return SCADAState(
                grid_measurements=dict(self.grid_measurements),
                triggered_rules=list(self.triggered_rules),
                anomalies=list(self.anomalies),
                setpoints=dict(self.setpoints),
                simulation_time=self.simulation_time,
                last_update=self.last_update,
            )
