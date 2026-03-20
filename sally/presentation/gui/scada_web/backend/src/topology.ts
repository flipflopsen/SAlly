import * as mqtt from "mqtt";
import * as fs from "fs/promises";
import * as path from "path";

const ENV = {
  // Support both Guardian (TWIN_) and Sally (SALLY_) env var prefixes
  MQTT_HOST: process.env["SALLY_MQTT_HOST"] ?? process.env["TWIN_MQTT_HOST"] ?? "localhost",
  MQTT_PORT: process.env["SALLY_MQTT_PORT"] ?? process.env["TWIN_MQTT_PORT"] ?? "1883",
  // Sally-specific: path to topology JSON file (alternative to MQTT)
  TOPOLOGY_FILE: process.env["SALLY_TOPOLOGY_FILE"] ?? "",
  // Mode: "mqtt" or "file"
  TOPOLOGY_MODE: process.env["SALLY_TOPOLOGY_MODE"] ?? "mqtt",
}

/**
 * Query topology from either MQTT broker or file depending on configuration.
 */
export async function queryTopology(): Promise<String> {
  if (ENV.TOPOLOGY_MODE === "file" || ENV.TOPOLOGY_FILE) {
    return await getTopologyFromFile();
  }
  return await getTopologyFromMqtt();
}

/**
 * Query Sally-specific topology (always from file).
 */
export async function querySallyTopology(): Promise<object | null> {
  const defaultPath = path.join(__dirname, "../default-layouts/sally_topology.json");
  const topologyPath = ENV.TOPOLOGY_FILE || defaultPath;

  try {
    const data = await fs.readFile(topologyPath, "utf-8");
    return JSON.parse(data);
  } catch (err) {
    console.warn("Sally topology file not found:", topologyPath);
    return null;
  }
}

/**
 * Get topology from MQTT broker (Guardian-compatible).
 */
async function getTopologyFromMqtt(): Promise<string> {
  let client = await mqtt.connectAsync(
    `mqtt://${ENV.MQTT_HOST}:${ENV.MQTT_PORT}`
  );
  console.log("Connected to MQTT broker");

  let topic = "topology";
  await client.subscribeAsync(topic);
  console.log("Subscribed to topic with retain option:", topic);

  let messagePromise: Promise<string> = new Promise((resolve) => {
    client.on("message", (receivedTopic: string, message: Buffer) => {
      client.end();
      resolve(message.toString());
    });
  });

  let result = await messagePromise;
  return result;
}

/**
 * Get topology from JSON file (Sally mode).
 */
async function getTopologyFromFile(): Promise<string> {
  const defaultPath = path.join(__dirname, "../default-layouts/sally_topology.json");
  const topologyPath = ENV.TOPOLOGY_FILE || defaultPath;

  try {
    const data = await fs.readFile(topologyPath, "utf-8");
    console.log("Loaded topology from file:", topologyPath);
    return data;
  } catch (err) {
    console.error("Error reading topology file:", err);
    throw new Error(`Failed to read topology file: ${topologyPath}`);
  }
}
