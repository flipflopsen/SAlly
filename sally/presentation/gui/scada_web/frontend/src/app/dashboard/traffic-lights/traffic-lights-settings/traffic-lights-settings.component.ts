import { Component, EventEmitter, Input, Output } from '@angular/core';
import {
  FormsModule, FormGroup, ReactiveFormsModule,
  FormControl, ValidatorFn, AbstractControl, ValidationErrors
} from "@angular/forms";
import { NgIf } from '@angular/common';
import { TrafficLightsService } from '../traffic-lights.service';

@Component({
  selector: 'traffic-lights-settings',
  standalone: true,
  imports: [FormsModule, ReactiveFormsModule, NgIf],
  templateUrl: './traffic-lights-settings.component.html',
})

export class TrafficLightsSettingsComponent {
  @Input() showSettings: boolean = false;
  @Input() greenYellowThreshold: number = this.trafficLightsService.greenYellow;
  @Input() yellowRedThreshold: number = this.trafficLightsService.yellowRed;

  @Output() closeSettingsEvent = new EventEmitter<void>();

  form!: FormGroup;

  constructor(
    private trafficLightsService: TrafficLightsService
  ) { }

  ngOnInit(): void {
    this.form = new FormGroup({
      "greenYellowThreshold": new FormControl(this.greenYellowThreshold),
      "yellowRedThreshold": new FormControl(this.yellowRedThreshold)
    }, { validators: this.compareValuesValidator });
  }

  compareValuesValidator: ValidatorFn = (
    control: AbstractControl,
  ): ValidationErrors | null => {
    const value1 = control.get("greenYellowThreshold")?.value;
    const value2 = control.get("yellowRedThreshold")?.value;
    if ((value1 && value2) != null) {
      return value1 > value2 ? { value1LargerThanValue2: true } : null;
    }
    return null;
  }

  saveSettings() {
    if (this.form.valid) {
      this.greenYellowThreshold = this.form.value.greenYellowThreshold;
      this.yellowRedThreshold = this.form.value.yellowRedThreshold;
      
      this.trafficLightsService.updateThresholds(
        this.greenYellowThreshold,
        this.yellowRedThreshold
      )
      this.closeSettings();

    } else {
      console.log("Threshold values not in right order");
      this.resetValues();
    }
  }
  
  closeSettings() {
    this.closeSettingsEvent.emit();
    this.resetValues();
  }


  resetValues() {
    this.greenYellowThreshold = this.trafficLightsService.greenYellow;
    this.yellowRedThreshold = this.trafficLightsService.yellowRed;
  }


}
