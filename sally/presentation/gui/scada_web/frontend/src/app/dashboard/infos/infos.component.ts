import { Component, HostBinding, OnInit, OnDestroy } from "@angular/core";
import { CommonModule } from "@angular/common";
import { Subscription } from "rxjs";
import { DataService } from "../data.service";

@Component({
  selector: "dashboard-infos",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./infos.component.html",
})
export class InfosComponent implements OnInit, OnDestroy {
  @HostBinding("style.margin") margin = "0 1.5rem 0 0";

  private initialSimDate: Date = new Date("2017-01-01 00:00:00+0100");
  simDate: Date = new Date(this.initialSimDate);

  private subscription!: Subscription;

  constructor(private dataService: DataService) {}

  ngOnInit() {
    this.subscription = this.dataService.step().subscribe(([timestamp]) => {
      this.simDate = new Date(this.initialSimDate.getTime() + timestamp * 1000);
    });
  }

  ngOnDestroy() {
    this.subscription.unsubscribe();
  }
}
