import { Component, HostBinding, OnInit } from "@angular/core";
import { Event } from "../../../../../shared/src/event"
import { NgFor, DatePipe } from "@angular/common";
import { DataService } from "../data.service";
import { Subscription } from "rxjs";
import { DetectionPipe } from "../misc/detection.pipe";
import { GrafanaService } from "../grafana.service";

@Component({
  selector: "dashboard-eventfeed",
  standalone: true,
  imports: [NgFor, DatePipe, DetectionPipe],
  templateUrl: "./eventfeed.component.html",
})
export class EventFeedComponent implements OnInit {
  events: Event[] = [];
  private subscription!: Subscription;

  constructor(private dataService: DataService, private grafanaService: GrafanaService) {}

  ngOnInit(): void {
    this.subscription = this.dataService.anomaly().subscribe((anomaly) => {
      this.events.push({
        timestamp: anomaly.timestamp,
        bus: anomaly.infected_bus,
        detector: anomaly.detector,
        name: "Anomaly",
        event_info: "Confidence(%): " + (anomaly.p_anomaly * 100).toString()
      });
    });
  }

  onEventClick(event: Event): void {
    let stringList : string[] = [];
    stringList[0] = event.bus.split('/')[1];
    this.grafanaService.updateComponents(stringList)
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
  }
}

