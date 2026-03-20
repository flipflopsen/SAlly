"""
Infra-level service for MIDAS scenario import.

Integrates the MIDAS adapter with SAlly's event bus so that import events
are observable by the rest of the system (logging, telemetry, GUI state
updates).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sally.core.event_bus import EventBus
from sally.domain.events import Event
from sally.application.simulation.midas import MidasSimulationAdapter

logger = logging.getLogger(__name__)


class MidasImportStarted(Event):
    """Fired when a MIDAS import begins."""

    def __init__(self, scenario_name: str) -> None:
        super().__init__()
        self.scenario_name = scenario_name


class MidasImportCompleted(Event):
    """Fired when a MIDAS import finishes successfully."""

    def __init__(self, scenario_name: str, module_count: int, entity_count: int) -> None:
        super().__init__()
        self.scenario_name = scenario_name
        self.module_count = module_count
        self.entity_count = entity_count


class MidasImportFailed(Event):
    """Fired when a MIDAS import fails."""

    def __init__(self, scenario_name: str, error: str) -> None:
        super().__init__()
        self.scenario_name = scenario_name
        self.error = error


class MidasImportService:
    """
    Service that wraps :class:`MidasSimulationAdapter` and publishes
    lifecycle events on the SAlly event bus.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._adapter = MidasSimulationAdapter()

    async def import_scenario(
        self,
        scenario_name: str,
        *,
        config_file: Optional[str | Path] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run a MIDAS scenario and publish events.

        Returns the GUI-serializable scenario dict.
        """
        try:
            await self._bus.publish(MidasImportStarted(scenario_name))

            # Run the scenario via native MIDAS API
            self._adapter.run_scenario(
                scenario_name,
                config=config_file,
                params=params,
            )

            # Parse and map for GUI preview
            available = self._adapter.list_available_scenarios()
            matching = [s for s in available if s["name"] == scenario_name]
            gui_dict = matching[0] if matching else {"name": scenario_name}

            await self._bus.publish(
                MidasImportCompleted(
                    scenario_name=scenario_name,
                    module_count=gui_dict.get("module_count", 0),
                    entity_count=gui_dict.get("entity_count", 0),
                )
            )

            return gui_dict

        except Exception as exc:
            await self._bus.publish(
                MidasImportFailed(scenario_name, str(exc))
            )
            raise

    async def list_scenarios(
        self, search_dir: Optional[Path] = None
    ) -> List[Dict[str, Any]]:
        """List available MIDAS scenarios (non-blocking wrapper)."""
        return self._adapter.list_available_scenarios(search_dir)

    async def preview_scenario(
        self, path: str | Path, scenario_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parse and map a scenario, returning a GUI dict without running it."""
        scenario = self._adapter.parse(path)
        mapped = self._adapter.map(scenario)
        return self._adapter.to_gui_dict(mapped)
