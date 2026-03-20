import { Component, ViewEncapsulation } from '@angular/core';

import { NavbarComponent } from './navbar/navbar.component';
import { FooterComponent } from './footer/footer.component';

import { EventFeedComponent } from './eventfeed/eventfeed.component';
import { GraphComponent } from './graph/graph.component';
import { InfosComponent } from './infos/infos.component';
import { GrafanaControlComponent } from './grafana-control/grafana-control.component';
import { TrafficLightsComponent } from './traffic-lights/traffic-lights.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    NavbarComponent,
    FooterComponent,
    EventFeedComponent,
    GraphComponent,
    InfosComponent,
    GrafanaControlComponent,
    TrafficLightsComponent
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
  encapsulation: ViewEncapsulation.None
})
export class DashboardComponent {

}
