"""
Sally Infrastructure Services

Service modules for SCADA orchestration, data bridging, and integrations.
"""

from sally.infrastructure.services.scada_orchestration_service import (
    SCADAOrchestrationService,
    SCADAOrchestrationConfig,
)

# Optional imports - only available if dependencies are installed
try:
    from sally.infrastructure.services.mqtt_bridge_service import (
        MqttBridgeService,
        MqttBridgeConfig,
    )
except ImportError:
    MqttBridgeService = None
    MqttBridgeConfig = None

try:
    from sally.infrastructure.services.websocket_bridge_service import (
        WebSocketBridgeService,
        WebSocketBridgeConfig,
    )
except ImportError:
    WebSocketBridgeService = None
    WebSocketBridgeConfig = None

__all__ = [
    "SCADAOrchestrationService",
    "SCADAOrchestrationConfig",
    "MqttBridgeService",
    "MqttBridgeConfig",
    "WebSocketBridgeService",
    "WebSocketBridgeConfig",
]
