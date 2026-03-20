/**
 * WebSocketService - Bridge between Sally's WebSocket bridge service and scada_web Socket.IO
 *
 * This service connects to Sally's websocket_bridge_service.py and forwards data to the frontend
 * via Socket.IO. It handles:
 * - Sensor data: 'step' event with (timestamp, sensor_data)
 * - Grid topology: 'topology' event
 * - Anomaly detection: 'anomaly' event
 * - Simulation termination: 'terminate' event
 */

import { io as socketIOClient, Socket } from 'socket.io-client';
import type { Server as SocketIOServer } from 'socket.io';
import type { SensorData } from '@guardian/scada-shared';

interface WebSocketConfig {
  host: string;
  port: number;
  path?: string;
}

interface TopologyMessage {
  buses: any[];
  lines: any[];
  transformers: any[];
  loads: any[];
  generators: any[];
  metadata?: any;
}

interface AnomalyMessage {
  detector: string;
  anomaly_type: string;
  device_id: string;
  severity: string;
  confidence: number;
  timestamp: number;
  details?: any;
}

export class WebSocketService {
  private sallyClient: Socket | null = null;
  private io: SocketIOServer;
  private config: WebSocketConfig;
  private isConnected: boolean = false;
  private topology: TopologyMessage | null = null;

  constructor(io: SocketIOServer, config?: Partial<WebSocketConfig>) {
    this.io = io;
    this.config = {
      host: config?.host || process.env['SALLY_WS_HOST'] || 'localhost',
      port: config?.port || parseInt(process.env['SALLY_WS_PORT'] || '3001'),
      path: config?.path || '/socket.io',
    };
  }

  /**
   * Start the WebSocket service and connect to Sally's WebSocket bridge
   */
  async start(): Promise<void> {
    console.log('[WebSocketService] Starting WebSocket bridge service...');
    const url = `http://${this.config.host}:${this.config.port}`;
    console.log(`[WebSocketService] Connecting to ${url}`);

    return new Promise((resolve, reject) => {
      this.sallyClient = socketIOClient(url, {
        path: this.config.path,
        reconnection: true,
        reconnectionDelay: 3000,
        reconnectionAttempts: 10,
      });

      this.sallyClient.on('connect', () => {
        console.log('[WebSocketService] Connected to Sally WebSocket bridge');
        this.isConnected = true;
        this.setupEventHandlers();
        resolve();
      });

      this.sallyClient.on('connect_error', (error: Error) => {
        console.error('[WebSocketService] Connection error:', error.message);
        if (!this.isConnected) {
          reject(error);
        }
      });

      this.sallyClient.on('disconnect', (reason: string) => {
        console.log(`[WebSocketService] Disconnected from Sally: ${reason}`);
        this.isConnected = false;
      });

      this.sallyClient.on('reconnect', (attemptNumber: number) => {
        console.log(`[WebSocketService] Reconnected to Sally (attempt ${attemptNumber})`);
        this.isConnected = true;
      });
    });
  }

  /**
   * Setup event handlers for Sally WebSocket bridge events
   */
  private setupEventHandlers(): void {
    if (!this.sallyClient) return;

    // Handle simulation step data
    this.sallyClient.on('step', (timestamp: number, sensorData: SensorData) => {
      console.log(`[WebSocketService] Received step data at ${timestamp}`);
      // Forward to all connected frontend clients
      this.io.emit('step', timestamp, sensorData);
    });

    // Handle grid topology
    this.sallyClient.on('topology', (topology: TopologyMessage) => {
      console.log('[WebSocketService] Received grid topology');
      this.topology = topology;

      // Forward to all connected frontend clients
      this.io.emit('topology', topology);

      // Also emit to newly connecting clients
      this.io.on('connection', (socket) => {
        if (this.topology) {
          socket.emit('topology', this.topology);
        }
      });
    });

    // Handle anomaly detection
    this.sallyClient.on('anomaly', (anomaly: AnomalyMessage) => {
      console.log(`[WebSocketService] Anomaly detected: ${anomaly.anomaly_type}`);
      // Forward to all connected frontend clients
      this.io.emit('anomaly', anomaly);
    });

    // Handle simulation termination
    this.sallyClient.on('terminate', (data: any) => {
      console.log('[WebSocketService] Simulation terminated');
      // Forward to all connected frontend clients
      this.io.emit('terminate', data);
    });

    // Handle errors
    this.sallyClient.on('error', (error: any) => {
      console.error('[WebSocketService] Sally bridge error:', error);
    });
  }

  /**
   * Stop the WebSocket service and disconnect
   */
  async stop(): Promise<void> {
    console.log('[WebSocketService] Stopping WebSocket bridge service...');

    if (this.sallyClient) {
      this.sallyClient.disconnect();
      this.sallyClient = null;
      this.isConnected = false;
      console.log('[WebSocketService] Disconnected from Sally WebSocket bridge');
    }
  }

  /**
   * Get current service status
   */
  getStatus(): { connected: boolean; topology: boolean; host: string; port: number } {
    return {
      connected: this.isConnected,
      topology: this.topology !== null,
      host: this.config.host,
      port: this.config.port,
    };
  }

  /**
   * Get current topology if available
   */
  getTopology(): TopologyMessage | null {
    return this.topology;
  }
}
