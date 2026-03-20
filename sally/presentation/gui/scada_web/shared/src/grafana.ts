export interface GrafanaUrl {
  /** The URL to the Grafana dashboard. */
  status: string;
  dashboardUrl: string;
}

export interface GrafanaIds {
  /** The URL to the Grafana dashboard. */
  status: string;
  componentIds: string[];
}
