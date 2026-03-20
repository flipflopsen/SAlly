import { Component, HostBinding } from '@angular/core';
import { GrafanaService } from '../grafana.service';
import { GrafanaControlComponent } from '../grafana-control/grafana-control.component';
import { firstValueFrom } from 'rxjs';

@Component({
  selector: 'dashboard-navbar',
  standalone: true,
  imports: [GrafanaControlComponent],
  templateUrl: './navbar.component.html'
})
export class NavbarComponent {
  dynamicDashboardUrl: string = "";

  constructor(private grafanaService: GrafanaService) { }

  ngOnInit(): void {
    this.getDynamicDashboardUrl();
  }

  getDynamicDashboardUrl(): void {
    firstValueFrom(this.grafanaService.fetchDashboardUrl()).then((response) => {
      this.dynamicDashboardUrl = response.dashboardUrl;
    });
  }
}
