import { EventEmitter, Injectable, Output } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class TrafficLightsService {
  yellowRed: number = 0.09;
  greenYellow: number = 0.05;

  @Output() thresholdsChangeEvent = new EventEmitter<void>();

  constructor() { }

  updateThresholds(greenYellow: number, yellowRed: number) {
    this.greenYellow = greenYellow;
    this.yellowRed = yellowRed;
    this.thresholdsChangeEvent.emit();
  }
}
