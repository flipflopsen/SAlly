import { DeviceId } from ".";

export interface SensorData {
  load: Record<DeviceId, {
    p_mw: number;
    q_mvar: number;
  }>,

  sgen: Record<DeviceId, {
    p_mw: number;
    q_mvar: number;
  }>,

  bus: Record<DeviceId, {
    vm_pu: number;
    va_degree: number;
    p_mw: number;
    q_mvar: number;
  }>,

  trafo: Record<DeviceId, {
    loading_percent: number;
  }>,

  line: Record<DeviceId, {
    loading_percent: number;
  }>,
}
