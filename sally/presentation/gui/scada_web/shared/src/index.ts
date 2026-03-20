import { SensorData } from ".";

export * from "./sensor-data";
export * from "./anomaly";
export * from "./grafana";

export type Timestamp = number;
export type DeviceId = string;
export type DeviceType = keyof SensorData;
