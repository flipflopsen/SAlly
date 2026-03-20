import { Injectable } from '@angular/core';
import { AnomalyGuess, SensorData, Timestamp } from '@guardian/scada-shared';
import { Observable, ReplaySubject } from 'rxjs';
import { io, Socket } from "socket.io-client";

const REPLAY_KEEP_TIME = 10 * 1000; // 10 seconds

export interface TopologyData {
  buses: any[];
  lines: any[];
  transformers: any[];
  loads: any[];
  generators: any[];
  metadata?: any;
}

@Injectable({
  providedIn: 'root',
})
export class DataService {

  private socket: Socket;
  private stepSubject?: ReplaySubject<[Timestamp, SensorData]>;
  private anomalySubject?: ReplaySubject<AnomalyGuess>;
  private topologySubject?: ReplaySubject<TopologyData>;

  constructor() {
    this.socket = io();
  }

  step(): Observable<[Timestamp, SensorData]> {
    if (this.stepSubject) return this.stepSubject;
    this.stepSubject = new ReplaySubject(Infinity, REPLAY_KEEP_TIME);
    this.socket.on("step", (timestamp: Timestamp, sensorData: SensorData) => {
      this.stepSubject!.next([timestamp, sensorData]);
    });
    return this.stepSubject;
  }

  anomaly(): Observable<AnomalyGuess> {
    if (this.anomalySubject) return this.anomalySubject;
    this.anomalySubject = new ReplaySubject(Infinity, REPLAY_KEEP_TIME);
    this.socket.on("anomaly", (anomaly: AnomalyGuess) => {
      this.anomalySubject!.next(anomaly);
    });
    return this.anomalySubject;
  }

  topology(): Observable<TopologyData> {
    if (this.topologySubject) return this.topologySubject;
    this.topologySubject = new ReplaySubject(1); // Only keep the latest topology
    this.socket.on("topology", (topology: TopologyData) => {
      console.log("[DataService] Received topology:", topology);
      this.topologySubject!.next(topology);
    });
    return this.topologySubject;
  }
}
