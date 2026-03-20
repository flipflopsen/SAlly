/**
 * MqttService - Bridge between Sally's MQTT bridge service and scada_web Socket.IO
 *
 * This service connects to Sally's mqtt_bridge_service.py and forwards data to the frontend
 * via Socket.IO. It handles:
 * - Sensor data: sensor/{category}/{device_id}
 * - Simulation metadata: meta/simulation/step-finished, meta/simulation/terminate
 * - Grid topology: topology (retained message)
 * - Anomaly detection: anomaly/{detector_name}
 */

import mqtt from 'mqtt';
import type { Server as SocketIOServer } from 'socket.io';
import type { SensorData } from '@guardian/scada-shared';

interface MqttConfig {
  host: string;
  port: number;
  username?: string;
  password?: string;
}

interface SensorMessage {
  device_id: string;
  category: string;
  values: Record<string, number>;
  timestamp: number;
}

interface StepFinishedMessage {
  step: number;
  timestamp: number;
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

export class MqttService {
  private client: mqtt.MqttClient | null = null;
  private io: SocketIOServer;
  private config: MqttConfig;
  private isConnected: boolean = false;
  private currentStepData: Map<string, any> = new Map();
  private currentTimestamp: number = 0;
  private topology: TopologyMessage | null = null;

  // Topic patterns matching Sally's mqtt_bridge_service.py
  private readonly SENSOR_TOPIC = 'sensor/+/+'; // sensor/{category}/{device_id}
  private readonly STEP_FINISHED_TOPIC = 'meta/simulation/step-finished';
  private readonly TERMINATE_TOPIC = 'meta/simulation/terminate';
  private readonly TOPOLOGY_TOPIC = 'topology';
  private readonly ANOMALY_TOPIC = 'anomaly/+'; // anomaly/{detector_name}

  constructor(io: SocketIOServer, config?: Partial<MqttConfig>) {
    this.io = io;
    this.config = {
      host: config?.host || process.env['SALLY_MQTT_HOST'] || 'localhost',
      port: config?.port || parseInt(process.env['SALLY_MQTT_PORT'] || '1883'),
      username: config?.username || process.env['SALLY_MQTT_USERNAME'],
      password: config?.password || process.env['SALLY_MQTT_PASSWORD'],
    };
  }

  /**
   * Start the MQTT service and connect to Sally's MQTT broker
   */
  async start(): Promise<void> {
    console.log('[MqttService] Starting MQTT bridge service...');
    console.log(`[MqttService] Connecting to mqtt://${this.config.host}:${this.config.port}`);

    return new Promise((resolve, reject) => {
      const connectUrl = `mqtt://${this.config.host}:${this.config.port}`;
      const options: mqtt.IClientOptions = {
        clean: true,
        connectTimeout: 5000,
        reconnectPeriod: 3000,
      };

      if (this.config.username && this.config.password) {
        options.username = this.config.username;
        options.password = this.config.password;
      }

      this.client = mqtt.connect(connectUrl, options);

      this.client.on('connect', () => {
        console.log('[MqttService] Connected to Sally MQTT broker');
        this.isConnected = true;
        this.subscribeToTopics();
        resolve();
      });

      this.client.on('error', (error) => {
        console.error('[MqttService] MQTT connection error:', error);
        if (!this.isConnected) {
          reject(error);
        }
      });

      this.client.on('reconnect', () => {
        console.log('[MqttService] Reconnecting to Sally MQTT broker...');
      });

      this.client.on('close', () => {
        console.log('[MqttService] Connection to Sally MQTT broker closed');
        this.isConnected = false;
      });

      this.client.on('message', (topic, payload) => {
        this.handleMessage(topic, payload);
      });
    });
  }

  /**
   * Subscribe to all relevant MQTT topics
   */
  private subscribeToTopics(): void {
    if (!this.client) return;

    const topics = [
      this.SENSOR_TOPIC,
      this.STEP_FINISHED_TOPIC,
      this.TERMINATE_TOPIC,
      this.TOPOLOGY_TOPIC,
      this.ANOMALY_TOPIC,
    ];

    topics.forEach(topic => {
      this.client!.subscribe(topic, { qos: 1 }, (err) => {
        if (err) {
          console.error(`[MqttService] Failed to subscribe to ${topic}:`, err);
        } else {
          console.log(`[MqttService] Subscribed to ${topic}`);
        }
      });
    });
  }

  /**
   * Handle incoming MQTT messages
   */
  private handleMessage(topic: string, payload: Buffer): void {
    try {
      const message = JSON.parse(payload.toString());

      if (topic.startsWith('sensor/')) {
        this.handleSensorMessage(topic, message);
      } else if (topic === this.STEP_FINISHED_TOPIC) {
        this.handleStepFinished(message);
      } else if (topic === this.TERMINATE_TOPIC) {
        this.handleTerminate(message);
      } else if (topic === this.TOPOLOGY_TOPIC) {
        this.handleTopology(message);
      } else if (topic.startsWith('anomaly/')) {
        this.handleAnomaly(topic, message);
      }
    } catch (error) {
      console.error(`[MqttService] Error parsing message from topic ${topic}:`, error);
    }
  }

  /**
   * Handle sensor data messages: sensor/{category}/{device_id}
   */
  private handleSensorMessage(topic: string, message: SensorMessage): void {
    const parts = topic.split('/');
    if (parts.length !== 3) return;

    const [, category, deviceId] = parts;
    const key = `${category}/${deviceId}`;

    // Accumulate sensor data for the current step
    this.currentStepData.set(key, {
      deviceId,
      category,
      values: message.values,
      timestamp: message.timestamp,
    });

    this.currentTimestamp = message.timestamp;
  }

  /**
   * Handle step-finished event - emit accumulated sensor data to frontend
   */
  private handleStepFinished(message: StepFinishedMessage): void {
    console.log(`[MqttService] Step ${message.step} finished at ${message.timestamp}`);

    // Convert accumulated data to SensorData format
    const sensorData: SensorData = {
      load: {},
      sgen: {},
      bus: {},
      trafo: {},
      line: {},
    };

    this.currentStepData.forEach((data, key) => {
      const { category, deviceId, values } = data;
      if (category in sensorData) {
        sensorData[category as keyof SensorData][deviceId] = values;
      }
    });

    // Emit to all connected Socket.IO clients
    this.io.emit('step', message.timestamp, sensorData);

    // Clear accumulated data for next step
    this.currentStepData.clear();
  }

  /**
   * Handle simulation terminate event
   */
  private handleTerminate(message: any): void {
    console.log('[MqttService] Simulation terminated');
    this.io.emit('terminate', message);
    this.currentStepData.clear();
  }

  /**
   * Handle grid topology message (retained)
   */
  private handleTopology(message: TopologyMessage): void {
    console.log('[MqttService] Received grid topology');
    this.topology = message;

    // Emit to all connected clients
    this.io.emit('topology', message);

    // Also emit to newly connecting clients
    this.io.on('connection', (socket) => {
      if (this.topology) {
        socket.emit('topology', this.topology);
      }
    });
  }

  /**
   * Handle anomaly detection messages: anomaly/{detector_name}
   */
  private handleAnomaly(topic: string, message: AnomalyMessage): void {
    const detectorName = topic.split('/')[1];
    console.log(`[MqttService] Anomaly detected by ${detectorName}:`, message.anomaly_type);

    // Emit to all connected Socket.IO clients
    this.io.emit('anomaly', message);
  }

  /**
   * Stop the MQTT service and disconnect
   */
  async stop(): Promise<void> {
    console.log('[MqttService] Stopping MQTT bridge service...');

    if (this.client) {
      return new Promise((resolve) => {
        this.client!.end(false, {}, () => {
          console.log('[MqttService] Disconnected from Sally MQTT broker');
          this.isConnected = false;
          this.client = null;
          resolve();
        });
      });
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
