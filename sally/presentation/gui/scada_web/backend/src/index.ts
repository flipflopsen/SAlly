import express from "express";
import http from "http";
import path from "path";
import fs from "fs/promises";
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import { createProxyMiddleware } from "http-proxy-middleware";
import { initializeInflux, queryInitialGridData } from "./influx.js";
import { queryTopology, querySallyTopology } from "./topology.js";
import { QueryApi } from "@influxdata/influxdb-client";
import { Server } from "socket.io";
import { SensorData } from "./sensor-data.js";
import { AnomalyGuess } from "./anomaly.js";
import { getDynamicBoardUrl, getGrafanaFilter, updateDetailGrafanaDashboard } from "./grafana.js";
import { MqttService } from "./MqttService.js";
import { WebSocketService } from "./WebSocketService.js";

/**
 * Configuration constants
 * Support both Guardian (TWIN_) and Sally (SALLY_) env var prefixes
 */
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const HOSTNAME = "0.0.0.0";
const PORT = +(process.env["SALLY_SCADA_PORT"] ?? process.env["TWIN_SCADA_PORT"] ?? 3000);
const DIST_DIR = "../../frontend/dist/guardian/scada-frontend/browser";
const NO_CIM_TOPOLOGY_FILE = path.join(__dirname, "../default-layouts/bhv_grid_pandapower.json");
const SALLY_TOPOLOGY_FILE = path.join(__dirname, "../default-layouts/sally_topology.json");
const IS_DEV: string | undefined = process.argv[2];
const LAYOUT_FOLDER = path.join(__dirname, "../layouts");

// Mode detection: Sally or Guardian
const IS_SALLY_MODE = !!(process.env["SALLY_MODE"] || process.env["SALLY_MQTT_HOST"]);

// Sally bridge mode: 'mqtt', 'websocket', or 'legacy' (default influx/mqtt polling)
const SALLY_BRIDGE_MODE = process.env["SALLY_BRIDGE_MODE"] || "legacy";

/**
 * Create an Express application
 */
const app = express();
const server = http.createServer(app);
const io = new Server(server);

// Initialize bridge service based on mode
let bridgeService: MqttService | WebSocketService | null = null;

async function initializeBridgeService() {
  if (SALLY_BRIDGE_MODE === "mqtt") {
    console.log("[Server] Initializing MQTT bridge service...");
    bridgeService = new MqttService(io);
    await bridgeService.start();
  } else if (SALLY_BRIDGE_MODE === "websocket") {
    console.log("[Server] Initializing WebSocket bridge service...");
    bridgeService = new WebSocketService(io);
    await bridgeService.start();
  } else {
    console.log("[Server] Using legacy mode (InfluxDB + MQTT polling)");
  }
}

/**
 * Create proxy
 */
const proxy = createProxyMiddleware({
  target: "http://localhost:4200",
  changeOrigin: true,
  ws: true,
  pathRewrite: {
    "^/": "/",
  },
  router: req => {
    if (req.url.startsWith("/socket.io")) return undefined;
    return "http://localhost:4200";
  }
});

let influxQueryApi: QueryApi = initializeInflux();

io.on("connection", async socket => {
  console.log("Client connected:", socket.id);

  // In bridge mode, services handle data emission automatically
  // Just send topology if available
  if (bridgeService) {
    const topology = bridgeService.getTopology();
    if (topology) {
      socket.emit("topology", topology);
    }
  } else {
    // Legacy mode: stream from InfluxDB and MQTT
    let tasks = [];
    tasks.push((async () => {
      for await (let [timestamp, sensorData] of SensorData.stream(influxQueryApi)) {
        socket.emit("step", timestamp, sensorData);
      }
    })());
    tasks.push((async () => {
      for await (let anomaly of AnomalyGuess.stream()) {
        socket.emit("anomaly", anomaly);
      }
    })());
    await Promise.all(tasks);
  }
});

app.use(express.urlencoded());
app.use(express.json());

/**
 * Send the topology requested by the Grid View (CIM or Sally)
 */
app.get("/api/v0/grid-topology", async (req, res) => {
  try {
    let data = await queryTopology();
    res.setHeader("Content-Type", "application/json");
    res.send(JSON.stringify(data))
  }
  catch (e) {
    console.error(e);
    res.status(500).json(e);
  }
});

/**
 * Send the no-CIM-topology requested by the Grid View (PandaPower format)
 */
app.get("/api/v0/grid-topology-no-cim", async (req, res) => {
  try {
    // pandapower topology which was converted into the same format as the CIM-topology
    let buff = await fs.readFile(path.join(__dirname, NO_CIM_TOPOLOGY_FILE));
    let data = buff.toString();

    res.setHeader("Content-Type", "application/json");
    res.send(JSON.stringify(data))
  }
  catch (e) {
    console.error(e);
    res.status(500).json(e);
  }
});

/**
 * Sally-specific topology endpoint
 */
app.get("/api/v0/grid-topology-sally", async (req, res) => {
  try {
    const topology = await querySallyTopology();
    if (!topology) {
      res.status(404).json({ error: "Sally topology not found" });
      return;
    }
    res.setHeader("Content-Type", "application/json");
    res.json(topology);
  }
  catch (e) {
    console.error(e);
    res.status(500).json(e);
  }
});

/**
 * Health check endpoint
 */
app.get("/api/v0/health", (req, res) => {
  const status: any = {
    status: "ok",
    mode: IS_SALLY_MODE ? "sally" : "guardian",
    bridgeMode: SALLY_BRIDGE_MODE,
    timestamp: Date.now(),
  };

  // Add bridge service status if available
  if (bridgeService) {
    status.bridge = bridgeService.getStatus();
  }

  res.json(status);
});

/**
 * Gets the latest saved layout
 */
app.get("/api/v0/layout", async function (req, res) {
  let layout_name = await getLatestFile();
  let layout = ""
  if (layout_name != null) {
    let buff = await fs.readFile(path.join(LAYOUT_FOLDER, layout_name));
    console.log("Loading file: " + layout_name);
    layout = buff.toString();
  };

  res.setHeader("Content-Type", "application/json");
  res.send(JSON.stringify(layout));
});

app.use(express.json());

app.post("/api/v0/layout", async function (req: any, res: any) {
  console.log("Saving the layout");

  const timestamp = new Date().toISOString().replace(/:|\./g, '-');
  const fileName = `${timestamp}.json`;

  let body = JSON.stringify(req.body, null, 2);

  let filePath = path.join(LAYOUT_FOLDER, `${fileName}`);

  res.setHeader("Content-Type", "application/boolean");

  try {
    try {
      await fs.access(LAYOUT_FOLDER);
    } catch (err) {
      console.log("Create layout dictionary");
      await fs.mkdir(LAYOUT_FOLDER);
    }
    await fs.writeFile(filePath, body);
    console.log("Saving successful as: " + fileName);
    res.send(true);
  } catch (err) {
    console.error(err);
    res.send(false);
  }
})

/**
 * Gets the latest File from the layout folder
 * @returns string with the name of the file
 */
async function getLatestFile(): Promise<string | null> {
  try {
    const files = await fs.readdir(LAYOUT_FOLDER);
    if (files.length === 1) {
      return "standard.json"; // Folder is empty
    }

    const fileStats = await Promise.all(
      files.map(async (file) => ({
        name: file,
        stat: await fs.stat(`${LAYOUT_FOLDER}/${file}`),
      }))
    );

    // Sort files by modification time in descending order
    fileStats.sort((a, b) => b.stat.mtime.getTime() - a.stat.mtime.getTime());

    // Return the latest file
    return fileStats[0].name;
  } catch (err) {
    console.error('Error:', err);
    return null;
  }
}
// Send data requested by the Grid View
app.get("/api/v0/initial-grid-data", async (req, res) => {
  try {
    let data = await queryInitialGridData(influxQueryApi);

    res.setHeader("Content-Type", "application/json");
    res.send(JSON.stringify(data));
  }
  catch (e) {
    console.error(e);
    res.status(500).json(e);
  }
});

app.post("/api/v1/grafana-cpes-components", async (req, res) => {
  try {
    let cpesComponents = req.body["cpes-components"];
    let dashboardUrl: string = await updateDetailGrafanaDashboard(cpesComponents);
    res.send({ "status": "done", "dashboardUrl": dashboardUrl });
  }
  catch (e) {
    console.error(e);
    res.status(500).json(e);
  }
});

app.get("/api/v1/grafana-dynamic-dashboard", async (req, res) => {
  try {
    let dashboardUrl: string = await getDynamicBoardUrl();
    res.send({ "status": "done", "dashboardUrl": dashboardUrl });
  }
  catch (e) {
    console.error(e);
    res.status(500).json({ "status": "error", "error": e });
  }
});

app.get("/api/v1/grafana-filters", async (req, res) => {
  try {
    let componentIds = await getGrafanaFilter();
    res.send({ "status": "done", "componentIds": componentIds });
  }
  catch (e) {
    console.error(e);
    res.status(500).json({ "status": "error", "error": e });
  }
});

if (!IS_DEV) {
  app.use((req, res, next) => {
    // In production mode all request that are not previously handled should
    // either return a static file or return the frontend
    let pathHasFileExtension: boolean = !!path.extname(req.path).length;
    if (pathHasFileExtension) return next();
    res.sendFile(path.join(__dirname, DIST_DIR, "index.html"));
  })
}

// Serve static files or proxy to ng serve based on development mode
if (!IS_DEV) app.use(express.static(path.join(__dirname, DIST_DIR)));
else app.use("/", proxy);

// Graceful shutdown handler
async function shutdown(signal: string) {
  console.log(`\n${signal} received. Shutting down gracefully...`);

  // Stop bridge services
  if (bridgeService) {
    await bridgeService.stop();
  }

  // Close server
  server.close(() => {
    console.log("HTTP server closed");
    process.exit(0);
  });

  // Force exit after 10 seconds if graceful shutdown fails
  setTimeout(() => {
    console.error("Forced shutdown after timeout");
    process.exit(1);
  }, 10000);
}

// Register shutdown handlers
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

// Start the server
async function startServer() {
  try {
    // Initialize bridge service if configured
    await initializeBridgeService();

    // Start HTTP server
    server.listen(PORT, HOSTNAME, () => {
      console.info(`Server running at ${HOSTNAME}:${PORT}`);
      console.info(`Mode: ${IS_SALLY_MODE ? "Sally" : "Guardian"}`);
      console.info(`Bridge Mode: ${SALLY_BRIDGE_MODE}`);
    });
  } catch (error) {
    console.error("Failed to start server:", error);
    process.exit(1);
  }
}

// Start the server
startServer();
