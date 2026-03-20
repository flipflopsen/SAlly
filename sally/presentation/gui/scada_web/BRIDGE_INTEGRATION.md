# Sally Bridge Integration - Implementation Summary

## Overview

This document describes the implementation of the bridge services that connect Sally's Python simulation engine with the scada_web TypeScript frontend/backend.

## What Was Implemented

### 1. Backend Services

#### MqttService.ts (`backend/src/MqttService.ts`)
- **Purpose**: Connects to Sally's MQTT bridge service and forwards data to frontend via Socket.IO
- **Features**:
  - Subscribes to MQTT topics: `sensor/{category}/{device_id}`, `meta/simulation/*`, `topology`, `anomaly/*`
  - Aggregates sensor data per simulation step
  - Forwards topology, sensor data, and anomalies to frontend
  - Automatic reconnection with exponential backoff
  - Status reporting endpoint

#### WebSocketService.ts (`backend/src/WebSocketService.ts`)
- **Purpose**: Direct WebSocket bridge to Sally's websocket_bridge_service.py
- **Features**:
  - Connects to Sally's Socket.IO server (default port 3001)
  - Receives events: `step`, `topology`, `anomaly`, `terminate`
  - Forwards all events to frontend clients
  - Automatic reconnection
  - Status reporting endpoint

### 2. Backend Integration

#### Updated `backend/src/index.ts`
- **SALLY_BRIDGE_MODE** environment variable support:
  - `mqtt` - Use MqttService for data flow
  - `websocket` - Use WebSocketService for data flow
  - `legacy` - Use existing InfluxDB + MQTT polling (default)
- **Features Added**:
  - Bridge service initialization on startup
  - Enhanced health check endpoint with bridge status
  - Graceful shutdown handlers (SIGTERM/SIGINT)
  - Topology forwarding to newly connected clients

### 3. Frontend Integration

#### Updated `frontend/src/app/dashboard/data.service.ts`
- **New Feature**: `topology()` observable
  - Returns ReplaySubject with latest topology data
  - Subscribes to Socket.IO "topology" event
  - Uses ReplaySubject(1) to cache the latest topology

#### Updated `frontend/src/app/grid/grid.component.ts`
- **New Features**:
  - Injects DataService for real-time data subscriptions
  - Subscribes to topology updates from Sally bridge
  - Subscribes to real-time sensor data (`step` events)
  - `updateGridWithSensorData()` method updates grid visualization:
    - Bus voltages (`vm_pu`)
    - Line loading (`loading_percent`)
    - Load power (`p_mw`, `q_mvar`)
    - Generator power (`p_mw`, `q_mvar`)
    - Transformer loading (`loading_percent`)

## Environment Variables

### Sally Bridge Service (Python)

These are configured in Sally's `config/default.yml` or via environment:

```bash
# MQTT Bridge Mode
SALLY_MQTT_HOST=localhost
SALLY_MQTT_PORT=1883
SALLY_MQTT_USERNAME=<optional>
SALLY_MQTT_PASSWORD=<optional>

# WebSocket Bridge Mode
SALLY_WS_HOST=localhost
SALLY_WS_PORT=3001
```

### SCADA Web Backend (Node.js)

```bash
# Bridge Mode Selection
SALLY_BRIDGE_MODE=mqtt    # or 'websocket' or 'legacy'
SALLY_MODE=true           # Enable Sally mode

# For MQTT bridge mode
SALLY_MQTT_HOST=localhost
SALLY_MQTT_PORT=1883
SALLY_MQTT_USERNAME=<optional>
SALLY_MQTT_PASSWORD=<optional>

# For WebSocket bridge mode
SALLY_WS_HOST=localhost
SALLY_WS_PORT=3001
```

## Data Flow Architecture

### MQTT Bridge Mode

```
Sally Simulation → mqtt_bridge_service.py → MQTT Broker
                                                ↓
                    MqttService (scada_web backend) → Socket.IO
                                                        ↓
                            Frontend (DataService) → Angular Components
```

### WebSocket Bridge Mode

```
Sally Simulation → websocket_bridge_service.py (Socket.IO server)
                                ↓
        WebSocketService (scada_web backend) → Socket.IO
                                ↓
            Frontend (DataService) → Angular Components
```

### Legacy Mode

```
Sally Simulation → InfluxDB
                      ↓
    Backend polls InfluxDB + MQTT → Socket.IO
                                      ↓
                    Frontend → Angular Components
```

## MQTT Topic Structure

Sally's mqtt_bridge_service.py publishes to these topics:

- `sensor/{category}/{device_id}` - Real-time sensor measurements
  - Categories: `load`, `sgen`, `bus`, `trafo`, `line`
  - Payload: `{ device_id, category, values: {...}, timestamp }`

- `meta/simulation/step-finished` - Simulation step completion
  - Payload: `{ step, timestamp }`

- `meta/simulation/terminate` - Simulation termination

- `topology` - Grid topology (retained message)
  - Payload: `{ buses, lines, transformers, loads, generators, metadata }`

- `anomaly/{detector_name}` - Anomaly detection events
  - Payload: `{ detector, anomaly_type, device_id, severity, confidence, timestamp, details }`

## Socket.IO Events (Backend → Frontend)

- **`step`** - Simulation step with sensor data
  - Args: `(timestamp: number, sensorData: SensorData)`
  - SensorData structure: `{ load: {}, sgen: {}, bus: {}, trafo: {}, line: {} }`

- **`topology`** - Grid topology data
  - Args: `(topology: TopologyData)`

- **`anomaly`** - Anomaly detection event
  - Args: `(anomaly: AnomalyMessage)`

- **`terminate`** - Simulation terminated
  - Args: `(data: any)`

## Testing the Integration

### 1. Start Sally with Bridge Service

**MQTT Bridge Mode:**
```powershell
cd A:\Thesis-Code\thesis-sally-repo
$env:SALLY_OTEL_ENABLED='true'
$env:SALLY_MQTT_HOST='localhost'
$env:SALLY_MQTT_PORT='1883'
python -m sally.main_scada_web --bridge-mode mqtt --with-gui
```

**WebSocket Bridge Mode:**
```powershell
cd A:\Thesis-Code\thesis-sally-repo
$env:SALLY_OTEL_ENABLED='true'
python -m sally.main_scada_web --bridge-mode websocket --with-gui
```

### 2. Start SCADA Web Backend

```powershell
cd A:\Thesis-Code\thesis-sally-repo\sally\presentation\gui\scada_web
$env:SALLY_BRIDGE_MODE='mqtt'  # or 'websocket'
$env:SALLY_MODE='true'
$env:SALLY_MQTT_HOST='localhost'
$env:SALLY_MQTT_PORT='1883'
pnpm run dev:backend
```

Expected output:
```
[Server] Initializing MQTT bridge service...
[MqttService] Connecting to mqtt://localhost:1883
[MqttService] Connected to Sally MQTT broker
[MqttService] Subscribed to sensor/+/+
[MqttService] Subscribed to meta/simulation/step-finished
[MqttService] Subscribed to topology
[MqttService] Subscribed to anomaly/+
Server running at 0.0.0.0:3000
Mode: Sally
Bridge Mode: mqtt
```

### 3. Start SCADA Web Frontend

```powershell
cd A:\Thesis-Code\thesis-sally-repo\sally\presentation\gui\scada_web\frontend
ng serve
# or
pnpm run start
```

### 4. Access the Application

- **Frontend**: http://localhost:4200
- **Dashboard**: http://localhost:4200/dashboard
- **Grid View**: http://localhost:4200/grid
- **Health Check**: http://localhost:3000/api/v0/health

Expected health check response with bridge mode:
```json
{
  "status": "ok",
  "mode": "sally",
  "bridgeMode": "mqtt",
  "timestamp": 1707494400000,
  "bridge": {
    "connected": true,
    "topology": true,
    "host": "localhost",
    "port": 1883
  }
}
```

### 5. Verify Data Flow

**Dashboard:**
- Should show real-time sensor data charts updating every simulation step
- Anomaly notifications should appear when rules are triggered

**Grid View:**
- Should load topology and display the power grid layout
- Bus colors should update based on voltage levels
- Line thickness/color should indicate loading
- Clicking on elements should show real-time power values

**Browser Console:**
```
[DataService] Received topology: { buses: [...], lines: [...], ... }
[GridComponent] Received topology from Sally: { ... }
```

**Backend Console:**
```
[MqttService] Step 42 finished at 1707494400000
[MqttService] Received grid topology
[MqttService] Anomaly detected by voltage_monitor: overvoltage
```

## Troubleshooting

### Backend doesn't connect to MQTT broker
- Verify MQTT broker is running: `mosquitto -v` or check Sally logs
- Check firewall settings for port 1883
- Verify SALLY_MQTT_HOST and SALLY_MQTT_PORT environment variables
- Check backend console for connection errors

### Frontend shows no data
- Check browser DevTools Console for Socket.IO connection errors
- Verify backend is running and healthy: `curl http://localhost:3000/api/v0/health`
- Check that SALLY_BRIDGE_MODE is set correctly in backend
- Verify Sally bridge services are running and publishing data

### Grid view is empty
- Check that topology event was received in browser console
- Verify topology endpoint: `curl http://localhost:3000/api/v0/grid-topology-sally`
- Check Sally logs for topology publication
- Ensure MQTT/WebSocket bridge is connected

### Sensor data not updating
- Verify Sally simulation is running (check logs for "Step X finished")
- Check backend console for "Step X finished" messages from MqttService
- Use MQTT client to verify data: `mosquitto_sub -h localhost -t 'sensor/#' -v`
- Check browser DevTools Network tab for Socket.IO messages

## Build Commands

```powershell
# Build all packages
cd sally/presentation/gui/scada_web
pnpm run build

# Build individually
pnpm run build:shared    # Build shared types
pnpm run build:backend   # Build backend (includes new services)
pnpm run build:frontend  # Build frontend (Angular 18)
```

## Package Dependencies Added

**Backend:**
- `socket.io-client@^4.7.2` - For WebSocketService to connect to Sally's WebSocket bridge

**All other dependencies were already present in the updated packages.**

## API Endpoints

### Health Check
**GET** `/api/v0/health`

Returns server status and bridge connection info:
```json
{
  "status": "ok",
  "mode": "sally",
  "bridgeMode": "mqtt",
  "timestamp": 1707494400000,
  "bridge": {
    "connected": true,
    "topology": true,
    "host": "localhost",
    "port": 1883
  }
}
```

### Grid Topology (Sally)
**GET** `/api/v0/grid-topology-sally`

Returns the grid topology received from Sally bridge.

### Legacy Endpoints (Still Available)
- **GET** `/api/v0/grid-topology` - CIM topology
- **GET** `/api/v0/grid-topology-no-cim` - PandaPower topology
- **GET** `/api/v0/initial-grid-data` - Initial data from InfluxDB
- **POST** `/api/v0/layout` - Save grid layout
- **GET** `/api/v0/layout` - Load grid layout

## Next Steps

1. **Test with actual Sally simulation** - Verify data flow works end-to-end
2. **Optimize bundle size** - Current bundle is 707KB (exceeds 512KB budget)
3. **Restore Bulma CSS** - Upgrade Sass or find alternative styling solution
4. **Add error boundaries** - Better error handling in Angular components
5. **Add loading states** - Show spinners while waiting for topology/data
6. **Add reconnection UI** - Show connection status in frontend
7. **Add metrics** - Track message rates, latency, connection health
8. **Add tests** - Unit tests for services and integration tests

## Files Changed/Created

### Created:
- `backend/src/MqttService.ts` (290 lines)
- `backend/src/WebSocketService.ts` (155 lines)
- `BRIDGE_INTEGRATION.md` (this file)

### Modified:
- `backend/src/index.ts` - Added bridge service initialization and graceful shutdown
- `backend/package.json` - Added socket.io-client dependency
- `frontend/src/app/dashboard/data.service.ts` - Added topology() observable
- `frontend/src/app/grid/grid.component.ts` - Added DataService subscription and real-time updates
- `frontend/src/styles.scss` - Commented out Bulma import (compatibility issue)

## Architecture Benefits

1. **Decoupled** - Sally and scada_web communicate through well-defined interfaces
2. **Flexible** - Support multiple bridge modes (MQTT, WebSocket, Legacy)
3. **Real-time** - Push-based architecture for low-latency updates
4. **Scalable** - MQTT broker can handle multiple subscribers
5. **Resilient** - Automatic reconnection on connection failures
6. **Observable** - Health endpoints and logging for monitoring

## References

- Sally MQTT Bridge: `sally/infrastructure/services/mqtt_bridge_service.py`
- Sally WebSocket Bridge: `sally/infrastructure/services/websocket_bridge_service.py`
- Sally Configuration: `sally/config/default.yml`
- SCADA Web Package Manager: `PNPM_MIGRATION.md`
