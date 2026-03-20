import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'detection',
  standalone: true
})
export class DetectionPipe implements PipeTransform {
  transform(value: string | undefined): string {
    switch (value) {
      case undefined: return "";
      case "pp": return "PandaPower Anomaly Detection";
      case "dt": return "DT Anomaly Detection";
      default: return value;
    }
  }
}
