import mqtt, { MqttClient, connectAsync } from "mqtt";
import { Readable } from "stream";
import * as mqttUtil from "./mqtt.js";
import { QueryApi } from "@influxdata/influxdb-client";
import { queryInitialGridData } from "./influx.js";
import * as shared from "@guardian/scada-shared";
import { Timestamp } from "@guardian/scada-shared";

const SENSOR_TOPIC_WILDCARD = "sensor/#";
const STEP_FINISHED_TOPIC = "meta/simulation/step-finished";
const TERMINATE_TOPIC = "meta/simulation/terminate";

/** Sensor data for a single timestamp. */
export class SensorData implements shared.SensorData {
  load: shared.SensorData["load"] = {};
  sgen: shared.SensorData["sgen"] = {};
  bus: shared.SensorData["bus"] = {};
  trafo: shared.SensorData["trafo"] = {};
  line: shared.SensorData["line"] = {};

  static async * stream(
    queryApi: QueryApi
  ): AsyncGenerator<[Timestamp, SensorData]> {
    let lastTimestamp = -1;

    // start stream early to start the mqtt client
    let mqttStream = SensorData.mqttStream();

    let influxData = await SensorData.fetchInflux(queryApi);
    for (let [timestampKey, sensorData] of Object.entries(influxData)) {
      let timestamp = +timestampKey;
      lastTimestamp = timestamp;
      yield [timestamp, sensorData];
    }

    for await (let [timestamp, sensorData] of mqttStream) {
      // ensure that data is always newer as already sent
      if (timestamp <= lastTimestamp) continue;
      yield [timestamp, sensorData];
      lastTimestamp = timestamp;
    }
  }

  /** Async generator for sensor data received from the mqtt. */
  static async * mqttStream(): AsyncGenerator<[Timestamp, SensorData]> {
    let stream = mqttUtil.stream(
      topic => topic == TERMINATE_TOPIC,
      SENSOR_TOPIC_WILDCARD,
      STEP_FINISHED_TOPIC,
      TERMINATE_TOPIC
    );

    let timestamp: Timestamp = 0;
    let sensorData = new SensorData();
    for await (let [topic, message] of stream) {
      if (topic == TERMINATE_TOPIC) continue;

      if (topic == STEP_FINISHED_TOPIC) {
        yield [timestamp, sensorData];
        sensorData = new SensorData();
        continue;
      }

      if (!topic.startsWith(SENSOR_TOPIC_WILDCARD.slice(0, -1))) {
        throw new Error(`unknown topic: ${topic}`);
      }

      let [deviceCategory, deviceId] = topic
        .split("/")
        .slice(1) as [keyof SensorData, string];
      let data = JSON.parse(message);
      timestamp = data.timestamp;
      delete data.timestamp; // SENSORDATA should not contain timestamp fields
      sensorData[deviceCategory][deviceId] = data;
    }
  }

  /** Fetch data from the influx db and format it into SensorData. */
  static async fetchInflux(
    queryApi: QueryApi
  ): Promise<Record<Timestamp, SensorData>> {
    let result: Record<Timestamp, SensorData> = {};
    let influxData = await queryInitialGridData(queryApi);

    for (let [key, entries] of Object.entries(influxData)) {
      // key has the format {deviceId}_{deviceParam}
      let splittenKey = key.split("_");
      let deviceId = splittenKey[0];
      // deviceParam may also contain "_"
      let deviceParam = splittenKey.slice(1).join("_");

      let deviceCategory = deviceId.split("-")[1]! as keyof SensorData;

      for (let entry of entries as Record<string, number>[]) {
        let [timestampStr, value] = Object.entries(entry)[0]!;
        let timestamp: number = +timestampStr;
        if (!result[timestamp]) result[timestamp] = new SensorData();
        if (!result[timestamp][deviceCategory][deviceId]) {
          // @ts-ignore due to this format, some device params are not
          // available in early iterations
          result[timestamp][deviceCategory][deviceId] = {};
        }
        // @ts-ignore deviceParam is not correctly typed, but too annoying rn
        result[timestamp][deviceCategory][deviceId][deviceParam] = value;
      }
    }

    return result;
  }
}
