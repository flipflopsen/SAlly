from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class SimulationStep:
    """Represents a single simulation step with its data and context"""
    step_number: int
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    triggered_rules: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SimulationTrace:
    """Captures the complete execution trace of a simulation"""
    steps: List[SimulationStep] = field(default_factory=list)
    total_steps: int = 0
    success: bool = True
    error_message: Optional[str] = None
