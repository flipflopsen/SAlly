import { QueryApi } from "@influxdata/influxdb-client";
import { getAllIds, initializeInflux } from "./influx.js";

const GRAFANA_HOST = process.env["TWIN_GRAFANA_HOST"] ?? "localhost";
const GRAFANA_PORT = process.env["TWIN_GRAFANA_PORT"] ?? "3005";
const GRAFANA_HOST_EXTERN =
  process.env["TWIN_GRAFANA_EXTERN_HOST"] ?? "localhost";
const GRAFANA_PORT_EXTERN = process.env["TWIN_GRAFANA_EXTERN_PORT"] ?? "3005";

const DASHBOARD_TEMPLATE: string =
  process.env["TWIN_GRAFANA_TEMPLATE_DASHBOARD"] ??
  "c9ed2bfb-651f-4850-9972-32f9e07443d1";
const GRAFANA_USERNAME: string = process.env["TWIN_GRAFANA_USER"] ?? "admin";
const GRAFANA_PASSWORD: string = process.env["TWIN_GRAFANA_PASSWORD"] ?? "admin";

const PANEL_FIELD_RELATIONS: Record<string, string> = {
  "Minimum Loading Percent": "loading_percent",
  "Loading Percent: Time Series": "loading_percent",
  "Maximum Loading Percent": "loading_percent",
  "p_mw": "p_mw",
  "vm_pu": "vm_pu",
  "va_degree": "va_degree",
  "q_mvar": "q_mvar",
} as const;

let dynamicBoardUid: string | undefined;
let dynamicBoardUrl: string | undefined;

/**
 * Updates the detail Grafana dashboard with the provided CPES components.
 * If the current uid is still the template, a new dashboard will be created.
 * Returns the URL of the updated dashboard.
 *
 * @param cpesComponents - An array of CPES components.
 * @returns A Promise that resolves to the URL of the updated dashboard.
 * @throws An error if the field is not found for a panel title or if the dynamic board URL is undefined.
 */
export async function updateDetailGrafanaDashboard(
  cpesComponents: string[],
): Promise<string> {
  await setDynamicBoardUidIfExists();
  if (!dynamicBoardUid) dynamicBoardUid = DASHBOARD_TEMPLATE;

  // Get Grafana Detail Dashboard
  let requestJson = await getGrafanaDashboard(dynamicBoardUid);

  // extract the influxdb queries from the dashboard
  let dashboardPanels: any[] = requestJson["dashboard"]["panels"];
  for (let panel of dashboardPanels) {
    for (let target of panel["targets"]) {
      if (target["datasource"]["type"] == "influxdb") {
        let field = PANEL_FIELD_RELATIONS[panel["title"]];
        console.log(field);
        if (field === undefined) {
          throw new Error(`Field not found for panel title: ${panel["title"]}`);
        }
        let newQuery: string = influxQueryBuilder(target["query"], field, cpesComponents);
        target["query"] = newQuery;
      }
    }
  }

  // If the current uid is still the template, ids need to be set to null, to create a new dashboard
  // Because provisioned dashboards cannot be modified via the API
  if (dynamicBoardUid === DASHBOARD_TEMPLATE) {
    requestJson["dashboard"]["id"] = null;
    requestJson["dashboard"]["uid"] = null;
    requestJson["dashboard"]["title"] = "Infoboard Dynamic Controlled";
  }

  let updateResponse = await updateGrafanaDashboard(requestJson);

  // Set url if it was not set
  if (dynamicBoardUid === DASHBOARD_TEMPLATE) {
    dynamicBoardUid = updateResponse["uid"];
    dynamicBoardUrl = `http://${GRAFANA_HOST_EXTERN}:${GRAFANA_PORT_EXTERN}${updateResponse["url"]}`;
  }

  // check for error
  if (dynamicBoardUrl === undefined) {
    throw new Error("Dynamic Board URL is undefined");
  } else {
    return dynamicBoardUrl;
  }
}

/**
 * Retrieves the dynamic board URL.
 * If the dynamicBoardUrl is already defined, it returns the URL.
 * Otherwise, it updates the detail Grafana dashboard and returns the URL.
 * @returns A Promise that resolves to the dynamic board URL.
 */
export async function getDynamicBoardUrl(): Promise<string> {
  if (dynamicBoardUrl !== undefined) return dynamicBoardUrl;
  return await updateDetailGrafanaDashboard([""]);
}

async function setDynamicBoardUidIfExists() {
  if (dynamicBoardUid === undefined) {
    let dynamicDashboard = await checkIfDynamicBoardExists();
    if (dynamicDashboard === undefined) {
      dynamicBoardUid = DASHBOARD_TEMPLATE;
    } else {
      dynamicBoardUid = dynamicDashboard[0];
      dynamicBoardUrl = dynamicDashboard[1];
    }
  }
}

async function getGrafanaDashboard(uid: string): Promise<any> {
  let url = `http://${GRAFANA_HOST}:${GRAFANA_PORT}/api/dashboards/uid/${uid}`;
  let request = await fetch(url);
  if (!request.ok) {
    throw new Error("Error fetching Grafana Dashboard");
  }

  // Parse the response
  return await request.json();
}

async function updateGrafanaDashboard(dashboard: any): Promise<any> {
  let updateUrl = `http://${GRAFANA_HOST}:${GRAFANA_PORT}/api/dashboards/db`;
  let updateRequest = await fetch(updateUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Basic " + btoa(`${GRAFANA_USERNAME}:${GRAFANA_PASSWORD}`),
    },
    body: JSON.stringify(dashboard),
  });
  if (!updateRequest.ok) {
    throw new Error("Error updating Grafana Dashboard");
  }

  return await updateRequest.json();
}

async function checkIfDynamicBoardExists(): Promise<string[] | undefined> {
  let url = `http://${GRAFANA_HOST}:${GRAFANA_PORT}/api/search`;
  let request = await fetch(url);
  if (!request.ok) {
    throw new Error("Error searching for Grafana Dashboards");
  }

  let requestJson: any = await request.json();
  let result: string[] | undefined = undefined;

  for (let dashboard of requestJson) {
    if (dashboard["title"] === "Infoboard Dynamic Controlled") {
      result = [
        dashboard["uid"],
        `http://${GRAFANA_HOST_EXTERN}:${GRAFANA_PORT_EXTERN}${dashboard["url"]}`,
      ];
      return result;
    }
  }

  return result;
}

/**
 * Retrieves the Grafana filter values.
 * @returns A promise that resolves to an array of filter values.
 */
export async function getGrafanaFilter(): Promise<string[]> {
  let queryApi: QueryApi = initializeInflux();

  let filters: string[] = await getAllIds(queryApi);

  return filters;
}

export function influxQueryBuilder(query: string, field: string, cpesComponents: string[]): string {
  let linesQuery = query.split("\n");
  let newQuery = "";
  let addedFilter = false;

  for (let line of linesQuery) {
    if (line.includes("filter(") && !addedFilter) {
      // Adding Field filter
      newQuery += `  |> filter(fn: (r) => r[\"_field\"] == \"${field}\")\n`;

      // Adding ID filter
      newQuery += "  |> filter(fn: (r) => ";
      let componentFilter: string[] = [];
      for (let component of cpesComponents) {
        componentFilter.push(`r[\"id\"] == \"${component}\"`);
      }
      newQuery += componentFilter.join(" or ");
      newQuery += ")\n";

      addedFilter = true;
    } else if (!line.includes("filter(")) {
      newQuery += line + "\n";
    }
  }

  return newQuery;
}
