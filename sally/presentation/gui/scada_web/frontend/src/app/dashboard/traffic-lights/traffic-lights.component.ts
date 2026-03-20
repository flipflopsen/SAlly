import { Component } from '@angular/core';
import { DataService } from '../data.service';
import { Subscription } from 'rxjs';
import { SensorData } from '@guardian/scada-shared';
import { GraphComponent } from '../graph/graph.component';
import { TrafficColors } from './color';
import { TrafficLightsSettingsComponent } from './traffic-lights-settings/traffic-lights-settings.component';
import { CommonModule } from '@angular/common';
import { TrafficLightsService } from './traffic-lights.service';

@Component({
  selector: 'traffic-lights',
  standalone: true,
  imports: [TrafficLightsSettingsComponent, CommonModule],
  templateUrl: './traffic-lights.component.html',
  styleUrl: './traffic-lights.component.scss'
})

export class TrafficLightsComponent {
  private subscription!: Subscription;
  deltaHealth: number = 0;
  expectedHealth: number = 1;
  currentPhase: TrafficColors = TrafficColors.GREEN;
  showSettings: boolean = false;

  red!: string;
  green!: string;
  yellow!: string;

  constructor(
    private dataService: DataService,
    private trafficLightsService: TrafficLightsService
  ) { }

  ngOnInit(): void {
    this.subscription = this.dataService
      .step()
      .subscribe(([timestamp, sensorData]) => {
        let health = GraphComponent.calcHealth(sensorData.bus);
        this.deltaHealth = Math.abs(this.expectedHealth - health);
        this.changePhase(this.checkForPhaseChange());
      }
      );
    this.trafficLightsService.thresholdsChangeEvent.subscribe(() => {
      this.changePhase(this.checkForPhaseChange());
    });
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
  }

  static calcHealth(busses: SensorData['bus']): number {
    return Object.values(busses)
      .map((bus) => bus.vm_pu)
      .reduce((acc, val, _idx, arr) => acc + val / arr.length, 0);
  }

  checkForPhaseChange(): TrafficColors {
    if (this.deltaHealth < this.trafficLightsService.greenYellow) {
      return TrafficColors.GREEN;
    }
    if (this.deltaHealth < this.trafficLightsService.yellowRed) {
      return TrafficColors.YELLOW;
    }
    return TrafficColors.RED;
  }

  changePhase(toPhase: TrafficColors) {
    this.currentPhase = toPhase;
  }

}
