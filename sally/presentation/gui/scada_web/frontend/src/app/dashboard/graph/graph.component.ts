import {
  AfterViewInit,
  Component,
  ElementRef,
  HostBinding,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import { NgIf } from '@angular/common'
import { DataService } from '../data.service';
import { Subscription } from 'rxjs';
import { BaseChartDirective } from 'ng2-charts';
import { ChartOptions, ChartData, Point } from 'chart.js';
import { SensorData, Timestamp } from '@guardian/scada-shared';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import { faInfoCircle } from '@fortawesome/free-solid-svg-icons';


interface LineDataPoint {
  id: string;
  x: Timestamp;
  y: number;
}

@Component({
  selector: 'dashboard-graph',
  standalone: true,
  imports: [NgIf, BaseChartDirective, FontAwesomeModule],
  templateUrl: './graph.component.html',
})
export class GraphComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild(BaseChartDirective) chart!: BaseChartDirective;

  chartOptions: ChartOptions<'line'> = {
    plugins: {
      tooltip: {
        callbacks: {
          label: context => {
            const bus = context.dataset.data[context.dataIndex] as LineDataPoint;
            return `${bus.id}: ${bus.y.toFixed(4)}`;
          },
        },
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Time in Seconds'
        }
      },
      y: {
        title: {
          display: true,
          text: 'Health Value'
        }
      },
    },
  };
  chartData: ChartData<'line', LineDataPoint[]> = {
    labels: [],
    datasets: [
      {
        label: 'Grid Health',
        borderColor: 'red',
        data: [],
        parsing: {
          xAxisKey: 'x',
          yAxisKey: 'y',
        },
      },
      {
        label: 'Ideal Health',
        borderColor: 'black',
        data: [],
        pointHitRadius: 0,
        pointStyle: false,
        parsing: {
          xAxisKey: 'x',
          yAxisKey: 'y',
        },
      },
      {
        label: 'Min Health',
        borderColor: 'blue',
        data: [],
        parsing: {
          xAxisKey: 'x',
          yAxisKey: 'y',
        },
      },
      {
        label: 'Max Health',
        borderColor: 'orange',
        data: [],
        parsing: {
          xAxisKey: 'x',
          yAxisKey: 'y',
        },
        fill: {
          target: '-1',
          // above: 'lightgrey',
          above: 'rgba(100,100,100,0.5)',
        },
      },
    ],
  };

  faInfo = faInfoCircle;

  private subscription!: Subscription;

  infoTextActive = false;

  constructor(private dataService: DataService) { }

  onInfoBtnClick() {
    this.infoTextActive = !this.infoTextActive;
  }

  ngOnInit(): void {
    this.subscription = this.dataService
      .step()
      .subscribe(([timestamp, sensorData]) => {
        let health = GraphComponent.calcHealth(sensorData.bus);
        let min = GraphComponent.minBusVm(sensorData.bus);
        let max = GraphComponent.maxBusVm(sensorData.bus);
        this.chartData.labels!.push(timestamp);
        this.chartData.datasets[0].data.push({
          id: 'Grid Health',
          x: timestamp,
          y: health,
        });
        this.chartData.datasets[1].data.push({ id: 'One', x: timestamp, y: 1 });
        this.chartData.datasets[2].data.push({
          id: min[0],
          x: timestamp,
          y: min[1],
        });
        this.chartData.datasets[3].data.push({
          id: max[0],
          x: timestamp,
          y: max[1],
        });
        this.chart.chart?.update();
      });
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
  }

  ngAfterViewInit(): void {
    this.chart.chart?.update();
  }

  static calcHealth(busses: SensorData['bus']): number {
    return Object.values(busses)
      .map((bus) => bus.vm_pu)
      .reduce((acc, val, _idx, arr) => acc + val / arr.length, 0);
  }

  static maxBusVm(busses: SensorData['bus']): [string, number] {
    const values: Array<any> = Object.entries(busses);
    let maxValue: number = -Infinity;
    let busID: string = '';
    for (const [devideID, bus] of values) {
      if (bus.vm_pu > maxValue) {
        maxValue = bus.vm_pu;
        busID = devideID;
      }
    }
    return [busID, maxValue];
  }

  static minBusVm(busses: SensorData['bus']): [string, number] {
    const values: Array<any> = Object.entries(busses);
    let minValue: number = +Infinity;
    let busID: string = '';
    for (const [devideID, bus] of values) {
      if (bus.vm_pu < minValue) {
        minValue = bus.vm_pu;
        busID = devideID;
      }
    }
    return [busID, minValue];
  }
}
