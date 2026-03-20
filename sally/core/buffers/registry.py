"""
Buffer registry for automatic buffer selection based on usage scenario.

This module provides functions to select the most appropriate buffer
implementation based on the detected producer/consumer scenario.
"""

import logging
from typing import List, Optional, Type

from .base import BufferScenario, EventBusBuffer
from .ring_buffer import RingBuffer
from .mpsc_buffer import MPSCBuffer
from .spmc_buffer import SPMCBuffer
from .mpmc_buffer import MPMCBuffer


logger = logging.getLogger(__name__)


# Default buffer types to use. EventBus will select the most appropriate buffer
# from this list based on the detected scenario.
# Order: [SPSC, SPMC, MPSC, MPMC] - EventBus will use the first suitable one.
AVAILABLE_BUFFERS: List[Type[EventBusBuffer]] = [RingBuffer, SPMCBuffer, MPSCBuffer, MPMCBuffer]


def get_buffer_for_scenario(
    scenario: str,
    capacity: int,
    available_buffers: Optional[List[Type[EventBusBuffer]]] = None
) -> EventBusBuffer:
    """
    Select and instantiate the most appropriate buffer for a scenario.

    Args:
        scenario: The detected scenario (SPSC, SPMC, MPSC, MPMC)
        capacity: Buffer capacity
        available_buffers: List of buffer classes to choose from

    Returns:
        Instantiated buffer appropriate for the scenario
    """
    buffers = available_buffers or AVAILABLE_BUFFERS

    # Map scenarios to buffer classes
    scenario_map = {
        BufferScenario.SPSC: RingBuffer,
        BufferScenario.SPMC: SPMCBuffer,
        BufferScenario.MPSC: MPSCBuffer,
        BufferScenario.MPMC: MPMCBuffer,
    }

    # Find the best match from available buffers
    preferred = scenario_map.get(scenario, MPMCBuffer)

    # Check if preferred is in available buffers
    if preferred in buffers:
        return preferred(capacity)

    # Fallback logic: if we need thread-safety, escalate to a safer buffer
    if scenario in (BufferScenario.MPSC, BufferScenario.MPMC):
        # Need producer thread-safety
        for buf_class in [MPMCBuffer, MPSCBuffer]:
            if buf_class in buffers:
                logger.info("Using %s as fallback for scenario %s", buf_class.__name__, scenario)
                return buf_class(capacity)

    if scenario in (BufferScenario.SPMC, BufferScenario.MPMC):
        # Need consumer thread-safety
        for buf_class in [MPMCBuffer, SPMCBuffer]:
            if buf_class in buffers:
                logger.info("Using %s as fallback for scenario %s", buf_class.__name__, scenario)
                return buf_class(capacity)

    # Last resort: use whatever is available, prefer MPMC for safety
    if MPMCBuffer in buffers:
        return MPMCBuffer(capacity)

    # Use first available
    if buffers:
        logger.warning(
            "No ideal buffer for scenario %s, using %s",
            scenario, buffers[0].__name__
        )
        return buffers[0](capacity)

    # Should never happen
    raise ValueError("No buffer types available")
