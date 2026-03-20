import { connectAsync } from "mqtt";
import { Readable } from "stream";

// Support both Guardian (TWIN_) and Sally (SALLY_) env var prefixes
const MQTT_HOST = process.env["SALLY_MQTT_HOST"] ?? process.env["TWIN_MQTT_HOST"] ?? "localhost";
const MQTT_PORT = process.env["SALLY_MQTT_PORT"] ?? process.env["TWIN_MQTT_PORT"] ?? "1883";

export type Topic = string;
export type Message = string;

/**
 * Asynchronous generator yielding messages from MQTT topics until a
 * termination condition is met.
 *
 * @param terminatePredicate Evaluates to `true` to terminate stream.
 * @param topics Topics to subscribe and yield messages from.
 * @returns Yields [Topic, Message] tuples from subscribed topics.
 */
export async function* stream(
  terminatePredicate: (topic: Topic, message: Message) => boolean,
  ...topics: Topic[]
): AsyncGenerator<[Topic, Message]> {
  let mqttClient = await connectAsync(`mqtt://${MQTT_HOST}:${MQTT_PORT}`);

  let messageStream = new Readable({
    objectMode: true,
    read() {
      // no implementation needed since we're pushing data manually
    }
  });

  mqttClient.on("message", (topic, messageBuf) => {
    let message: string = messageBuf.toString("utf-8");
    messageStream.push([topic, message]);
    if (terminatePredicate(topic, message)) messageStream.push(null);
  });

  for (let topic of topics) {
    await mqttClient.subscribeAsync(topic);
  }

  for await (let [topic, message] of messageStream) {
    yield [topic, message];
  }
}
