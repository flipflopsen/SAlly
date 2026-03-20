import { Injectable } from "@angular/core";
import { Observable } from "rxjs";
import { HttpClient } from "@angular/common/http";
import { GrafanaUrl, GrafanaIds } from "@guardian/scada-shared";

@Injectable({
  providedIn: "root",
})
export class GrafanaService {
  private configUrl = "/api/v1/grafana-dynamic-dashboard";
  private idsUrl = "/api/v1/grafana-filters";
  private updateUrl = "/api/v1/grafana-cpes-components";

  constructor(private http: HttpClient) {}

  fetchDashboardUrl(): Observable<GrafanaUrl> {
    return this.http.get<GrafanaUrl>(this.configUrl);
  }

  fetchComponentIds(): Observable<GrafanaIds> {
    return this.http.get<GrafanaIds>(this.idsUrl);
  }

  updateComponents(components: string[]): void {
    this.http
      .post(this.updateUrl, {
        "cpes-components": components,
      })
      .subscribe({
        error: (error) => {
          console.error("There was an error!", error);
        },
      });
  }
}
