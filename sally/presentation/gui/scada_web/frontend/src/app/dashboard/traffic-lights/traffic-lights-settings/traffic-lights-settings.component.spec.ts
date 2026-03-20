import { ComponentFixture, TestBed } from '@angular/core/testing';

import { TrafficLightsSettingsComponent } from './traffic-lights-settings.component';

describe('TrafficLightsSettingsComponent', () => {
  let component: TrafficLightsSettingsComponent;
  let fixture: ComponentFixture<TrafficLightsSettingsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TrafficLightsSettingsComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(TrafficLightsSettingsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
