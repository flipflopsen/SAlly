import { Timestamp, DeviceId, DeviceType } from ".";

/** Represents the anomaly guess provided by the DT Env. */
export interface AnomalyGuess {
  infected_bus: `${DeviceType}/${DeviceId}`,
  p_anomaly: number,
  correct_guess: boolean,
  timestamp: Timestamp,
  detector: string,
}
