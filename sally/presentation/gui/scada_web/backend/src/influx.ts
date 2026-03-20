import {InfluxDB, flux, QueryApi} from "@influxdata/influxdb-client";

// Support both Guardian (TWIN_) and Sally (SALLY_) env var prefixes
const INFLUX_HOST = process.env["SALLY_INFLUX_HOST"] ?? process.env["TWIN_INFLUX_HOST"] ?? "localhost";
const INFLUX_PORT = process.env["SALLY_INFLUX_PORT"] ?? process.env["TWIN_INFLUX_PORT"] ?? "8086";
const INFLUX_TOKEN = process.env["SALLY_INFLUX_TOKEN"] ?? process.env["TWIN_INFLUX_TOKEN"] ?? "random_token";
const INFLUX_ORG = process.env["SALLY_INFLUX_ORG"] ?? process.env["TWIN_INFLUX_ORG"] ?? "sally";
const INFLUX_BUCKET = process.env["SALLY_INFLUX_BUCKET"] ?? process.env["TWIN_INFLUX_BUCKET"] ?? "sally_grid_data";
const INFLUX_URL = "http://" + INFLUX_HOST + ":" + INFLUX_PORT;


export function initializeInflux(): QueryApi {
  let client = new InfluxDB({ url: INFLUX_URL, token: INFLUX_TOKEN });
  return client.getQueryApi(INFLUX_ORG);
}

export async function queryInitialGridData(
  queryApi: QueryApi
): Promise<Record<string, any[]>> {
  const query = flux`from(bucket: "${INFLUX_BUCKET}")
    |> range(start: -365d)
    |> group(columns: ["id", "simulation_timestamp"])
  `;

  let dataByComponent: Record<string, any[]> = {};
  await queryApi.collectRows(query, (row, tableMeta) => {
    const o = tableMeta.toObject(row);
    const key = `${o["id"]}_${o["_field"]}`;

    if (!(key in dataByComponent)) dataByComponent[key] = [];
    dataByComponent[key].push({[o["simulation_timestamp"]]: o["_value"]});
  });

  let sortedData: Record<string, any[]> = {};
  for (let id in dataByComponent) {
    dataByComponent[id].sort((a, b) => {
      return +Object.keys(a)[0] - +Object.keys(b)[0]
    });
    dataByComponent[id].map(obj => obj[Object.keys(obj)[0]]);
    sortedData[id] = dataByComponent[id];
  }

  return sortedData;
}

/**
 * Retrieves all IDs from the InfluxDB database.
 *
 * @param queryApi - The InfluxDB QueryApi object.
 * @returns A promise that resolves to an array of strings representing the IDs.
 */
export async function getAllIds(queryApi: QueryApi): Promise<string[]> {
  const query = flux`from(bucket: "${INFLUX_BUCKET}")
    |> range(start: -365d)
    |> group(columns: ["id"])
  `;

  let idsSet: Set<string> = new Set([]);
  await queryApi.collectRows(query, (row, tableMeta) => {
    const o = tableMeta.toObject(row);
    idsSet.add(o["id"]);
  });

  return Array.from(idsSet);
}
