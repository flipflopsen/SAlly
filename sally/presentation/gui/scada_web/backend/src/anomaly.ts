import * as shared from "@guardian/scada-shared";
import * as mqttUtil from "./mqtt.js";

const ANYOMALY_TOPIC = "anomaly/+";
const TERMINATE_TOPIC = "meta/simulation/terminate";

export class AnomalyGuess implements shared.AnomalyGuess {
  constructor(
    public infected_bus: shared.AnomalyGuess["infected_bus"],
    public p_anomaly: shared.AnomalyGuess["p_anomaly"],
    public correct_guess: shared.AnomalyGuess["correct_guess"],
    public timestamp: shared.AnomalyGuess["timestamp"],
    public detector: shared.AnomalyGuess["detector"]
  ) {}

  static async * stream(): AsyncGenerator<AnomalyGuess> {
    let stream = mqttUtil.stream(
      topic => topic == TERMINATE_TOPIC,
      ANYOMALY_TOPIC,
      TERMINATE_TOPIC
    );

    for await (let [topic, message] of stream) {
      if (topic == TERMINATE_TOPIC) break;
      let anomaly = JSON.parse(message);
      yield new AnomalyGuess(
        anomaly.infected_bus,
        anomaly.p_anomaly,
        anomaly.correct_guess,
        anomaly.timestamp,
        topic.split("/")[1]
      );
    }
  }
}
