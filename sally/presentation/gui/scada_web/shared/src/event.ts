import { Timestamp, DeviceId, DeviceType } from ".";

export interface Event {
    timestamp: Timestamp,
    bus: `${DeviceType}/${DeviceId}`,
    detector: string,
    name: string,
    event_info: string,
}
